from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', include('apps.core.admin_urls')),
    path('auth/', include('apps.accounts.urls')),
    path('', include('apps.core.urls')),
    path('devices/', include('apps.devices.urls')),
    path('telemetry/', include('apps.telemetry.urls')),
    path('alarms/', include('apps.alarms.urls')),
    path('ai/', include('apps.ai_engine.urls')),
    path('analytics/', include('apps.analytics.urls')),
    path('data/', include('apps.analytics.export_urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
