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
        
        if self.instance and self.instance.pk:
            self.fields['service_types'].initial = self.instance.service_types.all()
    
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
            'caption': forms.TextInput(attrs={'placeholder': 'Image caption (optional)'}),
        }

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
