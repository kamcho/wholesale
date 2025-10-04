from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.utils import timezone
from .models import ProductVariation, ChatMessage
from .chat_forms import ChatMessageForm

@login_required
def chat_room(request, variation_id):
    variation = get_object_or_404(ProductVariation, id=variation_id)
    messages = ChatMessage.objects.filter(variation=variation).order_by('created_at')
    
    if request.method == 'POST':
        form = ChatMessageForm(request.POST)
        if form.is_valid():
            message = form.save(commit=False)
            message.variation = variation
            message.user = request.user  # Set the current user
            message.save()
            return redirect('home:chat_room', variation_id=variation.id)
    else:
        form = ChatMessageForm()
    
    # Clear any existing messages to prevent them from showing up
    from django.contrib import messages as django_messages
    django_messages.get_messages(request).used = True
    
    return render(request, 'home/chat_room.html', {
        'variation': variation,
        'messages': [],  # Don't pass Django messages to template
        'form': form
    })

@login_required
def get_messages(request, variation_id):
    """API endpoint to get new messages via AJAX"""
    last_message_id = request.GET.get('last_message_id', 0)
    messages = ChatMessage.objects.filter(
        variation_id=variation_id,
        id__gt=last_message_id
    ).order_by('created_at')
    
    messages_data = [{
        'id': msg.id,
        'user': msg.user.username,
        'message': msg.message,
        'created_at': msg.created_at.strftime('%b %d, %Y %I:%M %p'),
        'is_own': msg.user == request.user
    } for msg in messages]
    
    return JsonResponse({'messages': messages_data})
