from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('api/dashboard-stats/', views.dashboard_api, name='dashboard_api'),
]
