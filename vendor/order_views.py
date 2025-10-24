from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Sum
from django.http import JsonResponse, HttpResponseRedirect, HttpResponseBadRequest
from django.views.decorators.http import require_http_methods, require_POST
from django.views.decorators.csrf import csrf_exempt
from django.urls import reverse
from django.views.decorators.http import require_http_methods
from decimal import Decimal
import json

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
    
    # Get payment information
    payment_info = None
    payment_requests = []
    try:
        from home.models import Payment, RawPayment, PaymentRequest
        
        # Get payment record if exists
        payment_record = Payment.objects.filter(order_id=order).select_related('raw_payment').first()
        if payment_record and payment_record.raw_payment:
            raw_payment = payment_record.raw_payment
            payment_info = {
                'status': 'completed',
                'transaction_id': raw_payment.transaction_id,
                'mpesa_receipt': raw_payment.mpesa_receipt,
                'phone_number': raw_payment.phone_number,
                'amount': str(raw_payment.amount),
                'created_at': raw_payment.created_at,
                'is_successful': True
            }
        else:
            payment_info = {
                'status': 'pending' if order.status == 'pending' else 'failed',
                'is_successful': False
            }
            
        # Get payment requests for this order
        payment_requests = PaymentRequest.objects.filter(
            order=order
        ).order_by('-created_at')
            
    except Exception as e:
        payment_info = {'status': 'error', 'error': str(e), 'is_successful': False}
    
    # Define allowed statuses that can be set by vendors
    allowed_statuses = ['processing', 'shipped', 'delivered']
    
    return render(request, 'vendor/order_detail.html', {
        'order': order,
        'order_items': order_items,
        'additional_fees': additional_fees,
        'payment_info': payment_info,
        'payment_requests': payment_requests,
        'status_choices': Order.STATUS_CHOICES,
        'allowed_statuses': allowed_statuses
    })

@login_required
@require_http_methods(['POST'])
def update_order_status(request, order_id):
    """Update order status via AJAX"""
    order = get_object_or_404(Order, id=order_id)
    
    # Verify the order belongs to one of the vendor's products
    vendor_products = Product.objects.filter(
        Q(business__owner=request.user) | Q(user=request.user)
    )
    order_items = order.items.filter(variation__product__in=vendor_products)
    
    if not order_items.exists() and not request.user.is_superuser:
        return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)
    
    status = request.POST.get('status')
    if not status:
        return JsonResponse({'success': False, 'error': 'Status is required'}, status=400)
    
    valid_statuses = dict(Order.STATUS_CHOICES).keys()
    if status not in valid_statuses:
        return JsonResponse({'success': False, 'error': 'Invalid status'}, status=400)
    
    try:
        order.status = status
        order.save(update_fields=['status', 'updated_at'])
        
        # If marking as paid, update payment status if not already paid
        if status == 'paid' and order.payment_status != 'paid':
            order.payment_status = 'paid'
            order.save(update_fields=['payment_status', 'updated_at'])
        
        return JsonResponse({
            'success': True,
            'message': f'Order status updated to {order.get_status_display()}',
            'status': status,
            'status_display': order.get_status_display()
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
def add_order_fee(request, order_id):
    """Add an additional fee to an order"""
    order = get_object_or_404(Order, id=order_id)
    
    # Verify the order belongs to one of the vendor's products
    vendor_products = Product.objects.filter(
        Q(business__owner=request.user) | Q(user=request.user)
    )
    order_items = order.items.filter(variation__product__in=vendor_products)
    
    if not order_items.exists() and not request.user.is_superuser:
        messages.error(request, "You don't have permission to modify this order.")
        return redirect('vendor:order_detail', order_id=order_id)
    
    if request.method == 'POST':
        fee_type = request.POST.get('fee_type')
        amount = request.POST.get('amount')
        description = request.POST.get('description', '')
        pay_now = request.POST.get('pay_now', 'off') == 'on'  # Get checkbox value
        
        if not fee_type or not amount:
            messages.error(request, 'Fee type and amount are required.')
            return redirect('vendor:order_detail', order_id=order_id)
        
        try:
            amount = Decimal(amount)
            if amount <= 0:
                raise ValueError('Amount must be greater than 0')
                
            # Create the fee without the created_by field since it's not in the model
            fee = OrderAdditionalFees.objects.create(
                order=order,
                fee_type=fee_type,
                amount=amount,
                description=description,
                pay_now=pay_now
            )
            
            # Don't update order total here to avoid NOT NULL constraint
            # The total will be calculated dynamically in the template
            # using the order's calculate_total() method
            
            messages.success(request, 'Additional fee added successfully.')
        except (ValueError, TypeError) as e:
            messages.error(request, f'Invalid amount: {str(e)}')
        except Exception as e:
            messages.error(request, f'Error adding fee: {str(e)}')
    
    return redirect('vendor:order_detail', order_id=order_id)


@csrf_exempt
@require_http_methods(["POST"])
def update_payment_split(request, order_id):
    """Update the payment split between pay now and pay later amounts"""
    try:
        # Verify authentication
        if not request.user.is_authenticated:
            return JsonResponse({
                'success': False,
                'error': 'Authentication required.'
            }, status=401)
            
        order = get_object_or_404(Order, id=order_id)
        
        # Verify the order belongs to one of the vendor's products
        vendor_products = Product.objects.filter(
            Q(business__owner=request.user) | Q(user=request.user)
        )
        order_items = order.items.filter(variation__product__in=vendor_products)
        
        if not order_items.exists() and not request.user.is_superuser:
            return JsonResponse({
                'success': False,
                'error': 'You do not have permission to modify this order.'
            }, status=403)
        
        # Parse JSON data
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'error': 'Invalid JSON data.'
            }, status=400)
            
        pay_now = data.get('pay_now')
        if pay_now is None:
            return JsonResponse({
                'success': False,
                'error': 'Missing required field: pay_now'
            }, status=400)
            
        try:
            pay_now = Decimal(str(pay_now))
        except (ValueError, TypeError):
            return JsonResponse({
                'success': False,
                'error': 'Invalid pay_now amount.'
            }, status=400)
        
        # Update payment split
        try:
            pay_now, pay_later = order.update_payment_split(pay_now)
            
            return JsonResponse({
                'success': True,
                'pay_now': str(pay_now),
                'pay_later': str(pay_later),
                'total': str(order.get_total_cost())
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': f'Error updating payment split: {str(e)}'
            }, status=500)
            
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Server error: {str(e)}'
        }, status=500)

@login_required
def delete_order_fee(request, fee_id):
    """Delete an additional fee from an order"""
    fee = get_object_or_404(OrderAdditionalFees, id=fee_id)
    order = fee.order
    
    # Verify the order belongs to one of the vendor's products
    vendor_products = Product.objects.filter(
        Q(business__owner=request.user) | Q(user=request.user)
    )
    order_items = order.items.filter(variation__product__in=vendor_products)
    
    if not order_items.exists() and not request.user.is_superuser:
        messages.error(request, "You don't have permission to modify this order.")
        return redirect('vendor:order_detail', order_id=order.id)
    
    if request.method == 'POST':
        try:
            order = fee.order
            fee.delete()
            
            # Don't update order total here to avoid NOT NULL constraint
            # The total will be calculated dynamically in the template
            # using the order's calculate_total() method
            
            messages.success(request, 'Fee removed successfully.')
        except Exception as e:
            messages.error(request, f'Error removing fee: {str(e)}')
    
    return redirect(request.META.get('HTTP_REFERER', 'vendor:order_detail', order_id=order.id))
