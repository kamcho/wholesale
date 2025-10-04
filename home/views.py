from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.utils.translation import gettext as _
from django.core.paginator import Paginator
from django.db.models import Q, Min, Max
from .models import Product, ProductCategory, Business, ProductImage, ProductCategoryFilter, Cart, CartItem, ProductVariation, Wishlist, WishlistItem, ProductOrder, Payment
from django.contrib.auth.decorators import login_required

def home(request):
    return render(request, 'users/home.html')

def product_list(request):
    """Display all products for customers to browse"""
    # Get all active products
    products = Product.objects.all().order_by('-created_at')
    
    # Search functionality
    search_query = request.GET.get('search', '')
    if search_query:
        products = products.filter(
            Q(name__icontains=search_query) |
            Q(description__icontains=search_query) |
            Q(business__name__icontains=search_query)
        )
    
    # Category filter (supports many-to-many)
    category_id = request.GET.get('category', '')
    if category_id:
        products = products.filter(categories__id=category_id)
    
    # Price range filter
    min_price = request.GET.get('min_price', '')
    max_price = request.GET.get('max_price', '')
    if min_price:
        products = products.filter(price__gte=min_price)
    if max_price:
        products = products.filter(price__lte=max_price)
    
    # Pagination
    paginator = Paginator(products, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get categories for filter dropdown
    categories = ProductCategory.objects.all()
    
    context = {
        'page_obj': page_obj,
        'categories': categories,
        'search_query': search_query,
        'selected_category': category_id,
        'min_price': min_price,
        'max_price': max_price,
    }
    
    return render(request, 'home/product_list.html', context)

def product_detail(request, pk):
    """Display detailed view of a single product"""
    product = get_object_or_404(Product, pk=pk)
    images = ProductImage.objects.filter(product=product)
    # Wishlist state for authenticated users
    wishlist_items = []
    # Logged-in user's orders and payments for this product
    my_orders = []
    my_payments = []
    
    # Get the default variation or first available variation for wishlist
    default_variation = product.variations.first()
    
    if request.user.is_authenticated:
        wishlist = Wishlist.objects.filter(user=request.user).first()
        if wishlist and default_variation:
            wishlist_items = list(WishlistItem.objects.filter(
                wishlist=wishlist, 
                product__in=product.variations.all()
            ))
            
        # Fetch user's ProductOrder objects for this product's variations
        my_orders = ProductOrder.objects.filter(
            user=request.user, 
            product__in=product.variations.all()
        ).order_by('-created_at')
        
        # Fetch user's Payments tied to orders of this product's variations
        my_payments = Payment.objects.filter(
            user=request.user, 
            order_id__product__in=product.variations.all()
        ).select_related('raw_payment').order_by('-created_at')
    
    # Get related products sharing at least one category
    related_products = Product.objects.filter(
        categories__in=product.categories.all()
    ).exclude(pk=product.pk).distinct()[:4]
    # Variation price range (min/max)
    variation_price_range = ProductVariation.objects.filter(product=product).aggregate(
        min_price=Min('price'), max_price=Max('price')
    )
    
    context = {
        'product': product,
        'images': images,
        'related_products': related_products,
        'wishlist_items': wishlist_items,
        'default_variation': default_variation,
        'my_orders': my_orders,
        'my_payments': my_payments,
        'variation_min_price': variation_price_range.get('min_price'),
        'variation_max_price': variation_price_range.get('max_price'),
    }
    
    return render(request, 'home/product_detail.html', context)


def variation_detail(request, pk):
    """Public detail page for a specific ProductVariation."""
    variation = get_object_or_404(ProductVariation.objects.select_related('product'), pk=pk)
    product = variation.product
    
    # Prefer variation-specific images; fallback to product images
    variation_images = variation.images.all()
    images = variation_images if variation_images.exists() else ProductImage.objects.filter(product=product)
    
    # Get all attribute assignments for this variation
    attributes = variation.attribute_assignments.select_related('value__attribute').all()
    
    # Group attributes by attribute type for better display
    attribute_groups = {}
    for attr in attributes:
        attr_name = attr.value.attribute.name
        if attr_name not in attribute_groups:
            attribute_groups[attr_name] = []
        attribute_groups[attr_name].append(attr.value.value)
    
    # Related products sharing at least one category with the parent product
    related_products = Product.objects.filter(
        categories__in=product.categories.all()
    ).exclude(pk=product.pk).distinct()[:4]

    context = {
        'product': product,
        'variation': variation,
        'images': images,
        'related_products': related_products,
        'attribute_groups': attribute_groups,
        'has_attributes': bool(attribute_groups),
    }
    return render(request, 'home/variation_detail.html', context)


@login_required
def create_product_order(request, pk):
    """Create a ProductOrder (commit-to-order) for a given product."""
    product = get_object_or_404(Product, pk=pk)
    
    if request.method == 'GET':
        # Redirect to the order creation page
        return redirect('home:product_order_create', pk=product.pk)
    
    # Handle POST request
    try:
        quantity = int(request.POST.get('quantity') or '0')
    except (TypeError, ValueError):
        quantity = 0

    if quantity <= 0:
        messages.error(request, _("Please enter a valid quantity."))
        return redirect('home:product_detail', pk=product.pk)

    # Enforce product-level MOQ
    if product.moq and quantity < product.moq:
        messages.error(request, _("Quantity must be at least the product MOQ of %(moq)d." % { 'moq': product.moq }))
        return redirect('home:product_detail', pk=product.pk)

    ProductOrder.objects.create(user=request.user, product=product, quantity=quantity)
    messages.success(request, _("Order commitment created."))
    return redirect('home:product_detail', pk=product.pk)


@login_required
def product_order_create(request, pk):
    product = get_object_or_404(Product, pk=pk)
    if request.method == 'POST':
        try:
            quantity = int(request.POST.get('quantity') or '0')
        except (TypeError, ValueError):
            quantity = 0
        if product.moq and quantity < product.moq:
            messages.error(request, _("Quantity must be at least the product MOQ of %(moq)d." % { 'moq': product.moq }))
        else:
            order = ProductOrder.objects.create(user=request.user, product=product, quantity=quantity)
            messages.success(request, _("Order created successfully."))
            return redirect('home:product_order_payment', order_id=order.id)
    return render(request, 'home/product_order_create.html', { 'product': product })


@login_required
def product_order_payment(request, order_id):
    order = get_object_or_404(ProductOrder, id=order_id, user=request.user)
    if request.method == 'POST':
        # Capture phone number and store in note (since there's no dedicated field)
        phone = (request.POST.get('phone') or '').strip()
        if phone:
            prefix = "Phone: "
            # Prepend or update phone in note
            existing = order.note or ''
            if existing.startswith(prefix):
                # Replace existing phone line
                rest = existing.split('\n', 1)[1] if '\n' in existing else ''
                order.note = f"{prefix}{phone}\n{rest}".rstrip()
            else:
                order.note = (f"{prefix}{phone}\n{existing}").rstrip()
        # Update order status to confirmed
        order.status = 'confirmed'
        order.save()
        messages.success(request, _("Order confirmed."))
        return redirect('home:product_detail', pk=order.product.pk)
    return render(request, 'home/product_order_payment.html', { 'order': order })

def category_products(request, category_id):
    """Display products filtered by category"""
    category = get_object_or_404(ProductCategory, pk=category_id)
    products = Product.objects.filter(categories=category).order_by('-created_at')
    
    # Search within category
    search_query = request.GET.get('search', '')
    if search_query:
        products = products.filter(
            Q(name__icontains=search_query) |
            Q(description__icontains=search_query)
        )
    
    # Pagination
    paginator = Paginator(products, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'category': category,
        'page_obj': page_obj,
        'search_query': search_query,
    }
    
    return render(request, 'home/category_products.html', context)




def _get_or_create_cart(request):
    """Return a cart for the current user/session, creating if needed."""
    if request.user.is_authenticated:
        cart, created = Cart.objects.get_or_create(user=request.user)
        return cart
    # Ensure a session exists
    if not request.session.session_key:
        request.session.create()
    session_id = request.session.session_key
    cart, created = Cart.objects.get_or_create(session_id=session_id, user=None)
    return cart


@require_POST
def add_to_cart(request):
    """Add a product (optionally with variation) to the cart."""
    product_id = request.POST.get('product_id')
    variation_id = request.POST.get('variation_id') or None
    quantity_raw = request.POST.get('quantity') or '1'

    product = get_object_or_404(Product, pk=product_id)

    # Validate quantity respects MOQ (product- or variation-level)
    try:
        quantity = int(quantity_raw)
    except ValueError:
        quantity = 1

    variation = None
    if variation_id:
        variation = get_object_or_404(ProductVariation, pk=variation_id, product=product)
        # Enforce variation-specific MOQ if present
        if variation.moq and quantity < variation.moq:
            quantity = variation.moq
    else:
        # Fallback to product-level MOQ
        if product.moq and quantity < product.moq:
            quantity = product.moq

    cart = _get_or_create_cart(request)

    # Merge with existing cart item if same product/variation
    item_qs = CartItem.objects.filter(cart=cart, product=product)
    if variation is None:
        item_qs = item_qs.filter(variation__isnull=True)
    else:
        item_qs = item_qs.filter(variation=variation)

    cart_item = item_qs.first()
    if cart_item:
        cart_item.quantity += quantity
        cart_item.save()
    else:
        CartItem.objects.create(cart=cart, product=product, variation=variation, quantity=quantity)

    messages.success(request, _("Added to cart."))
    return redirect('home:product_detail', pk=product.pk)

@require_POST
def remove_from_cart(request):
    """Add a product (optionally with variation) to the cart."""
    product_id = request.POST.get('product_id')
    variation_id = request.POST.get('variation_id') or None
    quantity_raw = request.POST.get('quantity') or '1'

    product = get_object_or_404(Product, pk=product_id)

  

    variation = None
    if variation_id:
        variation = get_object_or_404(ProductVariation, pk=variation_id, product=product)

    cart = _get_or_create_cart(request)

    # Merge with existing cart item if same product/variation
    item_qs = CartItem.objects.filter(cart=cart, product=product)
    if variation is None:
        item_qs = item_qs.filter(variation__isnull=True)
    else:
        item_qs = item_qs.filter(variation=variation)

    cart_item = item_qs.first()
    if cart_item:
        cart_item.quantity += quantity
        cart_item.save()
    else:
        CartItem.objects.create(cart=cart, product=product, variation=variation, quantity=quantity)

    messages.success(request, _("Remove from cart."))
    return redirect('home:product_detail', pk=product.pk)
def cart_detail(request):
    """Display current cart with items and totals."""
    cart = _get_or_create_cart(request)
    items = cart.items.select_related('product', 'variation').all()
    total = cart.total_price() if hasattr(cart, 'total_price') else sum(i.subtotal() for i in items)
    return render(request, 'home/cart_detail.html', {
        'cart': cart,
        'items': items,
        'total': total,
    })


@require_POST
def update_cart_item(request, item_id):
    """Update quantity of a cart item (enforce MOQ)."""
    cart = _get_or_create_cart(request)
    item = get_object_or_404(CartItem, pk=item_id, cart=cart)
    quantity_raw = request.POST.get('quantity')
    try:
        quantity = int(quantity_raw)
    except (TypeError, ValueError):
        quantity = item.product.moq

    # Enforce MOQ depending on whether item has a variation
    if item.variation and item.variation.moq and quantity < item.variation.moq:
        quantity = item.variation.moq
    elif quantity < item.product.moq:
        quantity = item.product.moq

    if quantity <= 0:
        item.delete()
        messages.success(request, _("Item removed from cart."))
    else:
        item.quantity = quantity
        item.save()
        messages.success(request, _("Cart updated."))
    return redirect('home:cart_detail')


@require_POST
def remove_cart_item(request, item_id):
    cart = _get_or_create_cart(request)
    item = get_object_or_404(CartItem, pk=item_id, cart=cart)
    item.delete()
    messages.success(request, _("Item removed from cart."))
    return redirect('home:cart_detail')


@require_POST
def clear_cart(request):
    cart = _get_or_create_cart(request)
    cart.items.all().delete()
    messages.success(request, _("Cart cleared."))
    return redirect('home:cart_detail')


# ==============================
# Wishlist
# ==============================
@login_required
def wishlist_list(request):
    wishlist, created = Wishlist.objects.get_or_create(user=request.user)
    items = wishlist.items.select_related('product').all()
    return render(request, 'home/wishlist.html', { 'wishlist': wishlist, 'items': items })


@login_required
@require_POST
def add_to_wishlist(request):
    variation_id = request.POST.get('variation_id')
    if not variation_id:
        messages.error(request, _('No product variation specified.'))
        return redirect('home:home')
        
    variation = get_object_or_404(ProductVariation, pk=variation_id)
    wishlist, created = Wishlist.objects.get_or_create(user=request.user)
    
    # Check if this variation is already in the wishlist
    item, created = WishlistItem.objects.get_or_create(
        wishlist=wishlist, 
        product=variation
    )
    
    if created:
        messages.success(request, _('Added %(name)s to your wishlist.') % {'name': variation.name})
    else:
        messages.info(request, _('%(name)s is already in your wishlist.') % {'name': variation.name})
        
    return redirect('home:product_detail', pk=variation.product.id)


@login_required
@require_POST
def remove_from_wishlist(request, item_id):
    wishlist, created = Wishlist.objects.get_or_create(user=request.user)
    item = get_object_or_404(WishlistItem, pk=item_id, wishlist=wishlist)
    product_id = item.product.product.id if hasattr(item.product, 'product') and item.product.product else None
    item_name = item.product.name
    item.delete()
    messages.success(request, _('Removed %(name)s from your wishlist.') % {'name': item_name})
    
    # Redirect back to the product detail page if we came from there
    if 'HTTP_REFERER' in request.META and 'product' in request.META.get('HTTP_REFERER', '') and product_id:
        return redirect('home:product_detail', pk=product_id)
    return redirect('home:wishlist')
