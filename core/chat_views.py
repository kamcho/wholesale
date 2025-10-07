import json
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.conf import settings

from home.models import Product, ProductVariation
from .chat_utils import get_chat_response, generate_product_context, get_system_prompt

@csrf_exempt
@require_http_methods(["POST"])
def chat_api(request):
    """API endpoint for chat functionality"""
    try:
        data = json.loads(request.body)
        user_message = data.get('message', '').strip()
        product_id = data.get('product_id')
        variation_id = data.get('variation_id')
        chat_history = data.get('chat_history', [])
        
        if not user_message:
            return JsonResponse({'error': 'Message is required'}, status=400)
            
        # Get variation (and product through variation)
        try:
            if variation_id:
                variation = ProductVariation.objects.get(id=variation_id)
                product = variation.product
            elif product_id:
                product = Product.objects.get(id=product_id)
                variation = None
            else:
                return JsonResponse({'error': 'Either product_id or variation_id is required'}, status=400)
        except (Product.DoesNotExist, ProductVariation.DoesNotExist, ValueError):
            return JsonResponse({'error': 'Product or variation not found'}, status=404)
        
        # Generate context and system prompt
        context = generate_product_context(product, variation)
        system_prompt = get_system_prompt(context)
        
        # Prepare messages for the API
        messages = [
            {"role": "system", "content": system_prompt}
        ]
        
        # Add chat history if available
        if chat_history:
            for msg in chat_history[-5:]:  # Limit history to last 5 messages
                role = "user" if msg.get('is_user') else "assistant"
                messages.append({"role": role, "content": msg.get('text', '')})
        
        # Add current user message
        messages.append({"role": "user", "content": user_message})
        
        # Get response from OpenAI
        response = get_chat_response(messages)
        
        return JsonResponse({
            'response': response,
            'context': context
        })
        
    except Exception as e:
        return JsonResponse(
            {'error': f'An error occurred: {str(e)}'}, 
            status=500
        )
