import json
from django import forms
from django.contrib.auth import get_user_model
from django.forms import inlineformset_factory, formset_factory, BaseFormSet
from home.models import Product, ProductCategory, Business, ProductImage, ProductCategoryFilter, ProductVariation, ProductAttributeAssignment, ProductAttributeValue, PriceTier, PromiseFee, ProductKB, IRate, Order, OrderItem, BuyerSellerChat

User = get_user_model()


class ProductForm(forms.ModelForm):
    """Form for creating/editing products using home app models"""
    
    class Meta:
        model = Product
        fields = ['name', 'description', 'moq', 'categories', 'business', 'user']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter product name'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Enter product description'
            }),
            'moq': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1',
                'placeholder': '1'
            }),
            'categories': forms.CheckboxSelectMultiple(),
            'business': forms.Select(attrs={
                'class': 'form-control'
            }),
            'user': forms.HiddenInput()
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)  # Store the user for later use
        super().__init__(*args, **kwargs)
        
        # Filter businesses to only show those owned by the current user
        if self.user:
            self.fields['business'].queryset = Business.objects.filter(owner=self.user)
            # Set the user field to the current user (hidden field)
            self.fields['user'].initial = self.user
        else:
            self.fields['business'].queryset = Business.objects.none()

    def save(self, commit=True):
        instance = super().save(commit=False)
        # Set the user field to the logged-in user
        if self.user:
            instance.user = self.user
        if commit:
            instance.save()
            self.save_m2m()
        return instance


class ProductImageForm(forms.ModelForm):
    """Form for adding product images and videos"""
    MEDIA_TYPE_CHOICES = [
        ('image', 'Image'),
        ('video', 'Video')
    ]
    media_type = forms.ChoiceField(
        choices=MEDIA_TYPE_CHOICES,
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'}),
        initial='image'
    )
    
    class Meta:
        model = ProductImage
        fields = ['image', 'video', 'caption', 'is_default']
        widgets = {
            'image': forms.FileInput(attrs={
                'class': 'form-control image-upload',
                'accept': 'image/*',
                'style': 'display: none;'
            }),
            'video': forms.FileInput(attrs={
                'class': 'form-control video-upload',
                'accept': 'video/*',
                'style': 'display: none;'
            }),
            'caption': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Media caption (optional)'
            }),
            'is_default': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            })
        }
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set initial media type based on which field has a value
        if self.instance and self.instance.video:
            self.fields['media_type'].initial = 'video'


class ProductVariationImageForm(forms.ModelForm):
    """Form for adding images attached to a ProductVariation."""
    class Meta:
        model = ProductImage
        fields = ['image', 'caption', 'is_default']
        widgets = {
            'image': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*',
                'required': True
            }),
            'caption': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Image caption (optional)'
            }),
            'is_default': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            })
        }
    
    def __init__(self, *args, **kwargs):
        self.variation = kwargs.pop('variation', None)
        super().__init__(*args, **kwargs)
        self.fields['image'].required = True
        
        # Set the variation on the instance if provided
        if self.variation and not self.instance.pk:
            self.instance.variation = self.variation
    
    def clean(self):
        cleaned_data = super().clean()
        if not self.variation:
            raise forms.ValidationError("Variation is required")
        
        # Ensure the variation is set and product is not set
        self.instance.variation = self.variation
        self.instance.product = None  # Explicitly set product to None
        
        return cleaned_data
    
    def save(self, commit=True):
        # Ensure variation is set and product is None before saving
        self.instance.variation = self.variation
        self.instance.product = None
        
        if commit:
            self.instance.save()
            
        return self.instance
        return self.instance

class ProductSearchForm(forms.Form):
    """Form for searching products"""
    search = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search products...'
        })
    )
    category = forms.ModelChoiceField(
        queryset=ProductCategory.objects.all(),
        required=False,
        empty_label="All Categories",
        widget=forms.Select(attrs={
            'class': 'form-control'
        })
    )
    min_price = forms.DecimalField(
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01',
            'min': '0',
            'placeholder': 'Min price'
        })
    )
    max_price = forms.DecimalField(
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01',
            'min': '0',
            'placeholder': 'Max price'
        })
    )


class BusinessForm(forms.ModelForm):
    """Form for creating/editing businesses"""
    
    class Meta:
        model = Business
        fields = ['name', 'description', 'address', 'phone', 'website', 'email', 'categories']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter business name'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Enter business description'
            }),
            'address': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter business address'
            }),
            'phone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter phone number'
            }),
            'website': forms.URLInput(attrs={
                'class': 'form-control',
                'placeholder': 'https://example.com'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter email address'
            }),
            'categories': forms.CheckboxSelectMultiple()
        }


class ProductVariationForm(forms.ModelForm):
    """Form for creating/editing product variations"""
    
    class Meta:
        model = ProductVariation
        fields = ['name', 'moq', 'price', 'order', 'closes_on']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., Color: Red, Size: XL'
            }),
            'moq': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1',
                'placeholder': '1'
            }),
            'price': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
                'placeholder': '0.00'
            }),
            'order': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0',
                'placeholder': '0'
            })
        }


class ProductAttributeAssignmentForm(forms.ModelForm):
    """Form for assigning product attributes to variations - now supports creating new attributes"""

    # Fields for creating new attribute and value
    new_attribute_name = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter attribute name (e.g., Color, Size)'
        })
    )
    new_attribute_description = forms.CharField(
        max_length=500,
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 2,
            'placeholder': 'Enter attribute description (optional)'
        })
    )
    new_attribute_value = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter attribute value (e.g., Red, Large)'
        })
    )

    # Field for selecting existing attribute value
    existing_value = forms.ModelChoiceField(
        queryset=ProductAttributeValue.objects.none(),  # Will be set in __init__
        required=False,
        empty_label="Select existing attribute value",
        widget=forms.Select(attrs={
            'class': 'form-control'
        })
    )

    class Meta:
        model = ProductAttributeAssignment
        fields = ['product', 'value']  # Include the required fields
        widgets = {
            'product': forms.HiddenInput(),
            'value': forms.HiddenInput()
        }

    def __init__(self, *args, **kwargs):
        self.variation = kwargs.pop('variation', None)
        super().__init__(*args, **kwargs)

        # Set initial values for the form
        if self.variation:
            self.fields['product'].initial = self.variation
            self.fields['product'].widget = forms.HiddenInput()
            
            # Get all attribute values that are already assigned to this variation
            assigned_values = self.variation.attribute_assignments.values_list('value_id', flat=True)
            
            # Exclude already assigned values from the queryset
            self.fields['existing_value'].queryset = ProductAttributeValue.objects.exclude(
                id__in=assigned_values
            )
        else:
            self.fields['existing_value'].queryset = ProductAttributeValue.objects.none()
            
        # Make the value field not required since we'll set it in the view
        self.fields['value'].required = False

    def clean(self):
        cleaned_data = super().clean()
        new_attribute_name = cleaned_data.get('new_attribute_name')
        new_attribute_value = cleaned_data.get('new_attribute_value')
        existing_value = cleaned_data.get('existing_value')
        
        # If variation was provided in the form data, use it
        if not hasattr(self, 'variation') and 'variation' in cleaned_data:
            self.variation = cleaned_data['variation']

        # Validate that either new attribute/value is provided OR existing value is selected
        if not new_attribute_name and not new_attribute_value and not existing_value:
            raise forms.ValidationError(
                "Please either create a new attribute/value pair or select an existing attribute value."
            )

        # If creating new attribute, both name and value are required
        if (new_attribute_name or new_attribute_value) and not (new_attribute_name and new_attribute_value):
            raise forms.ValidationError(
                "Both attribute name and attribute value are required when creating a new attribute."
            )

        return cleaned_data


class ProductKBForm(forms.ModelForm):
    """Form for adding/editing product knowledge base entries"""
    content = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 8,
            'placeholder': 'Enter any product information or notes here. You can use any format you prefer.'
        })
    )
    
    def clean_content(self):
        # Get the new content from the form
        new_content = self.cleaned_data.get('content', '').strip()
        return new_content
    
    class Meta:
        model = ProductKB
        fields = ['content']
        
    def __init__(self, *args, **kwargs):
        self.variation = kwargs.pop('variation', None)
        self.product = kwargs.pop('product', None)
        super().__init__(*args, **kwargs)
        
    def clean(self):
        cleaned_data = super().clean()
        # No JSON validation needed - accept any text as-is
        return cleaned_data
        
    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.variation:
            instance.variation = self.variation
        elif self.product:
            instance.product = self.product
            
        # If this is an update and there's new content, append it
        if instance.pk and self.cleaned_data.get('content'):
            existing_content = instance.content or ''
            if existing_content:
                instance.content = f"{existing_content}\n{self.cleaned_data['content']}"
            
        if commit:
            instance.save()
        return instance
        
    def save(self, commit=True):
        # This method is required but won't be used directly
        # The view handles the actual saving
        return super().save(commit=commit)


class PriceTierForm(forms.ModelForm):
    """Form to add/edit PriceTier rows for a variation."""
    class Meta:
        model = PriceTier
        fields = ["min_quantity", "max_quantity", "price"]
        widgets = {
            "min_quantity": forms.NumberInput(attrs={"class": "form-control", "min": "1"}),
            "max_quantity": forms.NumberInput(attrs={"class": "form-control", "min": "0"}),
            "price": forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "min": "0"}),
        }

    def __init__(self, *args, **kwargs):
        self.variation = kwargs.pop("variation", None)
        super().__init__(*args, **kwargs)

    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.variation is not None:
            instance.variation = self.variation
        if commit:
            instance.save()
        return instance


class PromiseFeeForm(forms.ModelForm):
    """Form to add/edit PromiseFee for a variation."""
    class Meta:
        model = PromiseFee
        fields = ["name", "min_percent", "max_percent"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g., Basic, Premium, Express"}),
            "min_percent": forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "min": "0", "placeholder": "Minimum percentage %"}),
            "max_percent": forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "min": "0", "placeholder": "Maximum percentage %"}),
        }

    def __init__(self, *args, **kwargs):
        self.variation = kwargs.pop("variation", None)
        super().__init__(*args, **kwargs)

    def clean_name(self):
        name = self.cleaned_data.get('name')
        if name and self.variation:
            # Check if a promise fee with this name already exists for this variation
            existing = PromiseFee.objects.filter(
                variation=self.variation, 
                name=name
            ).exclude(pk=self.instance.pk if self.instance else None)
            
            if existing.exists():
                raise forms.ValidationError(
                    f"A promise fee with the name '{name}' already exists for this variation. "
                    f"Please choose a different name."
                )
        return name

    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.variation is not None:
            instance.variation = self.variation
        if commit:
            instance.save()
        return instance


class IRateForm(forms.ModelForm):
    """Form to add/edit IRate for a variation."""
    class Meta:
        model = IRate
        fields = ['lower_range', 'upper_range', 'must_pay_shipping', 'rate']
        widgets = {
            'lower_range': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1',
                'step': '1',
                'placeholder': 'Min quantity'
            }),
            'upper_range': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1',
                'step': '1',
                'placeholder': 'Max quantity (leave blank for no limit)'
            }),
            'rate': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0.01',
                'placeholder': 'e.g. 5.00 for $5.00 per unit'
            }),
            'must_pay_shipping': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
            }),
        }
    
    def __init__(self, *args, **kwargs):
        self.variation = kwargs.pop("variation", None)
        super().__init__(*args, **kwargs)
        
        # Set initial variation if provided
        if self.variation:
            self.instance.variation = self.variation
    
    def clean(self):
        cleaned_data = super().clean()
        lower = cleaned_data.get('lower_range')
        upper = cleaned_data.get('upper_range')
        
        if lower and upper and lower > upper:
            raise forms.ValidationError("Lower range cannot be greater than upper range.")
            
        # Check for overlapping ranges
        if self.variation:
            existing_ranges = self.variation.irate_set.exclude(pk=self.instance.pk if self.instance else None)
            for existing in existing_ranges:
                if (lower <= existing.upper_range if existing.upper_range else float('inf')) and \
                   (not existing.upper_range or upper >= existing.lower_range):
                    raise forms.ValidationError(
                        f"This range overlaps with an existing range ({existing.lower_range} - {existing.upper_range or '∞'})."
                    )
        
        return cleaned_data
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.variation:
            instance.variation = self.variation
        if commit:
            instance.save()
        return instance


class OrderItemForm(forms.Form):
    """Form for a single order item"""
    variation = forms.ModelChoiceField(
        queryset=ProductVariation.objects.none(),
        widget=forms.Select(attrs={'class': 'form-select variation-select'})
    )
    quantity = forms.IntegerField(
        min_value=1,
        initial=1,
        widget=forms.NumberInput(attrs={'class': 'form-control quantity-input'})
    )
    price = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        widget=forms.NumberInput(attrs={'class': 'form-control price-input', 'readonly': 'readonly'})
    )


class VendorOrderForm(forms.Form):
    """Form for vendors to create orders for customers"""
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user')
        super().__init__(*args, **kwargs)
        
        # Filter customers who have purchased from this vendor before
        self.fields['customer'] = forms.ModelChoiceField(
            queryset=User.objects.filter(
                order_items__variation__product__business__owner=self.user
            ).distinct().order_by('first_name', 'last_name', 'email'),
            widget=forms.Select(attrs={'class': 'form-select'}),
            label="Customer"
        )
        
        # Filter products that belong to the vendor's businesses
        self.fields['products'] = forms.ModelMultipleChoiceField(
            queryset=Product.objects.filter(
                business__owner=self.user
            ).select_related('business').order_by('name'),
            widget=forms.SelectMultiple(attrs={'class': 'form-select'}),
            label="Products"
        )
    
    def save(self):
        """Create the order and order items"""
        customer = self.cleaned_data['customer']
        products = self.cleaned_data['products']
        
        # Create the order
        order = Order.objects.create(
            user=customer,
            status='pending',
            payment_method='cash_on_delivery',
            shipping_address=customer.shipping_addresses.filter(is_default=True).first()
        )
        
        # Create order items
        order_items = []
        for product in products:
            variation = product.variations.first()  # Get the first variation
            if variation:
                order_items.append(
                    OrderItem(
                        order=order,
                        product=product,
                        variation=variation,
                        quantity=1,  # Default quantity
                        price=variation.price
                    )
                )
        
        if order_items:
            OrderItem.objects.bulk_create(order_items)
        
        return order


class ChatOrderForm(forms.Form):
    """Form for creating an order from a chat conversation"""
    
    def __init__(self, *args, **kwargs):
        self.chat = kwargs.pop('chat', None)
        self._current_user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        if self.chat:
            # Set the user (buyer) field initial value and make it required
            self.fields['user'].initial = self.chat.buyer.id
            self.fields['user'].required = True
            
            # Add fields for each variation
            self.variations = self.chat.product.variations.all()
            
            # Add a field for each variation
            for i, variation in enumerate(self.variations):
                self.fields[f'variation_{variation.id}'] = forms.BooleanField(
                    required=False,
                    label=f"Add to order",
                    widget=forms.CheckboxInput(attrs={
                        'class': 'variation-checkbox',
                        'data-variation-id': variation.id
                    })
                )
                
                self.fields[f'quantity_{variation.id}'] = forms.IntegerField(
                    min_value=1,
                    initial=1,
                    required=False,
                    widget=forms.NumberInput(attrs={
                        'class': 'form-control variation-quantity',
                        'min': '1',
                        'data-variation-id': variation.id,
                        'style': 'width: 80px;',
                        'disabled': True
                    })
                )
                
                self.fields[f'use_custom_price_{variation.id}'] = forms.BooleanField(
                    required=False,
                    label="Custom price",
                    widget=forms.CheckboxInput(attrs={
                        'class': 'custom-price-toggle',
                        'data-variation-id': variation.id
                    })
                )
                
                self.fields[f'custom_price_{variation.id}'] = forms.DecimalField(
                    required=False,
                    min_value=0.01,
                    widget=forms.NumberInput(attrs={
                        'class': 'form-control custom-price',
                        'step': '0.01',
                        'data-variation-id': variation.id,
                        'style': 'width: 120px; display: none;',
                        'placeholder': '0.00'
                    })
                )    
            
            # Set the user (buyer) field queryset to only include the chat's buyer
            self.fields['user'].queryset = User.objects.filter(pk=self.chat.buyer.pk)
            
            # Set the product queryset to only include products from the vendor's businesses
            self.fields['product'].queryset = Product.objects.filter(
                business__owner=self._current_user
            ).select_related('business').order_by('name')
    
    user = forms.ModelChoiceField(
        queryset=User.objects.none(),
        widget=forms.HiddenInput(),
        label=""
    )
    
    product = forms.ModelChoiceField(
        queryset=Product.objects.none(),
        widget=forms.HiddenInput(),
        label="",
        required=False
    )
    
    note = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Add any special instructions or notes about this order...'
        })
    )
    
    def clean(self):
        cleaned_data = super().clean()
        
        # Make sure user is set
        if 'user' not in cleaned_data and hasattr(self, 'chat'):
            cleaned_data['user'] = self.chat.buyer
            
        # Check if at least one variation is selected
        selected_variations = False
        for field_name, value in cleaned_data.items():
            if field_name.startswith('variation_') and value:
                variation_id = field_name.replace('variation_', '')
                quantity = cleaned_data.get(f'quantity_{variation_id}')
                if quantity and quantity > 0:
                    selected_variations = True
                    break
        
        if not selected_variations:
            raise forms.ValidationError("Please select at least one variation to order.")
            
        return cleaned_data
    
    def save(self):
        """Create the order from the form data"""
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            # Get form data
            user = self.cleaned_data.get('user')
            if not user:
                raise ValueError("No user specified in the form data")
                
            note = self.cleaned_data.get('note', '')
            
            logger.info(f"Creating order for user: {user.id} with note: {note}")
            
            # Create the order first
            order = Order(
                user=user,  # The buyer from the chat
                status='pending',
                total=0,  # Will be calculated based on items
                payment_method='cash_on_delivery',
                note=note,
                shipping_address=user.email,  # Using email as a fallback
            )
            
            # Set the current user as the creator
            if hasattr(self, '_current_user'):
                order._current_user = self._current_user
            
            # Save the order first to get an ID
            order.save()
            logger.info(f"Created order with ID: {order.id}")
            
            total_amount = 0
            selected_items = 0
            
            # Add order items for each selected variation
            for field_name, is_selected in self.cleaned_data.items():
                if field_name.startswith('variation_') and is_selected:
                    variation_id = field_name.replace('variation_', '')
                    quantity = self.cleaned_data.get(f'quantity_{variation_id}')
                    use_custom_price = self.cleaned_data.get(f'use_custom_price_{variation_id}', False)
                    custom_price = self.cleaned_data.get(f'custom_price_{variation_id}')
                    
                    if not quantity or quantity <= 0:
                        logger.warning(f"Skipping variation {variation_id} - invalid quantity: {quantity}")
                        continue
                        
                    try:
                        # Get the variation
                        variation = ProductVariation.objects.get(id=variation_id)
                        logger.info(f"Processing variation: {variation.id} - {variation.name}")
                        
                        # Determine the price to use
                        if use_custom_price and custom_price is not None:
                            unit_price = custom_price
                            logger.debug(f"Using custom price: {unit_price}")
                        else:
                            unit_price = variation.price
                            logger.debug(f"Using variation price: {unit_price}")
                        
                        # Create order item
                        order_item = OrderItem(
                            order=order,
                            variation=variation,
                            quantity=quantity,
                            price=unit_price
                        )
                        order_item.save()
                        logger.info(f"Created order item: {order_item.id}")
                        
                        # Add to total
                        item_total = unit_price * quantity
                        total_amount += item_total
                        selected_items += 1
                        
                        logger.debug(f"Added item total: {item_total}, running total: {total_amount}")
                        
                    except ProductVariation.DoesNotExist:
                        logger.error(f"Variation with ID {variation_id} does not exist")
                        continue
                    except Exception as e:
                        logger.error(f"Error creating order item: {str(e)}")
                        raise
            
            if selected_items == 0:
                logger.error("No valid items were added to the order")
                order.delete()  # Clean up empty order
                raise ValueError("No valid items were added to the order")
            
            # Update order total
            order.total = total_amount
            order.save()
            logger.info(f"Order {order.id} completed with total: {total_amount}")
            
            return order
            
        except Exception as e:
            logger.error(f"Error in ChatOrderForm.save(): {str(e)}", exc_info=True)
            # If the order was created but there was an error with items,
            # we might want to delete it to avoid orphaned orders
            if 'order' in locals() and order.pk:
                logger.warning(f"Deleting order {order.id} due to error")
                order.delete()
            raise
