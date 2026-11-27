import pytest

from apps.common.testing import (
    add_org_member,
    add_project_member,
    authenticated_client,
    build_org_with_owner,
    create_project,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def workspace():
    organization, owner, _ = build_org_with_owner()
    project = create_project(organization, name="Finance Security Project", created_by=owner)
    owner_client = authenticated_client(owner, organization.id)
    member, _ = add_org_member(organization, "finance-editor@demo.test", role_code="member")
    add_project_member(project, member, role_code="member")
    member_client = authenticated_client(member, organization.id)
    return organization, owner, owner_client, member_client, project


def _create_invoice(client, project, number="INV-SEC-001"):
    response = client.post(
        "/api/v1/invoices/",
        {"project": str(project.id), "number": number, "title": "Security test invoice"},
        format="json",
    )
    assert response.status_code == 201, response.content
    invoice_id = response.data["id"]
    line = client.post(
        f"/api/v1/invoices/{invoice_id}/lines/",
        {"description": "Concrete", "quantity": "2", "unit_cost": "50.00"},
        format="json",
    )
    assert line.status_code == 201, line.content
    return invoice_id


def test_financial_status_and_paid_amount_are_not_client_writable(workspace):
    _, _, owner_client, member_client, project = workspace
    invoice_id = _create_invoice(owner_client, project)

    patched = member_client.patch(
        f"/api/v1/invoices/{invoice_id}/",
        {"status": "approved", "paid_amount": "999.00", "subtotal": "999.00"},
        format="json",
    )
    assert patched.status_code == 200, patched.content

    detail = owner_client.get(f"/api/v1/invoices/{invoice_id}/")
    assert detail.status_code == 200
    assert detail.data["status"] == "draft"
    assert float(detail.data["paid_amount"]) == 0
    assert float(detail.data["subtotal"]) == 100

    denied = member_client.post(f"/api/v1/invoices/{invoice_id}/approve/")
    assert denied.status_code == 403, denied.content

    approved = owner_client.post(f"/api/v1/invoices/{invoice_id}/approve/")
    assert approved.status_code == 200, approved.content
    assert approved.data["status"] == "approved"


def test_invoice_payment_is_validated_and_capped_at_outstanding(workspace):
    _, _, owner_client, _, project = workspace
    invoice_id = _create_invoice(owner_client, project, "INV-SEC-002")
    approved = owner_client.post(f"/api/v1/invoices/{invoice_id}/approve/")
    assert approved.status_code == 200, approved.content

    partial = owner_client.post(f"/api/v1/invoices/{invoice_id}/pay/", {"amount": "40.00"}, format="json")
    assert partial.status_code == 200, partial.content
    assert partial.data["status"] == "partially_paid"
    assert float(partial.data["paid_amount"]) == 40

    overpayment = owner_client.post(
        f"/api/v1/invoices/{invoice_id}/pay/", {"amount": "100.00"}, format="json"
    )
    assert overpayment.status_code == 400, overpayment.content

    negative = owner_client.post(f"/api/v1/invoices/{invoice_id}/pay/", {"amount": "-1"}, format="json")
    assert negative.status_code == 400, negative.content

    settled = owner_client.post(f"/api/v1/invoices/{invoice_id}/pay/", {"amount": "60.00"}, format="json")
    assert settled.status_code == 200, settled.content
    assert settled.data["status"] == "paid"
    assert float(settled.data["paid_amount"]) == 100


def test_retention_release_cannot_exceed_outstanding(workspace):
    _, _, owner_client, _, project = workspace
    created = owner_client.post(
        "/api/v1/retentions/",
        {"project": str(project.id), "withheld_amount": "100.00"},
        format="json",
    )
    assert created.status_code == 201, created.content
    retention_id = created.data["id"]

    released = owner_client.post(
        f"/api/v1/retentions/{retention_id}/release/", {"amount": "60.00"}, format="json"
    )
    assert released.status_code == 200, released.content
    assert float(released.data["outstanding"]) == 40

    overrelease = owner_client.post(
        f"/api/v1/retentions/{retention_id}/release/", {"amount": "50.00"}, format="json"
    )
    assert overrelease.status_code == 400, overrelease.content

    negative = owner_client.post(
        f"/api/v1/retentions/{retention_id}/release/", {"amount": "-1.00"}, format="json"
    )
    assert negative.status_code == 400, negative.content

    final = owner_client.post(
        f"/api/v1/retentions/{retention_id}/release/", {"amount": "40.00"}, format="json"
    )
    assert final.status_code == 200, final.content
    assert float(final.data["outstanding"]) == 0
