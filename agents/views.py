from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from formtools.wizard.views import SessionWizardView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.urls import reverse_lazy
from django.contrib import messages
from django.db.models import Q, Count, Avg
from django.core.paginator import Paginator

from home.models import Agent, AgentImage, ServiceCategory
from .forms import (
    AgentForm,
    AgentImageForm,
    AgentSearchForm,
    AgentBasicInfoForm,
    AgentContactInfoForm,
    AgentSocialLinksForm,
)

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

class AgentDetailView(DetailView):
    model = Agent
    template_name = 'agents/agent_detail.html'
    context_object_name = 'agent'
    
    def get_queryset(self):
        return Agent.objects.select_related('owner').prefetch_related(
            'service_types', 'images', 'reviews__user'
        )
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        agent = self.get_object()
        
        # Get reviews with user info
        reviews = agent.reviews.select_related('user').order_by('-created_at')
        
        # Calculate rating stats
        rating_stats = {
            'average': agent.reviews.aggregate(avg=Avg('rating'))['avg'] or 0,
            'count': reviews.count(),
            'distribution': agent.reviews.values('rating')
                                 .annotate(count=Count('rating'))
                                 .order_by('-rating')
        }
        
        context.update({
            'reviews': reviews[:5],  # Show only 5 most recent reviews
            'rating_stats': rating_stats,
            'image_form': AgentImageForm(),
            'is_owner': self.request.user == agent.owner,
            'can_edit': self.request.user.has_perm('home.change_agent') or self.request.user == agent.owner,
        })
        return context

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

    def get_context_data(self, form, **kwargs):
        context = super().get_context_data(form=form, **kwargs)
        context['steps_meta'] = [
            ('basic', 'Basic Info'),
            ('contact', 'Contact'),
            ('social', 'Social'),
        ]
        return context

    def done(self, form_list, **kwargs):
        # Combine cleaned data from steps
        aggregated = {}
        for form in form_list:
            aggregated.update(form.cleaned_data)

        # Create Agent
        agent = Agent(owner=self.request.user)
        # Fields excluding M2M service_types
        direct_fields = [
            'name', 'description', 'email', 'phone', 'phone2', 'website',
            'address', 'city', 'country',
            'social_facebook', 'social_twitter', 'social_linkedin', 'social_instagram'
        ]
        for field in direct_fields:
            if field in aggregated:
                setattr(agent, field, aggregated[field])
        agent.save()

        # Handle M2M service_types
        service_types = aggregated.get('service_types')
        if service_types is not None:
            agent.service_types.set(service_types)

        messages.success(self.request, 'Your agent profile has been created!')
        return redirect('agents:agent_detail', pk=agent.pk)

class AgentUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Agent
    form_class = AgentForm
    template_name = 'agents/agent_form.html'
    
    def test_func(self):
        agent = self.get_object()
        return self.request.user == agent.owner or self.request.user.has_perm('home.change_agent')
    
    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, 'Agent profile has been updated!')
        return response
    
    def get_success_url(self):
        return reverse_lazy('agents:agent_detail', kwargs={'pk': self.object.pk})

class AgentDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Agent
    template_name = 'agents/agent_confirm_delete.html'
    success_url = reverse_lazy('agents:agent_list')
    
    def test_func(self):
        agent = self.get_object()
        return self.request.user == agent.owner or self.request.user.has_perm('home.delete_agent')
    
    def delete(self, request, *args, **kwargs):
        messages.success(request, 'Agent profile has been deleted.')
        return super().delete(request, *args, **kwargs)

def add_agent_image(request, pk):
    agent = get_object_or_404(Agent, pk=pk)
    
    if request.method == 'POST' and request.user == agent.owner:
        form = AgentImageForm(request.POST, request.FILES)
        if form.is_valid():
            image = form.save(commit=False)
            image.agent = agent
            image.save()
            messages.success(request, 'Image added successfully!')
        else:
            messages.error(request, 'Error adding image. Please check the form.')
    
    return redirect('agents:agent_detail', pk=agent.pk)

def delete_agent_image(request, pk, image_pk):
    image = get_object_or_404(AgentImage, pk=image_pk, agent_id=pk)
    
    if request.method == 'POST' and (request.user == image.agent.owner or request.user.has_perm('home.delete_agentimage')):
        image.delete()
        messages.success(request, 'Image deleted successfully!')
    
    return redirect('agents:agent_detail', pk=pk)
