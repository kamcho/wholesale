from django.contrib.auth.decorators import user_passes_test
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.views.decorators.http import require_POST
from .models import ProductCategoryFilter, ProductCategory
from .forms import ProductCategoryFilterForm, ProductCategoryForm

def admin_required(user):
    return user.is_authenticated and user.role == 'Admin'

@user_passes_test(admin_required, login_url='users:login')
def manage_categories(request):
    filters = ProductCategoryFilter.objects.all().prefetch_related('categories')
    filter_form = ProductCategoryFilterForm()
    category_form = ProductCategoryForm()
    
    context = {
        'filters': filters,
        'filter_form': filter_form,
        'category_form': category_form,
    }
    return render(request, 'home/admin/manage_categories.html', context)

@require_POST
@user_passes_test(admin_required, login_url='users:login')
def add_category_filter(request):
    form = ProductCategoryFilterForm(request.POST)
    if form.is_valid():
        form.save()
        messages.success(request, 'Category filter added successfully.')
    else:
        messages.error(request, 'Error adding category filter.')
    return redirect('home:manage_categories')

@require_POST
@user_passes_test(admin_required, login_url='users:login')
def add_product_category(request):
    form = ProductCategoryForm(request.POST)
    if form.is_valid():
        form.save()
        messages.success(request, 'Product category added successfully.')
    else:
        messages.error(request, 'Error adding product category.')
    return redirect('home:manage_categories')

@require_POST
@user_passes_test(admin_required, login_url='users:login')
def delete_category_filter(request, filter_id):
    category_filter = get_object_or_404(ProductCategoryFilter, id=filter_id)
    category_filter.delete()
    messages.success(request, 'Category filter deleted successfully.')
    return redirect('home:manage_categories')

@require_POST
@user_passes_test(admin_required, login_url='users:login')
def delete_product_category(request, category_id):
    category = get_object_or_404(ProductCategory, id=category_id)
    category.delete()
    messages.success(request, 'Product category deleted successfully.')
    return redirect('home:manage_categories')
