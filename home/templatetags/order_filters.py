from django import template
from decimal import Decimal

register = template.Library()

@register.filter(name='sum_fees')
def sum_fees(fees):
    """Sum all fee amounts in the given queryset or list of fees."""
    if not fees:
        return Decimal('0.00')
    return sum(fee.amount for fee in fees if hasattr(fee, 'amount'))

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
    subtotal = Decimal('0.00')
    if hasattr(order, 'items'):
        for item in order.items.all():
            subtotal += Decimal(str(item.price)) * item.quantity
    else:
        subtotal = order.subtotal if hasattr(order, 'subtotal') else order.total
    
    # Get other amounts
    shipping = Decimal(str(order.shipping_cost)) if hasattr(order, 'shipping_cost') and order.shipping_cost else Decimal('0.00')
    discount = Decimal(str(order.discount_amount)) if hasattr(order, 'discount_amount') and order.discount_amount else Decimal('0.00')
    
    # Calculate total fees
    total_fees = sum_fees(additional_fees)
    
    # Calculate final total
    total = subtotal + shipping + total_fees - discount
    
    # Ensure total is not negative
    return max(total.quantize(Decimal('0.01')), Decimal('0.00'))
