from django.urls import path
from . import views

urlpatterns = [
    path('sessions/<uuid:device_id>/', views.scan_sessions_list, name='scan_sessions_list'),
]
