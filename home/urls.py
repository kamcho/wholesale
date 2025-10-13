from django.urls import path
from django.contrib.auth import views as auth_views
from . import views, admin_views, chat_views
from .views import AgentListView

app_name = 'home'

urlpatterns = [
    path('', views.home, name='home'),
    path('signup/', views.SignUpView.as_view(), name='signup'),
    path('products/', views.product_list, name='product_list'),
    path('products/<int:pk>/', views.product_detail, name='product_detail'),
    path('variations/<int:pk>/', views.variation_detail, name='variation_detail'),
    path('products/<int:pk>/order/', views.create_product_order, name='create_product_order'),
    path('products/<int:pk>/order/create/', views.product_order_create, name='product_order_create'),
    path('orders/<int:order_id>/confirm/', views.product_order_payment, name='product_order_payment'),
    path('orders/<int:order_id>/', views.order_detail, name='order_detail'),
    path('order-requests/<int:order_request_id>/', views.order_request_detail, name='order_request_detail'),
    path('category/<int:category_id>/', views.category_products, name='category_products'),
    path('cart/add/', views.add_to_cart, name='add_to_cart'),
    path('cart/remove/', views.remove_from_cart, name='remove_from_cart'),
    path('cart/', views.cart_detail, name='cart_detail'),
    path('cart/item/<int:item_id>/update/', views.update_cart_item, name='update_cart_item'),
    path('cart/item/<int:item_id>/remove/', views.remove_cart_item, name='remove_cart_item'),
    path('cart/clear/', views.clear_cart, name='clear_cart'),
    
    # Quick Checkout
    path('quick-checkout/', views.quick_checkout, name='quick_checkout'),
    path('quick-checkout/page/', views.quick_checkout_page, name='quick_checkout_page'),
    path('api/create-order/', views.create_order, name='create_order'),
    path('api/create-order-request/', views.create_order_request, name='create_order_request'),
    path('api/process-mpesa-payment/', views.process_mpesa_payment, name='process_mpesa_payment'),
    path('wishlist/', views.wishlist_list, name='wishlist'),
    path('wishlist/add/', views.add_to_wishlist, name='add_to_wishlist'),
    path('wishlist/item/<int:item_id>/remove/', views.remove_from_wishlist, name='remove_from_wishlist'),
    
    # Agent List
    path('agents/', AgentListView.as_view(), name='agent_list'),
    
    path('checkout/', views.checkout, name='checkout'),
    path('order-history/', views.order_history, name='order_history'),
    
    # Admin category management
    path('manage/categories/', admin_views.manage_categories, name='manage_categories'),
    path('manage/categories/filter/add/', admin_views.add_category_filter, name='add_category_filter'),
    path('manage/categories/filter/<int:filter_id>/delete/', admin_views.delete_category_filter, name='delete_category_filter'),
    path('manage/categories/category/<int:category_id>/delete/', admin_views.delete_product_category, name='delete_product_category'),
    
    # Chat URLs
    path('chat/<int:product_id>/', chat_views.chat_room, name='chat_room'),
    
    # Payment Confirmation
    path('confirm-payment/<int:order_id>/', views.confirm_payment, name='confirm_payment'),
    path('api/chat/<int:product_id>/messages/', chat_views.get_messages, name='get_chat_messages'),
]
