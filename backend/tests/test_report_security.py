import pytest
from django.core.files.base import ContentFile

from apps.common.testing import (
    add_org_member,
    add_project_member,
    authenticated_client,
    build_org_with_owner,
    create_project,
)
from apps.reports.models import ExportJob, ReportDefinition

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def no_export_queue(monkeypatch):
    monkeypatch.setattr("apps.reports.views.enqueue_export", lambda job: job)


@pytest.fixture
def workspace():
    organization, owner, _ = build_org_with_owner()
    project = create_project(organization, name="Report Project", created_by=owner)
    viewer, _ = add_org_member(organization, "viewer@reports.test", role_code="viewer")
    engineer, _ = add_org_member(organization, "engineer@reports.test", role_code="member")
    add_project_member(project, engineer)
    return {
        "organization": organization,
        "owner": owner,
        "project": project,
        "viewer_client": authenticated_client(viewer, organization.id),
        "engineer_client": authenticated_client(engineer, organization.id),
    }


def completed_job(organization, project, requested_by, report_definition=None):
    job = ExportJob.objects.create(
        organization=organization,
        project=project,
        report_definition=report_definition,
        requested_by=requested_by,
        export_type="rfi_aging",
        export_format="csv",
        status="completed",
    )
    job.file.save(f"{job.id}.csv", ContentFile(b"secret,data\n1,2\n"), save=True)
    return job


def rows(response):
    return response.data["results"] if isinstance(response.data, dict) else response.data


def error_details(response):
    error = response.data.get("error") if isinstance(response.data, dict) else None
    return error["details"] if error and "details" in error else response.data


def test_viewer_cannot_access_another_users_export(workspace):
    job = completed_job(workspace["organization"], workspace["project"], workspace["owner"])
    client = workspace["viewer_client"]

    listing = client.get("/api/v1/export-jobs/")
    assert listing.status_code == 200
    assert all(row["id"] != str(job.id) for row in rows(listing))
    assert client.get(f"/api/v1/export-jobs/{job.id}/").status_code == 404
    assert client.get(f"/api/v1/export-jobs/{job.id}/download/").status_code == 404


def test_viewer_can_download_own_export(workspace):
    job = completed_job(workspace["organization"], workspace["project"], workspace["owner"])
    viewer, _ = add_org_member(workspace["organization"], "viewer2@reports.test", role_code="viewer")
    client = authenticated_client(viewer, workspace["organization"].id)
    job.requested_by = viewer
    job.save(update_fields=["requested_by", "updated_at"])

    download = client.get(f"/api/v1/export-jobs/{job.id}/download/")
    assert download.status_code == 200
    assert b"secret,data" in b"".join(download.streaming_content)


def test_engineer_cannot_export_private_report(workspace):
    report = ReportDefinition.objects.create(
        organization=workspace["organization"],
        project=workspace["project"],
        name="Private report",
        report_type="rfi_aging",
        visibility="private",
        created_by=workspace["owner"],
    )

    response = workspace["engineer_client"].post(
        "/api/v1/export-jobs/",
        {
            "project": str(workspace["project"].id),
            "report_definition": str(report.id),
            "export_type": "rfi_aging",
            "export_format": "csv",
        },
        format="json",
    )

    assert response.status_code == 400
    assert "report_definition" in error_details(response)


def test_engineer_cannot_export_project_from_parameters_without_access(workspace):
    restricted = create_project(workspace["organization"], name="Restricted", created_by=workspace["owner"])

    response = workspace["engineer_client"].post(
        "/api/v1/export-jobs/",
        {
            "export_type": "rfi_aging",
            "export_format": "csv",
            "parameters": {"project_id": str(restricted.id)},
        },
        format="json",
    )

    assert response.status_code == 400
    assert "parameters" in error_details(response)


def test_engineer_cannot_request_unsupported_export(workspace):
    client = workspace["engineer_client"]

    export_type = client.post(
        "/api/v1/export-jobs/",
        {
            "project": str(workspace["project"].id),
            "export_type": "unknown_export",
            "export_format": "csv",
        },
        format="json",
    )
    export_format = client.post(
        "/api/v1/export-jobs/",
        {
            "project": str(workspace["project"].id),
            "export_type": "rfi_aging",
            "export_format": "pdf",
        },
        format="json",
    )

    assert export_type.status_code == 400
    assert "export_type" in error_details(export_type)
    assert export_format.status_code == 400
    assert "export_format" in error_details(export_format)


def test_engineer_cannot_delete_another_users_export(workspace):
    report = ReportDefinition.objects.create(
        organization=workspace["organization"],
        project=workspace["project"],
        name="Shared report",
        report_type="rfi_aging",
        visibility="organization",
        created_by=workspace["owner"],
    )
    job = completed_job(
        workspace["organization"],
        workspace["project"],
        workspace["owner"],
        report_definition=report,
    )

    response = workspace["engineer_client"].delete(f"/api/v1/export-jobs/{job.id}/")

    assert response.status_code == 403
    assert ExportJob.objects.filter(pk=job.pk).exists()
