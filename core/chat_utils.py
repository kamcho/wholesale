import os
from openai import OpenAI
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Initialize OpenAI client
try:
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        print("Warning: OPENAI_API_KEY not found in environment variables. Chat functionality will be disabled.")
        client = None
    else:
        client = OpenAI(api_key=api_key)
except Exception as e:
    print(f"Error initializing OpenAI client: {str(e)}")
    client = None

def get_chat_response(messages, model="gpt-3.5-turbo", temperature=0.7, max_tokens=500):
    """
    Get a response from OpenAI's chat completion API
    
    Args:
        messages (list): List of message dictionaries with 'role' and 'content'
        model (str): OpenAI model to use
        temperature (float): Controls randomness (0-2)
        max_tokens (int): Maximum number of tokens to generate
        
    Returns:
        str: Generated response from the model
    """
    if not client:
        return "I'm sorry, the AI chat service is not configured. Please contact support."
    
    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Error in get_chat_response: {str(e)}")
        return "I'm sorry, I'm having trouble connecting to the chat service. Please try again later."

def generate_product_context(product, variation=None):
    """Generate comprehensive context about the product and its variations for the AI"""
    from home.models import ProductImage, ProductAttribute  # Import models here to avoid circular imports
    
    # Get categories with details
    categories = [{
        'id': cat.id,
        'name': cat.name,
        'description': getattr(cat, 'description', '')
    } for cat in product.categories.all()] if product.categories.exists() else []

    # Get product images
    product_images = [{
        'id': img.id,
        'image_url': img.image.url if img.image else None,
        'alt_text': getattr(img, 'alt_text', f"Image of {product.name}"),
        'is_primary': getattr(img, 'is_primary', False)
    } for img in product.images.all()]

    # Get all variations for this product with related data
    variations = []
    for var in product.variations.all().select_related('product'):
        # Parse the name field to extract attribute information
        attributes = []
        try:
            # Try to parse name in format "Attribute: Value"
            if ': ' in var.name:
                attr_name, attr_value = var.name.split(': ', 1)
                attributes.append({
                    'name': attr_name.strip(),
                    'value': attr_value.strip()
                })
            else:
                # If not in standard format, just use the whole name as value
                attributes.append({
                    'name': 'Variant',
                    'value': var.name.strip()
                })
        except Exception as e:
            debug_print(f"Error parsing variation name '{var.name}': {str(e)}")
            attributes.append({
                'name': 'Variant',
                'value': var.name.strip() if var.name else 'Unnamed Variant'
            })
            
        variation_data = {
            'id': var.id,
            'name': var.name,
            'moq': var.moq,
            'price': str(var.price),
            'created_at': var.created_at.isoformat() if var.created_at else None,
            'updated_at': var.updated_at.isoformat() if var.updated_at else None,
            'closes_on': var.closes_on.isoformat() if var.closes_on else None,
            'attributes': attributes,
            'price_tiers': [{
                'min_quantity': tier.min_quantity,
                'max_quantity': tier.max_quantity,
                'price': str(tier.price)
            } for tier in var.price_tiers.all()]
        }
        
        # Add KB data for this variation if it exists
        try:
            kb_entry = var.kb.first()
            if kb_entry and kb_entry.content:
                variation_data['kb_data'] = kb_entry.content
        except Exception as e:
            print(f"Error fetching KB data for variation {var.id}: {str(e)}")
            
        variations.append(variation_data)

    # Get product KB data
    product_kb = None
    try:
        kb_entry = product.kb.first()
        if kb_entry and kb_entry.content:
            product_kb = kb_entry.content
    except Exception as e:
        print(f"Error fetching product KB data: {str(e)}")

    # Build the complete context
    context = {
        'product': {
            'id': product.id,
            'name': product.name,
            'description': product.description,
            'moq': getattr(product, 'moq', 1),  # Default MOQ to 1 if not set
            'created_at': product.created_at.isoformat() if product.created_at else None,
            'updated_at': product.updated_at.isoformat() if product.updated_at else None,
            'categories': categories,
            'images': product_images,
            'kb_data': product_kb,
            # Add business info if available
            'business': {
                'id': product.business.id if hasattr(product, 'business') and product.business else None,
                'name': product.business.name if hasattr(product, 'business') and product.business else 'No Business',
            } if hasattr(product, 'business') else {}
        },
        'variations': variations,
        'current_variation_id': variation.id if variation else None,
        'total_variations': len(variations)
    }
    
    return context

def get_system_prompt(context):
    """Generate a comprehensive system prompt with detailed product context"""
    product = context['product']
    variations = context.get('variations', [])
    current_variation_id = context.get('current_variation_id')
    
    # Format product information
    product_info = f"""
    PRODUCT INFORMATION:
    - Name: {product['name']}
    - Description: {product['description']}
    - MOQ: {product.get('moq', 1)} units
    - Business: {product.get('business', {}).get('name', 'Not specified')}
    - Categories: {', '.join([cat['name'] for cat in product.get('categories', [])]) or 'None'}
    - Images: {len(product.get('images', []))} available
    - Last Updated: {product.get('updated_at', 'N/A')}
    """
    
    # Format variations information
    variations_info = ""
    if variations:
        variations_info = "\nPRODUCT VARIATIONS:\n"
        for i, var in enumerate(variations, 1):
            is_current = " (Current Selection)" if var['id'] == current_variation_id else ""
            variations_info += f"""
            {i}. {var['name']}{is_current}
               - ID: {var['id']}
               - MOQ: {var.get('moq', 1)} units
               - Price: ${var['price']}
               - Created: {var.get('created_at', 'N/A')}
               - Attributes: {', '.join([f"{attr['name']}: {attr['value']}" for attr in var.get('attributes', [])]) or 'None'}
               - Price Tiers: {', '.join([f"{tier['min_quantity']}+: ${tier['price']}" for tier in var.get('price_tiers', [])]) or 'None'}
            """
    
    # Format product KB data if available
    kb_info = ""
    if product.get('kb_data'):
        kb_info = "\nPRODUCT KNOWLEDGE BASE:\n"
        if isinstance(product['kb_data'], dict):
            kb_info += '\n'.join([f"- {k}: {v}" for k, v in product['kb_data'].items()])
        else:
            kb_info += str(product['kb_data'])
    
    # Format variation KB data
    variation_kb_info = ""
    for var in variations:
        if var.get('kb_data'):
            variation_kb_info += f"\nKNOWLEDGE BASE FOR VARIATION '{var['name']}':\n"
            if isinstance(var['kb_data'], dict):
                variation_kb_info += '\n'.join([f"- {k}: {v}" for k, v in var['kb_data'].items()])
            else:
                variation_kb_info += str(var['kb_data'])
    
    # Combine all information
    full_context = f"""You are an AI shopping assistant for an e-commerce website. Your goal is to assist customers with product information, comparisons, and purchase decisions.
    
    {product_info}
    {variations_info}
    {kb_info}
    {variation_kb_info}
    
    GUIDELES FOR RESPONDING:
    1. Be friendly, helpful, and concise in your responses.
    2. Use the detailed product and variation information provided to answer questions accurately.
    3. When discussing prices, always mention if there's a sale price available.
    4. For stock inquiries, provide the exact stock quantity for specific variations when asked.
    5. If asked to compare variations, highlight the differences in attributes, prices, and availability.
    6. For technical specifications or details, refer to the knowledge base sections.
    7. If you don't know an answer, say so honestly instead of making up information.
    8. When showing prices, always include the currency (assume USD if not specified).
    9. If a specific variation is selected, focus on that variation's details unless asked about others.
    10. For product images, mention that multiple views are available but don't describe them unless specifically asked.
    """
    
    return full_context
