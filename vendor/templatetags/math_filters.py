from django import template
from decimal import Decimal

register = template.Library()

@register.filter(name='sub')
def sub(value, arg):
    """Subtract the arg from the value"""
    try:
        return float(value) - float(arg)
    except (ValueError, TypeError):
        try:
            return value - arg
        except Exception:
            return ''

@register.filter(name='multiply')
def multiply(value, arg):
    """Multiply the value by the arg"""
    try:
        # Try to convert to Decimal first for precision with monetary values
        return Decimal(str(value)) * Decimal(str(arg))
    except (ValueError, TypeError):
        try:
            # Fallback to float if Decimal conversion fails
            return float(value) * float(arg)
        except (ValueError, TypeError):
            try:
                # Last resort, try native multiplication
                return value * arg
            except Exception:
                return ''
