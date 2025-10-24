from django.db import models
from django.db.models import Q
from django.core.exceptions import ValidationError
from django.conf import settings   # use settings.AUTH_USER_MODEL instead of hardcoding
                                   # so it works with custom User models
import uuid
import json
from decimal import Decimal, ROUND_HALF_UP
from django_countries.fields import CountryField


class PaymentRequest(models.Model):
    """
    Model to store M-Pesa payment request and callback data
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
        ('timeout', 'Timed Out'),
        ('insufficient', 'Insufficient Balance'),
    ]

    # Request details
    merchant_request_id = models.CharField(max_length=100, blank=True, null=True)
    checkout_request_id = models.CharField(max_length=100, blank=True, null=True)
    order = models.ForeignKey('Order', on_delete=models.SET_NULL, null=True, blank=True, related_name='payment_requests')
    order_request = models.ForeignKey('OrderRequest', on_delete=models.SET_NULL, null=True, blank=True, related_name='payment_requests')
    
    # Payment details
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    account_reference = models.CharField(max_length=100, blank=True, null=True)
    transaction_desc = models.CharField(max_length=100, blank=True, null=True)
    
    # Status and timestamps
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    is_complete = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Raw request and response data
    request_data = models.JSONField(blank=True, null=True)
    callback_data = models.JSONField(blank=True, null=True)
    
    # Transaction details from callback
    mpesa_receipt_number = models.CharField(max_length=100, blank=True, null=True)
    transaction_date = models.DateTimeField(blank=True, null=True)
    transaction_id = models.CharField(max_length=100, blank=True, null=True)
    
    # Error information
    error_code = models.CharField(max_length=50, blank=True, null=True)
    error_message = models.TextField(blank=True, null=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Payment Request'
        verbose_name_plural = 'Payment Requests'
    
    def __str__(self):
        return f"Payment {self.id} - {self.get_status_display()} - {self.amount} KES"
    
    def update_from_callback(self, callback_data):
        """
        Update payment request with callback data from M-Pesa
        """
        self.callback_data = callback_data
        
        # Parse the callback data
        result_code = callback_data.get('Body', {}).get('stkCallback', {}).get('ResultCode')
        result_desc = callback_data.get('Body', {}).get('stkCallback', {}).get('ResultDesc', '').lower()
        
        # Map M-Pesa result codes to our statuses
        if result_code == 0:
            self.status = 'completed'
            self.is_complete = True
            
            # Extract transaction details from callback metadata
            metadata = {}
            for item in callback_data.get('Body', {}).get('stkCallback', {}).get('CallbackMetadata', {}).get('Item', []):
                if 'Name' in item and 'Value' in item:
                    metadata[item['Name']] = item['Value']
            
            self.mpesa_receipt_number = metadata.get('MpesaReceiptNumber')
            
            # Handle transaction date conversion
            transaction_date = metadata.get('TransactionDate')
            if transaction_date and isinstance(transaction_date, str):
                try:
                    # M-Pesa date format: YYYYMMDDHHmmss
                    from datetime import datetime
                    self.transaction_date = datetime.strptime(transaction_date, '%Y%m%d%H%M%S')
                except (ValueError, TypeError) as e:
                    # If parsing fails, just set to current time
                    from django.utils import timezone
                    self.transaction_date = timezone.now()
            
            # Update amount if provided in metadata
            amount = metadata.get('Amount')
            if amount is not None:
                try:
                    self.amount = Decimal(str(amount))
                except (TypeError, ValueError):
                    # If amount conversion fails, keep the existing value
                    pass
            
        elif 'cancelled' in result_desc or 'canceled' in result_desc:
            self.status = 'cancelled'
            self.error_message = result_desc
        elif 'timeout' in result_desc:
            self.status = 'timeout'
            self.error_message = result_desc
        elif 'insufficient' in result_desc or 'balance' in result_desc:
            self.status = 'insufficient'
            self.error_message = result_desc
        else:
            self.status = 'failed'
            self.error_message = result_desc
        
        self.save()
        return self


class ExchangeRate(models.Model):
    currency = models.CharField(max_length=3)
    rate = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.currency} - {self.rate}"

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
    
    # Profile Images
    photo = models.ImageField(
        upload_to='agent_photos/',
        blank=True,
        null=True,
        help_text='Profile photo of the agent'
    )
    logo = models.ImageField(
        upload_to='agent_logos/',
        blank=True,
        null=True,
        help_text='Company logo (if applicable)'
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
        
    @property
    def display_photo(self):
        """Return the agent's photo or a default avatar"""
        if self.photo:
            return self.photo.url
        return static('images/default-avatar.png')
        
    @property
    def display_logo(self):
        """Return the agent's logo or the photo if no logo exists"""
        if self.logo:
            return self.logo.url
        if self.photo:
            return self.photo.url
        return static('images/default-logo.png')


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
    origin = CountryField(blank_label='(Select country)', null=True, blank=True)
    is_active = models.BooleanField(default=True, help_text="Whether this product is active and visible to customers")
    is_archived = models.BooleanField(default=False, help_text="Whether this product has been archived (soft delete)")
    # price = models.DecimalField(max_digits=10, decimal_places=2)  # Unit price when MOQ is met
    # price_single = models.DecimalField(max_digits=10, decimal_places=2, default=0)  # Unit price for single/below MOQ

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

class ProductServicing(models.Model):
    product = models.OneToOneField(Product, on_delete=models.CASCADE, related_name="servicings")
    shipping = models.ForeignKey(Agent, on_delete=models.CASCADE, related_name="shippings", null=True, blank=True)
    sourcing = models.ForeignKey(Agent, on_delete=models.CASCADE, related_name="sourcing", null=True, blank=True)
    customs = models.ForeignKey(Agent, on_delete=models.CASCADE, related_name="customs", null=True, blank=True)
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
    is_active = models.BooleanField(default=True, help_text="Whether this variation is visible to customers")
    is_archived = models.BooleanField(default=False, help_text="Whether this variation has been archived (soft delete)")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    closes_on = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['order', 'name']
        
    def clean(self):
        super().clean()
        if self.is_archived and self.is_active:
            raise ValidationError('An archived variation cannot be active.')
    
    def __str__(self):
        status = []
        if not self.is_active:
            status.append("inactive")
        if self.is_archived:
            status.append("archived")
        status_str = f" ({', '.join(status)})" if status else ""
        return f"{self.product.name} - {self.name}{status_str}"
class AdditionalFees(models.Model):
    variation = models.ManyToManyField(ProductVariation, related_name='additional_fees')
    name = models.CharField(max_length=100, default='Basic')
    description = models.TextField(blank=True)
    is_required = models.BooleanField(default=False)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
class ProductKB(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="kb", null=True, blank=True)
    variation = models.ForeignKey(ProductVariation, on_delete=models.CASCADE, related_name="kb", null=True, blank=True)
    content = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
class PromiseFee(models.Model):
    variation = models.OneToOneField(ProductVariation, on_delete=models.CASCADE, related_name='promise_fee')
    name = models.CharField(max_length=100, default='Basic')
    min_percent = models.DecimalField(max_digits=10, decimal_places=2)
    max_percent = models.DecimalField(max_digits=10, decimal_places=2)
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
        "ProductVariation", on_delete=models.RESTRICT, null=True, blank=True
    )
    product = models.ForeignKey(Product, on_delete=models.RESTRICT, null=True, blank=True)
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
    # In home/models.py, in the Order model, add:
    order_request = models.OneToOneField(
    'OrderRequest',
    on_delete=models.SET_NULL,
    null=True,
    blank=True,
    related_name='order'
)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="order_creator"
    )
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
    note = models.TextField(blank=True, null=True, help_text="Additional notes or instructions for this order")
    pay_now = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    pay_later = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    def calculate_total(self):
        """Calculate the total cost including all items and additional fees."""
        item_total = sum(item.subtotal() for item in self.items.all())
        additional_fees = sum(fee.amount for fee in self.additional_fees.all())
        self.total = item_total + additional_fees
        return self.total
        
    def get_total_cost(self):
        """Calculate the total cost of the order by summing all items and additional fees."""
        if not self.pk:
            return getattr(self, 'total', 0)
        return self.calculate_total()
        
    def update_payment_split(self, pay_now_amount=None):
        """Update pay_now and pay_later amounts based on the total."""
        total = self.calculate_total()
        
        if pay_now_amount is not None:
            # Ensure pay_now_amount doesn't exceed the total
            pay_now = min(max(Decimal('0'), Decimal(str(pay_now_amount))), total)
            self.pay_now = pay_now
            self.pay_later = total - pay_now
        else:
            # Default to full amount to pay now if not specified
            self.pay_now = total
            self.pay_later = Decimal('0')
            
        self.save(update_fields=['pay_now', 'pay_later', 'updated_at'])
        return self.pay_now, self.pay_later
        
    def save(self, *args, **kwargs):
        # Set created_by to the user if it's a new order and created_by is not set
        if not self.pk and not self.created_by_id and hasattr(self, '_current_user'):
            self.created_by = self._current_user
        
        # Save the order first to get a primary key
        super().save(*args, **kwargs)
        
        # Update the total after saving (in case items were added before saving)
        if not kwargs.pop('skip_total_update', False):
            self.total = self.get_total_cost()
            # Save again with the updated total
            super().save(update_fields=['total'] if self.pk else None)

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
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def subtotal(self):
        return self.price * Decimal(self.quantity)
        
    def save(self, *args, **kwargs):
        skip_order_update = kwargs.pop('skip_order_update', False)
        is_new = self.pk is None
        super().save(*args, **kwargs)
        # Update order total after saving the item
        if not skip_order_update:
            # Create a copy of kwargs without skip_total_update to pass to order.save()
            order_save_kwargs = {k: v for k, v in kwargs.items() if k != 'skip_total_update'}
            self.order.save(**order_save_kwargs)
    
    def delete(self, *args, **kwargs):
        order = self.order
        skip_order_update = kwargs.pop('skip_order_update', False)
        super().delete(*args, **kwargs)
        # Update order total after deleting the item
        if not skip_order_update:
            # Create a copy of kwargs without skip_total_update to pass to order.save()
            order_save_kwargs = {k: v for k, v in kwargs.items() if k != 'skip_total_update'}
            order.save(**order_save_kwargs)

    def __str__(self):
        return f"{self.quantity} x {self.variation}"


class OrderRequest(models.Model):
    """A buyer's order request that a seller can accept/decline/counter."""
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("accepted", "Accepted"),
        ("declined", "Declined"),
        ("countered", "Countered"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='order_requests')
    session_id = models.CharField(max_length=100, blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"OrderRequest #{self.id} ({self.status})"
    
    @property
    def total_amount(self):
        """Total amount for the entire order request (deposits + balances + interest)"""
        total = sum(item.total_amount for item in self.items.all())
        return Decimal(total).quantize(Decimal('0.00'))
    
    @property
    def amount_due_now(self):
        """Total amount to be paid now. For items with deposit, it's the deposit amount.
        For items without deposit, it's the full price.
        """
        total = 0
        for item in self.items.all():
            if item.deposit_percentage > 0:
                # For items with deposit, add the deposit amount
                total += item.deposit_amount
            else:
                # For items without deposit, add the full price
                total += item.subtotal()
        return Decimal(total).quantize(Decimal('0.00'))
    
    @property
    def amount_due_at_pickup(self):
        """Total amount to be paid at pickup (balance + interest)"""
        pickup_total = Decimal('0')
        for item in self.items.all():
            if item.deposit_percentage > 0:
                # For items with deposit: remaining balance + interest
                remaining_balance = max(Decimal('0'), item.subtotal() - item.deposit_amount)
                pickup_total += remaining_balance + item.interest_amount
            # For items without deposit, nothing is due at pickup (already paid in full)
        return pickup_total.quantize(Decimal('0.00'))


class IRate(models.Model):
    variation = models.ForeignKey(ProductVariation, on_delete=models.CASCADE, related_name='i_rates')
    lower_range= models.PositiveIntegerField()
    upper_range = models.PositiveIntegerField()
    must_pay_shipping = models.BooleanField(default=False)
    rate = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
class OrderRequestItem(models.Model):
    """Items in an OrderRequest, including proposed deposit percentage per variation."""
    order_request = models.ForeignKey(OrderRequest, on_delete=models.CASCADE, related_name='items')
    variation = models.ForeignKey(ProductVariation, on_delete=models.RESTRICT)
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    # Proposed deposit percentage for this variation (0-100)
    deposit_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)

    def subtotal(self):
        """Calculate the subtotal as unit_price * quantity, rounded to 2 decimal places."""
        total = self.unit_price * Decimal(str(self.quantity))
        return total.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    
    @property
    def deposit_amount(self):
        """
        Calculate the deposit amount based on percentage.
        Ensures deposit doesn't exceed 100% of the subtotal.
        """
        if self.deposit_percentage <= 0:
            return Decimal('0.00')
        # Ensure deposit doesn't exceed 100% of the subtotal
        deposit = (self.subtotal() * min(self.deposit_percentage, Decimal('100'))) / 100
        return min(deposit, self.subtotal()).quantize(Decimal('0.00'), rounding=ROUND_HALF_UP)

    @property
    def irate(self):
        """Get the interest rate for this item's deposit percentage.
        
        Returns:
            Optional[IRate]: The matching interest rate, or None if:
                - No variation is set
                - Variation has no i_rates relationship
                - No matching rate range is found
        """
        if not hasattr(self, 'variation') or not hasattr(self.variation, 'i_rates'):
            return None
            
        try:
            return self.variation.i_rates.filter(
                lower_range__lte=self.deposit_percentage,
                upper_range__gte=self.deposit_percentage
            ).select_related('variation').first()
        except Exception:
            # Handle any potential database or query errors
            return None

    @property
    def interest_amount(self):
        """
        Calculates the interest on the remaining balance after deposit.
        Interest is calculated as: (remaining_balance * rate) / 100
        """
        if not self.irate or self.deposit_percentage <= 0:
            return Decimal('0.00')
        
        remaining_balance = self.subtotal() - self.deposit_amount
        if remaining_balance <= 0:
            return Decimal('0.00')
        
        interest = (remaining_balance * self.irate.rate) / 100
        return interest.quantize(Decimal('0.00'), rounding=ROUND_HALF_UP)
    
    @property
    def total_amount(self):
        """
        Calculates the total amount to be paid, which is the sum of:
        - The deposit amount
        - The remaining balance after deposit
        - Interest on the remaining balance
        """
        if self.deposit_percentage > 0:
            # For items with deposit: deposit + remaining balance + interest
            remaining_balance = max(Decimal('0'), self.subtotal() - self.deposit_amount)
            total = self.deposit_amount + remaining_balance + self.interest_amount
        else:
            # For items without deposit: just the subtotal
            total = self.subtotal()
        return total.quantize(Decimal('0.00'), rounding=ROUND_HALF_UP)
    
    @property
    def balance_due(self):
        """
        Calculates the amount to be paid at pickup, which is the sum of:
        - The remaining balance after deposit
        - Interest on the remaining balance
        """
        remaining_balance = max(Decimal('0'), self.subtotal() - self.deposit_amount)
        if remaining_balance <= 0:
            return Decimal('0.00')
            
        balance_due = remaining_balance + self.interest_amount
        return balance_due.quantize(Decimal('0.00'), rounding=ROUND_HALF_UP)
    
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
    order_id = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="payments")

    raw_payment = models.ForeignKey(RawPayment, on_delete=models.CASCADE, related_name="payments")

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.raw_payment.transaction_id} - {self.raw_payment.payment_method} - {self.raw_payment.amount} {self.raw_payment.currency}"


class OrderAdditionalFees(models.Model):
    """Additional fees for orders (customs, shipping, handling, etc.)"""
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="additional_fees")
    fee_type = models.CharField(max_length=100, help_text="Type of fee (e.g., Customs, Shipping, Handling)")
    description = models.TextField(blank=True, help_text="Description of the additional fee")
    amount = models.DecimalField(max_digits=10, decimal_places=2, help_text="Amount of the additional fee")
    pay_now = models.BooleanField(default=True, help_text="Whether this fee should be paid immediately")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Order Additional Fee"
        verbose_name_plural = "Order Additional Fees"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.order} - {self.fee_type}: KSh {self.amount}"


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


# ==============================
# BUYER-SELLER CHAT MODELS
# ==============================

class BuyerSellerChat(models.Model):
    """Model for private conversations between buyers and sellers"""
    buyer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='buyer_chats'
    )
    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='seller_chats'
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='buyer_seller_chats',
        null=True,
        blank=True,
        help_text="Optional: Link to a specific product being discussed"
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('buyer', 'seller', 'product')
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['buyer', 'is_active']),
            models.Index(fields=['seller', 'is_active']),
            models.Index(fields=['product', 'is_active']),
        ]

    def __str__(self):
        product_name = f" - {self.product.name}" if self.product else ""
        
        # Get buyer name
        if self.buyer and hasattr(self.buyer, 'get_full_name') and self.buyer.get_full_name():
            buyer_name = self.buyer.get_full_name()
        elif self.buyer and self.buyer.email:
            buyer_name = self.buyer.email
        else:
            buyer_name = "Unknown Buyer"
            
        # Get seller name
        if self.seller and hasattr(self.seller, 'get_full_name') and self.seller.get_full_name():
            seller_name = self.seller.get_full_name()
        elif self.seller and self.seller.email:
            seller_name = self.seller.email
        else:
            seller_name = "Unknown Seller"
            
        return f"Chat: {buyer_name} ↔ {seller_name}{product_name}"

    @property
    def last_message(self):
        """Get the last message in this chat"""
        return self.messages.last()

    @property
    def unread_count_for_user(self, user):
        """Get unread message count for a specific user"""
        return self.messages.filter(
            sender=user,
            is_read=False
        ).count()


class BuyerSellerMessage(models.Model):
    """Model for individual messages in buyer-seller chats"""
    chat = models.ForeignKey(
        BuyerSellerChat,
        on_delete=models.CASCADE,
        related_name='messages'
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='buyer_seller_messages'
    )
    product = models.ForeignKey(
        'Product',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='product_chat_messages',
        help_text="The product this message is about, if any"
    )
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['chat', 'created_at']),
            models.Index(fields=['sender']),
            models.Index(fields=['is_read']),
        ]

    def __str__(self):
        if self.sender:
            if hasattr(self.sender, 'get_full_name') and self.sender.get_full_name():
                sender_name = self.sender.get_full_name()
            elif self.sender.email:
                sender_name = self.sender.email
            else:
                sender_name = "Unknown User"
        else:
            sender_name = "Unknown User"
            
        return f"Message from {sender_name} in chat {self.chat.id}"

    def mark_as_read(self):
        """Mark this message as read"""
        self.is_read = True
        self.save(update_fields=['is_read'])
