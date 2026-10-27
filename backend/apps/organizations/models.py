"""Organization, membership, role and invitation models."""
from django.conf import settings as django_settings
from django.contrib.auth import get_user_model
from django.db import models

from apps.common.models import Base, SoftDeleteModel
from apps.common.permissions import DEFAULT_ROLES, permissions_for_role

User = get_user_model()


class Organization(SoftDeleteModel):
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=120, unique=True)
    legal_name = models.CharField(max_length=255, blank=True)
    tax_id = models.CharField(max_length=80, blank=True)
    timezone = models.CharField(max_length=64, default="UTC")
    currency = models.CharField(max_length=3, default="USD")
    address_line1 = models.CharField(max_length=255, blank=True)
    address_line2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=120, blank=True)
    region = models.CharField(max_length=120, blank=True)
    postal_code = models.CharField(max_length=40, blank=True)
    country = models.CharField(max_length=80, blank=True)
    logo = models.ImageField(upload_to="org-logos/", null=True, blank=True)
    is_active = models.BooleanField(default=True)
    settings = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["slug"], name="idx_org_slug"),
            models.Index(fields=["is_active", "deleted_at"], name="idx_org_active_deleted"),
        ]

    def __str__(self) -> str:
        return self.name


class Role(Base):
    """Named, organization-scoped role with a permission list."""

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="roles"
    )
    name = models.CharField(max_length=80)
    code = models.SlugField(max_length=80)
    description = models.CharField(max_length=255, blank=True)
    permissions = models.JSONField(default=list, blank=True)
    is_system = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["organization", "code"], name="uniq_role_org_code")
        ]
        ordering = ["name"]

    def __str__(self) -> str:
        return f"{self.organization_id}:{self.code}"


class Membership(Base):
    """Links a user to an organization with a role."""

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="memberships")
    role = models.ForeignKey(Role, on_delete=models.PROTECT, related_name="memberships", null=True, blank=True)
    role_code = models.CharField(max_length=32, default=django_settings.DEFAULT_ORG_ROLE, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)
    is_owner = models.BooleanField(default=False)
    title = models.CharField(max_length=150, blank=True)
    invited_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="sent_invitations"
    )
    joined_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["organization", "user"], name="uniq_membership_org_user")
        ]
        indexes = [
            models.Index(fields=["user", "is_active"], name="idx_membership_user_active"),
            models.Index(fields=["organization", "role_code"], name="idx_membership_org_role"),
        ]

    def __str__(self) -> str:
        return f"{self.user_id}@{self.organization_id} ({self.role_code})"

    @property
    def is_org_admin(self) -> bool:
        return self.is_owner or self.role_code in {"owner", "admin"}

    @property
    def effective_permissions(self) -> set[str]:
        if self.is_owner:
            return set(DEFAULT_ROLES["owner"])
        if self.role is not None and self.role.permissions:
            return set(self.role.permissions)
        return permissions_for_role(self.role_code)


class Invitation(Base):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("accepted", "Accepted"),
        ("revoked", "Revoked"),
        ("expired", "Expired"),
    ]

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="invitations")
    email = models.EmailField(db_index=True)
    role_code = models.CharField(max_length=32, default=django_settings.DEFAULT_ORG_ROLE)
    role = models.ForeignKey(Role, on_delete=models.SET_NULL, null=True, blank=True, related_name="invitations")
    token_hash = models.CharField(max_length=64, unique=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="pending", db_index=True)
    invited_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="invitations_sent"
    )
    project = models.ForeignKey(
        "projects.Project", on_delete=models.SET_NULL, null=True, blank=True, related_name="invitations"
    )
    expires_at = models.DateTimeField()
    accepted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["organization", "status"], name="idx_invitation_org_status"),
            models.Index(fields=["email", "status"], name="idx_invitation_email_status"),
        ]

    def __str__(self) -> str:  # pragma: no cover
        return f"Invitation({self.email} -> {self.organization_id})"


class OrgFeatureSetting(Base):
    """Per-organization feature toggles/flags."""

    organization = models.OneToOneField(
        Organization, on_delete=models.CASCADE, related_name="feature_settings"
    )
    flags = models.JSONField(default=dict, blank=True)

    def __str__(self) -> str:  # pragma: no cover
        return f"FeatureSettings({self.organization_id})"
