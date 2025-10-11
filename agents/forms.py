from django import forms
from django.core.exceptions import ValidationError
from home.models import Agent, ServiceCategory, AgentImage
from django.utils.translation import gettext_lazy as _

class AgentForm(forms.ModelForm):
    """Form for creating and updating agents"""
    service_types = forms.ModelMultipleChoiceField(
        queryset=ServiceCategory.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=True
    )
    
    class Meta:
        model = Agent
        fields = [
            'name', 'description', 'service_types',
            'email', 'phone', 'phone2', 'website',
            'address', 'city', 'country',
            'social_facebook', 'social_twitter',
            'social_linkedin', 'social_instagram'
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
            'address': forms.Textarea(attrs={'rows': 2}),
        }
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Set initial service types if editing
        if self.instance and self.instance.pk:
            self.fields['service_types'].initial = self.instance.service_types.all()
        
        # Add Tailwind classes to all fields
        for field_name, field in self.fields.items():
            if field_name == 'service_types':
                # Special handling for checkboxes
                field.widget.attrs['class'] = 'mt-2 space-y-2'
            elif isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs['class'] = 'h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500'
            elif isinstance(field.widget, forms.Textarea):
                field.widget.attrs.update({
                    'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm',
                    'rows': 3
                })
            elif isinstance(field.widget, (forms.Select, forms.SelectMultiple)):
                field.widget.attrs.update({
                    'class': 'mt-1 block w-full rounded-md border-gray-300 py-2 pl-3 pr-10 text-base focus:border-blue-500 focus:outline-none focus:ring-blue-500 sm:text-sm'
                })
            else:
                field.widget.attrs.update({
                    'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm'
                })
    
    def save(self, commit=True):
        agent = super().save(commit=False)
        if commit:
            agent.save()
            agent.service_types.set(self.cleaned_data['service_types'])
        return agent

class AgentImageForm(forms.ModelForm):
    """Form for uploading agent images"""
    class Meta:
        model = AgentImage
        fields = ['image', 'caption', 'is_primary']
        widgets = {
            'image': forms.FileInput(attrs={
                'class': 'block w-full text-sm text-gray-900 border border-gray-300 rounded-lg cursor-pointer bg-gray-50 focus:outline-none',
                'accept': 'image/*'
            }),
            'caption': forms.TextInput(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm',
                'placeholder': 'Enter a caption (optional)'
            }),
            'is_primary': forms.CheckboxInput(attrs={
                'class': 'h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500'
            })
        }
        labels = {
            'image': 'Image',
            'caption': 'Caption',
            'is_primary': 'Set as primary image'
        }
        widgets = {
            'caption': forms.TextInput(attrs={'placeholder': 'Image caption (optional)'}),
        }

class AgentReviewForm(forms.ModelForm):
    """Form for submitting agent reviews"""
    RATING_CHOICES = [
        (1, '★☆☆☆☆ (1/5)'),
        (2, '★★☆☆☆ (2/5)'),
        (3, '★★★☆☆ (3/5)'),
        (4, '★★★★☆ (4/5)'),
        (5, '★★★★★ (5/5)')
    ]
    
    rating = forms.ChoiceField(
        choices=RATING_CHOICES,
        widget=forms.RadioSelect(attrs={
            'class': 'flex space-x-2'
        }),
        required=True,
        label='Your Rating'
    )
    comment = forms.CharField(
        widget=forms.Textarea(attrs={
            'rows': 4,
            'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm',
            'placeholder': 'Share your experience with this agent...'
        }),
        required=True,
        label='Your Review'
    )
    
    class Meta:
        from home.models import AgentReview
        model = AgentReview
        fields = ['rating', 'comment', 'title']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm',
                'placeholder': 'Title your review (optional)'
            })
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['title'].required = False
        
    def clean_rating(self):
        rating = self.cleaned_data.get('rating')
        if rating:
            return int(rating)
        return None


class AgentSearchForm(forms.Form):
    """Form for searching agents"""
    query = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'placeholder': 'Search by name, location, or service...',
            'class': 'form-control'
        })
    )
    service_type = forms.ModelChoiceField(
        queryset=ServiceCategory.objects.all(),
        required=False,
        empty_label="All Service Types"
    )
    location = forms.CharField(required=False, widget=forms.TextInput(attrs={
        'placeholder': 'City or Country',
        'class': 'form-control'
    }))

# --- Multi-step Agent Creation Forms ---

class AgentBasicInfoForm(forms.ModelForm):
    class Meta:
        model = Agent
        fields = ['name', 'description', 'service_types']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-emerald-500 focus:ring-emerald-500',
                'placeholder': 'e.g. John Doe Real Estate'
            }),
            'description': forms.Textarea(attrs={
                'rows': 4,
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-emerald-500 focus:ring-emerald-500',
                'placeholder': 'Tell us about your services and expertise...'
            }),
        }
        help_texts = {
            'description': 'This will be displayed on your public profile.',
        }

    service_types = forms.ModelMultipleChoiceField(
        queryset=ServiceCategory.objects.all(),
        widget=forms.CheckboxSelectMultiple(attrs={
            'class': 'mt-2 space-y-2',
        }),
        required=True,
        label=_('Service Types'),
        help_text='Select all that apply',
        error_messages={
            'required': 'Please select at least one service type.'
        }
    )
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Add custom classes to each checkbox
        self.fields['service_types'].label_from_instance = lambda obj: f"{obj.name}"
        for field_name, field in self.fields.items():
            if field_name != 'service_types':
                field.widget.attrs['class'] = field.widget.attrs.get('class', '') + ' form-input'


class AgentContactInfoForm(forms.ModelForm):
    class Meta:
        model = Agent
        fields = ['email', 'phone', 'phone2', 'website', 'address', 'city', 'country']
        widgets = {
            'email': forms.EmailInput(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-emerald-500 focus:ring-emerald-500',
                'placeholder': 'your.email@example.com'
            }),
            'phone': forms.TextInput(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-emerald-500 focus:ring-emerald-500',
                'placeholder': '+1 (555) 123-4567'
            }),
            'phone2': forms.TextInput(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-emerald-500 focus:ring-emerald-500',
                'placeholder': 'Optional additional phone'
            }),
            'website': forms.URLInput(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-emerald-500 focus:ring-emerald-500',
                'placeholder': 'https://yourwebsite.com'
            }),
            'address': forms.Textarea(attrs={
                'rows': 2,
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-emerald-500 focus:ring-emerald-500',
                'placeholder': 'Your business address'
            }),
            'city': forms.TextInput(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-emerald-500 focus:ring-emerald-500',
                'placeholder': 'City'
            }),
            'country': forms.TextInput(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-emerald-500 focus:ring-emerald-500',
                'placeholder': 'Country'
            }),
        }


class AgentSocialLinksForm(forms.ModelForm):
    class Meta:
        model = Agent
        fields = ['social_facebook', 'social_twitter', 'social_linkedin', 'social_instagram']
        widgets = {
            'social_facebook': forms.TextInput(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-emerald-500 focus:ring-emerald-500',
                'placeholder': 'https://facebook.com/yourpage',
            }),
            'social_twitter': forms.TextInput(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-emerald-500 focus:ring-emerald-500',
                'placeholder': 'https://twitter.com/yourhandle',
            }),
            'social_linkedin': forms.TextInput(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-emerald-500 focus:ring-emerald-500',
                'placeholder': 'https://linkedin.com/in/yourprofile',
            }),
            'social_instagram': forms.TextInput(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-emerald-500 focus:ring-emerald-500',
                'placeholder': 'https://instagram.com/yourprofile',
            }),
        }
        help_texts = {
            'social_facebook': 'Your Facebook page or profile URL',
            'social_twitter': 'Your Twitter profile URL',
            'social_linkedin': 'Your LinkedIn profile URL',
            'social_instagram': 'Your Instagram profile URL',
        }
    
    def clean(self):
        cleaned_data = super().clean()
        
        # Add social media URL validation
        social_fields = ['social_facebook', 'social_twitter', 'social_linkedin', 'social_instagram']
        
        for field in social_fields:
            url = cleaned_data.get(field)
            if url and not url.startswith(('http://', 'https://')):
                cleaned_data[field] = f'https://{url}'
                
        return cleaned_data
