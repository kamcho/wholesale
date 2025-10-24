from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils.translation import gettext_lazy as _


class MyUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError(_('The Email field must be set'))
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError(_('Superuser must have is_staff=True.'))
        if extra_fields.get('is_superuser') is not True:
            raise ValueError(_('Superuser must have is_superuser=True.'))
        return self.create_user(email, password, **extra_fields)

class MyUser(AbstractUser):
    email = models.EmailField(_('email address'), max_length=50, unique=True)
    username = models.CharField(max_length=50, unique=True,null=True, blank=True)
    ROLE_CHOICES = [
        ('Admin', 'Admin'),
        ('Supervisor', 'Supervisor'),
        ('Manager', 'Manager'),
        ('Agent', 'Agent'),
        ('Customer', 'Customer'),
    ]
    role = models.CharField(
        _('Role'),
        max_length=20,
        choices=ROLE_CHOICES,
        default='Customer',  
        help_text=_('User role in the system')
    )

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    objects = MyUserManager()

    # Fix for reverse accessor clashes
    groups = models.ManyToManyField(
        'auth.Group', 
        related_name='myuser_groups',  # Unique related_name
        blank=True,
        help_text=_('The groups this user belongs to. A user will get all permissions granted to each of their groups.')
    )
    
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        related_name='myuser_permissions',  # Unique related_name
        blank=True,
        help_text=_('Specific permissions for this user.')
    )

    def __str__(self):
        return self.email

class PersonalProfile(models.Model):
    user = models.OneToOneField(
        MyUser, 
        on_delete=models.CASCADE, 
        related_name='profile',
        error_messages={
            'unique': 'A profile already exists for this user.',
            'invalid': 'Invalid user ID.',
        }
    )
    first_name = models.CharField(max_length=100, blank=True, null=True)
    surname = models.CharField(max_length=100, blank=True, null=True)
    last_name = models.CharField(max_length=100, blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    gender = models.CharField(
        max_length=1,
        choices=[('M', 'Male'), ('F', 'Female'), ('O', 'Other')],
        default='O'
    )
    location = models.CharField(max_length=255, blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.get_full_name()}'s Profile"

    def get_full_name(self):
        return f"{self.first_name} {self.last_name}"

 

