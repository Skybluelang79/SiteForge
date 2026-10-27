"""Unified API exception handling: consistent error envelope."""
import logging

from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.http import Http404
from rest_framework import exceptions, status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

logger = logging.getLogger("apps.api")


def api_exception_handler(exc, context):
    """Return {"error": {"code", "message", "details"}} for all errors."""
    if isinstance(exc, DjangoPermissionDenied):
        exc = exceptions.PermissionDenied(detail=str(exc) or "You do not have permission to perform this action.")
    if isinstance(exc, Http404):
        exc = exceptions.NotFound(detail="Not found.")

    response = drf_exception_handler(exc, context)

    if response is None:
        logger.exception("unhandled_api_error", exc_info=exc)
        return Response(
            {
                "error": {
                    "code": "internal_error",
                    "message": "An unexpected error occurred.",
                    "details": {},
                }
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    if isinstance(exc, exceptions.ValidationError):
        code = "validation_error"
    elif isinstance(exc, exceptions.AuthenticationFailed):
        code = "authentication_failed"
    elif isinstance(exc, exceptions.NotAuthenticated):
        code = "not_authenticated"
    elif isinstance(exc, exceptions.PermissionDenied):
        code = "permission_denied"
    elif isinstance(exc, exceptions.NotFound):
        code = "not_found"
    elif isinstance(exc, exceptions.Throttled):
        code = "throttled"
    elif isinstance(exc, exceptions.APIException):
        code = exc.default_code
    else:  # pragma: no cover
        code = "error"

    response.data = {
        "error": {
            "code": code,
            "message": _message(exc, response),
            "details": _details(response.data),
        }
    }
    return response


def _message(exc, response):
    if isinstance(exc.detail, (list, dict)):
        return "Request validation failed." if response.status_code == 400 else exc.default_detail
    return str(exc.detail)


def _details(data):
    detail = data.get("detail", data) if isinstance(data, dict) else data
    return detail if isinstance(detail, (dict, list)) else {}
