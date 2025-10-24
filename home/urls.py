from django.urls import path
from django.contrib.auth import views as auth_views
from . import views, admin_views, chat_views, buyer_seller_chat_views
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
    # M-Pesa API endpoints
    path('api/process-mpesa-payment/', views.process_mpesa_payment, name='process_mpesa_payment'),
    path('api/process-card-payment/', views.process_card_payment, name='process_card_payment'),
    path('api/mpesa-callback/', views.mpesa_callback, name='mpesa_callback'),
    path('api/check-payment-status/<str:checkout_request_id>/', views.check_payment_status, name='check_payment_status'),
    path('api/order-requests/<int:order_request_id>/process-mpesa-payment/', views.process_mpesa_payment_for_order_request, name='process_mpesa_payment_for_order_request'),
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
    
    # Buyer-Seller Chat URLs
    path('start-chat/<int:seller_id>/', buyer_seller_chat_views.start_chat, name='start_chat'),  # product_id can be passed as query parameter
    path('private-chat/<int:chat_id>/', buyer_seller_chat_views.buyer_seller_chat, name='buyer_seller_chat'),
    path('private-chat/<int:chat_id>/create-order/', buyer_seller_chat_views.create_order_from_chat, name='create_order_from_chat'),
    path('chats/', buyer_seller_chat_views.chat_list, name='chat_list'),
    path('private-chat/<int:chat_id>/delete/', buyer_seller_chat_views.delete_chat, name='delete_chat'),
    
    # Old Group Chat URLs (kept for backward compatibility)
    path('group-chat/<int:product_id>/', chat_views.chat_room, name='chat_room'),
    
    # Buyer-Seller Chat API URLs
    path('api/chat/<int:chat_id>/send/', buyer_seller_chat_views.send_message, name='send_message'),
    path('api/chat/<int:chat_id>/messages/', buyer_seller_chat_views.get_messages, name='get_buyer_seller_messages'),
    path('api/chat/<int:chat_id>/mark-read/', buyer_seller_chat_views.mark_messages_read, name='mark_messages_read'),
    
    # Payment Confirmation
    path('confirm-payment/<int:order_id>/', views.confirm_payment, name='confirm_payment'),
    path('api/chat/<int:product_id>/messages/', chat_views.get_messages, name='get_chat_messages'),
]
