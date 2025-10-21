from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from home.models import Product, Order, OrderItem, ProductVariation, OrderAdditionalFees
from .forms import VendorOrderForm

@login_required
def create_order(request):
    """
    View for creating a new order as a vendor/manager
    Only accessible to users with Manager role
    """
    if request.user.role != 'Manager':
        messages.error(request, "You don't have permission to access this page.")
        return redirect('vendor:dashboard')
    
    if request.method == 'POST':
        form = VendorOrderForm(request.POST, user=request.user)
        if form.is_valid():
            try:
                order = form.save(commit=False)
                order.user = form.cleaned_data['customer']
                order.status = 'pending'
                order.payment_method = 'cash_on_delivery'  # Default payment method
                order.save()
                
                # Add order items
                for item in form.cleaned_data['items']:
                    variation = item['variation']
                    OrderItem.objects.create(
                        order=order,
                        product=variation.product,
                        variation=variation,
                        quantity=item['quantity'],
                        price=variation.price * item['quantity']
                    )
                
                messages.success(request, f"Order #{order.id} has been created successfully!")
                return redirect('vendor:order_detail', order_id=order.id)
                
            except Exception as e:
                messages.error(request, f"Error creating order: {str(e)}")
    else:
        form = VendorOrderForm(user=request.user)
    
    return render(request, 'vendor/order_create.html', {'form': form})

@login_required
def order_detail(request, order_id):
    """View order details"""
    order = get_object_or_404(Order, id=order_id)
    
    # Verify the order belongs to one of the vendor's products
    # Get vendor products (both from business ownership and direct user ownership)
    vendor_products = Product.objects.filter(
        Q(business__owner=request.user) | Q(user=request.user)
    )
    order_items = order.items.filter(variation__product__in=vendor_products)
    
    if not order_items.exists() and not request.user.is_superuser:
        messages.error(request, "You don't have permission to view this order.")
        return redirect('vendor:dashboard')
    
    # Get additional fees for this order
    additional_fees = OrderAdditionalFees.objects.filter(order=order)
    
    return render(request, 'vendor/order_detail.html', {
        'order': order,
        'order_items': order_items,
        'additional_fees': additional_fees
    })
