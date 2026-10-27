"""ASGI entrypoint (HTTP + WebSockets via Daphne/uvicorn)."""
import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

django_asgi_app = get_asgi_application()

from channels.routing import ProtocolTypeRouter, URLRouter  # noqa: E402
from channels.security.websocket import AllowedHostsOriginValidator  # noqa: E402
from django.urls import re_path  # noqa: E402

from apps.notifications.consumers import NotificationConsumer  # noqa: E402
from config.middleware import JwtAuthMiddleware  # noqa: E402

websocket_urlpatterns = [
    re_path(r"^ws/notifications/$", NotificationConsumer.as_asgi()),
]

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": AllowedHostsOriginValidator(JwtAuthMiddleware(URLRouter(websocket_urlpatterns))),
    }
)
