from .models import Cart


def cart_info(request):
    """Expose cart item count (and optionally total) to all templates."""
    try:
        if request.user.is_authenticated:
            cart = Cart.objects.filter(user=request.user).first()
        else:
            session_id = request.session.session_key
            if not session_id:
                return {'cart_count': 0}
            cart = Cart.objects.filter(session_id=session_id, user=None).first()
        if not cart:
            return {'cart_count': 0}
        count = cart.items.count()
        return {'cart_count': count}
    except Exception:
        return {'cart_count': 0}


