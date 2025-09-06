"""
Signals for user registration and management
"""
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from .models import MyUser, PersonalProfile


@receiver(post_save, sender=MyUser)
def send_user_registration_notification(sender, instance, created, **kwargs):
    """
    Send email notification when a new user is created
    """
    if created:  # Only send email for new users, not updates
        try:
            # Prepare email content
            subject = f'🎉 New User Registration: {instance.username}'
            
            # Create email message
            email_content = f"""
🎉 New User Registration on ToursKe

👤 User Information:
Username: {instance.username}
Email: {instance.email}
Full Name: {instance.get_full_name() or 'Not provided'}
Date Registered: {instance.date_joined.strftime('%B %d, %Y at %I:%M %p')}

📋 Account Details:
- First Name: {instance.first_name or 'Not provided'}
- Last Name: {instance.last_name or 'Not provided'}
- Phone: {getattr(instance, 'phone', 'Not provided') or 'Not provided'}
- Is Active: {instance.is_active}
- Is Staff: {instance.is_staff}
- Is Superuser: {instance.is_superuser}

🌐 Platform Info:
- User ID: {instance.id}
- Registration IP: {getattr(instance, 'last_login_ip', 'Not available')}

---
This notification was automatically sent from ToursKe when a new user registered.
            """.strip()
            
            # Send email to admin
            admin_email = getattr(settings, 'ADMIN_EMAIL', 'kevingitundu@gmail.com')
            
            send_mail(
                subject=subject,
                message=email_content,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[admin_email],
                fail_silently=True,  # Don't break user registration if email fails
            )
            
            print(f"✅ Admin notification sent for new user: {instance.username}")
            
        except Exception as e:
            # Log the error but don't break user registration
            print(f"❌ Failed to send user registration notification: {e}")


@receiver(post_save, sender=MyUser)
def send_welcome_email_to_user(sender, instance, created, **kwargs):
    """
    Send welcome email to new users
    """
    if created and instance.email:
        try:
            subject = 'Welcome to ToursKe! 🎉'
            
            welcome_message = f"""
Dear {instance.first_name or instance.username},

🎉 Welcome to ToursKe! We're excited to have you join our community of travel enthusiasts.

✅ Your account has been successfully created with:
• Username: {instance.username}
• Email: {instance.email}
• Registration Date: {instance.date_joined.strftime('%B %d, %Y')}

🚀 What you can do next:
• Explore amazing destinations in Kenya
• Join group tours and events
• Connect with travel agencies
• Create your own travel experiences
• Build your travel community
• Complete your profile for personalized recommendations

📧 Need help? Contact us at: {settings.DEFAULT_FROM_EMAIL}
🌐 Visit our website: https://tourske.com

Happy Travels! ✈️
The ToursKe Team

---
This is an automated welcome message. Please do not reply to this email.
            """.strip()
            
            # Send welcome email to the new user
            send_mail(
                subject=subject,
                message=welcome_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[instance.email],
                fail_silently=True,
            )
            
            print(f"✅ Welcome email sent to: {instance.email}")
            
        except Exception as e:
            # Log the error but don't break user registration
            print(f"❌ Failed to send welcome email: {e}")


@receiver(post_save, sender=PersonalProfile)
def send_profile_completion_notification(sender, instance, created, **kwargs):
    """
    Send notification when user completes their profile
    """
    if not created and instance.user:  # Profile updated, not created
        try:
            # Check if this is a profile completion (has phone and location)
            if instance.phone and instance.location:
                subject = f'📝 Profile Completed: {instance.user.username}'
                
                profile_content = f"""
📝 User Profile Completed on ToursKe

👤 User Information:
Username: {instance.user.username}
Email: {instance.user.email}
Full Name: {instance.user.get_full_name() or 'Not provided'}

📋 Profile Details:
- First Name: {instance.first_name or 'Not provided'}
- Last Name: {instance.last_name or 'Not provided'}
- Phone: {instance.phone or 'Not provided'}
- Location: {instance.location or 'Not provided'}
- Date of Birth: {instance.date_of_birth.strftime('%B %d, %Y') if instance.date_of_birth else 'Not provided'}
- Profile Updated: {instance.updated_at.strftime('%B %d, %Y at %I:%M %p') if hasattr(instance, 'updated_at') else 'Recently'}

🌐 Account Status:
- User ID: {instance.user.id}
- Account Active: {instance.user.is_active}
- Date Joined: {instance.user.date_joined.strftime('%B %d, %Y')}

---
This notification was automatically sent from ToursKe when a user completed their profile.
                """.strip()
                
                # Send email to admin
                admin_email = getattr(settings, 'ADMIN_EMAIL', 'kevingitundu@gmail.com')
                
                send_mail(
                    subject=subject,
                    message=profile_content,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[admin_email],
                    fail_silently=True,
                )
                
                print(f"✅ Profile completion notification sent for user: {instance.user.username}")
                
        except Exception as e:
            # Log the error but don't break profile updates
            print(f"❌ Failed to send profile completion notification: {e}")
