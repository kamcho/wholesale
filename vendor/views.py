from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from decimal import Decimal, InvalidOperation

from home.models import Product, ProductCategory, Business, ProductImage, BusinessCategory, ProductVariation, OrderItem, ProductAttributeAssignment, ProductAttribute, ProductAttributeValue, PriceTier, PromiseFee, IRate, ProductServicing, Agent
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
    search_form = ProductSearchForm(request.GET)
    user_businesses = Business.objects.filter(owner=request.user)
    products = Product.objects.filter(
        Q(business__in=user_businesses) | Q(user=request.user)
    )
    
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
    product = get_object_or_404(Product, id=pk)
    # Ensure the product belongs to a business owned by the current user OR was created by the current user
    if product.business and product.business.owner == request.user:
        pass  # Allowed via business ownership
    elif product.user and product.user == request.user:
        pass  # Allowed via direct user ownership
    else:
        messages.error(request, 'You do not have permission to view this product.')
        return redirect('vendor:product_list')
    
    images = ProductImage.objects.filter(product=product)
    variations = ProductVariation.objects.filter(product=product)
    
    
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
    
    context = {
        'product': product,
        'images': images,
        'variations': variations,
        'product_servicing': product_servicing,
        'shipping_agents': shipping_agents,
        'sourcing_agents': sourcing_agents,
        'customs_agents': customs_agents,
    }
    
    return render(request, 'vendor/product_detail.html', context)


@login_required
def edit_product(request, pk):
    """Edit an existing product"""
    product = get_object_or_404(Product, id=pk)
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
def delete_product(request, pk):
    """Delete a product"""
    product = get_object_or_404(Product, id=pk)
    # Ensure the product belongs to a business owned by the current user OR was created by the current user
    if product.business and product.business.owner == request.user:
        pass  # Allowed via business ownership
    elif product.user and product.user == request.user:
        pass  # Allowed via direct user ownership
    else:
        messages.error(request, 'You do not have permission to delete this product.')
        return redirect('vendor:product_list')
    
    if request.method == 'POST':
        product.delete()
        messages.success(request, 'Product deleted successfully!')
        return redirect('vendor:product_list')
    
    context = {
        'product': product,
    }
    
    return render(request, 'vendor/delete_product.html', context)


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
        form = ProductImageForm(request.POST, request.FILES)
        if form.is_valid():
            image = form.save(commit=False)
            image.product = product
            
            # Set the image field from the form before validation
            if 'image' in request.FILES:
                image.image = request.FILES['image']
            
            image.save()
            
            # If this is set as default, unset other default images
            if image.is_default:
                ProductImage.objects.filter(product=product).exclude(id=image.id).update(is_default=False)
            
            messages.success(request, 'Image added successfully!')
            return redirect('vendor:product_detail', pk=product.id)
    else:
        form = ProductImageForm()
    
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
    """Add a new business"""
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
    
    VariationImageFormSet = modelformset_factory(
        ProductImage,
        form=ProductVariationImageForm,
        extra=1,
        can_delete=False,
    )

    if request.method == 'POST':
        form = ProductVariationForm(request.POST)
        formset = VariationImageFormSet(request.POST, request.FILES, queryset=ProductImage.objects.none())
        
        if form.is_valid() and formset.is_valid():
            try:
                # Create the variation
                variation = form.save(commit=False)
                variation.product = product
                variation.save()
                
                # Save images tied to this variation
                images = formset.save(commit=False)
                for img in images:
                    if img.image:  # Only save if there's an image file
                        img.variation = variation
                        img.product = None  # ensure XOR holds
                        img.save()
                
                messages.success(request, 'Product variation added successfully!')
                return redirect('vendor:product_detail', pk=product.id)
                
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
            
            for formset_form in formset:
                for field, errors in formset_form.errors.items():
                    for error in errors:
                        messages.error(request, f"Image {field}: {error}")
    else:
        form = ProductVariationForm()
        formset = VariationImageFormSet(queryset=ProductImage.objects.none())

    context = {
        'product': product,
        'form': form,
        'formset': formset,
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
                return redirect('vendor:edit_product_variation', pk=variation.id)
                
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
    variation = get_object_or_404(ProductVariation, id=pk)
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
    
    context = {
        'product': product,
        'variation': variation,
        'images': images,
        'price_tier_formset': price_tier_formset,
        'i_rate_formset': i_rate_formset,
        'promise_fee_form': promise_fee_form,
        'promise_fees': promise_fees,
        'kb_form': kb_form,
        'kb_entry': kb_entry if 'kb_entry' in locals() else None,
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
    """Get categories for a specific filter (AJAX)"""
    filter_id = request.GET.get('filter_id')
    if filter_id:
        categories = ProductCategory.objects.filter(filter_id=filter_id)
        data = [{'id': cat.id, 'name': cat.name} for cat in categories]
        return JsonResponse(data, safe=False)
    return JsonResponse([], safe=False)


@login_required
def orders(request):
    """List order items for products that belong to the vendor's businesses."""
    user_businesses = Business.objects.filter(owner=request.user)
    order_items = OrderItem.objects.filter(
        Q(product__business__in=user_businesses) | Q(product__user=request.user)
    ).select_related('order', 'product').order_by('-order__created_at')
    
    # Pagination
    paginator = Paginator(order_items, 10)  # Show 10 orders per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'vendor/orders.html', {
        'page_obj': page_obj,
        'order_count': order_items.count(),
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
@require_http_methods(["POST"])
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