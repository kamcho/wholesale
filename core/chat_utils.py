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
    """Generate context about the product for the AI"""
    # Get categories as a comma-separated string
    categories = ', '.join([cat.name for cat in product.categories.all()]) if product.categories.exists() else 'Not specified'
    
    context = {
        'product_name': product.name,
        'description': product.description,
        'price': str(variation.price) if variation and hasattr(variation, 'price') else 'Not specified',
        'stock': str(variation.stock_quantity) if variation and hasattr(variation, 'stock_quantity') else 'Not specified',
        'category': categories,
        'brand': product.business.name if product.business else 'Not specified',
    }
    
    if variation and hasattr(variation, 'attributes'):
        attributes = ", ".join([f"{attr.name}: {attr.value}" for attr in variation.attributes.all()])
        context['variation_attributes'] = attributes
    
    return context

def get_system_prompt(context):
    """Generate a system prompt with product context"""
    prompt = """You are a helpful shopping assistant for an e-commerce website. 
    Your goal is to assist customers with product information, comparisons, and purchase decisions.
    
    Product Information:
    - Name: {product_name}
    - Description: {description}
    - Price: {price}
    - Stock: {stock}
    - Category: {category}
    - Brand: {brand}
    {variation_info}
    
    Guidelines:
    1. Be friendly, helpful, and concise in your responses.
    2. Focus on the product's features and benefits.
    3. If asked about prices, always mention the current price.
    4. If asked about stock, provide the current availability.
    5. If you don't know an answer, say so honestly.
    6. Don't make up information about the product that isn't provided.
    """
    
    variation_info = f"- Variation: {context.get('variation_attributes', 'N/A')}" if 'variation_attributes' in context else ""
    
    return prompt.format(
        product_name=context['product_name'],
        description=context['description'],
        price=context['price'],
        stock=context['stock'],
        category=context['category'],
        brand=context['brand'],
        variation_info=variation_info
    )
