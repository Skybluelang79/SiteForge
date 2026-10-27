"""Vertical-slice tests: auth, org, project, membership, dashboard."""
import pytest

from apps.common.testing import (
    add_org_member,
    authenticated_client,
    build_org_with_owner,
    create_project,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def org_owner():
    return build_org_with_owner()


def test_register_and_login(api_client):
    resp = api_client.post(
        "/api/v1/auth/register/",
        {"email": "new@example.test", "password": "StrongPass123!", "password_confirm": "StrongPass123!",
         "first_name": "New", "last_name": "User"},
        format="json",
    )
    assert resp.status_code == 201, resp.content
    assert "access" in resp.data and "refresh" in resp.data

    login = api_client.post(
        "/api/v1/auth/login/", {"email": "new@example.test", "password": "StrongPass123!"}, format="json"
    )
    assert login.status_code == 200, login.content
    assert login.data["user"]["email"] == "new@example.test"


def test_login_rejects_bad_password(api_client, org_owner):
    org, user, _ = org_owner
    resp = api_client.post(
        "/api/v1/auth/login/", {"email": user.email, "password": "wrong"}, format="json"
    )
    assert resp.status_code == 401
    assert resp.data["error"]["code"] == "authentication_failed"


def test_create_organization_and_context(org_owner):
    org, user, membership = org_owner
    client = authenticated_client(user, org.id)
    resp = client.get("/api/v1/auth/context/")
    assert resp.status_code == 200
    assert resp.data["active_organization_id"] == str(org.id)
    assert "projects.view" in resp.data["permissions"]


def test_organization_isolation(org_owner):
    org_a, owner_a, _ = org_owner
    org_b, owner_b, _ = build_org_with_owner(name="Beta Builders", email="owner@beta.test")

    client_a = authenticated_client(owner_a, org_a.id)
    resp = client_a.get("/api/v1/projects/")
    assert resp.status_code == 200

    # Project in org B must not be visible to owner A.
    create_project(org_b, name="Hidden Project", created_by=owner_b)
    resp = client_a.get("/api/v1/projects/")
    names = [p["name"] for p in resp.data["results"]]
    assert "Hidden Project" not in names


def test_project_creation_adds_owner_membership(org_owner):
    org, user, _ = org_owner
    client = authenticated_client(user, org.id)
    resp = client.post(
        "/api/v1/projects/",
        {"name": "Harbor Bridge", "number": "PRJ-100", "status": "active"},
        format="json",
    )
    assert resp.status_code == 201, resp.content
    project_id = resp.data["id"]

    members = client.get(f"/api/v1/projects/{project_id}/members/")
    assert members.status_code == 200
    assert any(m["role_code"] == "owner" and m["user"]["email"] == user.email for m in members.data)


def test_member_cannot_access_private_project(org_owner):
    org, owner, _ = org_owner
    member, _ = add_org_member(org, "member@acme.test", role_code="member")
    project = create_project(org, name="Private Site", created_by=owner, is_public=False)

    client = authenticated_client(member, org.id)
    resp = client.get(f"/api/v1/projects/{project.id}/")
    assert resp.status_code == 404


def test_project_number_unique_per_org(org_owner):
    org, user, _ = org_owner
    client = authenticated_client(user, org.id)
    first = client.post("/api/v1/projects/", {"name": "One", "number": "DUP"}, format="json")
    assert first.status_code == 201
    second = client.post("/api/v1/projects/", {"name": "Two", "number": "DUP"}, format="json")
    assert second.status_code == 400
    assert second.data["error"]["code"] == "validation_error"


def test_invitation_flow_and_acceptance(org_owner):
    org, owner, _ = org_owner
    client = authenticated_client(owner, org.id)
    resp = client.post(
        "/api/v1/organizations/memberships/invite/",
        {"email": "invitee@acme.test", "role_code": "member"},
        format="json",
    )
    assert resp.status_code == 201, resp.content

    from apps.organizations.models import Invitation

    invitation = Invitation.objects.get(email="invitee@acme.test")
    # Raw token is not stored; generate a new invitation to obtain a token for acceptance.
    from apps.organizations.services import invite_member

    invitation2 = invite_member(
        organization=org, email="invitee2@acme.test", role_code="member", invited_by=owner
    )
    # Grab the raw token by reconstructing through the service return path is not possible;
    # instead directly test the accept service with a freshly minted token.
    from apps.organizations.services import _hash  # noqa

    # Use the API accept endpoint with a token we control via services.
    from apps.organizations.models import Invitation as Inv

    raw_token = "known-token-123"
    Inv.objects.filter(pk=invitation.pk).update(token_hash=_hash(raw_token))
    accept = authenticated_client(owner) if False else None  # anonymous accept path below

    from rest_framework.test import APIClient

    anon = APIClient()
    resp = anon.post(
        "/api/v1/organizations/invitations/accept/",
        {"token": raw_token, "password": "BrandNewPass123!", "first_name": "In", "last_name": "Vitee"},
        format="json",
    )
    assert resp.status_code == 200, resp.content
    assert resp.data["membership"]["role_code"] == "member"


def test_dashboard_kpis(org_owner):
    org, user, _ = org_owner
    create_project(org, name="Active One", created_by=user, status="active")
    client = authenticated_client(user, org.id)
    resp = client.get("/api/v1/dashboard/")
    assert resp.status_code == 200
    assert resp.data["kpis"]["total_projects"] >= 1


def test_health_and_readiness(api_client):
    assert api_client.get("/api/v1/health/").status_code == 200
    resp = api_client.get("/api/v1/health/ready/")
    assert resp.status_code == 200
    assert resp.data["checks"]["database"] == "ok"
