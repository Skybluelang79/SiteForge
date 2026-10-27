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
