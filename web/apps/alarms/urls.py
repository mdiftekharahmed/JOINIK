from django.urls import path
from . import views

urlpatterns = [
    path('', views.alarm_list, name='alarm_list'),
    path('<uuid:alarm_id>/', views.alarm_detail, name='alarm_detail'),
    path('<uuid:alarm_id>/action/', views.alarm_action, name='alarm_action'),
    path('api/<uuid:alarm_id>/cancel/', views.cancel_alarm_api, name='cancel_alarm_api'),
]
