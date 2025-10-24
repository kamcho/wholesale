from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseForbidden
from django.utils import timezone
from django.db.models import Q, Max
from django.contrib import messages
from django.core.paginator import Paginator
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.urls import reverse
import json

from django.contrib.auth import get_user_model
from .models import Product, BuyerSellerChat, BuyerSellerMessage, Order, OrderItem, ProductVariation
from .forms import BuyerSellerMessageForm

User = get_user_model()


@login_required
def start_chat(request, seller_id):
    """Start a new chat with a seller, optionally about a specific product
    
    URL format: /start-chat/<seller_id>/?product_id=<product_id>
    """
    seller = get_object_or_404(User, id=seller_id)
    
    # Don't allow users to chat with themselves
    if request.user == seller:
        messages.error(request, "You cannot start a chat with yourself.")
        return redirect('home:home')
    
    # Get the product if specified in query parameters
    product = None
    product_id = request.GET.get('product_id')
    if product_id:
        try:
            # First try to get the product by ID only
            product = Product.objects.get(id=product_id)
            # Verify the product belongs to the seller (but don't make it a requirement)
            if hasattr(product, 'business') and product.business.owner != seller:
                messages.warning(request, "This product doesn't belong to the selected seller.")
                # Continue with the product anyway, but show a warning
        except (Product.DoesNotExist, ValueError):
            messages.warning(request, "The specified product was not found.")
            # Continue without the product if it doesn't exist
    
    # Check if a chat already exists
    chat = None
    
    # If product is specified, try to find a chat with the same product first
    if product:
        chat = BuyerSellerChat.objects.filter(
            buyer=request.user,
            seller=seller,
            product=product
        ).first()
    
    # If no chat with product found, try to find any existing chat
    if not chat:
        chat = BuyerSellerChat.objects.filter(
            buyer=request.user,
            seller=seller
        ).first()
    
    # If still no chat exists, create a new one
    if not chat:
        chat = BuyerSellerChat.objects.create(
            buyer=request.user,
            seller=seller,
            product=product
        )
    # If chat exists but product is different, update the product
    elif product and chat.product != product:
        chat.product = product
        chat.save(update_fields=['product'])
    
    print(f"Debug - Product from URL: {request.GET.get('product_id')}")
    print(f"Debug - Product from chat: {chat.product}")
    print(f"Debug - Product variable: {product}")
    
    if product:
        print(f"Debug - Added product to context: {product.name} (ID: {product.id})")
    else:
        print("Debug - No product to add to context")
        chat.save(update_fields=['product'])
    
    # Redirect to the chat page with the product_id in the URL
    return redirect(f"{reverse('home:buyer_seller_chat', args=[chat.id])}?product_id={product.id if product else ''}")


@login_required
def buyer_seller_chat(request, chat_id):
    """Display the chat interface for buyer-seller conversations"""
    chat = get_object_or_404(
        BuyerSellerChat.objects.select_related('buyer', 'seller', 'product'),
        id=chat_id,
        buyer__isnull=False,
        seller__isnull=False
    )
    
    # Check if user is part of this chat
    if request.user not in [chat.buyer, chat.seller]:
        messages.error(request, "You don't have permission to view this chat.")
        return redirect('home:home')
    
    # Initialize product as None
    product = None
    
    # Get product_id from URL if provided
    product_id = request.GET.get('product_id')
    
    # Only process product details if the current user is the buyer
    if request.user == chat.buyer:
        if product_id:
            try:
                product = Product.objects.get(id=product_id)
                # Only update the chat's product if it's not already set
                if not chat.product:
                    chat.product = product
                    chat.save(update_fields=['product'])
            except (Product.DoesNotExist, ValueError):
                messages.warning(request, "The specified product was not found.")
        
        # If no product from URL but chat has a product, use that
        if not product and chat.product:
            product = chat.product
    
    # Get messages for this chat (exclude messages with None sender)
    messages_qs = chat.messages.select_related('sender').filter(sender__isnull=False).order_by('created_at')
    
    # Pagination for messages
    paginator = Paginator(messages_qs, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Mark messages as read when user views the chat
    if request.user == chat.buyer:
        chat.messages.filter(sender=chat.seller, is_read=False).update(is_read=True)
    elif request.user == chat.seller:
        chat.messages.filter(sender=chat.buyer, is_read=False).update(is_read=True)
    
    # Handle message sending
    if request.method == 'POST':
        form = BuyerSellerMessageForm(request.POST)
        if form.is_valid():
            message = form.save(commit=False)
            message.chat = chat
            message.sender = request.user
            # If we have a product in context, associate it with the message
            if product:
                message.product = product
            message.save()
            
            # Update chat's updated_at timestamp
            chat.updated_at = timezone.now()
            chat.save(update_fields=['updated_at'])
            
            # Redirect to the same page to avoid form resubmission
            return redirect('home:buyer_seller_chat', chat_id=chat.id)
    else:
        form = BuyerSellerMessageForm()
    
    # Determine the other participant
    other_user = chat.seller if request.user == chat.buyer else chat.buyer
    
    # Check if current user is the product creator and a manager
    is_manager = request.user.role == 'Manager'
    is_product_creator = chat.product and chat.product.business and chat.product.business.owner == request.user
    is_buyer = request.user == chat.buyer
    
    # Make sure we have the latest product from the chat if it wasn't in the URL
    if not product and chat.product:
        product = chat.product
    
    # Calculate min and max prices for variations
    min_price = None
    max_price = None
    variants_count = 0
    
    if product:
        if hasattr(product, 'variations') and product.variations.exists():
            variations = product.variations.all()
            variants_count = variations.count()
            prices = [v.price for v in variations if v.price is not None]
            if prices:  # Only calculate if we have valid prices
                min_price = min(prices)
                max_price = max(prices)
        elif hasattr(product, 'price'):
            # For products without variations, use the product's price
            min_price = max_price = product.price
    
    # Debug prints
    print(f"\n=== DEBUG - buyer_seller_chat ===")
    print(f"Product from URL param: {request.GET.get('product_id')}")
    print(f"Product from chat: {chat.product}")
    print(f"Product variable: {product}")
    print(f"Product ID in URL: {request.get_full_path()}")
    if product:
        print(f"Product name: {product.name}")
        print(f"Product has images: {product.images.exists()}")
        print(f"Min price: {min_price}, Max price: {max_price}, Variants: {variants_count}")
        if product.images.exists():
            print(f"First image URL: {product.images.first().image.url}")
    
    context = {
        'chat': chat,
        'other_user': other_user,
        'messages': page_obj,
        'form': form,
        'is_buyer': is_buyer,
        'is_manager': is_manager,
        'is_product_creator': is_product_creator,
        'product': product,  # Make sure product is passed to the template
        'min_price': min_price,
        'max_price': max_price,
        'variants_count': variants_count,
    }
    
    return render(request, 'home/buyer_seller_chat.html', context)


@login_required
def create_order_from_chat(request, chat_id):
    """Create an order from a chat conversation"""
    chat = get_object_or_404(BuyerSellerChat, id=chat_id)
    
    # Check if user is the product creator and a manager
    is_manager = request.user.role == 'Manager'
    is_product_creator = chat.product and chat.product.business and chat.product.business.owner == request.user
    
    if not (is_manager and is_product_creator and request.user == chat.seller):
        return HttpResponseForbidden("You don't have permission to create an order from this chat.")
    
    # Get the first variation of the product (you might want to modify this logic)
    variation = chat.product.variations.first()
    if not variation:
        messages.error(request, "This product has no variations available for ordering.")
        return redirect('home:buyer_seller_chat', chat_id=chat.id)
    
    try:
        # Create the order
        order = Order.objects.create(
            user=chat.buyer,
            status='pending',
            total=variation.price,  # You might want to calculate this based on quantity
            payment_method='cash_on_delivery',  # Default payment method
        )
        
        # Add order item
        OrderItem.objects.create(
            order=order,
            product=chat.product,
            variation=variation,
            quantity=1,  # Default quantity, you might want to make this configurable
            price=variation.price,
        )
        
        messages.success(request, f"Order #{order.id} has been created successfully!")
        return redirect('home:order_detail', order_id=order.id)
        
    except Exception as e:
        messages.error(request, f"Error creating order: {str(e)}")
        return redirect('home:buyer_seller_chat', chat_id=chat.id)


@login_required
def chat_list(request):
    """Display list of all chats for the current user"""
    # Get all chats where user is either buyer or seller, and both users exist
    chats = BuyerSellerChat.objects.filter(
        Q(buyer=request.user) | Q(seller=request.user),
        buyer__isnull=False,
        seller__isnull=False
    ).select_related('buyer', 'seller', 'product').prefetch_related('messages').order_by('-updated_at')
    
    # Add unread count for each chat
    for chat in chats:
        if request.user == chat.buyer:
            chat.unread_count = chat.messages.filter(sender=chat.seller, is_read=False).count()
        else:
            chat.unread_count = chat.messages.filter(sender=chat.buyer, is_read=False).count()
    
    # Pagination
    paginator = Paginator(chats, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'chats': page_obj,
        'title': 'My Chats'
    }
    
    return render(request, 'home/chat_list.html', context)


@login_required
@require_http_methods(["POST"])
def send_message(request, chat_id):
    """API endpoint to send a message via AJAX"""
    chat = get_object_or_404(BuyerSellerChat, id=chat_id)
    
    # Check if user is part of this chat
    if request.user not in [chat.buyer, chat.seller]:
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    try:
        data = json.loads(request.body)
        message_text = data.get('message', '').strip()
        
        if not message_text:
            return JsonResponse({'error': 'Message cannot be empty'}, status=400)
        
        # Get product from request data or URL
        product = None
        product_id = data.get('product_id')
        
        # If product_id is in the request data, get the product
        if product_id:
            try:
                product = Product.objects.get(id=product_id)
            except (Product.DoesNotExist, ValueError):
                pass
        # Otherwise, use the chat's product if it exists and matches the request
        elif chat.product and 'product_id' in request.GET:
            product = chat.product
        
        # Create message with the product
        message = BuyerSellerMessage.objects.create(
            chat=chat,
            sender=request.user,
            message=message_text,
            product=product
        )
        
        # Update chat's updated_at timestamp
        chat.updated_at = timezone.now()
        chat.save(update_fields=['updated_at'])
        
        # Get sender display name
        if hasattr(message.sender, 'get_full_name') and message.sender.get_full_name():
            sender_name = message.sender.get_full_name()
        elif message.sender.email:
            sender_name = message.sender.email
        else:
            sender_name = 'Unknown User'
            
        return JsonResponse({
            'success': True,
            'message': {
                'id': message.id,
                'text': message.message,
                'sender': sender_name,
                'created_at': message.created_at.strftime('%b %d, %Y %I:%M %p'),
                'is_own': message.sender == request.user
            }
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def get_messages(request, chat_id):
    """API endpoint to get new messages via AJAX"""
    chat = get_object_or_404(BuyerSellerChat, id=chat_id)
    
    # Check if user is part of this chat
    if request.user not in [chat.buyer, chat.seller]:
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    last_message_id = request.GET.get('last_message_id', 0)
    messages = chat.messages.filter(
        id__gt=last_message_id,
        sender__isnull=False
    ).select_related('sender', 'product').order_by('created_at')
    
    messages_data = []
    for msg in messages:
        if msg.sender:
            # Get sender display name
            if hasattr(msg.sender, 'get_full_name') and msg.sender.get_full_name():
                sender_name = msg.sender.get_full_name()
            elif msg.sender.email:
                sender_name = msg.sender.email
            else:
                sender_name = 'Unknown User'
        else:
            sender_name = 'Unknown User'
            
        message_data = {
            'id': msg.id,
            'text': msg.message,
            'sender': sender_name,
            'created_at': msg.created_at.strftime('%b %d, %Y %I:%M %p'),
            'is_own': msg.sender == request.user
        }
        
        # Add product data if exists
        if msg.product:
            # Get the first product image URL if available
            image_url = None
            if hasattr(msg.product, 'images') and msg.product.images.exists():
                first_image = msg.product.images.first()
                if first_image and hasattr(first_image, 'image'):
                    image_url = first_image.image.url
            
            message_data['product'] = {
                'id': msg.product.id,
                'name': msg.product.name,
                'price': str(msg.product.price) if hasattr(msg.product, 'price') else None,
                'image_url': image_url
            }
            
        messages_data.append(message_data)
    
    return JsonResponse({'messages': messages_data})


@login_required
@require_http_methods(["POST"])
def mark_messages_read(request, chat_id):
    """Mark messages as read for the current user"""
    chat = get_object_or_404(BuyerSellerChat, id=chat_id)
    
    # Check if user is part of this chat
    if request.user not in [chat.buyer, chat.seller]:
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    # Mark messages from the other user as read
    other_user = chat.seller if request.user == chat.buyer else chat.buyer
    updated_count = chat.messages.filter(
        sender=other_user,
        is_read=False
    ).update(is_read=True)
    
    return JsonResponse({
        'success': True,
        'updated_count': updated_count
    })


@login_required
def delete_chat(request, chat_id):
    """Delete a chat (soft delete by setting is_active=False)"""
    chat = get_object_or_404(BuyerSellerChat, id=chat_id)
    
    # Check if user is part of this chat
    if request.user not in [chat.buyer, chat.seller]:
        messages.error(request, "You don't have permission to delete this chat.")
        return redirect('home:chat_list')
    
    # Soft delete the chat
    chat.is_active = False
    chat.save(update_fields=['is_active'])
    
    return redirect('home:chat_list')
