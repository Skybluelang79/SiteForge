"""Idempotency support for money-moving and approval POSTs.

Clients may send an `Idempotency-Key` header on POST/PATCH requests. The first
successful response is cached; replays with the same key + body return the
cached response without re-executing side effects.
"""
import hashlib
import json

IDEMPOTENT_METHODS = {"POST", "PUT", "PATCH"}


class IdempotencyMiddleware:
    """Cache and replay responses for requests carrying an Idempotency-Key."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        key = request.META.get("HTTP_IDEMPOTENCY_KEY")
        if (
            not key
            or request.method not in IDEMPOTENT_METHODS
            or not request.user.is_authenticated
        ):
            return self.get_response(request)

        endpoint = f"{request.method} {request.path}"
        body_bytes = request.body or b""
        request_hash = hashlib.sha256(body_bytes).hexdigest()

        from .models import IdempotencyKey

        existing = (
            IdempotencyKey.objects.filter(
                user=request.user, key=key, endpoint=endpoint, completed_at__isnull=False
            )
            .order_by("-created_at")
            .first()
        )
        if existing:
            if existing.request_hash == request_hash:
                from django.http import JsonResponse

                return JsonResponse(existing.response_body, status=existing.response_status)
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

        record, _ = IdempotencyKey.objects.get_or_create(
            user=request.user,
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
                from django.utils import timezone

                record.response_status = response.status_code
                record.response_body = payload
                record.completed_at = timezone.now()
                record.save(update_fields=["response_status", "response_body", "completed_at"])
        return response
