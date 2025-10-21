from django import template
from decimal import Decimal

register = template.Library()

@register.filter(name='sum_fees')
def sum_fees(fees):
    """Sum all fee amounts in the given queryset or list of fees."""
    if not fees:
        return Decimal('0.00')
    return sum(fee.amount for fee in fees if hasattr(fee, 'amount'))

@register.filter(name='calculate_subtotal')
def calculate_subtotal(items):
    """Calculate subtotal from order items."""
    if not items:
        return Decimal('0.00')
    return sum(item.price * item.quantity for item in items if hasattr(item, 'price') and hasattr(item, 'quantity'))

@register.filter(name='calculate_order_total')
def calculate_order_total(order, additional_fees):
    """
    Calculate the total order amount including additional fees.
    
    Args:
        order: The order object
        additional_fees: List of OrderAdditionalFees objects
        
    Returns:
        Decimal: The total amount including all fees
    """
    # Calculate subtotal from order items
    if hasattr(order, 'items'):
        subtotal = calculate_subtotal(order.items.all())
    else:
        subtotal = Decimal(str(order.subtotal)) if hasattr(order, 'subtotal') else Decimal(str(order.total))
    
    # Get other amounts
    shipping = Decimal(str(order.shipping_cost)) if hasattr(order, 'shipping_cost') and order.shipping_cost else Decimal('0.00')
    discount = Decimal(str(order.discount_amount)) if hasattr(order, 'discount_amount') and order.discount_amount else Decimal('0.00')
    
    # Calculate total fees
    total_fees = sum_fees(additional_fees)
    
    # Calculate final total
    total = subtotal + shipping + total_fees - discount
    
    # Ensure total is not negative and properly rounded
    return max(total.quantize(Decimal('0.01')), Decimal('0.00'))
