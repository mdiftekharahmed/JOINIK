import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

django_asgi_app = get_asgi_application()

from apps.telemetry import routing as telemetry_routing
from apps.alarms import routing as alarms_routing

application = ProtocolTypeRouter({
    'http': django_asgi_app,
    'websocket': AuthMiddlewareStack(
        URLRouter(
            telemetry_routing.websocket_urlpatterns +
            alarms_routing.websocket_urlpatterns
        )
    ),
})
