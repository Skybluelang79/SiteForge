"""Health, readiness, version and meta endpoints."""
import os

from django.conf import settings
from django.core.cache import cache
from django.db import connection
from rest_framework import permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from .drf_permissions import IsOrganizationMember
from .permissions import PERMISSIONS


@api_view(["GET"])
@permission_classes([permissions.AllowAny])
def liveness(request):
    return Response({"status": "ok", "service": "siteforge-api", "version": "1.0.0"})


def _redis_check():
    backend = settings.CHANNEL_LAYERS.get("default", {}).get("BACKEND", "")
    if "RedisChannelLayer" not in backend:
        return "not_configured"
    try:
        import redis

        client = redis.from_url(settings.REDIS_URL, socket_connect_timeout=2, socket_timeout=2)
        client.ping()
        return "ok"
    except Exception:
        return "error"


def _storage_check():
    backend = settings.STORAGES.get("default", {}).get("BACKEND", "")
    if "FileSystemStorage" not in backend:
        return "ok"
    root = str(settings.MEDIA_ROOT)
    if os.path.isdir(root) and os.access(root, os.W_OK):
        return "ok"
    return "degraded"


@api_view(["GET"])
@permission_classes([permissions.AllowAny])
def readiness(request):
    checks = {}
    ok = True

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        checks["database"] = "ok"
    except Exception:
        checks["database"] = "error"
        ok = False

    checks["redis"] = _redis_check()
    if checks["redis"] == "error":
        ok = False

    try:
        cache.set("healthcheck", "1", 5)
        checks["cache"] = "ok" if cache.get("healthcheck") == "1" else "degraded"
    except Exception:
        checks["cache"] = "degraded"

    checks["storage"] = _storage_check()
    return Response(
        {"status": "ready" if ok else "unavailable", "checks": checks},
        status=200 if ok else 503,
    )


@api_view(["GET"])
@permission_classes([IsOrganizationMember])
def permission_catalog(request):
    membership = request.membership
    return Response(
        {
            "role": membership.role_code,
            "permissions": sorted(membership.effective_permissions),
            "catalog": [
                {"key": key, "description": desc} for key, desc in sorted(PERMISSIONS.items())
            ],
        }
    )
