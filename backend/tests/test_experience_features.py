"""Tests for advertising delivery and the AI assistant."""
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.ads.models import Advertisement
from apps.assistant.models import AssistantConversation
from apps.common.testing import authenticated_client, build_org_with_owner, create_project
from apps.financials.models import Budget, BudgetLine, CostCode
from apps.rfis.models import RFI
from apps.tasks.models import Task

pytestmark = pytest.mark.django_db


def test_public_ad_delivery_filters_placement_and_live_campaigns(api_client):
    Advertisement.objects.create(
        name="Live hero", placement="landing_hero", headline="Build faster", priority=50
    )
    Advertisement.objects.create(
        name="Paused hero", placement="landing_hero", is_active=False
    )
    Advertisement.objects.create(
        name="Expired hero",
        placement="landing_hero",
        end_at=timezone.now() - timedelta(days=1),
    )
    Advertisement.objects.create(name="Live strip", placement="landing_strip")

    response = api_client.get("/api/v1/ads/", {"placement": "landing_hero"})

    assert response.status_code == 200
    names = [item["name"] for item in response.data["results"]]
    assert names == ["Live hero"]
    assert response.data["results"][0]["headline"] == "Build faster"


def test_ad_event_records_impression(api_client):
    ad = Advertisement.objects.create(name="Tracked", placement="landing_hero")

    response = api_client.post(
        f"/api/v1/ads/{ad.id}/events/",
        {"event_type": "impression", "session_key": "demo-session"},
        format="json",
    )

    assert response.status_code == 201
    ad.refresh_from_db()
    assert ad.impressions == 1


@pytest.fixture
def workspace():
    organization, user, _ = build_org_with_owner()
    project = create_project(organization, name="Harbor Point", created_by=user)
    client = authenticated_client(user, organization.id)
    return organization, user, project, client


def test_assistant_offline_budget_briefing(workspace):
    _, _, project, client = workspace
    cost_code = CostCode.objects.create(project=project, code="03-000", name="Concrete")
    budget = Budget.objects.create(project=project, name="Baseline", is_primary=True)
    BudgetLine.objects.create(
        project=project,
        budget=budget,
        cost_code=cost_code,
        budgeted_amount="1000000.00",
        committed_amount="400000.00",
        actual_amount="250000.00",
    )

    response = client.post(
        "/api/v1/assistant/chat/",
        {"message": "What is our budget position?", "project_id": str(project.id)},
        format="json",
    )

    assert response.status_code == 200, response.content
    assert response.data["provider"] in {"offline", "fallback"}
    assert "Budget" in response.data["reply"]
    assert "$250.0K" in response.data["reply"]
    assert AssistantConversation.objects.count() == 1
    conversation = AssistantConversation.objects.get()
    assert conversation.messages.count() == 2


def test_assistant_continues_conversation_and_reports_context(workspace):
    _, _, project, client = workspace
    today = timezone.now().date()
    Task.objects.create(project=project, title="Pour slab", due_date=today - timedelta(days=2))
    RFI.objects.create(
        project=project,
        number="RFI-001",
        subject="Beam connection",
        question="Confirm detail.",
        status="open",
        due_date=today - timedelta(days=1),
    )

    first = client.post(
        "/api/v1/assistant/chat/",
        {"message": "Which tasks are overdue?", "project_id": str(project.id)},
        format="json",
    )
    assert first.status_code == 200, first.content
    assert "Pour slab" in first.data["reply"]

    second = client.post(
        "/api/v1/assistant/chat/",
        {
            "message": "Any overdue RFIs?",
            "project_id": str(project.id),
            "conversation_id": first.data["conversation_id"],
        },
        format="json",
    )
    assert second.status_code == 200, second.content
    assert "RFI-001" in second.data["reply"]
    assert second.data["conversation_id"] == first.data["conversation_id"]
    assert AssistantConversation.objects.get().messages.count() == 4

    context = client.get("/api/v1/assistant/context/", {"project_id": str(project.id)})
    assert context.status_code == 200, context.content
    assert context.data["context"]["project"]["name"] == "Harbor Point"
    assert context.data["suggestions"]
    assert context.data["provider_configured"] is False


def test_assistant_rejects_project_outside_membership(workspace):
    _, _, _, client = workspace
    other_org, other_user, _ = build_org_with_owner(
        name="Other Org", email="other-owner@example.test"
    )
    foreign_project = create_project(other_org, name="Foreign", created_by=other_user)

    response = client.post(
        "/api/v1/assistant/chat/",
        {"message": "Summarise", "project_id": str(foreign_project.id)},
        format="json",
    )

    assert response.status_code == 404
    assert AssistantConversation.objects.count() == 0
