from django.urls import path
from . import views

app_name = 'vendor'

urlpatterns = [
    # Dashboard
    path('', views.vendor_dashboard, name='dashboard'),
    
    # Business management
    path('businesses/', views.business_list, name='business_list'),
    path('businesses/add/', views.add_business, name='add_business'),
    path('businesses/<int:pk>/edit/', views.edit_business, name='edit_business'),
    
    # Product management
    path('products/', views.product_list, name='product_list'),
    path('products/add/', views.add_product, name='add_product'),
    path('products/<int:pk>/', views.product_detail, name='product_detail'),
    path('products/<int:pk>/edit/', views.edit_product, name='edit_product'),
    path('products/<int:pk>/delete/', views.delete_product, name='delete_product'),
    path('products/<int:pk>/add-image/', views.add_product_image, name='add_product_image'),
    path('products/<int:pk>/add-variation/', views.add_product_variation, name='add_product_variation'),
    path('variations/<int:pk>/edit/', views.edit_product_variation, name='edit_product_variation'),
    path('variations/<int:pk>/', views.variation_detail, name='variation_detail'),
    path('variations/<int:pk>/add-image/', views.add_variation_image, name='add_variation_image'),
    path('variations/<int:pk>/add-attribute/', views.add_variation_attribute, name='add_variation_attribute'),
    
    # Orders
    path('orders/', views.orders, name='orders'),
    path('order-requests/', views.order_requests, name='order_requests'),
    path('order-requests/vendor/<int:pk>/', views.order_request_detail, name='vendor_order_request_detail'),
    path('order-requests/<int:pk>/update-status/', views.order_request_update_status, name='order_request_update_status'),
    
    # AJAX endpoints
    path('ajax/categories/', views.get_categories, name='get_categories'),
    
    # Price tiers
    path('price-tiers/<int:pk>/delete/', views.delete_price_tier, name='delete_price_tier'),
    
    # Promise fee
    path('promise-fees/<int:pk>/delete/', views.delete_promise_fee, name='delete_promise_fee'),
]

