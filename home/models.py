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


class ServiceCategory(models.Model):
    """Categories for agent services (Sourcing, Shipping, etc.)"""
    name = models.CharField(
        max_length=100,
        unique=True,
        help_text="Name of the service type (e.g., Sourcing, Shipping, Customs Clearance)"
    )
    code = models.SlugField(
        max_length=50,
        unique=True,
        help_text="Short code for the service type (e.g., 'sourcing', 'shipping')"
    )
    description = models.TextField(blank=True)
    icon = models.CharField(
        max_length=50,
        blank=True,
        help_text="Icon class (e.g., 'fas fa-ship' or 'fas fa-warehouse')"
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this service type is currently available"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Service Categories"
        ordering = ['name']

    def __str__(self):
        return self.name


class Agent(models.Model):
    """Model for Sourcing and Shipping agents"""
    
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="agents")
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    
    # Service Types (replaces service_type and services fields)
    service_types = models.ManyToManyField(
        ServiceCategory,
        related_name="agents",
        verbose_name="Service Types",
        help_text="Select the types of services this agent provides"
    )
    
    # Contact Information
    email = models.EmailField()
    phone = models.CharField(max_length=20)
    phone2 = models.CharField(max_length=20, blank=True)
    website = models.URLField(blank=True)
    
    # Location
    address = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=100, blank=True)
    
    # Business Hours
    business_hours = models.JSONField(blank=True, null=True, help_text="JSON format for business hours")
    
    # Social Media
    social_facebook = models.URLField(blank=True)
    social_twitter = models.URLField(blank=True)
    social_linkedin = models.URLField(blank=True)
    social_instagram = models.URLField(blank=True)
    
    # Verification
    is_verified = models.BooleanField(default=False)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Sourcing/Shipping Agent"
        verbose_name_plural = "Sourcing/Shipping Agents"

    def __str__(self):
        return f"{', '.join(st.name for st in self.service_types.all())}: {self.name}"
    
    def get_primary_image(self):
        """Return the primary image or the first available image"""
        return self.images.filter(is_primary=True).first() or self.images.first()


class AgentImage(models.Model):
    """Images for Agent profiles"""
    agent = models.ForeignKey(Agent, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='agent_images/')
    caption = models.CharField(max_length=255, blank=True)
    is_primary = models.BooleanField(default=False, help_text="Set as primary image")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-is_primary', 'created_at']

    def save(self, *args, **kwargs):
        # If this is set as primary, unset any existing primary for this agent
        if self.is_primary:
            AgentImage.objects.filter(agent=self.agent, is_primary=True).update(is_primary=False)
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.agent.name} - {self.caption or 'Image'}"

class AgentAIKnowledgeBase(models.Model):
    agent = models.OneToOneField(Agent, on_delete=models.CASCADE, related_name="knowledge_base")
    content = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class BusinessReview(models.Model):
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="reviews")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    rating = models.PositiveSmallIntegerField(default=0)  # 1–5 stars
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('business', 'user')  # 1 review per user per business

    def __str__(self):
        return f"{self.user} review on {self.business.name}"

class AgentReview(models.Model):
    """Model for user reviews of agents"""
    RATING_CHOICES = [
        (1, '★☆☆☆☆ (1/5)'),
        (2, '★★☆☆☆ (2/5)'),
        (3, '★★★☆☆ (3/5)'),
        (4, '★★★★☆ (4/5)'),
        (5, '★★★★★ (5/5)')
    ]
    
    agent = models.ForeignKey(Agent, on_delete=models.CASCADE, related_name="reviews")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="agent_reviews")
    rating = models.PositiveSmallIntegerField(choices=RATING_CHOICES, default=5)
    title = models.CharField(max_length=200)
    comment = models.TextField(help_text="Share your experience with this agent")
    is_approved = models.BooleanField(default=False, help_text="Review will be visible only after approval")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        unique_together = ('agent', 'user')  # One review per user per agent
        verbose_name = "Agent Review"
        verbose_name_plural = "Agent Reviews"

    def __str__(self):
        return f"{self.user} review on {self.agent.name}"

    def save(self, *args, **kwargs):
        # Update agent's average rating
        super().save(*args, **kwargs)
        self.update_agent_rating()
    
    def update_agent_rating(self):
        """Update the agent's average rating"""
        from django.db.models import Avg, Count
        
        # Get approved reviews for this agent
        reviews = AgentReview.objects.filter(
            agent=self.agent,
            is_approved=True
        ).aggregate(
            average_rating=Avg('rating'),
            review_count=Count('id')
        )
        
        # Update the agent's rating fields
        self.agent.average_rating = reviews['average_rating'] or 0
        self.agent.review_count = reviews['review_count']
        self.agent.save(update_fields=['average_rating', 'review_count'])


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

class PromiseFee(models.Model):
    variation = models.ForeignKey(ProductVariation, on_delete=models.CASCADE, related_name='promise_fees')
    name = models.CharField(max_length=100, default='Basic')
    buy_back_fee = models.DecimalField(max_digits=10, decimal_places=2)
    percentage_fee = models.DecimalField(max_digits=10, decimal_places=2)
    must_pay_shipping = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('name', 'variation')
        verbose_name = 'Promise Fee'
        verbose_name_plural = 'Promise Fees'

    def __str__(self):
        return f"{self.variation} - {self.name}" 

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


class ChatMessage(models.Model):
    """Model for storing chat messages for products"""
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='chat_messages',
        null=True,  # Temporarily allow null for data migration
        blank=True
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='chat_messages'
    )
    reply_for = models.CharField(max_length=100, null=True, blank=True)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['product', 'created_at']),
            models.Index(fields=['user']),
        ]

    def __str__(self):
        return f"{self.id}"
