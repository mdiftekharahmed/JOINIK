from django.urls import path
from . import views

urlpatterns = [
    path('', views.ai_hub, name='ai_hub'),
    path('upload/', views.ai_model_upload, name='ai_model_upload'),
    path('<uuid:model_id>/activate/', views.ai_model_activate, name='ai_model_activate'),
]
