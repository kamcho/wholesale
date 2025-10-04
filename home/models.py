from django.db import models
from django.db.models import Q
from django.core.exceptions import ValidationError
from django.conf import settings   # use settings.AUTH_USER_MODEL instead of hardcoding
                                   # so it works with custom User models
import uuid
from decimal import Decimal
# ==============================
# BUSINESS & REVIEWS
# ==============================
class BusinessCategory(models.Model):
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class Business(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="businesses")
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    address = models.CharField(max_length=255, blank=True)

    # Geolocation
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)

    # Relationships
    categories = models.ManyToManyField(
        BusinessCategory,
        related_name="businesses",
        blank=True
    )

    # Contact info
    phone = models.CharField(max_length=20, blank=True)
    website = models.URLField(blank=True)
    email = models.EmailField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class BusinessImage(models.Model):
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to='business_images/')
    caption = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.business.name} Image"


class BusinessReview(models.Model):
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="reviews")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    rating = models.PositiveSmallIntegerField(default=0)  # 1–5 stars
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('business', 'user')  # 1 review per user per business

    def __str__(self):
        return f"{self.user} review on {self.business.name}"


# ==============================
# PRODUCT CATEGORIES
# ==============================
class ProductCategoryFilter(models.Model):
    """High-level grouping (e.g. Electronics, Fashion)."""
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class ProductCategory(models.Model):
    """Subcategory belonging to a filter (e.g. Phones under Electronics)."""
    filter = models.ForeignKey(ProductCategoryFilter, on_delete=models.CASCADE, related_name="categories")
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


# ==============================
# PRODUCTS
# ==============================
class Product(models.Model):
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="products", null=True, blank=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="products", null=True, blank=True)
    categories = models.ManyToManyField(ProductCategory, related_name="products", blank=True)
    # product_type = models.ForeignKey('ProductType', on_delete=models.SET_NULL, null=True, blank=True, related_name='products')
    moq = models.PositiveIntegerField(default=1)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    # price = models.DecimalField(max_digits=10, decimal_places=2)  # Unit price when MOQ is met
    # price_single = models.DecimalField(max_digits=10, decimal_places=2, default=0)  # Unit price for single/below MOQ

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class ProductImage(models.Model):
    # Link to either product OR variation (exactly one must be set)
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="images",
        null=True,
        blank=True,
    )
    variation = models.ForeignKey(
        'ProductVariation',
        on_delete=models.CASCADE,
        related_name="images",
        null=True,
        blank=True,
    )
    image = models.ImageField(upload_to='product_media/images/', null=True, blank=True)
    video = models.FileField(upload_to='product_media/videos/', null=True, blank=True,
                           help_text='Upload a video file (MP4, WebM, etc.)')
    caption = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_default = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.CheckConstraint(
                check=(
                    (Q(product__isnull=False) & Q(variation__isnull=True)) |
                    (Q(product__isnull=True) & Q(variation__isnull=False))
                ),
                name='productimage_exactly_one_of_product_or_variation'
            )
        ]

    def clean(self):
        super().clean()
        # XOR: exactly one of product or variation must be set
        if bool(self.product) == bool(self.variation):
            raise ValidationError(
                {
                    'product': 'Attach media to exactly one of product or variation.',
                    'variation': 'Attach media to exactly one of product or variation.'
                }
            )
            
        # Ensure either image or video is provided, but not both
        if not self.image and not self.video:
            raise ValidationError(
                'Either an image or a video must be provided.'
            )
            
        if self.image and self.video:
            raise ValidationError(
                'Please provide either an image or a video, not both.'
            )

    def save(self, *args, **kwargs):
        # Ensure validation runs on model.save()
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        media_type = 'Video' if self.video else 'Image'
        if self.variation:
            return f"{self.variation.product.name} – {self.variation.name} {media_type}"
        if self.product:
            return f"{self.product.name} {media_type}"
        return "Orphan Product Image"


class ProductVariation(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="variations")
    name = models.CharField(max_length=255)   # e.g. "Color: Red", "Size: XL"
    moq = models.PositiveIntegerField(default=1)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    closes_on = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"{self.product.name} - {self.name}"


class PriceTier(models.Model):
    """Quantity-based pricing for product variations"""
    variation = models.ForeignKey(ProductVariation, on_delete=models.CASCADE, related_name='price_tiers')
    min_quantity = models.PositiveIntegerField()
    max_quantity = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        unique_together = ('variation', 'min_quantity')
        ordering = ['min_quantity']

    def __str__(self):
        return f"{self.variation} - Qty {self.min_quantity}+: ${self.price}"


# ==============================
# PRODUCT REVIEWS
# ==============================
class ProductReview(models.Model):
    product = models.ForeignKey(ProductVariation, on_delete=models.CASCADE, related_name="reviews")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    rating = models.PositiveSmallIntegerField(default=0)
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('product', 'user')  # 1 review per user per product

    def __str__(self):
        return f"{self.user} review on {self.product.name}"


class ProductReviewImage(models.Model):
    review = models.ForeignKey(ProductReview, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to='product_review_images/')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Image for {self.review.product.name} review"


class Cart(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="carts",
        null=True,
        blank=True
    )
    name = models.CharField(max_length=255, blank=True, null=True)
    session_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        unique=True,
        help_text="Used for guest carts"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def total_price(self):
        return sum(item.subtotal() for item in self.items.all())

    def assign_session(self):
        """Assign a unique session_id if it doesn’t exist"""
        if not self.session_id:
            self.session_id = str(uuid.uuid4())
            self.save()

    def __str__(self):
        if self.user:
            return f"Cart (User: {self.user})"
        return f"Cart (Guest: {self.session_id})"


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name="items")
    variation = models.ForeignKey(
        "ProductVariation", on_delete=models.RESTRICT
    )
    quantity = models.PositiveIntegerField(default=1)

    def unit_price(self):
        # Prefer variation price when available; otherwise fallback to 0
        if self.variation:
            return self.variation.price
        return Decimal('0')

    def subtotal(self):
        return self.unit_price() * self.quantity

    def __str__(self):
        return f"{self.quantity} x {self.product.name}"



class Order(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("paid", "Paid"),
        ("shipped", "Shipped"),
        ("delivered", "Delivered"),
        ("cancelled", "Cancelled"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="orders"
    )
    session_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="For guest orders"
    )

    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    shipping_address = models.TextField(blank=True, null=True)
    billing_address = models.TextField(blank=True, null=True)
    payment_method = models.CharField(max_length=50, blank=True, null=True)
    transaction_id = models.CharField(max_length=100, blank=True, null=True)

    def calculate_total(self):
        self.total = sum(item.subtotal() for item in self.items.all())
        self.save()

    def __str__(self):
        if self.user:
            return f"Order #{self.id} by {self.user}"
        return f"Order #{self.id} (Guest)"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    variation = models.ForeignKey(
        "ProductVariation", on_delete=models.RESTRICT
    )
    quantity = models.PositiveIntegerField(default=1)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    def subtotal(self):
        return self.price * Decimal(self.quantity)

    def __str__(self):
        return f"{self.quantity} x {self.product}"


# ==============================
# WISHLIST
# ==============================
class Wishlist(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="wishlists")
    name = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Wishlist of {self.user}"


class WishlistItem(models.Model):
    wishlist = models.ForeignKey(Wishlist, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(ProductVariation, on_delete=models.CASCADE, related_name="wishlisted_in")
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("wishlist", "product")

    def __str__(self):
        return f"{self.product.name} in {self.wishlist}"




# ==============================
# SIMPLIFIED PRODUCT ATTRIBUTES
# ==============================

class ProductAttribute(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

class ProductAttributeValue(models.Model):
    attribute = models.ForeignKey(ProductAttribute, on_delete=models.CASCADE, related_name='values')
    value = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.value

class ProductAttributeAssignment(models.Model):
    product = models.ForeignKey(ProductVariation, on_delete=models.CASCADE, related_name='attribute_assignments')
    value = models.ForeignKey(ProductAttributeValue, on_delete=models.CASCADE, related_name='assignments')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.product.name} - {self.value.value}"

# ==============================
# PRODUCT ORDERS (per-product commitments)
# ==============================
class ProductOrder(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("confirmed", "Confirmed"),
        ("cancelled", "Cancelled"),
        ("fulfilled", "Fulfilled"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='product_orders')
    product = models.ForeignKey(ProductVariation, on_delete=models.CASCADE, related_name='orders')
    quantity = models.PositiveIntegerField(default=1)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    # Simple payment tracking
   
    note = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

   
    def __str__(self):
        base = f"{self.product.name} x{self.quantity}"
        return f"PO[{self.user} – {base} – {self.status}]"




class RawPayment(models.Model):
    PAYMENT_METHODS = [
        ('mpesa', 'Mpesa'),
        ('card', 'Card'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
    ]

    product_id = models.CharField(max_length=100, blank=True, null=True)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=10, default="KES")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")

    transaction_id = models.CharField(max_length=100, unique=True)  # from gateway

    # ---- Mpesa specific fields ----
    mpesa_receipt = models.CharField(max_length=100, blank=True, null=True)
    phone_number = models.CharField(max_length=20, blank=True, null=True)

    # ---- Card specific fields ----
    card_last4 = models.CharField(max_length=4, blank=True, null=True)
    card_brand = models.CharField(max_length=20, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.transaction_id} - {self.payment_method} - {self.amount} {self.currency}"

class Payment(models.Model):
   
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="payments")
    order_id = models.ForeignKey(ProductOrder, on_delete=models.CASCADE, related_name="payments")

    raw_payment = models.ForeignKey(RawPayment, on_delete=models.CASCADE, related_name="payments")

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.raw_payment.transaction_id} - {self.raw_payment.payment_method} - {self.raw_payment.amount} {self.raw_payment.currency}"
