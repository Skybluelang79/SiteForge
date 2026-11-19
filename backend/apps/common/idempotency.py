"""Idempotency support for money-moving and approval POSTs.

Clients may send an `Idempotency-Key` header on POST/PATCH requests. The first
successful response is cached; replays with the same key + body return the
cached response without re-executing side effects.
"""
import hashlib
import json
from datetime import timedelta

from django.utils import timezone
from rest_framework_simplejwt.authentication import JWTAuthentication

IDEMPOTENT_METHODS = {"POST", "PUT", "PATCH"}
IN_PROGRESS_TTL = timedelta(seconds=60)


def _authenticated_user(request):
    user = getattr(request, "user", None)
    if user is not None and getattr(user, "is_authenticated", False):
        return user
    header = request.META.get("HTTP_AUTHORIZATION", "")
    if not header.lower().startswith("bearer "):
        return None
    try:
        authenticator = JWTAuthentication()
        validated = authenticator.get_validated_token(header.split(" ", 1)[1])
        return authenticator.get_user(validated)
    except Exception:
        return None


class IdempotencyMiddleware:
    """Cache and replay responses for requests carrying an Idempotency-Key."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        key = request.META.get("HTTP_IDEMPOTENCY_KEY")
        if not key or request.method not in IDEMPOTENT_METHODS:
            return self.get_response(request)

        user = _authenticated_user(request)
        if user is None or not getattr(user, "is_authenticated", False):
            return self.get_response(request)

        endpoint = f"{request.method} {request.path}"
        body_bytes = request.body or b""
        request_hash = hashlib.sha256(body_bytes).hexdigest()

        from .models import IdempotencyKey

        existing = (
            IdempotencyKey.objects.filter(user=user, key=key, endpoint=endpoint)
            .order_by("-created_at")
            .first()
        )
        if existing:
            if existing.request_hash != request_hash:
                from django.http import JsonResponse

                return JsonResponse(
                    {
                        "error": {
                            "code": "idempotency_key_reuse",
                            "message": "This idempotency key was already used with a different payload.",
                            "details": {},
                        }
                    },
                    status=409,
                )
            if existing.completed_at is not None:
                from django.http import JsonResponse

                return JsonResponse(existing.response_body, status=existing.response_status)
            if timezone.now() - existing.created_at < IN_PROGRESS_TTL:
                from django.http import JsonResponse

                return JsonResponse(
                    {
                        "error": {
                            "code": "idempotency_key_in_progress",
                            "message": "A request with this idempotency key is already in progress.",
                            "details": {},
                        }
                    },
                    status=409,
                )
            existing.delete()

        record, _ = IdempotencyKey.objects.get_or_create(
            user=user,
            key=key,
            endpoint=endpoint,
            defaults={"request_hash": request_hash},
        )

        response = self.get_response(request)

        if 200 <= response.status_code < 300:
            try:
                payload = json.loads(response.content.decode())
            except (ValueError, UnicodeDecodeError):
                payload = None
            if payload is not None:
                record.response_status = response.status_code
                record.response_body = payload
                record.completed_at = timezone.now()
                record.save(update_fields=["response_status", "response_body", "completed_at"])
        else:
            record.delete()
        return response
