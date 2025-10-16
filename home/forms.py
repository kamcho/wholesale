from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from .models import ProductCategoryFilter, ProductCategory, BuyerSellerMessage

User = get_user_model()

class UserRegistrationForm(UserCreationForm):
    ROLE_CHOICES = [
        ('Agent', 'Agent'),
        ('Manager', 'Manager'),
    ]
    
    role = forms.ChoiceField(
        choices=ROLE_CHOICES,
        widget=forms.RadioSelect(attrs={'class': 'sr-only'}),
        label='I want to register as:',
        required=True,
        error_messages={
            'required': 'Please select a role (Agent or Manager)'
        }
    )
    
    class Meta:
        model = User
        fields = ('email', 'first_name', 'last_name', 'password1', 'password2', 'role')
        widgets = {
            'email': forms.EmailInput(attrs={
                'class': 'form-input block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500',
                'placeholder': 'your@email.com',
            }),
            'first_name': forms.TextInput(attrs={
                'class': 'form-input block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500',
                'placeholder': 'First Name',
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'form-input block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500',
                'placeholder': 'Last Name',
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Customize password fields
        self.fields['password1'].widget.attrs.update({
            'class': 'form-input block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500',
            'placeholder': 'Create a password',
        })
        self.fields['password2'].widget.attrs.update({
            'class': 'form-input block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500',
            'placeholder': 'Confirm password',
        })

class ProductCategoryFilterForm(forms.ModelForm):
    class Meta:
        model = ProductCategoryFilter
        fields = ['name', 'description']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-input mt-1 block w-full rounded-md border-gray-300 shadow-sm',
                'placeholder': 'e.g., Electronics, Fashion, etc.'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-textarea mt-1 block w-full rounded-md border-gray-300 shadow-sm',
                'rows': 2,
                'placeholder': 'Optional description for this category filter'
            }),
        }

class ProductCategoryForm(forms.ModelForm):
    class Meta:
        model = ProductCategory
        fields = ['filter', 'name', 'description']
        widgets = {
            'filter': forms.Select(attrs={
                'class': 'form-select mt-1 block w-full rounded-md border-gray-300 shadow-sm'
            }),
            'name': forms.TextInput(attrs={
                'class': 'form-input mt-1 block w-full rounded-md border-gray-300 shadow-sm',
                'placeholder': 'e.g., Smartphones, Laptops, etc.'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-textarea mt-1 block w-full rounded-md border-gray-300 shadow-sm',
                'rows': 2,
                'placeholder': 'Optional description for this category'
            }),
        }


# ==============================
# BUYER-SELLER CHAT FORMS
# ==============================

class BuyerSellerMessageForm(forms.ModelForm):
    """Form for sending messages in buyer-seller chats"""
    
    class Meta:
        model = BuyerSellerMessage
        fields = ['message']
        widgets = {
            'message': forms.Textarea(attrs={
                'class': 'form-textarea block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 resize-none',
                'rows': 3,
                'placeholder': 'Type your message here...',
                'maxlength': 1000,
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['message'].required = True
        self.fields['message'].max_length = 1000
    
    def clean_message(self):
        message = self.cleaned_data.get('message')
        if message and len(message.strip()) == 0:
            raise forms.ValidationError("Message cannot be empty.")
        return message.strip()
