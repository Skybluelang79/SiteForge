"""Validation helpers for outbound integrations."""
import ipaddress
import socket
from urllib.parse import urlparse

from django.conf import settings
from rest_framework.exceptions import ValidationError


def validate_webhook_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValidationError("target_url must be an absolute http(s) URL.")
    if parsed.username or parsed.password:
        raise ValidationError("target_url must not embed credentials.")

    host = parsed.hostname.lower().rstrip(".")
    if getattr(settings, "WEBHOOK_ALLOW_PRIVATE_TARGETS", False):
        return url

    blocked_names = {"localhost", "localhost.localdomain"}
    if host in blocked_names or host.endswith(".localhost"):
        raise ValidationError("target_url may not point to localhost.")

    try:
        address = ipaddress.ip_address(host)
        if not address.is_global:
            raise ValidationError("target_url may not point to a private network address.")
        return url
    except ValueError:
        pass

    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        resolved = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror:
        return url

    for entry in resolved:
        try:
            address = ipaddress.ip_address(entry[4][0])
        except ValueError:
            raise ValidationError("target_url host resolved to an invalid address.")
        if not address.is_global:
            raise ValidationError("target_url may not point to a private network address.")
    return url
