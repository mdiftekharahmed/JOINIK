from django.urls import path
from . import views

urlpatterns = [
    path('<uuid:device_id>/', views.telemetry_table, name='telemetry_table'),
    path('<uuid:device_id>/export/', views.telemetry_export_csv, name='telemetry_export_csv'),
    path('<uuid:device_id>/analyze/', views.telemetry_historical_analysis, name='telemetry_historical_analysis'),
    path('parameters/', views.parameter_list, name='parameter_list'),
    path('parameters/<int:param_id>/update/', views.parameter_update, name='parameter_update'),
]
