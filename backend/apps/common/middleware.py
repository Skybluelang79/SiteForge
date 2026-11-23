"""Middleware: attach request ids and log unhandled exceptions with context."""
import logging
import uuid

from .logging import JsonLogFormatter  # noqa: F401  (re-exported for settings)

logger = logging.getLogger("apps.request")


class RequestIdMiddleware:
    """Assign a request id and add it to the response headers."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.request_id = request.META.get("HTTP_X_REQUEST_ID") or uuid.uuid4().hex
        response = self.get_response(request)
        response["X-Request-Id"] = request.request_id
        return response


class SecurityHeadersMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        from django.conf import settings

        response = self.get_response(request)
        csp = getattr(settings, "SECURITY_CSP", "")
        if csp:
            header = (
                "Content-Security-Policy-Report-Only"
                if getattr(settings, "SECURITY_CSP_REPORT_ONLY", False)
                else "Content-Security-Policy"
            )
            response.setdefault(header, csp)
        referrer_policy = getattr(settings, "SECURITY_REFERRER_POLICY", "")
        if referrer_policy:
            response.setdefault("Referrer-Policy", referrer_policy)
        permissions_policy = getattr(settings, "SECURITY_PERMISSIONS_POLICY", "")
        if permissions_policy:
            response.setdefault("Permissions-Policy", permissions_policy)
        return response
