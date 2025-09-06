from django.shortcuts import render, get_object_or_404
from django.core.paginator import Paginator
from django.db.models import Q
from .models import Product, ProductCategory, Business, ProductImage, ProductCategoryFilter

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
    
    # Category filter
    category_id = request.GET.get('category', '')
    if category_id:
        products = products.filter(category_id=category_id)
    
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
    
    # Get related products from the same category
    related_products = Product.objects.filter(
        category=product.category
    ).exclude(pk=product.pk)[:4]
    
    context = {
        'product': product,
        'images': images,
        'related_products': related_products,
    }
    
    return render(request, 'home/product_detail.html', context)

def category_products(request, category_id):
    """Display products filtered by category"""
    category = get_object_or_404(ProductCategory, pk=category_id)
    products = Product.objects.filter(category=category).order_by('-created_at')
    
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



