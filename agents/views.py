from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, TemplateView, View
from formtools.wizard.views import SessionWizardView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.urls import reverse_lazy
from django.contrib import messages
from django.db.models import Q, Count, Avg
from django.core.paginator import Paginator
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import UserPassesTestMixin

from home.models import Agent, AgentImage, ServiceCategory
from .forms import (
    AgentForm,
    AgentImageForm,
    AgentSearchForm,
    AgentBasicInfoForm,
    AgentContactInfoForm,
    AgentSocialLinksForm,
)


class AgentDashboardView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = 'agents/agent_dashboard.html'
    
    def test_func(self):
        return self.request.user.role == 'Agent' or self.request.user.is_superuser
        
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Add any context data needed for the dashboard
        context['active_listings'] = 12  # Example data
        context['total_orders'] = 24     # Example data
        return context

class AgentListView(ListView):
    model = Agent
    template_name = 'agents/agent_list.html'
    context_object_name = 'agents'
    paginate_by = 12
    
    def get_queryset(self):
        queryset = Agent.objects.filter(is_verified=True).select_related('owner').prefetch_related('service_types')
        
        # Handle search
        search_form = AgentSearchForm(self.request.GET or None)
        if search_form.is_valid():
            query = search_form.cleaned_data.get('query')
            service_type = search_form.cleaned_data.get('service_type')
            location = search_form.cleaned_data.get('location')
            
            if query:
                queryset = queryset.filter(
                    Q(name__icontains=query) |
                    Q(description__icontains=query) |
                    Q(city__icontains=query) |
                    Q(country__icontains(query))
                )
            
            if service_type:
                queryset = queryset.filter(service_types=service_type)
                
            if location:
                queryset = queryset.filter(
                    Q(city__icontains=location) |
                    Q(country__icontains(location))
                )
        
        # Annotate with review stats
        queryset = queryset.annotate(
            review_count=Count('reviews'),
            avg_rating=Avg('reviews__rating')
        )
        
        # Order by rating and review count
        return queryset.order_by('-is_verified', '-avg_rating', '-review_count')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_form'] = AgentSearchForm(self.request.GET or None)
        context['service_categories'] = ServiceCategory.objects.all()
        return context

    model = Agent
    template_name = 'agents/agent_detail.html'
    context_object_name = 'agent'
    
    def get_queryset(self):
        # Only show active agents to non-staff users
        queryset = super().get_queryset()
        if not self.request.user.is_staff:
            queryset = queryset.filter(is_active=True)
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        agent = self.get_object()
        
        # Get related properties
        context['properties'] = agent.properties.filter(is_published=True)[:4]
        
        # Get reviews
        context['reviews'] = agent.reviews.filter(is_approved=True).order_by('-created_at')[:5]
        
        # Add review form if user is authenticated
        if self.request.user.is_authenticated:
            context.update({
                'review_form': AgentReviewForm(),
                'rating_stats': rating_stats,
                'image_form': AgentImageForm(),
                'is_owner': self.request.user == agent.owner,
                'can_edit': self.request.user.has_perm('home.change_agent') or self.request.user == agent.owner,
            })
    
        return context

class AgentDetailView(DetailView):
    model = Agent
    template_name = 'agents/agent_detail.html'
    context_object_name = 'agent'
    
    def get_queryset(self):
        # Only show active agents to non-staff users
        queryset = super().get_queryset()
        if not self.request.user.is_authenticated or not self.request.user.is_staff:
            queryset = queryset.filter(is_active=True)
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        agent = self.get_object()
        
        # Get agent's reviews
        reviews = agent.reviews.filter(is_approved=True)
        
        # Get agent's images
        context['agent_images'] = agent.images.all()
        
        # Calculate rating statistics
        rating_stats = {
            'count': reviews.count(),
            'average': reviews.aggregate(Avg('rating'))['rating__avg'] or 0,
            'distribution': {i: reviews.filter(rating=i).count() for i in range(1, 6)}
        }
        
        # Add data to context
        context.update({
            'reviews': reviews.order_by('-created_at')[:5],
            'rating_stats': rating_stats,
            'is_agent_owner': self.request.user == agent.owner,
        })
        
        # Add forms if user is authenticated
        if self.request.user.is_authenticated:
            from .forms import AgentReviewForm, AgentImageForm
            context.update({
                'review_form': AgentReviewForm(),
                'image_form': AgentImageForm(),
                'can_edit': (self.request.user.has_perm('home.change_agent') or 
                           self.request.user == agent.owner),
            })
        
        return context
        
    def post(self, request, *args, **kwargs):
        agent = self.get_object()
        
        if not (request.user == agent.owner or request.user.is_staff):
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse(
                    {'success': False, 'error': 'You do not have permission to add images.'}, 
                    status=403
                )
            messages.error(request, "You don't have permission to add images to this agent's profile.")
            return redirect('agents:agent_detail', pk=agent.pk)
            
        form = AgentImageForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                # If there's a new primary image, unset any existing primary
                if form.cleaned_data.get('is_primary'):
                    agent.images.filter(is_primary=True).update(is_primary=False)
                
                image = form.save(commit=False)
                image.agent = agent
                image.save()
                
                # If this is an AJAX request, return the new image HTML
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    from django.template.loader import render_to_string
                    image_html = render_to_string('agents/partials/agent_image.html', {
                        'image': image, 
                        'is_agent_owner': request.user == agent.owner
                    })
                    return JsonResponse({
                        'success': True, 
                        'message': 'Image uploaded successfully!', 
                        'image_html': image_html
                    })
                
                messages.success(request, 'Image uploaded successfully!')
                return redirect('agents:agent_detail', pk=agent.pk)
                
            except Exception as e:
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': False, 
                        'error': str(e)
                    }, status=500)
                messages.error(request, f'Error uploading image: {str(e)}')
        else:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False, 
                    'error': form.errors.as_json()
                }, status=400)
            messages.error(request, 'Please correct the errors below.')
        
        # If we get here, there was an error with the form
        return redirect('agents:agent_detail', pk=agent.pk)


class AgentCreateView(LoginRequiredMixin, CreateView):
    model = Agent
    form_class = AgentForm
    template_name = 'agents/agent_form.html'
    
    def form_valid(self, form):
        form.instance.owner = self.request.user
        response = super().form_valid(form)
        messages.success(self.request, 'Your agent profile has been created!')
        return response
    
    def get_success_url(self):
        return reverse_lazy('agents:agent_detail', kwargs={'pk': self.object.pk})


class AgentCreateWizardView(LoginRequiredMixin, SessionWizardView):
    form_list = [
        ('basic', AgentBasicInfoForm),
        ('contact', AgentContactInfoForm),
        ('social', AgentSocialLinksForm),
    ]
    template_name = 'agents/agent_form_wizard.html'
    
    def get_form_initial(self, step):
        """Set initial values for the forms if needed"""
        initial = super().get_form_initial(step)
        if step == 'basic' and not self.request.user.is_anonymous:
            initial.update({
                'email': self.request.user.email,
                'name': self.request.user.get_full_name() or self.request.user.email.split('@')[0],
            })
        return initial
    
    def get_form_kwargs(self, step=None):
        """Pass the request to the form if needed"""
        kwargs = super().get_form_kwargs(step)
        if step == 'basic':
            kwargs['user'] = self.request.user
        return kwargs
    
    def get_context_data(self, form, **kwargs):
        context = super().get_context_data(form=form, **kwargs)
        context['title'] = 'Become an Agent'
        
        # Add progress information
        step = int(self.steps.step1) + 1  # Convert to 1-based for display
        total_steps = len(self.form_list)
        context['progress'] = {
            'current': step,
            'total': total_steps,
            'percent': int((step / total_steps) * 100),
            'is_last_step': step == total_steps
        }
        
        return context
    
    def done(self, form_list, **kwargs):
        # Combine all form data
        form_data = {}
        for form in form_list:
            form_data.update(form.cleaned_data)
        
        try:
            # Create the agent
            agent = Agent.objects.create(
                owner=self.request.user,
                **{k: v for k, v in form_data.items() if k != 'service_types' and v is not None}
            )
            
            # Save many-to-many relationships
            if 'service_types' in form_data and form_data['service_types']:
                agent.service_types.set(form_data['service_types'])
            
            # Set the user's role to Agent if not already set
            if not self.request.user.role or self.request.user.role == 'Customer':
                self.request.user.role = 'Agent'
                self.request.user.save()
            
            messages.success(
                self.request,
                '🎉 Your agent profile has been created successfully! '\
                'It is now pending review by our team.'
            )
            return redirect('agents:agent_detail', pk=agent.pk)
            
        except Exception as e:
            messages.error(
                self.request,
                f'An error occurred while creating your agent profile. Please try again. Error: {str(e)}'
            )
            return redirect('agents:agent_create')

class AgentUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Agent
    form_class = AgentForm
    template_name = 'agents/agent_form.html'
    
    def test_func(self):
        agent = self.get_object()
        return self.request.user == agent.owner or self.request.user.has_perm('home.change_agent')
    
    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        
        # Handle AJAX file uploads (for photo/logo)
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return self.handle_ajax_upload(request)
            
        # Handle regular form submission
        return super().post(request, *args, **kwargs)
    
    def handle_ajax_upload(self, request):
        """Handle AJAX file upload for photo and logo"""
        from django.http import JsonResponse
        
        try:
            agent = self.get_object()
            
            # Handle photo upload
            if 'photo' in request.FILES:
                agent.photo = request.FILES['photo']
                agent.save(update_fields=['photo', 'updated_at'])
                return JsonResponse({
                    'success': True,
                    'message': 'Profile photo updated successfully',
                    'photo_url': agent.photo.url if agent.photo else '',
                    'logo_url': agent.logo.url if agent.logo else ''
                })
                
            # Handle logo upload
            elif 'logo' in request.FILES:
                agent.logo = request.FILES['logo']
                agent.save(update_fields=['logo', 'updated_at'])
                return JsonResponse({
                    'success': True,
                    'message': 'Logo updated successfully',
                    'photo_url': agent.photo.url if agent.photo else '',
                    'logo_url': agent.logo.url if agent.logo else ''
                })
                
            return JsonResponse({
                'success': False,
                'error': 'No file was uploaded'
            }, status=400)
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)
    
    def form_valid(self, form):
        response = super().form_valid(form)
        
        # Only show success message for regular form submission, not AJAX
        if not self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            messages.success(self.request, 'Agent profile has been updated!')
        
        return response
    
    def get_success_url(self):
        return reverse_lazy('agents:agent_detail', kwargs={'pk': self.object.pk})

class AgentDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Agent
    template_name = 'agents/agent_confirm_delete.html'
    success_url = reverse_lazy('home:agent_list')
    
    def test_func(self):
        agent = self.get_object()
        return self.request.user == agent.owner or self.request.user.has_perm('home.delete_agent')
    
    def delete(self, request, *args, **kwargs):
        messages.success(request, 'Agent profile has been deleted.')
        return super().delete(request, *args, **kwargs)

def add_agent_image(request, pk):
    agent = get_object_or_404(Agent, pk=pk)
    
    # Check permissions
    if request.user != agent.owner and not request.user.is_superuser:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)
        messages.error(request, "You don't have permission to add images to this agent's profile.")
        return redirect('agents:agent_detail', pk=agent.pk)
    
    if request.method == 'POST':
        form = AgentImageForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                # If there's a new primary image, unset any existing primary
                if form.cleaned_data.get('is_primary'):
                    agent.images.filter(is_primary=True).update(is_primary=False)
                
                image = form.save(commit=False)
                image.agent = agent
                image.save()
                
                # If this is an AJAX request, return the new image HTML
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    from django.template.loader import render_to_string
                    image_html = render_to_string('agents/partials/agent_image.html', {
                        'image': image, 
                        'is_agent_owner': request.user == agent.owner
                    })
                    return JsonResponse({
                        'success': True, 
                        'message': 'Image uploaded successfully!', 
                        'image_html': image_html
                    })
                
                messages.success(request, 'Image uploaded successfully!')
                return redirect('agents:agent_detail', pk=agent.pk)
                
            except Exception as e:
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({'success': False, 'error': str(e)}, status=500)
                messages.error(request, f'Error uploading image: {str(e)}')
                return redirect('agents:agent_detail', pk=agent.pk)
        else:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'error': 'Invalid form data'}, status=400)
            messages.error(request, 'Error adding image. Please check the form.')
    
    return redirect('agents:agent_detail', pk=agent.pk)

def delete_agent_image(request, pk, image_pk):
    agent = get_object_or_404(Agent, pk=pk)
    if request.user != agent.owner and not request.user.is_superuser:
        messages.error(request, "You don't have permission to delete this image.")
        return redirect('agents:agent_detail', pk=pk)
    
    image = get_object_or_404(AgentImage, pk=image_pk, agent=agent)
    image.delete()
    messages.success(request, 'Image deleted successfully.')
    return redirect('agents:agent_detail', pk=pk)


def set_primary_image(request, pk):
    """Set an image as primary for an agent"""
    image = get_object_or_404(AgentImage, pk=pk)
    
    # Check permissions
    if request.user != image.agent.owner and not request.user.is_superuser:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)
        messages.error(request, "You don't have permission to modify this image.")
        return redirect('agents:agent_detail', pk=image.agent.pk)
    
    try:
        # Unset any existing primary image for this agent
        AgentImage.objects.filter(agent=image.agent, is_primary=True).update(is_primary=False)
        
        # Set this image as primary
        image.is_primary = True
        image.save()
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': True, 'message': 'Primary image updated successfully!'})
        
        messages.success(request, 'Primary image updated successfully!')
        return redirect('agents:agent_detail', pk=image.agent.pk)
        
    except Exception as e:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'error': str(e)}, status=500)
        
        messages.error(request, f'Error updating primary image: {str(e)}')
        return redirect('agents:agent_detail', pk=image.agent.pk)


def delete_image(request, pk):
    """Delete an agent image via AJAX"""
    image = get_object_or_404(AgentImage, pk=pk)
    
    # Check permissions
    if request.user != image.agent.owner and not request.user.is_superuser:
        return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)
    
    try:
        agent_pk = image.agent.pk
        image.delete()
        
        return JsonResponse({
            'success': True, 
            'message': 'Image deleted successfully!',
            'agent_pk': agent_pk
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


class AgentProfileView(LoginRequiredMixin, TemplateView):
    """View for displaying the logged-in agent's profile."""
    template_name = 'agents/agent_profile.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        agent = get_object_or_404(Agent, user=self.request.user)
        context['agent'] = agent
        context['title'] = 'My Profile'
        return context
