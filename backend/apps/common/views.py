"""Health, readiness, version and meta endpoints."""
from django.conf import settings
from django.core.cache import cache
from django.db import connection
from rest_framework import permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from .permissions import PERMISSIONS
from .drf_permissions import IsOrganizationMember


@api_view(["GET"])
@permission_classes([permissions.AllowAny])
def liveness(request):
    return Response({"status": "ok", "service": "siteforge-api", "version": "1.0.0"})


@api_view(["GET"])
@permission_classes([permissions.AllowAny])
def readiness(request):
    checks = {}
    ok = True

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        checks["database"] = "ok"
    except Exception as exc:  # pragma: no cover
        checks["database"] = f"error: {exc}"
        ok = False

    try:
        cache.set("healthcheck", "1", 5)
        checks["cache"] = "ok" if cache.get("healthcheck") == "1" else "degraded"
    except Exception as exc:  # pragma: no cover
        checks["cache"] = f"error: {exc}"

    checks["storage"] = "ok"
    status_code = 200 if ok else 503
    return Response({"status": "ready" if ok else "unavailable", "checks": checks}, status=status_code)


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
