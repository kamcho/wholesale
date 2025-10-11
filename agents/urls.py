from django.urls import path
from . import views
from django.contrib.auth.decorators import login_required

app_name = 'agents'  # Keeping the same app name for other agent-related views

urlpatterns = [
    # Agent Dashboard
    path('dashboard/', login_required(views.AgentDashboardView.as_view()), name='agent_dashboard'),
    
    # Agent CRUD - Note: agent_list has been moved to home app
    path('create/', views.AgentCreateWizardView.as_view(), name='agent_create'),
    path('<int:pk>/', views.AgentDetailView.as_view(), name='agent_detail'),
    path('<int:pk>/update/', views.AgentUpdateView.as_view(), name='agent_update'),
    path('<int:pk>/delete/', views.AgentDeleteView.as_view(), name='agent_delete'),
    
    # Agent Images
    path('<int:pk>/add-image/', views.add_agent_image, name='agent_add_image'),
    path('<int:pk>/delete-image/<int:image_pk>/', views.delete_agent_image, name='agent_delete_image'),
    path('image/<int:pk>/set-primary/', views.set_primary_image, name='set_primary_image'),
    path('image/<int:pk>/delete/', views.delete_image, name='delete_image'),
    
    # Agent Profile
    path('profile/', login_required(views.AgentProfileView.as_view()), name='agent_profile'),
]
