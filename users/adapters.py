from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.account.utils import perform_login
from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse
from django.conf import settings
from .models import MyUser

class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    def pre_social_login(self, request, sociallogin):
        """
        Invoked just before a user is logged in (in this case, by a social account).
        """
        user = sociallogin.user
        if user.id:
            return  # If user is already logged in, proceed normally
            
        # Check if a user with this email already exists
        if user.email:
            try:
                # Check if a user with this email already exists
                existing_user = MyUser.objects.get(email=user.email)
                
                # If the social account is not already connected to this user
                if not sociallogin.is_existing:
                    # Connect the social account to the existing user
                    sociallogin.connect(request, existing_user)
                    # Add a success message
                    messages.success(request, 'Your Google account has been connected.')
            except MyUser.DoesNotExist:
                # User doesn't exist, proceed with normal signup flow
                pass

    def populate_user(self, request, sociallogin, data):
        """
        Populate user information from social provider info.
        """
        user = super().populate_user(request, sociallogin, data)
        
        # Get the social account data
        extra_data = sociallogin.account.extra_data
        
        # Set additional user fields from social account
        if 'given_name' in extra_data:
            user.first_name = extra_data.get('given_name', '')
        if 'family_name' in extra_data:
            user.last_name = extra_data.get('family_name', '')
        if 'picture' in extra_data:
            user.avatar_url = extra_data.get('picture', '')
            
        return user

    def get_connect_redirect_url(self, request, socialaccount):
        """
        Returns the default URL to redirect to after successfully connecting a social account.
        """
        return reverse('profile')  # Redirect to profile after connecting account
