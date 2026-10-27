"""Test configuration for the backend."""
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
os.environ.setdefault("DB_ENGINE", "sqlite3")
os.environ.setdefault("USE_IN_MEMORY_CHANNEL_LAYER", "1")
os.environ.setdefault("CELERY_TASK_ALWAYS_EAGER", "1")
os.environ.setdefault("DJANGO_SECRET_KEY", "test-secret-key")

import pytest  # noqa: E402


@pytest.fixture
def api_client():
    from rest_framework.test import APIClient

    return APIClient()


@pytest.fixture
def make_org(db):
    from apps.common.testing import build_org_with_owner

    def _make(name="Acme Construction", email="owner@acme.test", **kwargs):
        return build_org_with_owner(name=name, email=email, **kwargs)

    return _make

