import json
import logging
import time
from decimal import Decimal, ROUND_HALF_UP

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q, Min, Max, Count, Avg
from django.views.generic import ListView
from django.core.paginator import Paginator

from .models import Agent, ServiceCategory, ProductServicing
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
    WishlistItem, ProductOrder, Payment, OrderRequest, OrderRequestItem, AdditionalFees
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
            order_id__product__in=product.variations.all()
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
    related_orders = OrderItem.objects.filter(
        variation__product=product
    ).select_related('order', 'variation').order_by('-order__created_at')
    
    # Get unique order requests with their items for this product
    from django.db.models import Prefetch
    from django.db.models.functions import Coalesce
    
    # First, get the order requests that have items for this product
    order_requests = OrderRequest.objects.filter(
        items__variation__product=product
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
        logger = logging.getLogger(__name__)
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
            logger.info(f"Payment request for phone: {phone_number}")
            logger.info(f"Payment plans: {payment_plans}")
        except json.JSONDecodeError:
            logger.error("Invalid JSON data received")
            return JsonResponse({'error': 'Invalid request data. Please try again.'}, status=400)
        
        # Validate phone number
        if not phone_number or not str(phone_number).strip():
            logger.error("No phone number provided")
            return JsonResponse({'error': 'Phone number is required'}, status=400)
            
        # Get cart for the current user/session
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
        
        # Calculate total amount based on payment plans with interest rates
        total_amount = Decimal('0')
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
        
        # Initiate STK push
        logger.info(f"Initiating STK push for {phone}, amount: {total_amount}")
        response = mpesa.initiate_stk_push(
            phone_number=phone,
            amount=total_amount,
            account_reference=order_ref,
            description=f"Order {order_ref}"
        )
        
        # Handle M-Pesa response
        if 'error' in response:
            error_code = response.get('error_code', 'UNKNOWN')
            error_msg = response.get('error', 'Payment request failed')
            
            # Log the error with details
            logger.error(f"STK push failed: {error_msg} (Code: {error_code})")
            
            # User-friendly error messages based on error code
            if '500.001.1001' in str(error_code) or 'AUTH_ERROR' in str(error_code):
                user_message = "Payment service is not configured. Please contact support."
            elif 'credentials' in error_msg.lower() or 'configured' in error_msg.lower():
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
                'debug_info': 'Please check server logs for more details.'
            }, status=400)
        
        # Success - log and return success response
        logger.info(f"STK push initiated successfully. Response: {json.dumps(response)}")
        
        # Store order data in session for confirmation page
        order_id = int(time.time())  # Generate unique order ID
        request.session[f'pending_order_{order_id}'] = {
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
            'order_id': order_id,
            'redirect_url': f'/confirm-payment/{order_id}/',
            'data': response
        })
        
    except Exception as e:
        logger.exception("Unexpected error processing M-Pesa payment")
        return JsonResponse({
            'error': 'An unexpected error occurred. Our team has been notified.',
            'debug_info': str(e)
        }, status=500)


# ==============================
# Order Confirmation
# ==============================

def confirm_payment(request, order_id):
    """Confirm payment page that shows order details and creates order"""
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
    """Display a user's order history"""
    if not request.user.is_authenticated:
        messages.warning(request, 'Please log in to view your order history.')
        return redirect('account_login')
    
    # Get user's orders, ordered by most recent first
    orders = Order.objects.filter(user=request.user).order_by('-created_at')
    
    context = {
        'orders': orders,
        'title': 'My Orders'
    }
    return render(request, 'home/order_history.html', context)


# ==============================
# Order Detail
# ==============================

def order_detail(request, order_id):
    """Display a single Order and its items."""
    order = get_object_or_404(Order.objects.prefetch_related('items__variation__product'), id=order_id)
    return render(request, 'home/order_detail.html', {
        'order': order,
        'items': order.items.all(),
    })


def order_request_detail(request, order_request_id):
    """Display an OrderRequest and its items including proposed deposit percentages."""
    order_request = get_object_or_404(
        OrderRequest.objects.select_related('user').prefetch_related('items__variation__product'),
        id=order_request_id
    )
    return render(request, 'home/order_request_detail.html', {
        'order_request': order_request,
        'items': order_request.items.all(),
    })

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
