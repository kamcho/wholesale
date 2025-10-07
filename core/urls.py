from django.urls import path
from . import views
from . import chat_views

app_name = 'core'

urlpatterns = [
    # Chat API
    path('api/chat/', chat_views.chat_api, name='chat_api'),
    
    # Existing URLs
    path('health/', views.health, name='health'),
    path('gava/pin-check/', views.gava_pin_check, name='gava_pin_check'),
    path('gava/pin-check/form/', views.pin_check_form, name='pin_check_form'),
    path('gava/pending-returns/', views.gava_pending_returns, name='gava_pending_returns'),
    path('gava/pending-returns/form/', views.pending_returns_form, name='pending_returns_form'),
]
