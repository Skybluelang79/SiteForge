"""Cloudflare Turnstile and Access authentication tests."""
from unittest.mock import MagicMock, patch

import jwt
import pytest
from django.test import override_settings
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.common.testing import UserFactory, authenticated_client

pytestmark = pytest.mark.django_db

REGISTER_URL = "/api/v1/auth/register/"
LOGIN_URL = "/api/v1/auth/login/"
ACCESS_URL = "/api/v1/auth/cloudflare-access/"


def _registration(**extra):
    payload = {
        "email": "new@example.test",
        "password": "StrongPass123!",
        "password_confirm": "StrongPass123!",
        "first_name": "New",
        "last_name": "User",
    }
    payload.update(extra)
    return payload


def test_disabled_turnstile_allows_register_and_login(api_client):
    user = UserFactory()
    with patch("apps.accounts.cloudflare.httpx.post") as post:
        registered = api_client.post(REGISTER_URL, _registration(), format="json")
    assert registered.status_code == 201, registered.content
    assert post.call_count == 0

    logged_in = api_client.post(
        LOGIN_URL, {"email": user.email, "password": "TestPass123!"}, format="json"
    )
    assert logged_in.status_code == 200, logged_in.content


@override_settings(TURNSTILE_ENABLED=True, TURNSTILE_SECRET_KEY="turnstile-secret")
def test_enabled_turnstile_rejects_missing_token(api_client):
    user = UserFactory()
    with patch("apps.accounts.cloudflare.httpx.post") as post:
        registered = api_client.post(REGISTER_URL, _registration(), format="json")
        logged_in = api_client.post(
            LOGIN_URL, {"email": user.email, "password": "TestPass123!"}, format="json"
        )
    assert registered.status_code == 400
    assert logged_in.status_code == 400
    assert "turnstile_token" in str(registered.data)
    assert "turnstile_token" in str(logged_in.data)
    assert post.call_count == 0


@override_settings(TURNSTILE_ENABLED=True, TURNSTILE_SECRET_KEY="turnstile-secret")
def test_enabled_turnstile_rejects_invalid_token(api_client):
    response_mock = MagicMock()
    response_mock.json.return_value = {"success": False}
    with patch("apps.accounts.cloudflare.httpx.post", return_value=response_mock) as post:
        registered = api_client.post(
            REGISTER_URL, _registration(turnstile_token="bad-token"), format="json"
        )
    assert registered.status_code == 400
    assert post.call_args.kwargs["json"]["response"] == "bad-token"


@override_settings(
    TURNSTILE_ENABLED=True,
    TURNSTILE_SECRET_KEY="turnstile-secret",
    TURNSTILE_HOSTNAME="siteforge.test",
)
def test_enabled_turnstile_accepts_matching_token(api_client):
    response_mock = MagicMock()
    response_mock.json.return_value = {"success": True, "hostname": "siteforge.test"}
    with patch("apps.accounts.cloudflare.httpx.post", return_value=response_mock):
        registered = api_client.post(
            REGISTER_URL, _registration(turnstile_token="good-token"), format="json"
        )
    assert registered.status_code == 201, registered.content


def test_access_endpoint_rejects_missing_assertion(api_client):
    response = api_client.post(ACCESS_URL, {}, format="json")
    assert response.status_code == 401
    assert response.data["error"]["code"] == "authentication_failed"


@override_settings(
    CLOUDFLARE_ACCESS_TEAM_DOMAIN="siteforge.cloudflareaccess.com",
    CLOUDFLARE_ACCESS_AUD="access-audience",
)
def test_access_endpoint_rejects_invalid_assertion(api_client):
    with patch("apps.accounts.cloudflare.PyJWKClient") as jwks_client:
        jwks_client.return_value.get_signing_key_from_jwt.side_effect = jwt.PyJWKClientError("bad")
        response = api_client.post(ACCESS_URL, {"assertion": "bad.jwt.token"}, format="json")
    assert response.status_code == 401
    assert response.data["error"]["code"] == "authentication_failed"


@override_settings(
    CLOUDFLARE_ACCESS_TEAM_DOMAIN="siteforge.cloudflareaccess.com",
    CLOUDFLARE_ACCESS_AUD="access-audience",
)
def test_access_endpoint_issues_tokens_for_valid_assertion(api_client):
    claims = {"email": "sso-new@example.test", "given_name": "SSO", "family_name": "User"}
    with (
        patch("apps.accounts.cloudflare.PyJWKClient") as jwks_client,
        patch("apps.accounts.cloudflare.jwt.decode", return_value=claims) as decode,
    ):
        jwks_client.return_value.get_signing_key_from_jwt.return_value.key = "public-key"
        response = api_client.post(ACCESS_URL, {"assertion": "signed.jwt.token"}, format="json")

    assert response.status_code == 200, response.content
    assert "access" in response.data and "refresh" in response.data
    assert jwks_client.call_args.args[0] == (
        "https://siteforge.cloudflareaccess.com/cdn-cgi/access/certs"
    )
    assert decode.call_args.kwargs["algorithms"] == ["RS256"]
    assert decode.call_args.kwargs["audience"] == "access-audience"
    assert decode.call_args.kwargs["issuer"] == "https://siteforge.cloudflareaccess.com"

    user = User.objects.get(email="sso-new@example.test")
    assert user.email_verified_at is not None
    assert not user.has_usable_password()
    verified_client = APIClient()
    verified_client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")
    assert verified_client.get("/api/v1/auth/me/").status_code == 200


@override_settings(
    CLOUDFLARE_ACCESS_TEAM_DOMAIN="siteforge.cloudflareaccess.com",
    CLOUDFLARE_ACCESS_AUD="access-audience",
)
def test_access_endpoint_reuses_existing_user(api_client):
    user = UserFactory(email="sso-existing@example.test")
    assert authenticated_client(user).get("/api/v1/auth/me/").status_code == 200
    with (
        patch("apps.accounts.cloudflare.PyJWKClient") as jwks_client,
        patch(
            "apps.accounts.cloudflare.jwt.decode", return_value={"email": user.email}
        ),
    ):
        jwks_client.return_value.get_signing_key_from_jwt.return_value.key = "public-key"
        response = api_client.post(
            ACCESS_URL, {}, HTTP_CF_ACCESS_JWT_ASSERTION="signed.jwt.token", format="json"
        )
    assert response.status_code == 200, response.content
    assert response.data["user"]["email"] == user.email
    assert User.objects.filter(email=user.email).count() == 1
    user.refresh_from_db()
    assert user.email_verified_at is not None
