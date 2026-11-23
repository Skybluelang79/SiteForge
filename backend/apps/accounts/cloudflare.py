"""Cloudflare Turnstile and Access verification helpers."""
import httpx
import jwt
from django.conf import settings
from jwt import PyJWKClient
from rest_framework import exceptions, serializers

TURNSTILE_VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"


def _turnstile_secret():
    if not getattr(settings, "TURNSTILE_ENABLED", False):
        return ""
    return getattr(settings, "TURNSTILE_SECRET_KEY", "") or ""


def verify_turnstile(token, remoteip=None):
    secret = _turnstile_secret()
    if not secret:
        return True
    if not isinstance(token, str) or not token.strip():
        raise serializers.ValidationError({"turnstile_token": "Turnstile verification failed."})

    payload = {"secret": secret, "response": token.strip()}
    if remoteip:
        payload["remoteip"] = remoteip
    hostname = getattr(settings, "TURNSTILE_HOSTNAME", "") or ""
    if hostname:
        payload["hostname"] = hostname

    try:
        response = httpx.post(TURNSTILE_VERIFY_URL, json=payload, timeout=10)
        response.raise_for_status()
        data = response.json()
    except (httpx.HTTPError, ValueError, TypeError):
        raise serializers.ValidationError({"turnstile_token": "Turnstile verification failed."})

    if not isinstance(data, dict) or not data.get("success"):
        raise serializers.ValidationError({"turnstile_token": "Turnstile verification failed."})
    if hostname and data.get("hostname") != hostname:
        raise serializers.ValidationError({"turnstile_token": "Turnstile verification failed."})
    return True


def verify_access_assertion(assertion):
    if not isinstance(assertion, str) or not assertion.strip():
        raise exceptions.AuthenticationFailed("Missing Cloudflare Access assertion.")

    domain = (getattr(settings, "CLOUDFLARE_ACCESS_TEAM_DOMAIN", "") or "").strip().rstrip("/")
    audience = getattr(settings, "CLOUDFLARE_ACCESS_AUD", "") or ""
    if not domain or not audience:
        raise exceptions.AuthenticationFailed("Cloudflare Access is not configured.")

    jwks_url = f"https://{domain}/cdn-cgi/access/certs"
    try:
        signing_key = PyJWKClient(jwks_url).get_signing_key_from_jwt(assertion.strip()).key
        return jwt.decode(
            assertion.strip(),
            signing_key,
            algorithms=["RS256"],
            audience=audience,
            issuer=f"https://{domain}",
        )
    except (jwt.PyJWTError, ValueError, TypeError, KeyError, AttributeError) as exc:
        raise exceptions.AuthenticationFailed("Invalid Cloudflare Access assertion.") from exc
