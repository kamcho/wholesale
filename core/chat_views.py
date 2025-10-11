import json
import traceback
import sys
import json
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.conf import settings

# Debug print function
def debug_print(*args, **kwargs):
    """Print debug information with file and line number"""
    import inspect
    frame = inspect.currentframe().f_back
    print(f"\n[DEBUG] {frame.f_code.co_filename}:{frame.f_lineno} - ", end="")
    print(*args, **{**{'file': sys.stderr}, **kwargs})

# Import models and utilities with error handling
try:
    from home.models import Product, ProductVariation
except Exception as e:
    debug_print(f"Error importing models: {str(e)}")
    raise

try:
    from .chat_utils import get_chat_response, generate_product_context, get_system_prompt
except Exception as e:
    debug_print(f"Error importing chat utilities: {str(e)}")
    debug_print("Traceback:", traceback.format_exc())
    raise

@csrf_exempt
@require_http_methods(["POST"])
def chat_api(request):
    """API endpoint for chat functionality"""
    debug_print("Chat API endpoint called")
    
    try:
        debug_print("Request body:", request.body)
        data = json.loads(request.body)
        debug_print("Parsed data:", data)
        
        user_message = data.get('message', '').strip()
        product_id = data.get('product_id')
        variation_id = data.get('variation_id')
        chat_history = data.get('chat_history', [])
        
        debug_print(f"Message: {user_message}, Product ID: {product_id}, Variation ID: {variation_id}")
        
        if not user_message:
            debug_print("Error: No message provided")
            return JsonResponse({'error': 'Message is required'}, status=400)
            
        # Get variation (and product through variation)
        try:
            debug_print("Attempting to fetch product/variation...")
            if variation_id:
                debug_print(f"Fetching variation with ID: {variation_id}")
                variation = ProductVariation.objects.get(id=variation_id)
                product = variation.product
                debug_print(f"Found variation: {variation.name}, Product: {product.name}")
            elif product_id:
                debug_print(f"Fetching product with ID: {product_id}")
                product = Product.objects.get(id=product_id)
                variation = None
                debug_print(f"Found product: {product.name}")
            else:
                debug_print("Error: Neither product_id nor variation_id provided")
                return JsonResponse({'error': 'Either product_id or variation_id is required'}, status=400)
                
        except Product.DoesNotExist:
            debug_print(f"Product not found with ID: {product_id}")
            return JsonResponse({'error': 'Product not found'}, status=404)
        except ProductVariation.DoesNotExist:
            debug_print(f"Variation not found with ID: {variation_id}")
            return JsonResponse({'error': 'Variation not found'}, status=404)
        except ValueError as ve:
            debug_print(f"ValueError: {str(ve)}")
            return JsonResponse({'error': 'Invalid ID format'}, status=400)
        except Exception as e:
            debug_print(f"Unexpected error fetching product/variation: {str(e)}")
            debug_print("Traceback:", traceback.format_exc())
            return JsonResponse({'error': 'Error retrieving product information'}, status=500)
        
        try:
            # Generate context and system prompt
            debug_print("Generating product context...")
            context = generate_product_context(product, variation)
            debug_print("Context generated successfully")
            
            debug_print("Generating system prompt...")
            system_prompt = get_system_prompt(context)
            debug_print("System prompt generated successfully")
            
            # Prepare messages for the API
            messages = [
                {"role": "system", "content": system_prompt}
            ]
            debug_print(f"System prompt length: {len(system_prompt)} characters")
            
            # Add chat history if available
            if chat_history:
                debug_print(f"Adding {len(chat_history)} messages from chat history")
                for msg in chat_history[-5:]:  # Limit history to last 5 messages
                    role = "user" if msg.get('is_user') else "assistant"
                    messages.append({"role": role, "content": msg.get('text', '')})
            
            # Add current user message
            messages.append({"role": "user", "content": user_message})
            debug_print(f"Total messages to send: {len(messages)}")
            
            # Get response from OpenAI
            debug_print("Sending request to OpenAI...")
            response = get_chat_response(messages)
            debug_print("Received response from OpenAI")
            
            return JsonResponse({
                'response': response,
                'context': {
                    'product_id': product.id,
                    'product_name': product.name,
                    'variation_id': variation.id if variation else None,
                    'variation_name': variation.name if variation else None
                }
            })
            
        except Exception as e:
            debug_print(f"Error in chat processing: {str(e)}")
            debug_print("Traceback:", traceback.format_exc())
            return JsonResponse(
                {
                    'error': 'An error occurred while processing your request',
                    'details': str(e),
                    'type': type(e).__name__
                }, 
                status=500
            )
            
    except json.JSONDecodeError as je:
        debug_print(f"JSON decode error: {str(je)}")
        return JsonResponse(
            {'error': 'Invalid JSON in request body'}, 
            status=400
        )
    except Exception as e:
        debug_print(f"Unexpected error in chat_api: {str(e)}")
        debug_print("Traceback:", traceback.format_exc())
        return JsonResponse(
            {'error': 'An unexpected error occurred'}, 
            status=500
        )
