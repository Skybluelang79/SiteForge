import pytest
from django.test import Client
from rest_framework.test import APIClient

from apps.accounts.models import User


@pytest.mark.django_db
def test_user_api_login_returns_tokens():
    user = User.objects.create_user(
        email="member@example.test", password="StrongPass123!", first_name="Member", last_name="User"
    )
    client = APIClient()

    response = client.post(
        "/api/v1/auth/login/", {"email": user.email, "password": "StrongPass123!"}, format="json"
    )

    assert response.status_code == 200
    assert response.data["access"]
    assert response.data["refresh"]
    assert response.data["user"]["email"] == user.email


@pytest.mark.django_db
def test_admin_login_allows_superuser_and_blocks_regular_user(settings):
    settings.STORAGES = {
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }
    password = "StrongPass123!"
    superuser = User.objects.create_superuser(
        email="admin@example.test", password=password, first_name="Admin", last_name="User"
    )
    regular = User.objects.create_user(
        email="regular@example.test", password=password, first_name="Regular", last_name="User"
    )
    client = Client()

    assert client.get("/admin/login/").status_code == 200
    assert client.post("/admin/login/", {"username": superuser.email, "password": password}).status_code == 302
    assert client.get("/admin/").status_code == 200
    client.logout()

    assert client.post("/admin/login/", {"username": regular.email, "password": password}).status_code == 200
    response = client.get("/admin/")
    assert response.status_code == 302
    assert "/admin/login/" in response["Location"]
