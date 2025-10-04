from django.urls import path
from . import views

app_name = 'agents'

urlpatterns = [
    # Agent CRUD
    path('', views.AgentListView.as_view(), name='agent_list'),
    path('create/', views.AgentCreateView.as_view(), name='agent_create'),
    path('<int:pk>/', views.AgentDetailView.as_view(), name='agent_detail'),
    path('<int:pk>/update/', views.AgentUpdateView.as_view(), name='agent_update'),
    path('<int:pk>/delete/', views.AgentDeleteView.as_view(), name='agent_delete'),
    
    # Agent Images
    path('<int:pk>/add-image/', views.add_agent_image, name='agent_add_image'),
    path('<int:pk>/delete-image/<int:image_pk>/', views.delete_agent_image, name='agent_delete_image'),
]
