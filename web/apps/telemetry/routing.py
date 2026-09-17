from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/telemetry/(?P<device_id>[\w-]+)/$', consumers.TelemetryConsumer.as_asgi()),
]
