"""ASGI middleware: authenticate WebSocket connections with JWT."""
from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from django.conf import settings
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import AccessToken


@database_sync_to_async
def get_user_from_token(token: str):
    from django.contrib.auth import get_user_model

    try:
        validated = AccessToken(token)
        user_id = validated["user_id"]
    except (TokenError, KeyError):
        return AnonymousUser()
    User = get_user_model()
    try:
        return User.objects.get(id=user_id, is_active=True)
    except User.DoesNotExist:
        return AnonymousUser()


class JwtAuthMiddleware:
    """Resolve the connecting user from ?token=<access_token> or Authorization header."""

    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        query = parse_qs(scope.get("query_string", b"").decode())
        token = None
        if "token" in query and query["token"]:
            token = query["token"][0]
        else:
            headers = dict(scope.get("headers") or [])
            auth_header = headers.get(b"authorization", b"").decode()
            if auth_header.lower().startswith("bearer "):
                token = auth_header[7:]
        scope["user"] = await get_user_from_token(token) if token else AnonymousUser()
        return await self.inner(scope, receive, send)
