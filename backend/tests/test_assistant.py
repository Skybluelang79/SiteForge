"""AI copilot API tests."""
from unittest.mock import Mock, patch

import pytest
from rest_framework.test import APIClient

from apps.common.testing import (
    authenticated_client,
    build_org_with_owner,
    create_project,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def org_owner():
    return build_org_with_owner()


def test_assistant_requires_authentication():
    response = APIClient().post(
        "/api/v1/assistant/chat/",
        {"messages": [{"role": "user", "content": "Summarise risk"}]},
        format="json",
    )
    assert response.status_code in {401, 403}


def test_assistant_uses_grounded_fallback_without_provider(org_owner, settings):
    org, user, _ = org_owner
    project = create_project(org, name="Harbor Bridge", created_by=user, status="active")
    settings.AI_API_KEY = ""
    settings.AI_ENABLED = False

    client = authenticated_client(user, org.id)
    response = client.post(
        "/api/v1/assistant/chat/",
        {
            "messages": [
                {"role": "user", "content": "Summarise portfolio risk"},
            ],
        },
        format="json",
    )

    assert response.status_code == 200, response.content
    assert response.data["provider"] == "fallback"
    assert response.data["degraded"] is False
    assert response.data["context"]["selected_project_id"] == str(project.id)
    assert response.data["reply"]
    assert response.data["actions"]


def test_assistant_calls_openai_compatible_provider(org_owner, settings):
    org, user, _ = org_owner
    create_project(org, name="Harbor Bridge", created_by=user, status="active")
    settings.AI_API_KEY = "test-key"
    settings.AI_ENABLED = True
    settings.AI_BASE_URL = "https://ai.example.test/v1"
    settings.AI_MODEL = "test-model"

    provider_response = Mock()
    provider_response.raise_for_status.return_value = None
    provider_response.json.return_value = {
        "model": "test-model",
        "choices": [{"message": {"content": "Harbor Bridge is stable."}}],
        "usage": {"total_tokens": 42},
    }

    client = authenticated_client(user, org.id)
    with patch(
        "apps.assistant.services.httpx.post", return_value=provider_response
    ) as provider_post:
        response = client.post(
            "/api/v1/assistant/chat/",
            {
                "messages": [
                    {"role": "user", "content": "How is Harbor Bridge doing?"},
                ],
            },
            format="json",
        )

    assert response.status_code == 200, response.content
    assert response.data["provider"] == "openai-compatible"
    assert response.data["reply"] == "Harbor Bridge is stable."
    assert response.data["usage"]["total_tokens"] == 42
    payload = provider_post.call_args.kwargs["json"]
    assert payload["model"] == "test-model"
    assert "Harbor Bridge" in payload["messages"][0]["content"]


def test_assistant_rejects_inaccessible_project(org_owner, settings):
    org, user, _ = org_owner
    other_org, other_owner, _ = build_org_with_owner(
        name="Other Builders", email="owner@other.test"
    )
    hidden = create_project(other_org, name="Hidden Site", created_by=other_owner)
    settings.AI_API_KEY = ""
    settings.AI_ENABLED = False

    client = authenticated_client(user, org.id)
    response = client.post(
        "/api/v1/assistant/chat/",
        {
            "messages": [{"role": "user", "content": "What is happening?"}],
            "project_id": str(hidden.id),
        },
        format="json",
    )

    assert response.status_code == 404
    assert response.data["error"]["code"] == "project_not_found"
