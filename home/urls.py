from django.urls import path
from . import views
from . import chat_views

app_name = 'home'

urlpatterns = [
    path('', views.home, name='home'),
    path('products/', views.product_list, name='product_list'),
    path('products/<int:pk>/', views.product_detail, name='product_detail'),
    path('variations/<int:pk>/', views.variation_detail, name='variation_detail'),
    path('products/<int:pk>/order/', views.create_product_order, name='create_product_order'),
    path('products/<int:pk>/order/create/', views.product_order_create, name='product_order_create'),
    path('orders/<int:order_id>/confirm/', views.product_order_payment, name='product_order_payment'),
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
    path('api/process-mpesa-payment/', views.process_mpesa_payment, name='process_mpesa_payment'),
    path('confirm-payment/<int:order_id>/', views.confirm_payment, name='confirm_payment'),
    
    # Wishlist
    path('wishlist/', views.wishlist_list, name='wishlist'),
    path('wishlist/add/', views.add_to_wishlist, name='add_to_wishlist'),
    path('wishlist/item/<int:item_id>/remove/', views.remove_from_wishlist, name='remove_from_wishlist'),
    
    # Order History
    path('my-orders/', views.order_history, name='order_history'),
    
    # Chat URLs
    path('chat/<int:product_id>/', chat_views.chat_room, name='chat_room'),
    path('api/chat/<int:product_id>/messages/', chat_views.get_messages, name='get_chat_messages'),
]

