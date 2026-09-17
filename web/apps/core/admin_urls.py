from django.urls import path
from . import admin_views

urlpatterns = [
    path('sensors/', admin_views.sensor_config, name='admin_sensors'),
    path('sensors/<int:pk>/edit/', admin_views.sensor_edit, name='admin_sensor_edit'),
    path('ai-model/', admin_views.ai_model, name='admin_ai_model'),
    path('users/', admin_views.users, name='admin_users'),
    path('organizations/', admin_views.organizations, name='admin_organizations'),
    path('audit/', admin_views.audit_log, name='admin_audit'),
]
