from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from home.models import Product, ProductCategory, Business, ProductImage, BusinessCategory
from .forms import ProductForm, ProductImageForm, ProductSearchForm, BusinessForm


@login_required
def vendor_dashboard(request):
    """Vendor dashboard showing overview of products and sales"""
    # Get products from businesses owned by the current user
    user_businesses = Business.objects.filter(owner=request.user)
    products = Product.objects.filter(business__in=user_businesses)
    
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
    products = Product.objects.filter(business__in=user_businesses)
    
    if search_form.is_valid():
        search = search_form.cleaned_data.get('search')
        category = search_form.cleaned_data.get('category')
        min_price = search_form.cleaned_data.get('min_price')
        max_price = search_form.cleaned_data.get('max_price')
        
        if search:
            products = products.filter(
                Q(name__icontains=search) |
                Q(description__icontains=search)
            )
        
        if category:
            products = products.filter(category=category)
        
        if min_price:
            products = products.filter(price__gte=min_price)
        
        if max_price:
            products = products.filter(price__lte=max_price)
    
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
    # Ensure the product belongs to a business owned by the current user
    if product.business.owner != request.user:
        messages.error(request, 'You do not have permission to view this product.')
        return redirect('vendor:product_list')
    
    images = ProductImage.objects.filter(product=product)
    
    context = {
        'product': product,
        'images': images,
    }
    
    return render(request, 'vendor/product_detail.html', context)


@login_required
def edit_product(request, pk):
    """Edit an existing product"""
    product = get_object_or_404(Product, id=pk)
    # Ensure the product belongs to a business owned by the current user
    if product.business.owner != request.user:
        messages.error(request, 'You do not have permission to edit this product.')
        return redirect('vendor:product_list')
    
    if request.method == 'POST':
        form = ProductForm(request.POST, instance=product, user=request.user)
        
        if form.is_valid():
            form.save()
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
    # Ensure the product belongs to a business owned by the current user
    if product.business.owner != request.user:
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
    # Ensure the product belongs to a business owned by the current user
    if product.business.owner != request.user:
        messages.error(request, 'You do not have permission to add images to this product.')
        return redirect('vendor:product_list')
    
    if request.method == 'POST':
        form = ProductImageForm(request.POST, request.FILES)
        if form.is_valid():
            image = form.save(commit=False)
            image.product = product
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
def get_categories(request):
    """Get categories for a specific filter (AJAX)"""
    filter_id = request.GET.get('filter_id')
    if filter_id:
        categories = ProductCategory.objects.filter(filter_id=filter_id)
        data = [{'id': cat.id, 'name': cat.name} for cat in categories]
        return JsonResponse(data, safe=False)
    return JsonResponse([], safe=False)