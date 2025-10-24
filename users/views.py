from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth import login, logout, authenticate, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.urls import reverse
from .forms import MyUserCreationForm, MyAuthenticationForm, ProfileEditForm, CustomPasswordChangeForm
from .models import PersonalProfile

def redirect_user_by_role(user):
    """
    Helper function to redirect users based on their role
    """
    if not hasattr(user, 'role'):
        return redirect('home:home')
    
    role = user.role.lower()
    
    # Define role-based redirects
    role_redirects = {
        'admin': 'vendor:dashboard',
        'supervisor': 'vendor:dashboard',
        'manager': 'vendor:dashboard',
        'agent': 'agents:agent_dashboard',
    }
    
    # Get the URL name for the role, default to home if role not found
    url_name = role_redirects.get(role, 'home:home')
    
    try:
        # Try to get the URL, fallback to home if it doesn't exist
        return redirect(reverse(url_name))
    except:
        return redirect(reverse('home:home'))

# Create your views here.

def login_view(request):
    if request.user.is_authenticated:
        next_url = request.GET.get('next') or request.POST.get('next')
        if next_url:
            return redirect(next_url)
        # If already logged in, redirect based on role
        return redirect_user_by_role(request.user)
    
    if request.method == 'POST':
        form = MyAuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, f'Welcome back, {user.email}!')
            
            # Check for next URL first
            next_url = request.GET.get('next') or request.POST.get('next')
            if next_url:
                return redirect(next_url)
                
            # Redirect based on user role
            return redirect_user_by_role(user)
        else:
            messages.error(request, 'Invalid email or password.')
    else:
        form = MyAuthenticationForm()

    context = {'form': form, 'next': request.GET.get('next')}
    return render(request, 'users/login.html', context)

def signup_view(request):
    if request.user.is_authenticated:
        return redirect('home:home')
    
    if request.method == 'POST':
        form = MyUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            # Specify the backend to use for authentication
            from django.contrib.auth import get_backends
            backend = 'django.contrib.auth.backends.ModelBackend'
            user.backend = backend
            login(request, user)
            # Clear any existing messages and show only this one
            messages.get_messages(request)
            messages.success(request, f'Account created successfully! Let\'s complete your profile.')
            return redirect('profile_completion')  # Redirect to profile completion instead of home
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = MyUserCreationForm()
    
    return render(request, 'users/signup.html', {'form': form})

@login_required
def logout_view(request):
    logout(request)
    messages.success(request, 'You have been logged out successfully.')
    return redirect('home:home')

@login_required
def profile_view(request):
    return render(request, 'users/profile.html')

@login_required
def profile_edit_view(request):
    if request.method == 'POST':
        form = ProfileEditForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated successfully!')
            return redirect('profile')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = ProfileEditForm(instance=request.user)
    
    return render(request, 'users/profile_edit.html', {'form': form})

@login_required
def profile_completion_view(request):
    if request.method == 'POST':
        # Handle profile completion form submission
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        phone = request.POST.get('phone')
        location = request.POST.get('location')
        
        # Update user model
        user = request.user
        user.first_name = first_name
        user.last_name = last_name
        user.save()
        
        # Create or update personal profile
        profile, created = PersonalProfile.objects.get_or_create(user=user)
        profile.first_name = first_name
        profile.last_name = last_name
        profile.phone = phone
        profile.location = location
        profile.save()
        
        # Clear any existing messages and show only this one
        messages.get_messages(request)
        messages.success(request, 'Profile completed successfully! Now let\'s set your preferences.')
        return redirect('home:home')
    
    return render(request, 'users/profile_completion.html')

@login_required
def password_change_view(request):
    if request.method == 'POST':
        form = CustomPasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            messages.success(request, 'Your password was successfully updated!')
            return redirect('profile')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = CustomPasswordChangeForm(request.user)
    
    return render(request, 'users/password_change.html', {'form': form})

@login_required
def dashboard(request):
    """User dashboard with overview of places, agencies, and activities"""
    user = request.user
    
    return render(request, 'users/dashboard.html', {'user': user})