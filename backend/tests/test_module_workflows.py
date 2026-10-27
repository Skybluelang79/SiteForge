"""Smoke and workflow tests for the module endpoints."""
import pytest

from apps.common.testing import authenticated_client, build_org_with_owner, create_project
from apps.integrations import services as integration_services
from apps.reports.models import ExportJob
from apps.reports.services import generate_export

pytestmark = pytest.mark.django_db


@pytest.fixture
def workspace():
    organization, user, _ = build_org_with_owner()
    project = create_project(organization, name="Workflow Project", created_by=user)
    client = authenticated_client(user, organization.id)
    return organization, user, project, client


def test_financial_change_order_approval_posts_budget_and_commitment(workspace):
    _, _, project, client = workspace
    cost_code = client.post(
        "/api/v1/cost-codes/",
        {"project": str(project.id), "code": "03-100", "name": "Concrete"},
        format="json",
    )
    assert cost_code.status_code == 201, cost_code.content

    budget = client.post(
        "/api/v1/budgets/",
        {"project": str(project.id), "name": "Baseline", "is_primary": True},
        format="json",
    )
    assert budget.status_code == 201, budget.content

    line = client.post(
        "/api/v1/budget-lines/",
        {
            "budget": budget.data["id"],
            "project": str(project.id),
            "cost_code": cost_code.data["id"],
            "budgeted_amount": "1000.00",
        },
        format="json",
    )
    assert line.status_code == 201, line.content

    commitment = client.post(
        "/api/v1/commitments/",
        {
            "project": str(project.id),
            "number": "SC-001",
            "title": "Concrete subcontract",
            "original_amount": "500.00",
            "revised_amount": "500.00",
        },
        format="json",
    )
    assert commitment.status_code == 201, commitment.content

    change_order = client.post(
        "/api/v1/change-orders/",
        {
            "project": str(project.id),
            "commitment": commitment.data["id"],
            "cost_code": cost_code.data["id"],
            "number": "CO-001",
            "title": "Added footing",
            "amount": "100.00",
        },
        format="json",
    )
    assert change_order.status_code == 201, change_order.content

    approved = client.post(f"/api/v1/change-orders/{change_order.data['id']}/approve/")
    assert approved.status_code == 200, approved.content
    assert approved.data["status"] == "approved"

    budget_line = client.get(f"/api/v1/budget-lines/{line.data['id']}/")
    assert budget_line.status_code == 200
    assert float(budget_line.data["budgeted_amount"]) == 1100.0

    updated_commitment = client.get(f"/api/v1/commitments/{commitment.data['id']}/")
    assert float(updated_commitment.data["revised_amount"]) == 600.0


def test_inspection_signoff_and_punch_list(workspace):
    _, _, project, client = workspace
    inspection = client.post(
        "/api/v1/inspections/",
        {"project": str(project.id), "number": "INS-001", "title": "Slab inspection"},
        format="json",
    )
    assert inspection.status_code == 201, inspection.content

    item = client.post(
        f"/api/v1/inspections/{inspection.data['id']}/items/",
        {"description": "Rebar spacing", "result": "pass"},
        format="json",
    )
    assert item.status_code == 201, item.content

    signed = client.post(
        f"/api/v1/inspections/{inspection.data['id']}/signoff/",
        {"status": "passed"},
        format="json",
    )
    assert signed.status_code == 200, signed.content
    assert signed.data["status"] == "passed"
    assert signed.data["signed_off_by"]["email"] is not None

    punch_list = client.post(
        "/api/v1/punch-lists/",
        {"project": str(project.id), "name": "Level 2 punch"},
        format="json",
    )
    assert punch_list.status_code == 201, punch_list.content

    punch_item = client.post(
        f"/api/v1/punch-lists/{punch_list.data['id']}/items/",
        {"description": "Touch up paint", "trade": "Painting"},
        format="json",
    )
    assert punch_item.status_code == 201, punch_item.content

    closed = client.post(f"/api/v1/punch-list-items/{punch_item.data['id']}/close/")
    assert closed.status_code == 200, closed.content
    assert closed.data["status"] == "closed"


def test_rfi_respond_and_task_creation(workspace):
    _, _, project, client = workspace
    rfi = client.post(
        "/api/v1/rfis/",
        {
            "project": str(project.id),
            "number": "RFI-001",
            "subject": "Beam depth",
            "question": "Confirm beam depth at grid B.",
        },
        format="json",
    )
    assert rfi.status_code == 201, rfi.content

    response = client.post(
        f"/api/v1/rfis/{rfi.data['id']}/respond/",
        {"official_response": "Use 600 mm.", "status": "answered"},
        format="json",
    )
    assert response.status_code == 200, response.content
    assert response.data["status"] == "answered"

    task = client.post(
        "/api/v1/tasks/",
        {"project": str(project.id), "title": "Review beam shop drawings"},
        format="json",
    )
    assert task.status_code == 201, task.content


def test_export_job_generates_csv(workspace, monkeypatch):
    _, _, project, client = workspace

    def _noop_delay(*args, **kwargs):
        return None

    from apps.reports import tasks as report_tasks

    monkeypatch.setattr(report_tasks.run_export_job, "delay", _noop_delay, raising=False)

    job = client.post(
        "/api/v1/export-jobs/",
        {
            "project": str(project.id),
            "export_type": "rfi_aging",
            "export_format": "csv",
        },
        format="json",
    )
    assert job.status_code == 201, job.content

    export_job = ExportJob.objects.get(pk=job.data["id"])
    generate_export(export_job)
    export_job.refresh_from_db()
    assert export_job.status == "completed"
    assert export_job.row_count == 0
    assert export_job.file.name.endswith(".csv")


def test_rfi_sweep_marks_overdue_and_notifies(workspace, monkeypatch):
    from datetime import timedelta

    from django.utils import timezone

    from apps.rfis.models import RFI
    from apps.rfis.tasks import sweep_due_dates

    _, user, project, _ = workspace
    rfi = RFI.objects.create(
        project=project,
        number="RFI-LATE",
        subject="Late response",
        question="When?",
        due_date=timezone.now().date() - timedelta(days=2),
        created_by=user,
        assigned_to=user,
    )
    notifications = []
    monkeypatch.setattr("apps.rfis.tasks.notify", lambda **kwargs: notifications.append(kwargs))

    sweep_due_dates()
    rfi.refresh_from_db()
    assert rfi.status == "overdue"
    assert notifications
    assert notifications[0]["verb"] == "rfi.overdue"


def test_collect_metrics_creates_snapshots(workspace):
    from apps.reports.models import MetricSnapshot
    from apps.reports.services import collect_metrics_for_org

    organization, _, project, _ = workspace
    created = collect_metrics_for_org(organization)
    assert created > 0
    assert MetricSnapshot.objects.filter(project=project, metric_key="open_tasks").exists()


def test_integration_credentials_and_webhook_dispatch(workspace, monkeypatch):
    organization, _, _, client = workspace
    application = client.post(
        "/api/v1/api-applications/",
        {"name": "Field App", "environment": "development"},
        format="json",
    )
    assert application.status_code == 201, application.content
    assert application.data["client_id"]
    assert application.data["client_secret"]

    webhook = client.post(
        "/api/v1/webhooks/",
        {
            "name": "Payload listener",
            "target_url": "https://example.test/hooks",
            "event_types": ["rfi.created"],
        },
        format="json",
    )
    assert webhook.status_code == 201, webhook.content
    assert webhook.data["secret"]

    from apps.integrations import tasks as integration_tasks

    monkeypatch.setattr(
        integration_tasks.deliver_webhook, "delay", lambda *args, **kwargs: None, raising=False
    )

    event, deliveries = integration_services.dispatch_event(
        organization=organization,
        event_type="rfi.created",
        payload={"rfi_id": "123"},
    )
    assert event.event_type == "rfi.created"
    assert len(deliveries) == 1
    assert deliveries[0].status == "pending"
