from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.utils import timezone
from django.db.models import Q, Max
from django.contrib import messages
from django.core.paginator import Paginator
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
import json

from django.contrib.auth import get_user_model
from .models import Product, BuyerSellerChat, BuyerSellerMessage
from .forms import BuyerSellerMessageForm

User = get_user_model()


@login_required
def start_chat(request, seller_id, product_id=None):
    """Start a new chat with a seller, optionally about a specific product"""
    seller = get_object_or_404(User, id=seller_id)
    
    # Don't allow users to chat with themselves
    if request.user == seller:
        messages.error(request, "You cannot start a chat with yourself.")
        return redirect('home:home')
    
    # Get the product if specified
    product = None
    if product_id:
        product = get_object_or_404(Product, id=product_id)
    
    # Check if a chat already exists
    chat = BuyerSellerChat.objects.filter(
        buyer=request.user,
        seller=seller,
        product=product
    ).first()
    
    if not chat:
        # Create new chat
        chat = BuyerSellerChat.objects.create(
            buyer=request.user,
            seller=seller,
            product=product
        )
    
    return redirect('home:buyer_seller_chat', chat_id=chat.id)


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
            message.save()
            
            # Update chat's updated_at timestamp
            chat.updated_at = timezone.now()
            chat.save(update_fields=['updated_at'])
            
            return redirect('home:buyer_seller_chat', chat_id=chat.id)
    else:
        form = BuyerSellerMessageForm()
    
    # Determine the other participant
    other_user = chat.seller if request.user == chat.buyer else chat.buyer
    
    context = {
        'chat': chat,
        'other_user': other_user,
        'messages': page_obj,
        'form': form,
        'is_buyer': request.user == chat.buyer,
    }
    
    return render(request, 'home/buyer_seller_chat.html', context)


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
        
        # Create message
        message = BuyerSellerMessage.objects.create(
            chat=chat,
            sender=request.user,
            message=message_text
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
    ).select_related('sender').order_by('created_at')
    
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
            
        messages_data.append({
            'id': msg.id,
            'text': msg.message,
            'sender': sender_name,
            'created_at': msg.created_at.strftime('%b %d, %Y %I:%M %p'),
            'is_own': msg.sender == request.user
        })
    
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
