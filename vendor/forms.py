from django import forms
from django.contrib.auth import get_user_model
from home.models import Product, ProductCategory, Business, ProductImage, ProductCategoryFilter, ProductVariation, ProductAttributeAssignment, ProductAttributeValue, PriceTier, PromiseFee

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
    """Form for adding images/videos attached to a ProductVariation."""
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make image field not required for formsets (can be added later)
        self.fields['image'].required = False

    def _post_clean(self):
        """Override _post_clean to skip model validation for excluded fields"""
        # Don't run model validation since we're manually setting product/variation fields
        # in the view, and they're excluded from form validation
        pass

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
        fields = []  # We'll handle all fields manually

    def __init__(self, *args, **kwargs):
        self.variation = kwargs.pop('variation', None)
        super().__init__(*args, **kwargs)

        if self.variation:
            # Set the variation as the initial value for the variation field
            self.fields['variation'].initial = self.variation
            
            
        else:
            self.fields['existing_value'].queryset = ProductAttributeValue.objects.none()

    def clean(self):
        cleaned_data = super().clean()
        new_attribute_name = cleaned_data.get('new_attribute_name')
        new_attribute_value = cleaned_data.get('new_attribute_value')
        existing_value = cleaned_data.get('existing_value')

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
        fields = ["name", "buy_back_fee", "percentage_fee", "must_pay_shipping"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g., Basic, Premium, Express"}),
            "buy_back_fee": forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "min": "0"}),
            "percentage_fee": forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "min": "0"}),
            "must_pay_shipping": forms.CheckboxInput(attrs={"class": "form-check-input"}),
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
