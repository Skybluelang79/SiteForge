"""Test helpers and factory functions shared across apps."""
from __future__ import annotations

import factory
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

User = get_user_model()


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User

    email = factory.Sequence(lambda n: f"user{n}@example.test")
    first_name = "Test"
    last_name = factory.Sequence(lambda n: f"User{n}")
    is_active = True

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        password = kwargs.pop("password", "TestPass123!")
        return model_class.objects.create_user(*args, password=password, **kwargs)


def build_org_with_owner(name="Acme Construction", email="owner@acme.test", password="TestPass123!"):
    """Create org + owner user + system roles. Returns (organization, user, membership)."""
    from apps.organizations.services import create_organization

    user = User.objects.create_user(email=email, password=password, first_name="Owner", last_name="User")
    organization = create_organization(name=name, owner=user)
    membership = organization.memberships.get(user=user)
    return organization, user, membership


def authenticated_client(user, organization_id=None, project_access=None) -> APIClient:
    """Return an APIClient authenticated via JWT with an optional active org header."""
    from rest_framework_simplejwt.tokens import RefreshToken

    client = APIClient()
    token = RefreshToken.for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.access_token}")
    if organization_id:
        client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {token.access_token}",
            HTTP_X_ORGANIZATION_ID=str(organization_id),
        )
    return client


def add_org_member(organization, email, role_code="member", password="TestPass123!"):
    from apps.organizations.models import Membership, Role

    user, created = User.objects.get_or_create(
        email=email, defaults={"first_name": "Member", "last_name": "User"}
    )
    if created:
        user.set_password(password)
        user.save()
    membership, _ = Membership.objects.update_or_create(
        organization=organization,
        user=user,
        defaults={
            "role_code": role_code,
            "role": Role.objects.filter(organization=organization, code=role_code).first(),
            "is_active": True,
        },
    )
    return user, membership


def add_project_member(project, user, role_code="member"):
    from apps.projects.models import ProjectMember

    member, _ = ProjectMember.objects.update_or_create(
        project=project, user=user, defaults={"role_code": role_code, "is_active": True}
    )
    return member


def create_project(organization, name="Riverside Tower", created_by=None, **kwargs):
    from apps.projects.models import Project, ProjectMember

    project = Project.objects.create(organization=organization, name=name, **kwargs)
    if created_by is not None:
        ProjectMember.objects.create(project=project, user=created_by, role_code="owner")
    return project
