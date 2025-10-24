import json
import logging
import re
import time
import decimal
from decimal import Decimal, ROUND_HALF_UP
from django.conf import settings

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q, Min, Max, Count, Avg
from django.views.generic import ListView
from django.core.paginator import Paginator

from .models import Agent, ServiceCategory, ProductServicing,OrderAdditionalFees, PaymentRequest
from .forms import UserRegistrationForm
from django.contrib import messages
from django.contrib.auth import login
from agents.forms import AgentSearchForm
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, get_object_or_404, redirect, reverse
from django.views.generic import CreateView, TemplateView
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_http_methods
from django_countries import countries

from .models import (
    Order, OrderItem, Product, ProductCategory, Business, ProductImage, 
    ProductCategoryFilter, Cart, CartItem, ProductVariation, Wishlist, 
    WishlistItem, ProductOrder, Payment, OrderRequest, OrderRequestItem, AdditionalFees,
    RawPayment
)
class SignUpView(CreateView):
    form_class = UserRegistrationForm
    template_name = 'home/signup.html'
    
    def get_success_url(self):
        # Redirect to appropriate dashboard based on user role
        if self.request.user.role == 'buyer':
            return reverse_lazy('home:buyer_dashboard')
        elif self.request.user.role == 'seller':
            return reverse_lazy('home:seller_dashboard')
        return reverse_lazy('home:home')
    
    def form_valid(self, form):
        # Save the user with the selected role
        user = form.save(commit=False)
        user.role = form.cleaned_data['role']
        user.save()
        
        # Save many-to-many data if needed
        form.save_m2m()
        
        # Log the user in
        from django.contrib.auth import login
        login(self.request, user, backend='django.contrib.auth.backends.ModelBackend')
        
        # Show success message
        messages.success(
            self.request, 
            f'Account created successfully! Welcome, {user.get_full_name() or user.email}.'
        )
        
        return super().form_valid(form)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Create an Account'
        return context
    
    def dispatch(self, request, *args, **kwargs):
        # Redirect to home if user is already authenticated
        if request.user.is_authenticated:
            return redirect('home:home')
        return super().dispatch(request, *args, **kwargs)

def home(request):
    return render(request, 'users/home.html')

def product_list(request):
    """Display all products for customers to browse with advanced filtering"""
    # Get filter parameters
    search_query = request.GET.get('search', '')
    category_id = request.GET.get('category', '')
    min_price = request.GET.get('min_price', '')
    max_price = request.GET.get('max_price', '')
    country = request.GET.get('country', '')
    sort = request.GET.get('sort', '-created_at')
    
    # Get all active products with related data and price ranges
    from django.db.models import Min, Max
    products = Product.objects.prefetch_related('images', 'categories', 'business', 'variations')
    
    # Annotate each product with min and max price from its variations
    products = products.annotate(
        min_variation_price=Min('variations__price'),
        max_variation_price=Max('variations__price')
    )
    
    # Apply filters
    if search_query:
        products = products.filter(
            Q(name__icontains=search_query) |
            Q(description__icontains=search_query) |
            Q(business__name__icontains=search_query)
        )
    
    if category_id:
        products = products.filter(categories__id=category_id)
    
    if min_price:
        products = products.filter(price__gte=min_price)
    if max_price:
        products = products.filter(price__lte=max_price)
        
    # Filter by country
    if country:
        products = products.filter(origin=country)
    
    # Apply sorting
    valid_sort_fields = ['name', '-name', 'price', '-price', 'created_at', '-created_at']
    if sort in valid_sort_fields:
        products = products.order_by(sort)
    else:
        products = products.order_by('-created_at')
    
    # Get categories with product counts for the sidebar
    categories = ProductCategory.objects.annotate(
        product_count=Count('products')
    ).filter(product_count__gt=0).order_by('name')
    
    # Get unique countries with product counts
    country_choices = []
    
    # Get all distinct country codes that have products
    country_codes = Product.objects.exclude(origin__isnull=True).exclude(origin='').values_list('origin', flat=True).distinct()
    
    if country_codes:
        # Create a list of (code, name, count) tuples
        for code in country_codes:
            if code in countries:
                count = Product.objects.filter(origin=code).count()
                if count > 0:
                    country_choices.append((code, f"{countries.name(code)} ({count})"))
        
        # Sort countries by name
        country_choices.sort(key=lambda x: x[1])
    else:
        # If no countries are set, show a message in the template
        country_choices = [('', 'No countries available')]
    
    # Pagination
    paginator = Paginator(products, 12)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'categories': categories,
        'search_query': search_query,
        'selected_category': category_id,
        'min_price': min_price,
        'max_price': max_price,
        'selected_country': country,
        'country_choices': country_choices,
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
            

        
        # Fetch user's Payments tied to orders of this product's variations
        my_payments = Payment.objects.filter(
            user=request.user, 
            order_id__items__variation__in=product.variations.all()
        ).select_related('raw_payment').order_by('-created_at')
    
    # Get related products sharing at least one category
    related_products = Product.objects.filter(
        categories__in=product.categories.all()
    ).exclude(pk=product.pk).distinct()[:4]
    
    # Check if any variation has a promise fee
    has_promise_fee = product.variations.filter(promise_fee__isnull=False).exists()
    
    # Variation price range (min/max)
    variation_qs = ProductVariation.objects.filter(product=product).prefetch_related('price_tiers')
    variation_price_range = variation_qs.aggregate(
        min_price=Min('price'), max_price=Max('price')
    )
    # Map of variation id -> list of price tiers
    price_tiers_by_variation = {}
    for v in variation_qs:
        tiers = list(v.price_tiers.all())
        if tiers:
            price_tiers_by_variation[v.id] = tiers
    
    # Cart state: which variation ids are in the current cart
    try:
        cart = _get_or_create_cart(request)
        cart_variation_ids = set(CartItem.objects.filter(cart=cart).values_list('variation_id', flat=True))
    except Exception:
        cart_variation_ids = set()

    # Get product servicing information
    product_servicing = None
    try:
        product_servicing = ProductServicing.objects.get(product=product)
    except ProductServicing.DoesNotExist:
        pass

    # Get additional fees for this product's variations
    additional_fees = AdditionalFees.objects.filter(variation__product=product).distinct()
    
    # Get related orders for this product and its variations
    # First get unique orders that have items for this product
    related_order_ids = OrderItem.objects.filter(
        variation__product=product
    ).values_list('order_id', flat=True).distinct()
    
    # Then get the orders with their items for this product (excluding cancelled orders)
    from django.db.models import Prefetch
    related_orders = Order.objects.filter(
        id__in=related_order_ids
    ).exclude(
        status='cancelled'
    ).prefetch_related(
        Prefetch(
            'items',
            queryset=OrderItem.objects.filter(
                variation__product=product
            ).select_related('variation'),
            to_attr='product_items'
        )
    ).order_by('-created_at')
    
    # Get unique order requests with their items for this product
    from django.db.models import Prefetch
    from django.db.models.functions import Coalesce
    
    # First, get the order requests that have items for this product and are pending
    order_requests = OrderRequest.objects.filter(
        items__variation__product=product,
        status='pending'
    ).distinct().prefetch_related(
        Prefetch(
            'items',
            queryset=OrderRequestItem.objects.filter(
                variation__product=product
            ).select_related('variation'),
            to_attr='filtered_items'
        )
    ).order_by('-created_at')
    
    # Group order requests by their ID
    related_order_requests = {}
    for order_request in order_requests:
        related_order_requests[order_request.id] = {
            'order_request': order_request,
            'items': order_request.filtered_items,
            'total': sum(item.subtotal() for item in order_request.filtered_items),
            'deposit_total': sum(item.deposit_amount for item in order_request.filtered_items)
        }
    
    context = {
        'product': product,
        'images': images,
        'related_products': related_products,
        'wishlist_items': wishlist_items,
        'default_variation': default_variation,
        'my_payments': my_payments,
        'variation_min_price': variation_price_range.get('min_price'),
        'variation_max_price': variation_price_range.get('max_price'),
        'price_tiers_by_variation': price_tiers_by_variation,
        'cart_variation_ids': cart_variation_ids,
        'has_promise_fee': has_promise_fee,
        'product_servicing': product_servicing,
        'additional_fees': additional_fees,
        'related_orders': related_orders,
        'related_order_requests': related_order_requests,
    }
    
    return render(request, 'home/product_detail.html', context)


def variation_detail(request, pk):
    """Public detail page for a specific ProductVariation."""
    variation = get_object_or_404(
        ProductVariation.objects.select_related('product').prefetch_related('price_tiers'),
        pk=pk
    )
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

    # Cart state for this variation
    try:
        cart = _get_or_create_cart(request)
        in_cart = CartItem.objects.filter(cart=cart, variation=variation).exists()
    except Exception:
        in_cart = False

    # Check if this variation has a promise fee
    has_promise_fee = hasattr(variation, 'promise_fee') and variation.promise_fee is not None
    
    # Get all variations for this product with prefetched images
    variations = product.variations.all().select_related('product').prefetch_related('images')
    variations_count = variations.count()
    
    # Get additional fees for this specific variation
    additional_fees = AdditionalFees.objects.filter(variation=variation).distinct()
    
    context = {
        'product': product,
        'variation': variation,
        'variations': variations,
        'images': images,
        'related_products': related_products,
        'attribute_groups': attribute_groups,
        'has_attributes': bool(attribute_groups),
        'price_tiers': list(variation.price_tiers.all()),
        'has_promise_fee': has_promise_fee,
        'in_cart': in_cart,
        'variations_count': variations_count,
        'additional_fees': additional_fees,
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
    variations = ProductVariation.objects.filter(product=product)
    if request.method == 'POST':
        created_any = False
        for v in variations:
            raw = request.POST.get(f'qty_{v.id}', '').strip()
            if not raw:
                continue
            try:
                qty = int(raw)
            except (TypeError, ValueError):
                qty = 0
            if qty <= 0:
                continue
            if v.moq and qty < v.moq:
                messages.warning(request, _("Adjusted %(name)s to MOQ %(moq)d." % { 'name': v.name, 'moq': v.moq }))
                qty = v.moq
            ProductOrder.objects.create(user=request.user, product=v, quantity=qty)
            created_any = True
        if created_any:
            messages.success(request, _("Order(s) created successfully."))
            return redirect('home:product_detail', pk=product.id)
        else:
            messages.error(request, _("Please enter quantities for at least one variation."))
    return render(request, 'home/product_order_create.html', { 'product': product, 'variations': variations })


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
        # No variation specified – CartItem requires a variation; abort with message
        messages.error(request, _("Unable to add to cart: please select a product variation."))
        return redirect('home:product_detail', pk=product.pk)

    cart = _get_or_create_cart(request)

    # Merge with existing cart item if same variation
    item_qs = CartItem.objects.filter(cart=cart, variation=variation)

    cart_item = item_qs.first()
    if cart_item:
        cart_item.quantity += quantity
        cart_item.save()
    else:
        CartItem.objects.create(cart=cart, variation=variation, quantity=quantity)

    messages.success(request, _("Added to cart."))
    # Redirect back to where the user came from
    next_url = request.POST.get('next') or request.GET.get('next') or request.META.get('HTTP_REFERER')
    if next_url:
        return redirect(next_url)
    # Fallbacks
    if variation:
        return redirect('home:variation_detail', pk=variation.pk)
    return redirect('home:product_detail', pk=product.pk)

@require_POST
def remove_from_cart(request):
    """Remove a cart item for a given variation."""
    product_id = request.POST.get('product_id')
    variation_id = request.POST.get('variation_id') or None

    product = get_object_or_404(Product, pk=product_id)

    if not variation_id:
        messages.error(request, _("Unable to remove from cart: missing variation."))
        return redirect('home:product_detail', pk=product.pk)

    variation = get_object_or_404(ProductVariation, pk=variation_id, product=product)
    cart = _get_or_create_cart(request)

    cart_item = CartItem.objects.filter(cart=cart, variation=variation).first()
    if cart_item:
        cart_item.delete()
        messages.success(request, _("Removed from cart."))
    else:
        messages.info(request, _("Item not found in cart."))
    # Redirect back to where the user came from
    next_url = request.POST.get('next') or request.GET.get('next') or request.META.get('HTTP_REFERER')
    if next_url:
        return redirect(next_url)
    return redirect('home:variation_detail', pk=variation.pk)
def cart_detail(request):
    """Display current cart with items and totals."""
    cart = _get_or_create_cart(request)
    items = cart.items.select_related('variation__product').all()
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
    item = get_object_or_404(CartItem.objects.select_related('variation__product'), pk=item_id, cart=cart)
    
    # Get the quantity from the form, defaulting to the current quantity
    quantity_raw = request.POST.get('quantity', str(item.quantity))
    
    try:
        quantity = max(1, int(quantity_raw))  # Ensure at least 1
    except (TypeError, ValueError):
        quantity = 1
    
    # Get the minimum order quantity (MOQ) from the variation or product
    moq = 1  # Default MOQ
    if hasattr(item, 'variation') and item.variation:
        if hasattr(item.variation, 'moq') and item.variation.moq is not None:
            moq = item.variation.moq
        elif hasattr(item.variation, 'product') and hasattr(item.variation.product, 'moq') and item.variation.product.moq is not None:
            moq = item.variation.product.moq
    
    # Ensure quantity meets or exceeds MOQ
    if quantity < moq:
        quantity = moq
        messages.warning(request, f"Minimum order quantity for this item is {moq}.")
    
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
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'success': True})
    return redirect('home:cart_detail')


def quick_checkout(request):
    """Handle quick checkout form submission and redirect to checkout page."""
    if request.method == 'POST':
        # Get the cart or create a new one
        cart = _get_or_create_cart(request)
        
        # Clear existing items in the cart
        cart.items.all().delete()
        
        # Process each variation quantity from the form
        for key, value in request.POST.items():
            if key.startswith('quantity_') and value.isdigit() and int(value) > 0:
                variation_id = key.replace('quantity_', '')
                quantity = int(value)
                
                try:
                    variation = ProductVariation.objects.get(id=variation_id)
                    # Add item to cart
                    cart_item, created = CartItem.objects.get_or_create(
                        cart=cart,
                        variation=variation,
                        defaults={'quantity': quantity}
                    )
                    if not created:
                        cart_item.quantity = quantity
                        cart_item.save()
                except ProductVariation.DoesNotExist:
                    continue
        
        # Store cart ID in session for quick checkout
        request.session['quick_checkout_cart_id'] = cart.id
        
        # Redirect to the checkout page
        return redirect('home:quick_checkout_page')
    
    return redirect('home:home')


def quick_checkout_page(request):
    """Display the quick checkout page with the items in the cart."""
    cart_id = request.session.get('quick_checkout_cart_id')
    if not cart_id:
        return redirect('home:home')
    
    try:
        cart = Cart.objects.get(id=cart_id)
        # Optimize the query to fetch all related data efficiently
        cart_items = cart.items.select_related(
            'variation__product'
        ).prefetch_related(
            'variation__promise_fee',
            'variation__i_rates'
        ).all()
        
        if not cart_items:
            messages.warning(request, "Your cart is empty.")
            return redirect('home:product_list')
        
        # Calculate total and prepare cart items
        total = Decimal('0')
        processed_items = []
        
        for item in cart_items:
            # Calculate item total (base price)
            item_total = item.variation.price * item.quantity
            total += item_total
            
            # Create a dictionary with the item data including promise fee
            processed_item = {
                'id': item.id,
                'variation': item.variation,
                'quantity': item.quantity,
                'price': item.variation.price,
                'total_price': item_total,
            }
            processed_items.append(processed_item)
        
        context = {
            'cart_items': processed_items,
            'total': total,
        }
        return render(request, 'home/quick_checkout.html', context)
    except Cart.DoesNotExist:
        messages.error(request, "Invalid cart. Please try again.")
        return redirect('home:home')


@require_http_methods(["POST"])
def create_order(request):
    """Create an order and redirect to order detail page."""
    logger = logging.getLogger(__name__)
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request method'}, status=405)
    
    try:
        # Get cart from session
        cart_id = request.session.get('quick_checkout_cart_id')
        if not cart_id:
            return JsonResponse({'error': 'Your session has expired. Please add items to your cart again.'}, status=400)
        
        cart = Cart.objects.get(id=cart_id)
        cart_items = cart.items.select_related('variation__product').all()
        
        if not cart_items:
            return JsonResponse({'error': 'Your cart is empty'}, status=400)
        
        # Create order
        order = Order.objects.create(
            user=request.user if request.user.is_authenticated else None,
            status='pending',
            total=Decimal('0.00'),
            shipping_address=request.user.shipping_address if hasattr(request.user, 'shipping_address') else None
        )
        
        # Add items to order
        total = Decimal('0.00')
        for item in cart_items:
            item_total = item.variation.price * item.quantity
            total += item_total
            
            OrderItem.objects.create(
                order=order,
                variation=item.variation,
                quantity=item.quantity,
                price=item.variation.price
            )
        
        # Update order total
        order.total = total
        order.save()
        
        # Clear the cart
        cart.items.all().delete()
        if 'quick_checkout_cart_id' in request.session:
            del request.session['quick_checkout_cart_id']
        
        # Return success response with redirect URL
        return JsonResponse({
            'success': True,
            'order_id': order.id,
            'redirect_url': f'/orders/{order.id}/'
        })
        
    except Cart.DoesNotExist:
        return JsonResponse({'error': 'Cart not found'}, status=404)
    except Exception as e:
        logger.error(f'Error creating order: {str(e)}')
        return JsonResponse({'error': 'An error occurred while creating your order'}, status=500)


@require_http_methods(["POST"])
def create_order_request(request):
    """Create an OrderRequest with items and optional per-item deposit percentages."""
    try:
        payload = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    # Deposit map: { cart_item_id: { enabled: bool, percentage: number } }
    deposit_map = payload.get('payment_plans', {}) or {}

    # Get cart
    cart_id = request.session.get('quick_checkout_cart_id')
    if not cart_id:
        return JsonResponse({'error': 'Your session has expired. Please add items again.'}, status=400)

    try:
        cart = Cart.objects.get(id=cart_id)
    except Cart.DoesNotExist:
        return JsonResponse({'error': 'Cart not found'}, status=404)

    cart_items = cart.items.select_related('variation__product').all()
    if not cart_items:
        return JsonResponse({'error': 'Your cart is empty'}, status=400)

    # Create OrderRequest
    if request.user.is_authenticated:
        order_request = OrderRequest.objects.create(user=request.user)
    else:
        if not request.session.session_key:
            request.session.create()
        order_request = OrderRequest.objects.create(session_id=request.session.session_key)

    # Copy items and store deposit percentages
    for item in cart_items:
        deposit_info = deposit_map.get(str(item.id)) or {}
        enabled = bool(deposit_info.get('enabled'))
        percentage = deposit_info.get('percentage')

        try:
            percentage_value = Decimal(str(percentage)) if (enabled and percentage is not None) else Decimal('0')
        except Exception:
            percentage_value = Decimal('0')

        OrderRequestItem.objects.create(
            order_request=order_request,
            variation=item.variation,
            quantity=item.quantity,
            unit_price=item.variation.price,
            deposit_percentage=percentage_value
        )

    # Optionally clear cart
    cart.items.all().delete()
    request.session.pop('quick_checkout_cart_id', None)

    return JsonResponse({
        'success': True,
        'order_request_id': order_request.id,
        'redirect_url': f"/order-requests/{order_request.id}/"
    })


def process_mpesa_payment(request):
    """Process M-Pesa payment via STK push."""
    logger = logging.getLogger(__name__)
    logger.info("Received M-Pesa payment request")
    
    try:
        # Parse request data
        try:
            data = json.loads(request.body)
            phone_number = data.get('phone_number')
            payment_plans = data.get('payment_plans', {})
            order_id = data.get('order_id')
            logger.info(f"Payment request for phone: {phone_number}")
            logger.info(f"Payment plans: {payment_plans}")
            logger.info(f"Order ID: {order_id}")
        except json.JSONDecodeError:
            logger.error("Invalid JSON data received")
            return JsonResponse({'error': 'Invalid request data. Please try again.'}, status=400)
        
        # Validate phone number
        if not phone_number or not str(phone_number).strip():
            logger.error("No phone number provided")
            return JsonResponse({'error': 'Phone number is required'}, status=400)
        
        # Check if this is an order payment or cart payment
        if order_id:
            # Order-based payment
            try:
                order = get_object_or_404(Order, id=order_id)
                logger.info(f"Processing M-Pesa payment for existing order: {order_id}")
                
                # Calculate total amount from order items
                total_amount = order.total
                order_ref = f"ORD-{order_id}"
                
            except Order.DoesNotExist:
                logger.error(f"Order {order_id} not found")
                return JsonResponse({'error': 'Order not found'}, status=404)
        else:
            # Cart-based payment (original functionality)
            try:
                cart = _get_or_create_cart(request)
                cart_items = cart.items.select_related('variation__product').all()
                logger.info(f"Found cart with {cart_items.count()} items")
                
                if not cart_items.exists():
                    logger.error("Cart is empty")
                    return JsonResponse({'error': 'Your cart is empty. Please add items before checking out.'}, status=400)
                    
            except Exception as e:
                logger.error(f"Error retrieving cart: {str(e)}")
                return JsonResponse({'error': 'Unable to retrieve your cart. Please try again.'}, status=400)
            
            if not cart_items:
                logger.error("Cart is empty")
                return JsonResponse({'error': 'Your cart is empty. Please add items before checking out.'}, status=400)
        
        # Calculate total amount based on payment type
        if order_id:
            # For order payments, check if we have a specific amount in the request
            amount_override = data.get('amount')
            if amount_override is not None:
                try:
                    total_amount = Decimal(str(amount_override))
                    logger.info(f"Using override amount from request: ${total_amount}")
                except (ValueError, TypeError, decimal.InvalidOperation) as e:
                    logger.warning(f"Invalid amount override '{amount_override}': {str(e)}")
                    # Fall back to order total
                    logger.info(f"Using order total: ${total_amount}")
            else:
                # Check if we should use pay_now amount or calculate from fees
                if hasattr(order, 'pay_now') and order.pay_now and order.pay_now > 0:
                    total_amount = order.pay_now
                    logger.info(f"Using pay_now amount from order: ${total_amount}")
                else:
                    # Calculate total from order items and pay_now fees
                    pay_now_fees = Decimal('0')
                    for fee in order.additional_fees.filter(pay_now=True):
                        pay_now_fees += fee.amount
                    
                    total_amount = order.total + pay_now_fees
                    logger.info(f"Calculated amount from order total + pay_now fees: ${total_amount} (order: ${order.total}, fees: ${pay_now_fees})")
        else:
            # For cart payments, calculate based on payment plans with interest rates
            pay_now_amount = Decimal('0')
            pay_later_amount = Decimal('0')
            total_interest = Decimal('0')
            
            for item in cart_items:
                item_total = item.variation.price * item.quantity
                
                # Check if this item has a payment plan
                item_id = str(item.id)
                if item_id in payment_plans and payment_plans[item_id].get('enabled', False):
                    # Calculate payment plan amounts
                    percentage = Decimal(str(payment_plans[item_id].get('percentage', 0)))
                    
                    # Find the appropriate interest rate for this percentage
                    interest_rate = Decimal('0')
                    i_rates = item.variation.i_rates.all().order_by('lower_range')
                    
                    for i_rate in i_rates:
                        if i_rate.lower_range <= percentage <= i_rate.upper_range:
                            interest_rate = i_rate.rate
                            logger.info(f"Item {item_id}: Found interest rate {interest_rate}% for percentage {percentage}%")
                            break
                    
                    # Calculate amounts with interest
                    pay_now_item = (item_total * percentage / 100).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                    remaining_amount = item_total - pay_now_item
                    
                    # Apply interest rate to the remaining amount
                    interest_amount = (remaining_amount * interest_rate / 100).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                    pay_later_item = remaining_amount + interest_amount
                    
                    pay_now_amount += pay_now_item
                    pay_later_amount += pay_later_item
                    total_interest += interest_amount
                    total_amount += pay_now_item  # Only charge the pay now amount
                    
                    logger.info(f"Item {item_id}: Base ${item_total}, Pay Now ${pay_now_item} ({percentage}%), Pay Later ${pay_later_item} (Interest: ${interest_amount} at {interest_rate}%)")
                else:
                    # No payment plan, pay full amount now
                    total_amount += item_total
                    logger.info(f"Item {item_id}: No payment plan, full amount ${item_total}")
            
            logger.info(f"Final amounts - Total: ${total_amount}, Pay Now: ${pay_now_amount}, Pay Later: ${pay_later_amount}, Total Interest: ${total_interest}")
        
        # Format phone number to M-Pesa format (254XXXXXXXXX)
        phone = str(phone_number).strip()
        if phone.startswith('0'):
            phone = f'254{phone[1:]}'
        elif not phone.startswith('254'):
            phone = f'254{phone}'
            
        logger.info(f"Formatted phone number: {phone}")
        
        # Generate a unique order reference
        timestamp = int(timezone.now().timestamp())
        if order_id:
            order_ref = f"ORD-{order_id}-{timestamp}"
        else:
            order_ref = f"ORD-{cart.id}-{timestamp}"
        logger.info(f"Generated order reference: {order_ref}")
        
        # Initialize M-Pesa service
        try:
            from core.mpesa_service import MPesaService
            mpesa = MPesaService()
            logger.info("Initialized M-Pesa service")
        except Exception as e:
            logger.error(f"Failed to initialize M-Pesa service: {str(e)}")
            return JsonResponse({
                'error': 'Payment service is currently unavailable. Please try again later.'
            }, status=503)
        
        # For testing, we'll use a public callback URL that M-Pesa can reach
        # In production, replace this with your actual domain
        # Let M-Pesa service handle callback URL generation
        # This ensures ngrok and dynamic URLs work properly
        callback_url = None  # Let the service determine the URL
        
        # Ensure amount is an integer (KSH)
        try:
            total_amount = int(float(total_amount))
            if total_amount <= 0:
                raise ValueError("Amount must be greater than 0")
        except (ValueError, TypeError) as e:
            error_msg = f"Invalid amount: {total_amount}. Must be a positive number."
            logger.error(error_msg)
            return JsonResponse({"error": error_msg, "error_code": "INVALID_AMOUNT"}, status=400)
        
        # Create PaymentRequest record before initiating STK push
        payment_request = PaymentRequest.objects.create(
            order_id=order_id,
            amount=total_amount,
            phone_number=phone,
            status='pending',
            account_reference=f"ORDER{order_id}",
            transaction_desc=f"Order {order_id}",
            request_data={
                'order_id': order_id,
                'phone_number': phone,
                'amount': str(total_amount)
            }
        )
        
        # Store payment request ID in session for status checking
        request.session['payment_request_id'] = str(payment_request.id)
        request.session['payment_phone'] = phone
        request.session['payment_amount'] = str(total_amount)
        request.session['payment_order_id'] = order_id
        
        # Initiate STK push with proper error handling
        logger.info(f"Initiating STK push for {phone}, amount: {total_amount}")
        
        try:
            response = mpesa.initiate_stk_push(
                phone_number=phone,
                amount=total_amount,
                account_reference=f"ORDER{order_id}",  # No underscores in reference
                request=request,
                order_id=order_id,
                description=f"Order {order_id}",
                callback_url=callback_url
            )
            
            # Update PaymentRequest with M-Pesa response
            payment_request.merchant_request_id = response.get('MerchantRequestID')
            payment_request.checkout_request_id = response.get('CheckoutRequestID')
            payment_request.save()
            
            # Store checkout ID in session for frontend polling
            request.session['checkout_request_id'] = response.get('CheckoutRequestID')
            
            # Log the raw response for debugging
            logger.info(f"STK push response: {response}")
            
            # Check for errors in the response
            if 'error' in response:
                error_code = response.get('error_code', 'UNKNOWN')
                error_msg = response.get('error', 'Payment request failed')
                
                # Log the error with details
                logger.error(f"STK push failed: {error_msg} (Code: {error_code})")
                
                # User-friendly error messages based on error code
                if error_code in ['400.002.02', '400.001.01']:
                    error_msg = 'Invalid payment request. Please check the details and try again.'
                elif error_code == '500.001.1001':
                    error_msg = 'M-Pesa service is currently unavailable. Please try again later.'
                
                return JsonResponse({
                    'success': False,
                    'error': error_msg,
                    'error_code': error_code
                }, status=400)
                
            # If we get here, the STK push was initiated successfully
            logger.info(f"STK push initiated successfully for order {order_id}")
            
            # Double-check the order status was saved correctly
            order.refresh_from_db()
            logger.info(f"Order {order_id} final status after save: {order.status}")
            
            return JsonResponse({
                'success': True,
                'message': 'Payment request sent to your phone. Please complete the payment on your device.',
                'checkout_request_id': response.get('CheckoutRequestID'),
                'merchant_request_id': response.get('MerchantRequestID'),
                'order_id': order_id,
                'order_status': order.status,  # Include current status in response
                'redirect_url': f'/orders/{order_id}/'
            })
            
        except Exception as e:
            logger.exception("STK push failed with exception")
            return JsonResponse({
                'success': False,
                'error': f'Payment request failed: {str(e)}'
            }, status=500)
        
        # Handle M-Pesa response
        if 'error' in response:
            error_code = response.get('error_code', 'UNKNOWN')
            error_msg = response.get('error', 'Payment request failed')
            
            # Log the error with details
            logger.error(f"STK push failed: {error_msg} (Code: {error_code})")
            
            # Update order status to failed if we have an order
            if order_id:
                try:
                    order = Order.objects.get(id=order_id)
                    order.status = 'failed'
                    order.save()
                    logger.info(f"Order {order_id} status updated to 'failed' due to payment error")
                except Order.DoesNotExist:
                    logger.warning(f"Order {order_id} not found when trying to update status")
            
            # User-friendly error messages based on error code
            if '500.001.1001' in str(error_code) or 'AUTH_ERROR' in str(error_code):
                user_message = "Payment service is not configured. Please contact support."
            elif '400.002.02' in str(error_code):
                user_message = "Invalid phone number. Please check and try again."
            elif '400.001.02' in str(error_code):
                user_message = "Invalid amount. Please try again or contact support."
            else:
                user_message = f"Payment request failed: {error_msg}"
                
            return JsonResponse({
                'error': user_message,
                'error_code': error_code,
                'debug_info': 'Please check server logs for more details.',
                'order_status': 'failed' if order_id else None
            }, status=400)
        
        # Success - log and return success response
        logger.info(f"STK push initiated successfully. Response: {json.dumps(response)}")
        
        # Store order data in session for confirmation page
        if order_id:
            # For existing orders, create a RawPayment record
            raw_payment = RawPayment.objects.create(
                product_id=str(order_id),
                payment_method='mpesa',
                amount=total_amount,
                currency='KES',
                status='pending',
                transaction_id=response.get('CheckoutRequestID', ''),
                phone_number=phone
            )
            
            # Update order with payment info and set status to pending if not already in a terminal state
            if order.status not in ['paid', 'completed', 'shipped', 'delivered']:
                order.payment_method = 'mpesa'
                order.transaction_id = response.get('CheckoutRequestID', '')
                order.status = 'pending'  # Explicitly set status to pending
                order.save()
                logger.info(f"Order {order.id} status set to 'pending' for M-Pesa payment")
            else:
                logger.info(f"Order {order.id} already in {order.status} state, not changing to pending")
            
            return JsonResponse({
                'success': True,
                'message': 'Payment request sent to your phone. Please check your M-Pesa to complete the payment.',
                'order_reference': order_ref,
                'order_id': order_id,
                'redirect_url': f'/orders/{order_id}/',
                'data': response
            })
        else:
            # For cart payments, store in session as before
            session_order_id = int(time.time())  # Generate unique order ID
            request.session[f'pending_order_{session_order_id}'] = {
                'cart_id': cart.id,
                'total_amount': float(total_amount),
                'phone': phone,
                'transaction_id': response.get('CheckoutRequestID', ''),
                'order_ref': order_ref
            }
            
            return JsonResponse({
                'success': True,
                'message': 'Payment request sent to your phone. Please check your M-Pesa to complete the payment.',
                'order_reference': order_ref,
                'order_id': session_order_id,
                'redirect_url': f'/confirm-payment/{session_order_id}/',
                'data': response
            })
        
    except Exception as e:
        logger.exception("Unexpected error processing M-Pesa payment")
        return JsonResponse({
            'error': 'An unexpected error occurred. Our team has been notified.',
            'debug_info': str(e)
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def mpesa_callback(request):
    """Handle M-Pesa payment callback to confirm payment completion."""
    logger = logging.getLogger(__name__)
    logger.info("Received M-Pesa callback")
    
    if request.method != 'POST':
        logger.warning(f"Invalid request method: {request.method}")
        return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)
    
    try:
        # Parse the callback data
        body_unicode = request.body.decode('utf-8')
        logger.info(f"Raw callback data: {body_unicode}")
        
        try:
            data = json.loads(body_unicode)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON data: {e}")
            return JsonResponse({'status': 'error', 'message': 'Invalid JSON data'}, status=400)
        
        # Extract the important parts of the callback
        result_code = data.get('Body', {}).get('stkCallback', {}).get('ResultCode')
        result_desc = data.get('Body', {}).get('stkCallback', {}).get('ResultDesc', '')
        checkout_request_id = data.get('Body', {}).get('stkCallback', {}).get('CheckoutRequestID')
        
        logger.info(f"Callback received - ResultCode: {result_code}, ResultDesc: {result_desc}, CheckoutRequestID: {checkout_request_id}")
        
        # Try to find the payment request by checkout_request_id
        try:
            payment_request = PaymentRequest.objects.get(checkout_request_id=checkout_request_id)
            logger.info(f"Found payment request: {payment_request.id} for checkout request: {checkout_request_id}")
            
            # Update the payment request with the callback data
            payment_request.update_from_callback(data)
            
            # Get the order if it exists
            if hasattr(payment_request, 'order'):
                order = payment_request.order
                
                # Handle different payment statuses
                if payment_request.status == 'completed':
                    # Successful payment
                    order.status = 'paid'
                    order.payment_method = 'M-Pesa'
                    order.transaction_id = payment_request.mpesa_receipt_number
                    order.save()
                    
                    logger.info(f"Order {order.id} marked as paid with M-Pesa receipt {payment_request.mpesa_receipt_number}")
                    
                    # Clear the cart if it exists
                    if hasattr(request, 'session') and 'cart_id' in request.session:
                        try:
                            cart = Cart.objects.get(id=request.session['cart_id'])
                            cart.delete()
                            del request.session['cart_id']
                            logger.info(f"Cart cleared after successful payment for order {order.id}")
                        except Cart.DoesNotExist:
                            logger.warning(f"Cart {request.session.get('cart_id')} not found")
                        except Exception as e:
                            logger.error(f"Error clearing cart: {str(e)}", exc_info=True)
                
                elif payment_request.status == 'cancelled':
                    # Payment was cancelled by user
                    order.status = 'cancelled'
                    order.payment_status = 'cancelled'
                    order.save()
                    logger.info(f"Order {order.id} marked as cancelled")
                
                elif payment_request.status == 'failed':
                    # Payment failed
                    order.status = 'payment_failed'
                    order.save()
                    logger.info(f"Order {order.id} marked as payment failed")
            
            return JsonResponse({
                'status': 'success', 
                'message': 'Callback processed successfully',
                'payment_status': payment_request.status
            })
            
        except PaymentRequest.DoesNotExist:
            logger.warning(f"Payment request not found for checkout_request_id: {checkout_request_id}")
            return JsonResponse(
                {'status': 'error', 'message': 'Payment request not found'}, 
                status=404
            )
        
    except Exception as e:
        logger.error(f"Error processing M-Pesa callback: {str(e)}", exc_info=True)
        return JsonResponse(
            {'status': 'error', 'message': 'Internal server error'}, 
            status=500
        )


@require_http_methods(["GET"])
def check_payment_status(request, checkout_request_id):
    """Check the payment status of a payment request by checkout_request_id."""
    logger = logging.getLogger(__name__)
    try:
        # Find the payment request by checkout_request_id
        payment_request = get_object_or_404(PaymentRequest, checkout_request_id=checkout_request_id)
        logger.info(f"Found payment request: {payment_request.id}, status: {payment_request.status}")
        
        # Get the associated order if it exists
        order = payment_request.order if hasattr(payment_request, 'order') else None
        order_id = order.id if order else None
        
        if payment_request:
            logger.info(f"Found payment request for order {order_id}: {payment_request.id}, status: {payment_request.status}")
            
            # Map payment request status to payment info
            if payment_request.status == 'completed':
                payment_info = {
                    'status': 'completed',
                    'is_successful': True,
                    'transaction_id': payment_request.checkout_request_id,
                    'mpesa_receipt': payment_request.mpesa_receipt_number,
                    'phone_number': payment_request.phone_number,
                    'amount': str(payment_request.amount),
                    'created_at': payment_request.updated_at.isoformat(),
                    'age_seconds': (timezone.now() - payment_request.updated_at).total_seconds(),
                    'order_status': order.status if order else 'unknown',
                    'redirect_url': reverse('home:order_detail', kwargs={'order_id': order_id}) if order_id else None
                }
            elif payment_request.status in ['cancelled', 'failed']:
                # Get result details from callback_data JSONField
                callback_data = payment_request.callback_data or {}
                result_desc = callback_data.get('Body', {}).get('stkCallback', {}).get('ResultDesc', '')
                result_code = callback_data.get('Body', {}).get('stkCallback', {}).get('ResultCode', '')
                
                payment_info = {
                    'status': payment_request.status,
                    'is_successful': False,
                    'transaction_id': payment_request.checkout_request_id,
                    'created_at': payment_request.updated_at.isoformat(),
                    'age_seconds': (timezone.now() - payment_request.updated_at).total_seconds(),
                    'is_user_cancelled': payment_request.status == 'cancelled',
                    'is_timeout': 'timeout' in (result_desc or '').lower(),
                    'is_insufficient_funds': 'insufficient' in (result_desc or '').lower(),
                    'code': result_code,
                    'message': result_desc or 'Payment failed',
                    'order_status': order.status if order else 'unknown',
                    'redirect_url': reverse('home:order_detail', kwargs={'order_id': order_id}) if order_id else None
                }
            else:  # pending
                payment_info = {
                    'status': 'pending',
                    'is_successful': False,
                    'transaction_id': payment_request.checkout_request_id,
                    'created_at': payment_request.created_at.isoformat(),
                    'age_seconds': (timezone.now() - payment_request.created_at).total_seconds(),
                    'message': 'Payment processing...',
                    'order_status': order.status if order else 'pending'
                }
        
        # If we have a payment request but no order, try to find the order through the request's order_id
        if not order and hasattr(payment_request, 'order_id') and payment_request.order_id:
            try:
                order = Order.objects.get(id=payment_request.order_id)
                order_id = order.id
            except Order.DoesNotExist:
                logger.warning(f"Order {payment_request.order_id} not found for payment request {payment_request.id}")
        
        # Prepare the response data
        response_data = {
            'order_id': order_id,
            'order_status': payment_info.get('order_status', 'unknown'),
            'payment_status': payment_info.get('status', 'pending'),
            'transaction_id': payment_info.get('transaction_id'),
            'is_pending': payment_info.get('status') == 'pending',
            'is_paid': payment_info.get('status') == 'completed',
            'is_failed': payment_info.get('status') in ['failed', 'cancelled'],
            'payment_info': {
                'status': payment_info.get('status'),
                'created_at': payment_info.get('created_at'),
                'age_seconds': payment_info.get('age_seconds', 0),
                'is_recent': payment_info.get('age_seconds', 0) < 300  # Less than 5 minutes
            },
            'error': None
        }

        # Include error details if available
        if payment_info and payment_info.get('status') in ['failed', 'cancelled']:
            response_data['error'] = {
                'is_user_cancelled': payment_info.get('is_user_cancelled', False),
                'is_timeout': payment_info.get('is_timeout', False),
                'is_insufficient_funds': payment_info.get('is_insufficient_funds', False),
                'description': payment_info.get('message', 'Payment failed'),
                'code': payment_info.get('code')
            }
            
        return JsonResponse(response_data)
        
    except PaymentRequest.DoesNotExist:
        logger.warning(f"Payment request with checkout_request_id {checkout_request_id} not found")
        return JsonResponse(
            {'status': 'not_found', 'message': 'Payment request not found'}, 
            status=404
        )
        
    except Exception as e:
        logger.error(f"Error checking payment status: {str(e)}")
        return JsonResponse({
            'error': 'Failed to check payment status'
        }, status=500)


# ==============================
# Order Confirmation
# ==============================

def confirm_payment(request, order_id):
    """Confirm payment page that shows order details and creates order"""
    logger = logging.getLogger(__name__)
    try:
        # First, check if the order already exists in the database
        try:
            order = Order.objects.get(id=order_id)
            # If order exists, render the confirmation page with existing order data
            context = {
                'order': order,
                'order_items': order.items.all(),
                'total_amount': order.total,
            }
            return render(request, 'home/confirm_payment.html', context)
            
        except Order.DoesNotExist:
            # If order doesn't exist, check session for pending order data
            order_data = request.session.get(f'pending_order_{order_id}')
            if not order_data:
                messages.error(request, "Order not found or has expired.")
                return redirect('home:home')
            
            # Get cart items
            cart_id = order_data.get('cart_id')
            if not cart_id:
                messages.error(request, "Cart not found.")
                return redirect('home:home')
            
            try:
                cart = Cart.objects.get(id=cart_id)
                cart_items = cart.items.select_related('variation__product').all()
            except Cart.DoesNotExist:
                messages.error(request, "Cart not found.")
                return redirect('home:home')
            
            if not cart_items:
                messages.error(request, "Cart is empty.")
                return redirect('home:home')
            
            # Calculate total
            total_amount = sum(item.variation.price * item.quantity for item in cart_items)
            
            # Create the order
            order = Order.objects.create(
                id=order_id,
                user=request.user if request.user.is_authenticated else None,
                session_id=request.session.session_key if not request.user.is_authenticated else None,
                total=total_amount,
                status='pending',
                payment_method='mpesa',
                transaction_id=order_data.get('transaction_id', ''),
            )
            
            # Create order items
            for cart_item in cart_items:
                OrderItem.objects.create(
                    order=order,
                    variation=cart_item.variation,
                    quantity=cart_item.quantity,
                    price=cart_item.variation.price
                )
            
            # Clear the cart and session data
            cart.delete()
            request.session.pop(f'pending_order_{order_id}', None)
            
            messages.success(request, "Order created successfully!")
            
            context = {
                'order': order,
                'order_items': order.items.all(),
                'total_amount': total_amount,
            }
        
        return render(request, 'home/confirm_payment.html', context)
        
    except Exception as e:
        logger.error(f"Error in confirm_payment: {str(e)}")
        messages.error(request, "An error occurred. Please try again.")
        return redirect('home:home')

# ==============================
# Checkout
# ==============================

@login_required
def checkout(request):
    """Display the checkout page with order summary and shipping/payment forms"""
    cart = _get_or_create_cart(request)
    cart_items = cart.items.select_related('variation__product').all()
    
    if not cart_items.exists():
        messages.warning(request, _("Your cart is empty. Please add items to your cart before checking out."))
        return redirect('home:cart_detail')
    
    # Calculate cart totals
    subtotal = sum(float(item.subtotal()) for item in cart_items)
    # For now, we'll use a flat shipping rate and tax rate
    # You can replace these with your actual shipping and tax calculation logic
    shipping_cost = 5.00  # Example flat rate shipping
    tax_rate = 0.16  # Example 16% tax rate
    tax = round(subtotal * tax_rate, 2)
    total = subtotal + shipping_cost + tax
    
    context = {
        'cart_items': cart_items,
        'subtotal': subtotal,
        'shipping_cost': shipping_cost,
        'tax': tax,
        'total': total,
    }
    
    return render(request, 'home/checkout.html', context)

# ==============================
# Order History
# ==============================

class AgentListView(ListView):
    model = Agent
    template_name = 'home/agent_list.html'
    context_object_name = 'agents'
    paginate_by = 12
    
    def get_queryset(self):
        queryset = Agent.objects.filter(is_verified=True).select_related('owner').prefetch_related('service_types')
        
        # Handle search
        search_form = AgentSearchForm(self.request.GET or None)
        if search_form.is_valid():
            query = search_form.cleaned_data.get('query')
            service_type = search_form.cleaned_data.get('service_type')
            location = search_form.cleaned_data.get('location')
            
            if query:
                queryset = queryset.filter(
                    Q(name__icontains=query) |
                    Q(description__icontains=query) |
                    Q(city__icontains=query) |
                    Q(country__icontains(query))
                )
            
            if service_type:
                queryset = queryset.filter(service_types=service_type)
                
            if location:
                queryset = queryset.filter(
                    Q(city__icontains=location) |
                    Q(country__icontains(location))
                )
        
        return queryset.order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_form'] = AgentSearchForm(self.request.GET or None)
        context['service_categories'] = ServiceCategory.objects.all()
        return context


def order_history(request):
    """Display a user's order history and order requests"""
    if not request.user.is_authenticated:
        messages.warning(request, 'Please log in to view your order history.')
        return redirect('account_login')
    
    # Get user's orders and order requests, ordered by most recent first
    orders = Order.objects.filter(user=request.user).order_by('-created_at')
    order_requests = OrderRequest.objects.filter(
        user=request.user
    ).order_by('-created_at')
    
    context = {
        'orders': orders,
        'order_requests': order_requests,
        'title': 'My Orders & Requests'
    }
    return render(request, 'home/order_history.html', context)


# ==============================
# Order Detail
# ==============================

@csrf_exempt
def order_detail(request, order_id):
    """Display a single Order and its items. Also handles M-Pesa callbacks."""
    logger = logging.getLogger(__name__)
    order = get_object_or_404(Order.objects.prefetch_related('items__variation__product'), id=order_id)
    
    # Handle M-Pesa callback if this is a POST request
    if request.method == 'POST':
        logger.info(f"M-Pesa callback POST received for order {order_id}")
        print(f"DEBUG: M-Pesa callback POST received for order {order_id}")
        try:
            # Parse M-Pesa callback data
            callback_data = json.loads(request.body)
            logger.info(f"M-Pesa callback received for order {order_id}: {callback_data}")
            print(f"DEBUG: M-Pesa callback data: {callback_data}")
            
            # Extract payment information from callback
            callback_body = callback_data.get('Body', {})
            stk_callback = callback_body.get('stkCallback', {})
            result_code = stk_callback.get('ResultCode', 0)
            result_desc = stk_callback.get('ResultDesc', '')
            
            # Check if this is a user cancellation (ResultCode 1032)
            is_user_cancellation = (result_code == 1032 or 'cancelled' in result_desc.lower())
            
            if result_code == 0:
                # Payment successful
                callback_metadata = stk_callback.get('CallbackMetadata', {}).get('Item', [])
                
                # Extract payment details
                payment_data = {}
                for item in callback_metadata:
                    if item.get('Name') == 'Amount':
                        payment_data['amount'] = item.get('Value')
                    elif item.get('Name') == 'MpesaReceiptNumber':
                        payment_data['mpesa_receipt'] = item.get('Value')
                    elif item.get('Name') == 'PhoneNumber':
                        payment_data['phone_number'] = item.get('Value')
                    elif item.get('Name') == 'TransactionDate':
                        payment_data['transaction_date'] = item.get('Value')
                
                # Only update order status for successful payments
                if order.status != 'paid':  # Only update if not already paid
                    order.status = 'paid'
                    order.payment_method = 'mpesa'
                    order.save()
                
                # Only create/update RawPayment record for successful payments
                raw_payment = RawPayment.objects.filter(product_id=str(order_id)).first()
                if raw_payment:
                    # Update existing record
                    raw_payment.status = 'success'
                    raw_payment.transaction_id = payment_data.get('mpesa_receipt', '')
                    raw_payment.mpesa_receipt = payment_data.get('mpesa_receipt', '')
                    raw_payment.phone_number = payment_data.get('phone_number', '')
                    raw_payment.amount = payment_data.get('amount', 0)
                    raw_payment.save()
                else:
                    # Create new record only for successful payments
                    RawPayment.objects.create(
                        product_id=str(order_id),
                        status='success',
                        transaction_id=payment_data.get('mpesa_receipt', ''),
                        mpesa_receipt=payment_data.get('mpesa_receipt', ''),
                        phone_number=payment_data.get('phone_number', ''),
                        amount=payment_data.get('amount', 0),
                    )
                
                logger.info(f"Order {order_id} payment processed successfully")
                
                # Set session variable to indicate callback was processed successfully
                request.session[f'callback_processed_{order_id}'] = {
                    'status': 'success',
                    'message': 'Payment successful',
                    'timestamp': timezone.now().isoformat()
                }
                
            else:
                # Payment failed or was cancelled - determine failure type
                is_timeout = 'timeout' in result_desc.lower() or result_code in [1037, 2001]
                is_insufficient_funds = 'insufficient' in result_desc.lower() or result_code in [1, 1001]
                
                # Determine failure type
                if is_user_cancellation:
                    failure_type = "cancelled"
                elif is_timeout:
                    failure_type = "timeout"
                elif is_insufficient_funds:
                    failure_type = "insufficient_funds"
                else:
                    failure_type = "failed"
                
                logger.warning(f"Payment for order {order_id} {failure_type} with code {result_code}: {result_desc}")
                
                # Set session variable to indicate callback was processed
                request.session[f'callback_processed_{order_id}'] = {
                    'status': 'failed',
                    'failure_type': failure_type,
                    'message': result_desc,
                    'timestamp': timezone.now().isoformat()
                }
                
                # Return failure response with details for frontend processing
                return JsonResponse({
                    'ResultCode': 1, 
                    'ResultDesc': 'Failed',
                    'failure_type': failure_type,
                    'is_user_cancelled': is_user_cancellation,
                    'is_timeout': is_timeout,
                    'is_insufficient_funds': is_insufficient_funds,
                    'message': result_desc,
                    'order_id': order_id
                })
            
            # Return success response to M-Pesa for successful payments
            return JsonResponse({'ResultCode': 0, 'ResultDesc': 'Success'}) 
            
        except Exception as e: 
            logger.error(f"Error processing M-Pesa callback for order {order_id}: {str(e)}")
            return JsonResponse({'ResultCode': 1, 'ResultDesc': 'Failed'}, status=500)
    
    # Get payment information from Payment and RawPayment
    payment_info = None
    completed_payments = []
    try:
        # Get all payment records for this order, most recent first
        payment_records = Payment.objects.filter(order_id=order).select_related('raw_payment').order_by('-created_at')
        
        # Get the most recent payment for the main payment info
        payment_record = payment_records.first()
        
        if payment_record and payment_record.raw_payment:
            raw_payment = payment_record.raw_payment
            payment_info = {
                'status': 'completed',
                'transaction_id': raw_payment.transaction_id,
                'mpesa_receipt': raw_payment.mpesa_receipt,
                'phone_number': raw_payment.phone_number,
                'card_last4': raw_payment.card_last4,
                'card_brand': raw_payment.card_brand,
                'amount': str(raw_payment.amount),
                'created_at': raw_payment.created_at,
                'is_successful': True,
                'payment_method': order.payment_method  # Include payment method from order
            }
            
            # Get all completed payments for this order
            for record in payment_records.filter(raw_payment__isnull=False):
                if record.raw_payment:
                    completed_payments.append({
                        'transaction_id': record.raw_payment.transaction_id,
                        'mpesa_receipt': record.raw_payment.mpesa_receipt,
                        'phone_number': record.raw_payment.phone_number,
                        'amount': str(record.raw_payment.amount),
                        'created_at': record.raw_payment.created_at,
                        'payment_method': record.payment_method or 'M-Pesa',
                        'is_successful': record.status == 'completed'
                    })
        else:
            # No successful payment found
            payment_info = {
                'status': 'pending' if order.status == 'pending' else 'failed',
                'transaction_id': None,
                'mpesa_receipt': None,
                'phone_number': None,
                'card_last4': None,
                'card_brand': None,
                'amount': str(order.total),
                'created_at': order.created_at,
                'is_successful': False,
                'payment_method': order.payment_method  # Include payment method from order
            }
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"Error fetching payment info: {str(e)}")
        payment_info = {
            'status': 'error',
            'error': str(e),
            'is_successful': False
        }
    
    # Get additional fees for this order
    additional_fees = OrderAdditionalFees.objects.filter(order=order)
    
    # Get all completed payment requests for this order
    completed_payment_requests = PaymentRequest.objects.filter(
        order=order,
        status='completed'
    ).order_by('-created_at')
    
    return render(request, 'home/order_detail.html', {
        'order': order,
        'items': order.items.all(),
        'payment_info': payment_info,
        'completed_payments': completed_payments,
        'additional_fees': additional_fees,
        'completed_payment_requests': completed_payment_requests,
    })


def order_request_detail(request, order_request_id):
    """Display an OrderRequest and its items including proposed deposit percentages."""
    order_request = get_object_or_404(
        OrderRequest.objects.select_related('user').prefetch_related(
            'items__variation__product',
            'items__variation__images',
            'items__variation__i_rates',
        ),
        id=order_request_id
    )

    items = list(order_request.items.all())

    from decimal import Decimal, ROUND_HALF_UP

    def to_decimal(value):
        try:
            if callable(value):
                value = value()
            if value is None:
                return Decimal('0')
            return Decimal(str(value))
        except Exception:
            return Decimal('0')

    total_quantity = 0
    total_amount = Decimal('0')
    total_proposed_deposit = Decimal('0')
    amount_payable_now = Decimal('0')
    amount_payable_later = Decimal('0')

    for item in items:
        qty_raw = getattr(item, 'quantity', 0)
        qty = int(qty_raw or 0)

        subtotal_raw = getattr(item, 'subtotal', 0)
        subtotal = to_decimal(subtotal_raw)

        deposit_pct_raw = getattr(item, 'deposit_percentage', 0)
        percentage = to_decimal(deposit_pct_raw)

        total_quantity += qty
        total_amount += subtotal

        # Proposed deposit total (for display)
        proposed_deposit_amount = (subtotal * percentage / Decimal('100')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        total_proposed_deposit += proposed_deposit_amount

        if percentage > 0:
            # Find interest rate from IRate table for this percentage
            interest_rate = Decimal('0')
            try:
                i_rates = item.variation.i_rates.all().order_by('lower_range')
                for i_rate in i_rates:
                    lower = to_decimal(i_rate.lower_range)
                    upper = to_decimal(i_rate.upper_range)
                    if lower <= percentage <= upper:
                        interest_rate = to_decimal(i_rate.rate)
                        break
            except Exception:
                interest_rate = Decimal('0')

            pay_now_item = proposed_deposit_amount
            remaining_amount = subtotal - pay_now_item
            interest_amount = (remaining_amount * interest_rate / Decimal('100')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            pay_later_item = remaining_amount + interest_amount

            amount_payable_now += pay_now_item
            amount_payable_later += pay_later_item
        else:
            # No deposit plan: full amount payable now
            amount_payable_now += subtotal
            # Later remains zero for this line

    context = {
        'order_request': order_request,
        'items': items,
        'total_quantity': total_quantity,
        'total_amount': total_amount,
        'total_proposed_deposit': total_proposed_deposit,
        'amount_payable_now': amount_payable_now,
        'amount_payable_later': amount_payable_later,
    }
    return render(request, 'home/order_request_detail.html', context)

# ==============================
# Wishlist
# ==============================

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

@require_http_methods(["POST"])
def process_mpesa_payment_for_order_request(request, order_request_id):
    """Initiate M-Pesa STK push for an accepted OrderRequest using payable-now amount (includes deposits + full non-deposit items), with IRate interest applied to pay-later only."""
    logger = logging.getLogger(__name__)
    try:
        body = json.loads(request.body or '{}')
        print(body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid request data'}, status=400)

    phone_number = (body.get('phone_number') or '').strip()
    if not phone_number:
        return JsonResponse({'error': 'Phone number is required'}, status=400)

    # Normalize phone
    phone = str(phone_number)
    if phone.startswith('0'):
        phone = f'254{phone[1:]}'
    elif not phone.startswith('254'):
        phone = f'254{phone}'

    try:
        order_request = get_object_or_404(
            OrderRequest.objects.select_related('user').prefetch_related(
                'items__variation__product',
                'items__variation__i_rates',
            ),
            id=order_request_id
        )
        if getattr(order_request, 'status', '') != 'accepted':
            return JsonResponse({'error': 'This order request is not accepted yet.'}, status=400)

        from decimal import Decimal, ROUND_HALF_UP

        def to_decimal(value):
            try:
                if callable(value):
                    value = value()
                if value is None:
                    return Decimal('0')
                return Decimal(str(value))
            except Exception:
                return Decimal('0')

        amount_payable_now = Decimal('0')

        for item in order_request.items.all():
            subtotal = to_decimal(getattr(item, 'subtotal', 0))
            percentage = to_decimal(getattr(item, 'deposit_percentage', 0))

            if percentage > 0:
                pay_now_item = (subtotal * percentage / Decimal('100')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                amount_payable_now += pay_now_item
            else:
                amount_payable_now += subtotal

        if amount_payable_now <= 0:
            return JsonResponse({'error': 'Nothing to pay right now.'}, status=400)

        # Initiate STK push via MPesaService
        try:
            from core.mpesa_service import MPesaService
            mpesa = MPesaService()
        except Exception as e:
            logger.error(f'Failed to init MPesaService: {e}')
            return JsonResponse({'error': 'Payment service unavailable. Try again later.'}, status=503)

        try:
            response = mpesa.initiate_stk_push(
                phone_number=phone,
                amount=amount_payable_now,
                account_reference=f'OR-{order_request_id}',
                request=request,
                order_id=order_request_id,
                description=f'OrderRequest {order_request_id} payment'
            )
            # Normalize response to dict-like
            resp_dict = {}
            if isinstance(response, dict):
                resp_dict = response
            else:
                # Try to map common attributes
                for attr in ('error', 'error_code', 'MerchantRequestID', 'CheckoutRequestID', 'ResponseCode', 'ResponseDescription'):
                    if hasattr(response, attr):
                        resp_dict[attr] = getattr(response, attr)
                # Fallback: mark success if not explicitly error
                if not resp_dict:
                    resp_dict = {'raw': str(response)}

            # If explicit error key -> fail
            if 'error' in resp_dict and resp_dict.get('error'):
                err_msg = resp_dict.get('error') or 'Payment initiation failed'
                err_code = resp_dict.get('error_code') or resp_dict.get('ResponseCode') or 'UNKNOWN'
                return JsonResponse({'error': f'{err_msg}', 'error_code': err_code}, status=400)

            # Otherwise treat as success (STK prompt delivered)
            return JsonResponse({
                'success': True,
                'message': 'STK push sent. Check your phone.',
                'checkout_request_id': resp_dict.get('CheckoutRequestID'),
                'merchant_request_id': resp_dict.get('MerchantRequestID'),
            })
        except Exception as e:
            logger.error(f'STK push failed: {e}', exc_info=True)
            return JsonResponse({'error': 'Failed to initiate payment. Please try again.'}, status=500)
    except:
        pass


@require_http_methods(["POST"])
def process_card_payment(request):
    """Process card payment for an order."""
    logger = logging.getLogger(__name__)
    logger.info("Received card payment request")
    
    try:
        # Parse request data
        try:
            data = json.loads(request.body)
            card_number = data.get('card_number')
            expiry_date = data.get('expiry_date')
            cvv = data.get('cvv')
            cardholder_name = data.get('cardholder_name')
            order_id = data.get('order_id')
            logger.info(f"Card payment request for order: {order_id}")
        except json.JSONDecodeError:
            logger.error("Invalid JSON data received")
            return JsonResponse({'error': 'Invalid request data. Please try again.'}, status=400)
        
        # Validate required fields
        if not all([card_number, expiry_date, cvv, cardholder_name, order_id]):
            return JsonResponse({'error': 'All card details are required'}, status=400)
        
        # Get the order
        try:
            order = get_object_or_404(Order, id=order_id)
        except Order.DoesNotExist:
            return JsonResponse({'error': 'Order not found'}, status=404)
        
        # Basic card validation
        card_number_clean = card_number.replace(' ', '').replace('-', '')
        if not card_number_clean.isdigit() or len(card_number_clean) < 13 or len(card_number_clean) > 19:
            return JsonResponse({'error': 'Invalid card number'}, status=400)
        
        # Validate expiry date format
        if not re.match(r'^(0[1-9]|1[0-2])\/\d{2}$', expiry_date):
            return JsonResponse({'error': 'Invalid expiry date format'}, status=400)
        
        # Validate CVV
        if not re.match(r'^\d{3,4}$', cvv):
            return JsonResponse({'error': 'Invalid CVV'}, status=400)
        
        # For demo purposes, we'll simulate a successful payment
        # In a real implementation, you would integrate with a payment processor like Stripe, PayPal, etc.
        
        # Generate a mock transaction ID
        import time
        transaction_id = f"CARD_{int(time.time())}_{order_id}"
        
        # Create RawPayment record
        raw_payment = RawPayment.objects.create(
            product_id=str(order_id),
            payment_method='card',
            amount=order.total,
            currency='KES',
            status='completed',
            transaction_id=transaction_id,
            card_last4=card_number[-4:],
            card_brand='Visa'  # Mock brand
        )
        
        # Update order with payment information
        order.payment_method = 'card'
        order.status = 'paid'
        order.transaction_id = transaction_id
        order.save()
        
        logger.info(f"Card payment processed successfully for order {order_id}")
        
        return JsonResponse({
            'success': True,
            'message': 'Card payment processed successfully!',
            'transaction_id': transaction_id,
            'redirect_url': f'/orders/{order_id}/'
        })
        
    except Exception as e:
        logger.exception("Unexpected error processing card payment")
        return JsonResponse({
            'error': 'An unexpected error occurred. Our team has been notified.',
            'debug_info': str(e)
        }, status=500)