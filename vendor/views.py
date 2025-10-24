import logging
from django.shortcuts import render, get_object_or_404, redirect
from django.http import Http404, JsonResponse
from django.urls import reverse

logger = logging.getLogger(__name__)
from django.contrib.auth.decorators import login_required
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Count, Sum, F
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.views.decorators.csrf import csrf_exempt

from home.models import (
    Product, ProductCategory, Business, ProductImage, 
    BusinessCategory, ProductVariation, OrderItem, CartItem,
    ProductAttributeAssignment, ProductAttribute, 
    ProductAttributeValue, PriceTier, PromiseFee, 
    IRate, ProductServicing, Agent, OrderRequest, OrderRequestItem, AdditionalFees,
    BuyerSellerChat, Order, ProductCategoryFilter
)
from .forms import (
    ProductForm,
    ProductImageForm,
    ProductSearchForm,
    BusinessForm,
    ProductVariationForm,
    ProductVariationImageForm,
    ProductAttributeAssignmentForm,
    PriceTierForm,
    PromiseFeeForm,
    ProductKBForm,
    IRateForm,
    ChatOrderForm,
)
from django.forms import inlineformset_factory
from django.forms import modelformset_factory
from django.views.decorators.http import require_http_methods


@login_required
def vendor_dashboard(request):
    """Vendor dashboard showing overview of products and sales"""
    # Get products from businesses owned by the current user
    user_businesses = Business.objects.filter(owner=request.user)
    products = Product.objects.filter(
        Q(business__in=user_businesses) | Q(user=request.user)
    )
    
    # Get statistics
    total_products = products.count()
    total_businesses = user_businesses.count()
    
    # Recent products
    recent_products = products.order_by('-created_at')[:5]
    
    context = {
        'total_products': total_products,
        'total_businesses': total_businesses,
        'recent_products': recent_products,
        'user_businesses': user_businesses,
    }
    
    return render(request, 'vendor/dashboard.html', context)


@login_required
def product_list(request):
    """List all products for the current vendor"""
    from django.db.models import Min, Max, Prefetch
    from home.models import Product, ProductVariation, Business
    
    search_form = ProductSearchForm(request.GET)
    user_businesses = Business.objects.filter(owner=request.user)
    
    # Only show non-archived products and their non-archived variations with price tiers
    products = Product.objects.filter(
        (Q(business__in=user_businesses) | Q(user=request.user)) &
        Q(is_archived=False)
    ).prefetch_related(
        'images',
        'categories',
        Prefetch(
            'variations',
            queryset=ProductVariation.objects.filter(is_archived=False).prefetch_related(
                Prefetch(
                    'price_tiers',
                    queryset=PriceTier.objects.all(),
                    to_attr='price_tiers_list'
                )
            ),
            to_attr='active_variations'
        )
    )
    
    # No need to set variations attribute as we'll use active_variations in the template
    
    if search_form.is_valid():
        search = search_form.cleaned_data.get('search')
        category = search_form.cleaned_data.get('category')
        # price filters removed (no price field)
        
        if search:
            products = products.filter(
                Q(name__icontains=search) |
                Q(description__icontains=search)
            )
        
        if category:
            products = products.filter(categories=category)
        
        # no price filtering
    
    # Add price information to each product
    for product in products:
        prices = []
        
        if hasattr(product, 'active_variations') and product.active_variations:
            for variation in product.active_variations:
                # Get direct price from variation if it exists
                if variation.price is not None:
                    prices.append(variation.price)
                
                # Get prices from price tiers if they exist
                if hasattr(variation, 'price_tiers_list') and variation.price_tiers_list:
                    tier_prices = [tier.price for tier in variation.price_tiers_list if tier.price is not None]
                    prices.extend(tier_prices)
        
        # Set price range if we found any prices
        if prices:
            product.min_price = min(prices)
            product.max_price = max(prices) if len(prices) > 1 else product.min_price
            product.has_pricing = True
        else:
            product.min_price = None
            product.max_price = None
            product.has_pricing = False
    
    # Pagination
    paginator = Paginator(products, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'search_form': search_form,
    }
    
    return render(request, 'vendor/product_list.html', context)


@login_required
def add_product(request):
    """Add a new product"""
    if request.method == 'POST':
        form = ProductForm(request.POST, user=request.user)
        
        if form.is_valid():
            product = form.save()
            messages.success(request, 'Product added successfully!')
            return redirect('vendor:product_detail', pk=product.id)
    else:
        form = ProductForm(user=request.user)
    
    context = {
        'form': form,
    }
    
    return render(request, 'vendor/add_product.html', context)


@login_required
def product_detail(request, pk):
    """View product details"""
    # Only get non-archived products
    product = get_object_or_404(Product, id=pk, is_archived=False)
    
    # Ensure the product belongs to a business owned by the current user OR was created by the current user
    if product.business and product.business.owner == request.user:
        pass  # Allowed via business ownership
    elif product.user and product.user == request.user:
        pass  # Allowed via direct user ownership
    else:
        messages.error(request, 'You do not have permission to view this product.')
        return redirect('vendor:product_list')
    
    # Get non-archived images and variations
    images = ProductImage.objects.filter(product=product)
    variations = ProductVariation.objects.filter(product=product, is_archived=False)
    
    
    # Get or create ProductServicing for this product
    product_servicing, created = ProductServicing.objects.get_or_create(product=product)
    
    # Handle form submission
    if request.method == 'POST' and 'update_servicing' in request.POST:
        shipping_id = request.POST.get('shipping')
        sourcing_id = request.POST.get('sourcing')
        customs_id = request.POST.get('customs')
        
        try:
            # Only update the fields if the agent provides the required service
            if shipping_id:
                shipping_agent = Agent.objects.get(id=shipping_id)
                if shipping_agent.service_types.filter(code='SH-2').exists():
                    product_servicing.shipping = shipping_agent
                else:
                    messages.error(request, 'The selected agent does not provide shipping services.')
                    return redirect('vendor:product_detail', pk=product.id)
            else:
                product_servicing.shipping = None
                
            if sourcing_id:
                sourcing_agent = Agent.objects.get(id=sourcing_id)
                if sourcing_agent.service_types.filter(code='s-1').exists():
                    product_servicing.sourcing = sourcing_agent
                else:
                    messages.error(request, 'The selected agent does not provide sourcing services.')
                    return redirect('vendor:product_detail', pk=product.id)
            else:
                product_servicing.sourcing = None
                
            if customs_id:
                customs_agent = Agent.objects.get(id=customs_id)
                if customs_agent.service_types.filter(code='C-1').exists():
                    product_servicing.customs = customs_agent
                else:
                    messages.error(request, 'The selected agent does not provide customs services.')
                    return redirect('vendor:product_detail', pk=product.id)
            else:
                product_servicing.customs = None
                
            product_servicing.save()
            messages.success(request, 'Product servicing information updated successfully.')
            return redirect('vendor:product_detail', pk=product.id)
            
        except Agent.DoesNotExist:
            messages.error(request, 'One or more selected agents were not found or do not provide the required service.')
    
    # Get available agents for each service type
    # Using the code field to filter agents by their service types
    # Note: Using the actual codes from the database
    shipping_agents = Agent.objects.filter(service_types__code='SH-2').distinct()
    sourcing_agents = Agent.objects.filter(service_types__code='s-1').distinct()
    customs_agents = Agent.objects.filter(service_types__code='C-1').distinct()
    
    # Handle Additional Fees
    existing_fees = AdditionalFees.objects.filter(variation__in=variations).distinct()
    
    if request.method == 'POST' and 'add_fee' in request.POST:
        # Add new fee
        name = request.POST.get('fee_name', '').strip()
        description = request.POST.get('fee_description', '').strip()
        price_raw = request.POST.get('fee_price', '')
        is_required = request.POST.get('fee_required') == 'on'
        variation_ids = request.POST.getlist('fee_variations')
        
        try:
            from decimal import Decimal, InvalidOperation
            price = Decimal(str(price_raw)) if price_raw else Decimal('0')
        except (InvalidOperation, ValueError, TypeError):
            messages.error(request, 'Invalid price value.')
            return redirect('vendor:product_detail', pk=product.id)
        
        if name and price > 0:
            fee = AdditionalFees.objects.create(
                name=name,
                description=description,
                is_required=is_required,
                price=price
            )
            
            # Set variations
            try:
                variation_ids = [int(v) for v in variation_ids if v]
                v_qs = ProductVariation.objects.filter(id__in=variation_ids)
                fee.variation.set(v_qs)
            except Exception:
                pass
            
            messages.success(request, 'Additional fee added successfully!')
        else:
            messages.error(request, 'Name and price are required.')
        
        return redirect('vendor:product_detail', pk=product.id)
    
    if request.method == 'POST' and 'delete_fee' in request.POST:
        # Delete fee
        fee_id = request.POST.get('fee_id')
        try:
            fee = AdditionalFees.objects.get(id=fee_id)
            fee.delete()
            messages.success(request, 'Additional fee deleted successfully!')
        except AdditionalFees.DoesNotExist:
            messages.error(request, 'Fee not found.')
        return redirect('vendor:product_detail', pk=product.id)
    
    context = {
        'product': product,
        'images': images,
        'variations': variations,
        'product_servicing': product_servicing,
        'shipping_agents': shipping_agents,
        'sourcing_agents': sourcing_agents,
        'customs_agents': customs_agents,
        'existing_fees': existing_fees,
    }
    
    return render(request, 'vendor/product_detail.html', context)


@login_required
def edit_product(request, pk):
    """Edit an existing product"""
    # Only allow editing non-archived products
    product = get_object_or_404(Product, id=pk, is_archived=False)
    
    # Ensure the product belongs to a business owned by the current user OR was created by the current user
    if product.business and product.business.owner == request.user:
        pass  # Allowed via business ownership
    elif product.user and product.user == request.user:
        pass  # Allowed via direct user ownership
    else:
        messages.error(request, 'You do not have permission to edit this product.')
        return redirect('vendor:product_list')
    
    if request.method == 'POST':
        form = ProductForm(request.POST, instance=product, user=request.user)
        
        if form.is_valid():
            product = form.save()
            messages.success(request, 'Product updated successfully!')
            return redirect('vendor:product_detail', pk=product.id)
    else:
        form = ProductForm(instance=product, user=request.user)
    
    context = {
        'product': product,
        'form': form,
    }
    
    return render(request, 'vendor/edit_product.html', context)

@login_required
def order_request_update_status(request, pk):
    """Update the status of an order request via AJAX"""
    from django.http import JsonResponse
    import json
    from django.db import transaction
    from decimal import Decimal
    
    if request.method != 'POST' or not request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'success': False, 'error': 'Invalid request'}, status=400)
    
    try:
        data = json.loads(request.body) if request.body else {}
        new_status = data.get('status')
        
        if not new_status:
            return JsonResponse({'success': False, 'error': 'Status is required'}, status=400)
        
        order_request = get_object_or_404(OrderRequest, pk=pk)
        
        if order_request.status == new_status:
            return JsonResponse({
                'success': True, 
                'message': f'Order request is already {order_request.get_status_display()}'
            })
        # First, check if we can proceed with the update
        if new_status == 'accepted' and hasattr(order_request, 'order') and order_request.order:
            return JsonResponse({
                'success': False,
                'error': 'An order already exists for this request'
            }, status=400)
            
        # Get items before starting the transaction
        items = list(order_request.items.all())
        if new_status == 'accepted' and not items:
            return JsonResponse({
                'success': False,
                'error': 'No items found in the order request'
            }, status=400)
        
        # Calculate total before the transaction
        if new_status == 'accepted':
            from home.models import Order, OrderItem
            total_amount = sum(
                Decimal(str(item.unit_price)) * item.quantity 
                for item in items
            )
        
        # Perform the update in a single transaction
        with transaction.atomic():
            # Update the order request status
            order_request.status = new_status
            order_request.save(update_fields=['status', 'updated_at'])
            
            if new_status == 'accepted':
                # Create the order
                order = Order.objects.create(
                    user=order_request.user,
                    created_by=request.user,
                    status='pending',
                    total=total_amount,
                    order_request=order_request
                )
                
                # Create order items
                order_items = [
                    OrderItem(
                        order=order,
                        variation=item.variation,
                        quantity=item.quantity,
                        price=item.unit_price
                    ) for item in items
                ]
                OrderItem.objects.bulk_create(order_items)
                
                logger.info(f"Created order {order.id} from order request {order_request.id}")
                
                return JsonResponse({
                    'success': True,
                    'message': 'Order request accepted and order created successfully',
                    'order_id': order.id,
                    'order_url': reverse('vendor:order_detail', kwargs={'order_id': order.id})
                })
                
                logger.info(f"Order {order.id} created from order request {order_request.id}")
                
                return JsonResponse({
                    'success': True,
                    'message': 'Order request accepted and order created successfully',
                    'order_id': order.id,
                    'order_url': reverse('vendor:order_detail', kwargs={'order_id': order.id})
                })
        return JsonResponse({
            'success': True,
            'message': f'Order request status updated to {order_request.get_status_display()}'
        })
        
    except Exception as e:
        logger.error(f"Error updating order request status: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': 'An error occurred while updating the order status'
        }, status=500)




@login_required
def toggle_product_active(request, pk):
    """Toggle the active status of a product"""
    from django.shortcuts import get_object_or_404, redirect
    from django.contrib import messages
    from home.models import Product
    
    try:
        product = get_object_or_404(Product, id=pk, is_archived=False)
        
        # Check if the user has permission to modify this product
        has_permission = False
        if hasattr(product, 'business') and product.business and product.business.owner == request.user:
            has_permission = True
        elif hasattr(product, 'user') and product.user == request.user:
            has_permission = True
        
        if not has_permission:
            messages.error(request, 'You do not have permission to modify this product.')
            return redirect('vendor:product_list')
        
        # Toggle the active status
        product.is_active = not product.is_active
        product.save()
        
        status = 'activated' if product.is_active else 'deactivated'
        messages.success(request, f'Product has been {status} successfully.')
        
        return redirect('vendor:product_detail', pk=pk)
        
    except Exception as e:
        messages.error(request, f'Error updating product status: {str(e)}')
        return redirect('vendor:product_detail', pk=pk)

@login_required
def delete_product(request, pk):
    """Archive a product instead of deleting it"""
    from django.shortcuts import get_object_or_404, redirect
    from django.contrib import messages
    from home.models import Product
    
    product = get_object_or_404(Product, id=pk)
    
    # Check if the user has permission to archive this product
    has_permission = False
    if hasattr(product, 'business') and product.business and product.business.owner == request.user:
        has_permission = True
    elif hasattr(product, 'user') and product.user == request.user:
        has_permission = True
    
    if not has_permission:
        messages.error(request, 'You do not have permission to archive this product.')
        return redirect('vendor:product_list')
    
    # Archive the product
    product_name = product.name
    product.is_archived = True
    product.save()
    
    messages.success(request, f'Product "{product_name}" has been archived successfully.')
    return redirect('vendor:product_list')


@login_required
def toggle_variation_active(request, pk):
    """Toggle the active status of a product variation"""
    from django.shortcuts import get_object_or_404, redirect
    from django.contrib import messages
    from home.models import ProductVariation
    
    try:
        variation = get_object_or_404(ProductVariation, id=pk, is_archived=False)
        
        # Check if the user has permission to modify this variation
        has_permission = False
        if hasattr(variation.product, 'business') and variation.product.business and variation.product.business.owner == request.user:
            has_permission = True
        elif hasattr(variation.product, 'user') and variation.product.user == request.user:
            has_permission = True
        
        if not has_permission:
            messages.error(request, 'You do not have permission to modify this variation.')
            return redirect('vendor:variation_detail', pk=pk)
        
        # Toggle the active status
        variation.is_active = not variation.is_active
        variation.save()
        
        status = 'activated' if variation.is_active else 'deactivated'
        messages.success(request, f'Variation has been {status} successfully.')
        
        return redirect('vendor:variation_detail', pk=pk)
        
    except Exception as e:
        messages.error(request, f'Error updating variation status: {str(e)}')
        return redirect('vendor:variation_detail', pk=pk)

@login_required
def archive_variation(request, pk):
    """Archive a product variation"""
    from django.http import JsonResponse
    from home.models import ProductVariation
    
    try:
        variation = ProductVariation.objects.get(id=pk, is_archived=False)
        
        # Check if the user has permission to archive this variation
        has_permission = False
        if hasattr(variation.product, 'business') and variation.product.business and variation.product.business.owner == request.user:
            has_permission = True
        elif hasattr(variation.product, 'user') and variation.product.user == request.user:
            has_permission = True
        
        if not has_permission:
            return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)
        
        # Archive the variation
        variation.is_archived = True
        variation.is_active = False  # Ensure archived items are not active
        variation.save()
        
        return JsonResponse({'success': True})
        
    except ProductVariation.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Variation not found'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
def delete_promise_fee(request, pk):
    """Delete a promise fee"""
    from home.models import PromiseFee
    from django.shortcuts import get_object_or_404, redirect
    from django.contrib import messages
    
    promise_fee = get_object_or_404(PromiseFee, id=pk)
    
    # Check if the user has permission to delete this promise fee
    if request.user != promise_fee.variation.product.business.owner and request.user != promise_fee.variation.product.user:
        messages.error(request, "You don't have permission to delete this promise fee.")
        return redirect('vendor:product_detail', pk=promise_fee.variation.product.id)
    
    if request.method == 'POST':
        product_id = promise_fee.variation.product.id
        promise_fee.delete()
        messages.success(request, "Promise fee deleted successfully.")
        return redirect('vendor:product_detail', pk=product_id)
    
    return render(request, 'vendor/delete_confirm.html', {
        'object': promise_fee,
        'cancel_url': reverse('vendor:product_detail', kwargs={'pk': promise_fee.variation.product.id})
    })


@login_required
def create_order_from_chat(request, chat_id):
    """Create an order from a chat conversation"""
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        logger.info(f"Creating order from chat {chat_id} for user {request.user.id}")
        
        # Get the chat with related objects
        chat = get_object_or_404(
            BuyerSellerChat.objects.select_related('buyer', 'seller', 'product'),
            id=chat_id,
            seller=request.user  # Only the seller can create orders
        )
        
        logger.debug(f"Found chat: {chat.id} with product: {chat.product.id if chat.product else 'None'}")
        
        # Check if the user is the seller in this chat
        if request.user != chat.seller:
            error_msg = "You don't have permission to create an order from this chat."
            logger.warning(f"Permission denied: {error_msg}")
            messages.error(request, error_msg)
            return redirect('home:buyer_seller_chat', chat_id=chat_id)
        
        # Initialize the form with the chat and current user
        if request.method == 'POST':
            logger.debug("Processing POST request")
            form = ChatOrderForm(request.POST, chat=chat, user=request.user)
            
            if form.is_valid():
                logger.debug("Form is valid, attempting to save")
                try:
                    # Pass the current user to the form to set as created_by
                    form._current_user = request.user
                    order = form.save()
                    success_msg = f"Order #{order.id} has been created successfully!"
                    logger.info(success_msg)
                    messages.success(request, success_msg)
                    return redirect('vendor:orders')
                except Exception as e:
                    error_msg = f"An error occurred while creating the order: {str(e)}"
                    logger.error(f"Error creating order: {error_msg}", exc_info=True)
                    messages.error(request, error_msg)
            else:
                logger.warning(f"Form is invalid: {form.errors}")
                messages.error(request, "Please correct the errors below.")
        else:
            logger.debug("Handling GET request")
            form = ChatOrderForm(chat=chat, user=request.user)
        
        # Get the product variations for the selected product (if any)
        variations = []
        if chat.product:
            variations = chat.product.variations.all()
            logger.debug(f"Found {len(variations)} variations for product {chat.product.id}")
        else:
            logger.warning("No product associated with this chat")
        
        context = {
            'form': form,
            'chat': chat,
            'variations': variations,
            'title': 'Create Order from Chat'
        }
        
        return render(request, 'vendor/create_order_from_chat_new.html', context)
        
    except Exception as e:
        error_msg = f"An unexpected error occurred: {str(e)}"
        logger.error(error_msg, exc_info=True)
        messages.error(request, error_msg)
        return redirect('vendor:dashboard')  # Redirect to a safe page


@login_required
def add_product_image(request, pk):
    """Add an image to a product"""
    product = get_object_or_404(Product, id=pk)
    
    # Ensure the product belongs to a business owned by the current user OR was created by the current user
    if product.business and product.business.owner == request.user:
        pass  # Allowed via business ownership
    elif product.user and product.user == request.user:
        pass  # Allowed via direct user ownership
    else:
        messages.error(request, 'You do not have permission to add images to this product.')
        return redirect('vendor:product_list')
    
    if request.method == 'POST':
        form = ProductImageForm(request.POST, request.FILES, product=product)
        
        if form.is_valid():
            try:
                # The form's save method will handle setting the product
                image = form.save()
                
                # If this is set as default, unset other default images
                if image.is_default:
                    ProductImage.objects.filter(product=product).exclude(id=image.id).update(is_default=False)
                
                messages.success(request, 'Image added successfully!')
                return redirect('vendor:product_detail', pk=product.id)
                
            except Exception as e:
                messages.error(request, f'Error saving image: {str(e)}')
        else:
            # Log form errors for debugging
            logger.error(f'Form errors: {form.errors}')
    else:
        form = ProductImageForm(product=product)
    
    context = {
        'product': product,
        'form': form,
    }
    
    return render(request, 'vendor/add_product_image.html', context)


@login_required
def business_list(request):
    """List all businesses for the current vendor"""
    businesses = Business.objects.filter(owner=request.user)
    
    context = {
        'businesses': businesses,
    }
    
    return render(request, 'vendor/business_list.html', context)


@login_required
def add_business(request):
    """Add a new business - only one business per user is allowed"""
    # Check if user already has a business
    existing_business = Business.objects.filter(owner=request.user).first()
    if existing_business:
        messages.info(request, 'You already have a business. You can only have one business per account.')
        return redirect('vendor:edit_business', pk=existing_business.id)
    
    if request.method == 'POST':
        form = BusinessForm(request.POST)
        
        if form.is_valid():
            business = form.save(commit=False)
            business.owner = request.user
            business.save()
            form.save_m2m()  # Save many-to-many relationships
            messages.success(request, 'Business added successfully!')
            return redirect('vendor:business_list')
    else:
        form = BusinessForm()
    
    context = {
        'form': form,
        'existing_business': existing_business,
    }
    
    return render(request, 'vendor/add_business.html', context)


@login_required
def edit_business(request, pk):
    """Edit an existing business"""
    business = get_object_or_404(Business, id=pk, owner=request.user)
    
    if request.method == 'POST':
        form = BusinessForm(request.POST, instance=business)
        
        if form.is_valid():
            form.save()
            messages.success(request, 'Business updated successfully!')
            return redirect('vendor:business_list')
    else:
        form = BusinessForm(instance=business)
    
    context = {
        'business': business,
        'form': form,
    }
    
    return render(request, 'vendor/edit_business.html', context)


@login_required
def add_product_variation(request, pk):
    """Add a variation to a product"""
    product = get_object_or_404(Product, id=pk)
    # Ensure the product belongs to a business owned by the current user OR was created by the current user
    if product.business and product.business.owner == request.user:
        pass  # Allowed via business ownership
    elif product.user and product.user == request.user:
        pass  # Allowed via direct user ownership
    else:
        messages.error(request, 'You do not have permission to add variations to this product.')
        return redirect('vendor:product_list')
    
    if request.method == 'POST':
        form = ProductVariationForm(request.POST)
        
        if form.is_valid():
            try:
                # Create the variation
                variation = form.save(commit=False)
                variation.product = product
                variation.save()
                
                messages.success(request, 'Product variation added successfully!')
                return redirect('vendor:variation_detail', pk=variation.id)
                
            except Exception as e:
                # Log the error for debugging
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Error creating product variation: {str(e)}")
                messages.error(request, f'Error creating product variation: {str(e)}')
        else:
            # Form is invalid, show errors
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
    else:
        form = ProductVariationForm()

    context = {
        'product': product,
        'form': form,
    }

    return render(request, 'vendor/add_product_variation.html', context)


@login_required
def edit_product_variation(request, pk):
    """Edit an existing product variation"""
    variation = get_object_or_404(ProductVariation, id=pk)
    product = variation.product
    # Ensure ownership
    if product.business and product.business.owner == request.user:
        pass  # Allowed via business ownership
    elif product.user and product.user == request.user:
        pass  # Allowed via direct user ownership
    else:
        messages.error(request, 'You do not have permission to edit this variation.')
        return redirect('vendor:product_list')

    if request.method == 'POST':
        form = ProductVariationForm(request.POST, instance=variation)
        if form.is_valid():
            form.save()
            messages.success(request, 'Product variation updated successfully!')
            return redirect('vendor:product_detail', pk=product.id)
    else:
        form = ProductVariationForm(instance=variation)

    return render(request, 'vendor/edit_product_variation.html', {
        'product': product,
        'variation': variation,
        'form': form,
    })


@login_required
def add_variation_image(request, pk):
    """Add an image tied to a specific ProductVariation"""
    variation = get_object_or_404(ProductVariation, id=pk)
    product = variation.product
    
    # Check permissions
    if not (product.business and product.business.owner == request.user) and not (product.user and product.user == request.user):
        messages.error(request, 'You do not have permission to add images to this variation.')
        return redirect('vendor:product_list')

    if request.method == 'POST':
        # Create the form with POST and FILES data
        form = ProductVariationImageForm(
            request.POST, 
            request.FILES, 
            variation=variation
        )
        
        if form.is_valid():
            try:
                # Save the form (the form's save method will handle setting variation and clearing product)
                img = form.save()
                
                # If this is set as default, unset any other default images for this variation
                if img.is_default:
                    ProductImage.objects.filter(
                        variation=variation,
                        is_default=True
                    ).exclude(pk=img.pk).update(is_default=False)
                
                messages.success(request, 'Variation image added successfully!')
                return redirect('vendor:variation_detail', pk=variation.id)
                
            except Exception as e:
                messages.error(request, f'Error saving image: {str(e)}')
        else:
            # Add form errors to messages
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
    else:
        form = ProductVariationImageForm(variation=variation)

    return render(request, 'vendor/add_variation_image.html', {
        'product': product,
        'variation': variation,
        'form': form,
    })


@login_required
def variation_detail(request, pk):
    """View a single product variation and its images."""
    # Only get non-archived variations and products
    variation = get_object_or_404(
        ProductVariation,
        id=pk,
        is_archived=False,
        product__is_archived=False
    )
    product = variation.product
    
    # Ensure ownership
    if product.business and product.business.owner == request.user:
        pass  # Allowed via business ownership
    elif product.user and product.user == request.user:
        pass  # Allowed via direct user ownership
    else:
        messages.error(request, 'You do not have permission to view this variation.')
        return redirect('vendor:product_list')

    images = ProductImage.objects.filter(variation=variation).order_by('-is_default', '-created_at')

    # Handle PriceTier formset
    PriceTierFormSet = inlineformset_factory(
        ProductVariation,
        PriceTier,
        form=PriceTierForm,
        extra=1,
        can_delete=True,
        fields=('min_quantity', 'max_quantity', 'price')
    )
    
    # Handle IRate formset
    IRateFormSet = inlineformset_factory(
        ProductVariation,
        IRate,
        form=IRateForm,
        extra=1,
        can_delete=True,
        fields=('lower_range', 'upper_range', 'must_pay_shipping', 'rate')
    )
    
    # Get analytics data
    from django.db.models import Sum, Count, Q, F
    
    # Number of carts containing this variation
    cart_count = CartItem.objects.filter(variation=variation).count()
    
    # Number of orders for this variation
    order_count = OrderItem.objects.filter(variation=variation).count()
    
    # Number of order requests for this variation
    order_request_count = OrderRequestItem.objects.filter(variation=variation).count()
    
    # Total quantity ordered
    total_ordered = OrderItem.objects.filter(variation=variation).aggregate(
        total=Sum('quantity')
    )['total'] or 0
    
    # Total revenue from this variation
    total_revenue = OrderItem.objects.filter(
        variation=variation,
        order__status='completed'  # Only count completed orders
    ).aggregate(
        total=Sum(F('price') * F('quantity'))
    )['total'] or 0
    
    # Get recent orders for this variation
    recent_orders = OrderItem.objects.filter(variation=variation).select_related(
        'order', 'order__user'
    ).order_by('-order__created_at')[:5]
    
    # Get recent order requests for this variation
    recent_order_requests = OrderRequestItem.objects.filter(
        variation=variation
    ).select_related(
        'order_request', 'order_request__user'
    ).order_by('-order_request__created_at')[:5]
    
    if request.method == 'POST' and 'price_tier_submit' in request.POST:
        price_tier_formset = PriceTierFormSet(
            request.POST,
            instance=variation,
            prefix='pricetier',
            form_kwargs={'variation': variation}  # Pass variation to each form in the formset
        )
        
        if price_tier_formset.is_valid():
            try:
                # Check for duplicate min_quantity values
                min_quantities = []
                for form in price_tier_formset:
                    if form.cleaned_data and not form.cleaned_data.get('DELETE', False):
                        min_qty = form.cleaned_data.get('min_quantity')
                        if min_qty in min_quantities:
                            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                                return JsonResponse({
                                    'success': False,
                                    'message': f'Duplicate minimum quantity: {min_qty}. Each tier must have a unique minimum quantity.'
                                }, status=400)
                            messages.error(request, f'Duplicate minimum quantity: {min_qty}. Each tier must have a unique minimum quantity.')
                            return redirect('vendor:variation_detail', pk=variation.id)
                        min_quantities.append(min_qty)
                
                # Save the formset
                instances = price_tier_formset.save(commit=False)
                for instance in instances:
                    instance.variation = variation  # Ensure variation is set
                    instance.save()
                
                # Delete any marked for deletion
                for obj in price_tier_formset.deleted_objects:
                    obj.delete()
                
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': True,
                        'message': 'Price tiers updated successfully.'
                    })
                
                messages.success(request, 'Price tiers updated successfully.')
                return redirect('vendor:variation_detail', pk=variation.id)
                
            except Exception as e:
                error_message = f'Error saving price tiers: {str(e)}'
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': False,
                        'message': error_message
                    }, status=500)
                    
                messages.error(request, error_message)
                # Log the full error for debugging
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f'Error saving price tiers: {str(e)}', exc_info=True)
        else:
            # Collect formset errors
            form_errors = []
            for form in price_tier_formset:
                if hasattr(form, 'cleaned_data') and form.cleaned_data.get('DELETE', False):
                    continue  # Skip errors from forms being deleted
                for field, errors in form.errors.items():
                    for error in errors:
                        if field == '__all__':
                            error_msg = f'Price tier error: {error}'
                        else:
                            field_label = form.fields[field].label
                            error_msg = f'Price tier {field_label}: {error}'
                        
                        form_errors.append(error_msg)
                        messages.error(request, error_msg)
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'message': 'Please correct the errors below.',
                    'errors': form_errors
                }, status=400)
    
    # Handle IRate formset submission
    if request.method == 'POST' and 'i_rate_submit' in request.POST:
        i_rate_formset = IRateFormSet(
            request.POST,
            instance=variation,
            prefix='irate',
            form_kwargs={'variation': variation}
        )
        
        if i_rate_formset.is_valid():
            try:
                # Check for overlapping ranges
                ranges = []
                for form in i_rate_formset:
                    if form.cleaned_data and not form.cleaned_data.get('DELETE', False):
                        lower = form.cleaned_data.get('lower_range')
                        upper = form.cleaned_data.get('upper_range')
                        if lower and upper:
                            ranges.append((lower, upper))
                
                # Check for overlaps
                for i, (lower1, upper1) in enumerate(ranges):
                    for j, (lower2, upper2) in enumerate(ranges):
                        if i != j:
                            # Check if ranges overlap
                            if not (upper1 <= lower2 or upper2 <= lower1):
                                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                                    return JsonResponse({
                                        'success': False,
                                        'message': f'Overlapping ranges detected: {lower1}-{upper1} and {lower2}-{upper2}'
                                    }, status=400)
                                messages.error(request, f'Overlapping ranges detected: {lower1}-{upper1} and {lower2}-{upper2}')
                                return redirect('vendor:variation_detail', pk=variation.id)
                
                # Save the formset
                instances = i_rate_formset.save(commit=False)
                for instance in instances:
                    instance.variation = variation
                    instance.save()
                
                # Delete any marked for deletion
                for obj in i_rate_formset.deleted_objects:
                    obj.delete()
                
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': True,
                        'message': 'IRates updated successfully.'
                    })
                
                messages.success(request, 'IRates updated successfully.')
                return redirect('vendor:variation_detail', pk=variation.id)
                
            except Exception as e:
                error_message = f'Error saving IRates: {str(e)}'
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': False,
                        'message': error_message
                    }, status=500)
                    
                messages.error(request, error_message)
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f'Error saving IRates: {str(e)}', exc_info=True)
        else:
            # Collect formset errors
            form_errors = []
            for form in i_rate_formset:
                if hasattr(form, 'cleaned_data') and form.cleaned_data.get('DELETE', False):
                    continue
                for field, errors in form.errors.items():
                    for error in errors:
                        if field == '__all__':
                            error_msg = f'IRate error: {error}'
                        else:
                            field_label = form.fields[field].label
                            error_msg = f'IRate {field_label}: {error}'
                        
                        form_errors.append(error_msg)
                        messages.error(request, error_msg)
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'message': 'Please correct the errors below.',
                    'errors': form_errors
                }, status=400)
    
    # Initialize the formset for GET requests or if not submitting price tiers
    price_tier_formset = PriceTierFormSet(
        instance=variation,
        queryset=variation.price_tiers.order_by('min_quantity'),
        prefix='pricetier',
        form_kwargs={'variation': variation}
    )
    
    # Initialize IRate formset
    i_rate_formset = IRateFormSet(
        instance=variation,
        queryset=variation.i_rates.order_by('lower_range'),
        prefix='irate',
        form_kwargs={'variation': variation}
    )

    # Handle Knowledge Base form submission
    if request.method == 'POST' and 'kb_submit' in request.POST:
        kb_entry = variation.kb.first()  # Get existing or create new
        if kb_entry:
            kb_form = ProductKBForm(request.POST, instance=kb_entry, variation=variation)
        else:
            kb_form = ProductKBForm(request.POST, variation=variation)
            
        if kb_form.is_valid():
            kb_entry = kb_form.save(commit=False)
            kb_entry.variation = variation
            kb_entry.save()
            messages.success(request, 'Knowledge base updated successfully!')
            return redirect('vendor:variation_detail', pk=variation.id)
        else:
            # If form is invalid, we'll continue to render the page with errors
            pass
    else:
        # Initialize KB form for GET request
        kb_entry = variation.kb.first()
        if kb_entry:
            # Show existing content in the input field
            kb_form = ProductKBForm(instance=kb_entry, variation=variation)
        else:
            kb_form = ProductKBForm(variation=variation)
    
    # Handle PromiseFee form submission
    if request.method == 'POST' and 'promise_fee_submit' in request.POST:
        # Debug: Log all POST data
        print("\n=== DEBUG: RAW POST DATA ===")
        for key, value in request.POST.lists():
            print(f"{key}: {value}")
        print("==========================\n")
        
        # Log all form data with types
        print("\n=== DEBUG: FORM DATA WITH TYPES ===")
        for key, value in request.POST.items():
            print(f"{key}: {value} (type: {type(value).__name__})")
        print("================================\n")
        
        # Check if this is a request to clear the fee
        if 'no_fees' in request.POST and request.POST['no_fees'] == 'true':
            try:
                if hasattr(variation, 'promise_fee'):
                    variation.promise_fee.delete()
                    messages.success(request, 'Promise fee has been cleared.')
                else:
                    messages.info(request, 'No promise fee to clear.')
                return redirect('vendor:variation_detail', pk=variation.id)
            except Exception as e:
                messages.error(request, f'Error clearing promise fee: {str(e)}')
                return redirect('vendor:variation_detail', pk=variation.id)
        
        # Process the single promise fee (since it's a OneToOne relationship)
        errors = []
        saved = False
        
        # Get the fee data from the form - handle multiple fees
        fee_data = {}
        fee_index = 0
        
        # Look for fee data with index 0 first (existing fee)
        if 'fee_0_name' in request.POST:
            fee_data = {
                'name': request.POST.get('fee_0_name', '').strip(),
                'min_percent': request.POST.get('fee_0_min_percent', '0'),
                'max_percent': request.POST.get('fee_0_max_percent', '0'),
            }
        else:
            # Look for new fees with higher indices
            while f'fee_{fee_index}_name' in request.POST:
                name = request.POST.get(f'fee_{fee_index}_name', '').strip()
                if name:  # Only process if name is provided
                    fee_data = {
                        'name': name,
                        'min_percent': request.POST.get(f'fee_{fee_index}_min_percent', '0'),
                        'max_percent': request.POST.get(f'fee_{fee_index}_max_percent', '0'),
                    }
                    break
                fee_index += 1
        
        # Debug: Print all POST data
        print("\n=== DEBUG: POST DATA ===")
        for key, value in request.POST.items():
            print(f"{key}: {value}")
        print("======================\n")
        
        # Debug: Log fee data
        print(f"\n=== DEBUG: Processing promise fee ===")
        if fee_data:
            print(f"Name: {fee_data.get('name', 'N/A')}")
            print(f"Min Percent: {fee_data.get('min_percent', 'N/A')}")
            print(f"Max Percent: {fee_data.get('max_percent', 'N/A')}")
        else:
            print("No fee data found")
        
        # Convert string values to Decimal with 2 decimal places, handling empty strings
        if fee_data:
            try:
                from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
                
                # Convert and validate min_percent
                min_percent = Decimal(fee_data.get('min_percent', '0') or '0').quantize(
                    Decimal('0.00'), rounding=ROUND_HALF_UP
                )
                if min_percent < 0 or min_percent > 100:
                    errors.append("Minimum percentage must be between 0 and 100.")
                    
                # Convert and validate max_percent
                max_percent = Decimal(fee_data.get('max_percent', '0') or '0').quantize(
                    Decimal('0.00'), rounding=ROUND_HALF_UP
                )
                if max_percent < 0 or max_percent > 100:
                    errors.append("Maximum percentage must be between 0 and 100.")
                    
                # Validate min_percent <= max_percent
                if min_percent > max_percent:
                    errors.append("Minimum percentage cannot be greater than maximum percentage.")
                    
            except (ValueError, TypeError, InvalidOperation) as e:
                errors.append(f"Invalid number format: {str(e)}")
        
        if not errors and fee_data and fee_data.get('name'):
            try:
                # Get or create the promise fee
                promise_fee, created = PromiseFee.objects.update_or_create(
                    variation=variation,
                    defaults={
                        'name': fee_data['name'],
                        'min_percent': min_percent,
                        'max_percent': max_percent,
                    }
                )
                
                try:
                    promise_fee.full_clean()  # Validate the model
                    promise_fee.save()
                    saved = True
                    messages.success(request, 'Promise fee saved successfully!')
                except ValidationError as e:
                    errors.append(f"Validation error: {str(e)}")
            except Exception as e:
                errors.append(f"Error saving promise fee: {str(e)}")
        elif not fee_data or not fee_data.get('name'):
            errors.append("Name is required for the promise fee.")
        
        # Show any errors that occurred
        for error in errors:
            messages.error(request, error)
        
        return redirect('vendor:variation_detail', pk=variation.id)
    
    # For GET requests or if not submitting fees, load the promise fee if it exists
    try:
        promise_fee = variation.promise_fee
        promise_fees = [promise_fee] if promise_fee else []
    except PromiseFee.DoesNotExist:
        promise_fees = []
        
    promise_fee_form = PromiseFeeForm()  # Empty form for adding new fees
    
    # Debug output (will be visible in the server console)
    print(f"Promise fee for variation {variation.id}:", promise_fees[0] if promise_fees else 'None')
    
    # Get product attributes for this variation
    attributes = ProductAttributeAssignment.objects.filter(product=variation).select_related('value__attribute')
    
    context = {
        'product': product,
        'variation': variation,
        'images': images,
        'attributes': attributes,
        'price_tier_formset': price_tier_formset,
        'i_rate_formset': i_rate_formset,
        'i_rates': variation.i_rates.order_by('lower_range'),  # Add this line for template
        'promise_fee_form': promise_fee_form,
        'promise_fees': promise_fees,
        'kb_form': kb_form,
        'kb_entry': kb_entry if 'kb_entry' in locals() else None,
        'cart_count': cart_count,
        'order_count': order_count,
        'order_request_count': order_request_count,
        'total_ordered': total_ordered,
        'total_revenue': total_revenue,
        'recent_orders': recent_orders,
        'recent_order_requests': recent_order_requests,
    }
    
    # Debug output of context keys
    print("Context keys:", context.keys())
    
    return render(request, 'vendor/variation_detail.html', context)

import logging
logger = logging.getLogger(__name__)

@login_required
def add_variation_attribute(request, pk):
    """Add a product attribute assignment to a variation"""
    logger.info(f"Starting add_variation_attribute view for variation {pk}")
    variation = get_object_or_404(ProductVariation, id=pk)
    product = variation.product

    # Log the request data
    if request.method == 'POST':
        logger.info(f"POST data: {request.POST}")
    
    # Ensure ownership
    if product.business and product.business.owner == request.user:
        pass  # Allowed via business ownership
    elif product.user and product.user == request.user:
        pass  # Allowed via direct user ownership
    else:
        error_msg = 'You do not have permission to add attributes to this variation.'
        logger.warning(f"Permission denied for user {request.user} on variation {pk}")
        messages.error(request, error_msg)
        return redirect('vendor:product_list')

    if request.method == 'POST':
        # Create a mutable copy of the POST data
        post_data = request.POST.copy()
        # Add the variation to the form data
        post_data['product'] = variation.id
        
        form = ProductAttributeAssignmentForm(post_data, variation=variation)
        logger.info(f"Form is bound: {form.is_bound}")
        logger.info(f"Form data: {form.data}")
        
        if form.is_valid():
            logger.info("Form is valid")
            new_attribute_name = form.cleaned_data.get('new_attribute_name')
            new_attribute_description = form.cleaned_data.get('new_attribute_description')
            new_attribute_value = form.cleaned_data.get('new_attribute_value')
            existing_value = form.cleaned_data.get('existing_value')
            
            logger.info(f"New Attribute Name: {new_attribute_name}")
            logger.info(f"New Attribute Value: {new_attribute_value}")
            logger.info(f"Existing Value: {existing_value}")

            try:
                if new_attribute_name and new_attribute_value:
                    logger.info("Creating new attribute and value")
                    attribute, created = ProductAttribute.objects.get_or_create(
                        name=new_attribute_name,
                        defaults={'description': new_attribute_description or ''}
                    )
                    logger.info(f"Attribute {'created' if created else 'exists'}: {attribute}")

                    # Create the attribute value
                    attribute_value, created = ProductAttributeValue.objects.get_or_create(
                        attribute=attribute,
                        value=new_attribute_value
                    )
                    logger.info(f"Attribute value {'created' if created else 'exists'}: {attribute_value}")
                    form.instance.value = attribute_value
                    
                elif existing_value:
                    logger.info(f"Using existing attribute value: {existing_value}")
                    form.instance.value = existing_value
                else:
                    error_msg = 'Please provide attribute information.'
                    logger.warning(error_msg)
                    messages.error(request, error_msg)
                    return redirect('vendor:variation_detail', pk=variation.id)

                # Save the form
                assignment = form.save(commit=False)
                assignment.product = variation
                assignment.save()
                logger.info(f"Assignment created successfully: {assignment}")

                messages.success(request, 'Product attribute added successfully!')
                return redirect('vendor:variation_detail', pk=variation.id)
                
            except Exception as e:
                error_msg = f'Error saving attribute: {str(e)}'
                logger.error(error_msg, exc_info=True)
                messages.error(request, error_msg)
        else:
            # Form is not valid, log and show errors
            logger.warning(f"Form errors: {form.errors}")
            for field, errors in form.errors.items():
                for error in errors:
                    error_msg = f"{field}: {error}"
                    logger.warning(error_msg)
                    messages.error(request, error_msg)
    else:
        logger.info("Rendering empty form")
        form = ProductAttributeAssignmentForm(variation=variation)
    
    logger.info("Rendering template with form")

    context = {
        'product': product,
        'variation': variation,
        'form': form,
    }
    return render(request, 'vendor/add_variation_attribute.html', context)


@login_required
def get_categories(request):
    """Get categories based on filter_id with support for existing product categories"""
    filter_id = request.GET.get('filter_id')
    product_id = request.GET.get('product_id')
    
    try:
        if filter_id:
            # Handle filter selection
            if isinstance(filter_id, str) and filter_id.startswith('filter_'):
                filter_id = filter_id[7:]  # Remove 'filter_' prefix
            
            try:
                filter_id = int(filter_id)  # Ensure it's an integer
                # Get categories for the selected filter
                categories = ProductCategory.objects.filter(filter_id=filter_id).order_by('name')
                
                # If we have a product ID, include its current category even if not in this filter
                current_category = None
                if product_id and product_id.isdigit():
                    try:
                        product = Product.objects.get(id=product_id)
                        if product.categories.exists():
                            current_category = product.categories.first()
                            # If current category is not in the filtered set, add it
                            if current_category.filter_id != filter_id and not categories.filter(id=current_category.id).exists():
                                categories = list(categories) + [current_category]
                    except (Product.DoesNotExist, ValueError):
                        pass
                
                data = [{
                    'id': str(cat.id),  # Ensure ID is a string for consistency
                    'name': cat.name,
                    'filter_id': cat.filter_id,
                    'is_current': (current_category and cat.id == current_category.id)
                } for cat in categories]
                
                # Sort by name but ensure current category is first if it exists
                data.sort(key=lambda x: (not x.get('is_current', False), x['name']))
                
                return JsonResponse(data, safe=False)
                
            except (ValueError, TypeError) as e:
                logger.warning(f"Invalid filter_id format: {filter_id}")
                return JsonResponse([], safe=False)
                
        else:
            # Initial load - get all filters with their categories
            filters = ProductCategoryFilter.objects.prefetch_related('categories').order_by('name')
            
            # Get current category if product_id is provided
            current_category = None
            if product_id and product_id.isdigit():
                try:
                    product = Product.objects.get(id=product_id)
                    if product.categories.exists():
                        current_category = product.categories.first()
                except (Product.DoesNotExist, ValueError):
                    pass
            
            data = []
            for filter_obj in filters:
                categories = filter_obj.categories.all()
                
                # If we have a current category not in this filter, include it
                if current_category and current_category.filter_id == filter_obj.id and \
                   not categories.filter(id=current_category.id).exists():
                    categories = list(categories) + [current_category]
                
                filter_data = {
                    'id': f'filter_{filter_obj.id}',
                    'name': filter_obj.name,
                    'is_filter': True,
                    'categories': [{
                        'id': str(cat.id),  # Ensure ID is a string for consistency
                        'name': cat.name,
                        'filter_id': cat.filter_id,
                        'is_current': (current_category and cat.id == current_category.id)
                    } for cat in categories]
                }
                
                # Sort categories by name but ensure current category is first if it exists
                filter_data['categories'].sort(key=lambda x: (not x.get('is_current', False), x['name']))
                
                data.append(filter_data)
            
            return JsonResponse(data, safe=False)
            
    except Exception as e:
        logger.error(f"Error in get_categories: {str(e)}", exc_info=True)
        return JsonResponse(
            {'error': 'An error occurred while loading categories'}, 
            status=500
        )


@login_required
def orders(request):
    """List orders for products that belong to the vendor's businesses."""
    user_businesses = Business.objects.filter(owner=request.user)
    
    # Get all orders that have items from this vendor
    orders = Order.objects.filter(
        items__variation__product__business__in=user_businesses
    ).distinct().order_by('-created_at')
    
    # Apply filters
    status = request.GET.get('status')
    date_range = request.GET.get('date_range')
    min_price = request.GET.get('min_price')
    max_price = request.GET.get('max_price')
    search = request.GET.get('search', '').strip()
    
    if status:
        orders = orders.filter(status=status)
    
    if date_range:
        start_date, end_date = date_range.split(' - ')
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        orders = orders.filter(created_at__date__range=[start_date, end_date])
    
    if min_price:
        orders = orders.filter(total_amount__gte=float(min_price))
    
    if max_price:
        orders = orders.filter(total_amount__lte=float(max_price))
    
    if search:
        orders = orders.filter(
            Q(id__icontains=search) |
            Q(items__variation__product__name__icontains=search) |
            Q(user__email__icontains=search)
        ).distinct()
    
    # Get order items for the filtered orders
    order_items = OrderItem.objects.filter(
        order__in=orders,
        variation__product__business__in=user_businesses
    ).select_related('order', 'variation__product', 'variation')
    
    # Group order items by order
    order_dict = {}
    for item in order_items:
        if item.order_id not in order_dict:
            order_dict[item.order_id] = {
                'order': item.order,
                'items': [],
                'total_items': 0,
                'total_amount': 0
            }
        order_dict[item.order_id]['items'].append(item)
        order_dict[item.order_id]['total_items'] += item.quantity
        order_dict[item.order_id]['total_amount'] += float(item.subtotal())  # Call subtotal() to get the value
    
    # Convert to list for pagination
    orders_with_items = list(order_dict.values())
    
    # Get status choices for the filter
    status_choices = Order.STATUS_CHOICES
    selected_statuses = request.GET.getlist('status')
    
    # Pagination
    paginator = Paginator(orders_with_items, 10)  # Show 10 orders per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'vendor/orders.html', {
        'page_obj': page_obj,
        'order_count': len(orders_with_items),
        'status_choices': status_choices,
        'selected_statuses': selected_statuses,
    })


@login_required
@require_http_methods(["POST"])
def delete_price_tier(request, pk):
    """Delete a price tier"""
    price_tier = get_object_or_404(PriceTier, pk=pk)
    variation = price_tier.variation
    
    # Check if the user has permission to delete this price tier
    if variation.product.user != request.user and variation.product.business.owner != request.user:
        messages.error(request, 'You do not have permission to delete this price tier.')
        return redirect('vendor:variation_detail', pk=variation.id)
    
    price_tier.delete()
    messages.success(request, 'Price tier deleted successfully.')
    return redirect('vendor:variation_detail', pk=variation.id)


@login_required
def order_requests(request):
    """List order requests for the vendor's products"""
    # Get order requests for the vendor's products
    order_requests = OrderRequest.objects.filter(
        items__variation__product__user=request.user
    ).distinct().annotate(
        item_count=Count('items'),
        total_quantity=Sum('items__quantity'),
        order_total=Sum(F('items__unit_price') * F('items__quantity'))
    ).order_by('-created_at')
    
    # Pagination
    paginator = Paginator(order_requests, 10)  # Show 10 order requests per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get stats for the dashboard
    stats = {
        'total_requests': order_requests.count(),
        'pending_requests': order_requests.filter(status='pending').count(),
        'accepted_requests': order_requests.filter(status='accepted').count(),
        'rejected_requests': order_requests.filter(status='rejected').count(),
    }
    
    return render(request, 'vendor/order_requests.html', {
        'page_obj': page_obj,
        'stats': stats,
    })


@login_required
def order_request_detail(request, pk):
    """View details of a specific order request"""
    from django.db import transaction
    from decimal import Decimal
    from home.models import Order, OrderItem, OrderAdditionalFees
    
    try:
        logger.info(f"Fetching order request {pk} for user {request.user.id}")
        
        # First check if any order request with this ID exists and user has access
        order_request = OrderRequest.objects.filter(
            id=pk,
            items__variation__product__user=request.user
        ).first()
        
        if not order_request:
            logger.warning(f"Order request {pk} not found or user {request.user.id} doesn't have permission")
            raise Http404("Order request not found or you don't have permission to view it.")
            
        logger.info(f"Found order request {pk}, now fetching related data")
        
        # Get all items in this request that belong to the current vendor
        items = order_request.items.filter(
            variation__product__user=request.user
        ).select_related('variation', 'variation__product')
        
        if not items.exists():
            logger.warning(f"No items found for order request {pk} that belong to user {request.user.id}")
            raise Http404("No items found in this order request.")
        
        # Handle Accept Request form submission
        if request.method == 'POST' and 'accept_request' in request.POST:
            try:
                with transaction.atomic():
                    # Check if order already exists
                    if hasattr(order_request, 'order') and order_request.order:
                        messages.error(request, 'An order already exists for this request.')
                        return redirect('vendor:order_request_detail', pk=pk)
                    
                    # Create the order
                    order = Order.objects.create(
                        user=order_request.user,
                        created_by=request.user,
                        status='pending',
                        total=Decimal('0'),
                        order_request=order_request
                    )
                    
                    # Create order items
                    order_items = []
                    total_amount = Decimal('0')
                    
                    for item in items:
                        order_item = OrderItem.objects.create(
                            order=order,
                            variation=item.variation,
                            quantity=item.quantity,
                            price=item.unit_price
                        )
                        order_items.append(order_item)
                        total_amount += order_item.subtotal()
                    
                    # Update order total
                    order.total = total_amount
                    order.save(update_fields=['total'])
                    
                    # Update order request status
                    order_request.status = 'accepted'
                    order_request.save(update_fields=['status', 'updated_at'])
                    
                    logger.info(f"Order {order.id} created from order request {order_request.id}")
                    messages.success(request, 'Order request accepted and order created successfully!')
                    return redirect('vendor:order_detail', order_id=order.id)
                    
            except Exception as e:
                logger.error(f"Error creating order: {str(e)}", exc_info=True)
                messages.error(request, 'An error occurred while creating the order. Please try again.')
                return redirect('vendor:order_request_detail', pk=pk)
        
        # Calculate totals for display
        total_quantity = items.aggregate(Sum('quantity'))['quantity__sum'] or 0
        total_amount = sum(item.unit_price * item.quantity for item in items)
        total_deposit = sum(item.deposit_amount for item in items)
        
        # Get additional fees if any (for accepted order requests)
        additional_fees = []
        if order_request.status == 'accepted' and hasattr(order_request, 'order') and order_request.order:
            additional_fees = OrderAdditionalFees.objects.filter(order=order_request.order)
        
        return render(request, 'vendor/order_request_detail.html', {
            'order_request': order_request,
            'items': items,
            'total_quantity': total_quantity,
            'total_amount': total_amount,
            'total_deposit': total_deposit,
            'additional_fees': additional_fees,
        })
        
    except Http404:
        raise  # Re-raise the Http404 exception
    except Exception as e:
        logger.error(f"Unexpected error in order_request_detail: {str(e)}", exc_info=True)
        raise Http404("An error occurred while processing your request.")
def delete_promise_fee(request, pk):
    """Delete a promise fee"""
    from home.models import PromiseFee  # Import here to avoid circular imports
    
    promise_fee = get_object_or_404(PromiseFee, pk=pk)
    variation = promise_fee.variation
    
    # Check if the user has permission to delete this promise fee
    if variation.product.user != request.user and variation.product.business.owner != request.user:
        messages.error(request, 'You do not have permission to delete this promise fee.')
        return redirect('vendor:variation_detail', pk=variation.id)
    
    promise_fee.delete()
    messages.success(request, 'Promise fee deleted successfully.')
    return redirect('vendor:variation_detail', pk=variation.id)