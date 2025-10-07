from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from home.models import Product, ProductCategory, Business, ProductImage, BusinessCategory, ProductVariation, OrderItem, ProductAttributeAssignment, ProductAttribute, ProductAttributeValue, PriceTier
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
    
    context = {
        'product': product,
        'images': images,
        'variations': variations,
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
    if product.business and product.business.owner == request.user:
        pass  # Allowed via business ownership
    elif product.user and product.user == request.user:
        pass  # Allowed via direct user ownership
    else:
        messages.error(request, 'You do not have permission to add images to this variation.')
        return redirect('vendor:product_list')

    if request.method == 'POST':
        form = ProductVariationImageForm(request.POST, request.FILES)
        if form.is_valid():
            img = form.save(commit=False)
            img.variation = variation
            img.product = None
            
            # Set the image field from the form before validation
            if 'image' in request.FILES:
                img.image = request.FILES['image']
            
            img.save()
            
            # If default set, unset others on this variation
            if img.is_default:
                ProductImage.objects.filter(variation=variation).exclude(id=img.id).update(is_default=False)
            messages.success(request, 'Variation image added successfully!')
            return redirect('vendor:edit_product_variation', pk=variation.id)
    else:
        form = ProductVariationImageForm()

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
    
    if request.method == 'POST' and 'price_tier_submit' in request.POST:
        price_tier_formset = PriceTierFormSet(
            request.POST,
            instance=variation,
            prefix='pricetier'
        )
        if price_tier_formset.is_valid():
            price_tier_formset.save()
            messages.success(request, 'Price tiers updated successfully.')
            return redirect('vendor:variation_detail', pk=variation.id)
        else:
            messages.error(request, 'Please correct the errors in the price tiers.')
    else:
        price_tier_formset = PriceTierFormSet(
            instance=variation,
            queryset=variation.price_tiers.order_by('min_quantity'),
            prefix='pricetier'
        )

    # Handle PromiseFee form submission
    if request.method == 'POST' and 'promise_fee_submit' in request.POST:
        promise_fee_form = PromiseFeeForm(request.POST, variation=variation)
        if promise_fee_form.is_valid():
            promise_fee_form.save()
            messages.success(request, 'Promise fee saved.')
            return redirect('vendor:variation_detail', pk=variation.id)
        else:
            messages.error(request, 'Please correct the errors below (Promise Fee).')
    else:
        # If a PromiseFee already exists, load it for editing; else blank
        existing = variation.promise_fees.order_by('-created_at').first()
        promise_fee_form = PromiseFeeForm(instance=existing) if existing else PromiseFeeForm()

    return render(request, 'vendor/variation_detail.html', {
        'product': product,
        'variation': variation,
        'images': images,
        'price_tier_formset': price_tier_formset,
        'promise_fee_form': promise_fee_form,
    })

@login_required
def add_variation_attribute(request, pk):
    """Add a product attribute assignment to a variation"""
    variation = get_object_or_404(ProductVariation, id=pk)
    product = variation.product

    # Ensure ownership
    if product.business and product.business.owner == request.user:
        pass  # Allowed via business ownership
    elif product.user and product.user == request.user:
        pass  # Allowed via direct user ownership
    else:
        messages.error(request, 'You do not have permission to add attributes to this variation.')
        return redirect('vendor:product_list')

    if request.method == 'POST':
        form = ProductAttributeAssignmentForm(request.POST, variation=variation)
        if form.is_valid():
            new_attribute_name = form.cleaned_data.get('new_attribute_name')
            new_attribute_description = form.cleaned_data.get('new_attribute_description')
            new_attribute_value = form.cleaned_data.get('new_attribute_value')
            existing_value = form.cleaned_data.get('existing_value')

            if new_attribute_name and new_attribute_value:
                # Create new attribute and value
                # Create or get the attribute
                attribute, created = ProductAttribute.objects.get_or_create(
                    name=new_attribute_name,
                    defaults={'description': new_attribute_description or ''}
                )

                # Create the attribute value
                attribute_value, created = ProductAttributeValue.objects.get_or_create(
                    attribute=attribute,
                    value=new_attribute_value
                )

                # Use the new attribute value for the assignment
                assignment_value = attribute_value
            elif existing_value:
                # Use existing attribute value
                assignment_value = existing_value
            else:
                # This shouldn't happen due to form validation, but just in case
                messages.error(request, 'Please provide attribute information.')
                return redirect('vendor:variation_detail', pk=variation.id)

            # Create the assignment
            assignment = form.save(commit=False)
            assignment.product = variation
            assignment.value = assignment_value
            assignment.save()

            messages.success(request, 'Product attribute added successfully!')
            return redirect('vendor:variation_detail', pk=variation.id)
    else:
        form = ProductAttributeAssignmentForm(variation=variation)

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