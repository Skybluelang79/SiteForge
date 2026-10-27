"""Organization domain services: creation, invitations, membership."""
import hashlib
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone

from apps.audit.services import record_audit_event
from apps.common.permissions import DEFAULT_ROLES

from .models import Invitation, Membership, OrgFeatureSetting, Organization, Role

User = get_user_model()

INVITATION_TTL_DAYS = 14


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


@transaction.atomic
def create_organization(*, name: str, owner: User, **fields) -> Organization:
    """Create an organization, seed system roles and add the owner membership."""
    if not fields.get("slug"):
        from django.utils.text import slugify

        base = slugify(name)[:110] or "org"
        slug = base
        suffix = 1
        while Organization.objects.filter(slug=slug).exists():
            suffix += 1
            slug = f"{base}-{suffix}"
        fields["slug"] = slug
    organization = Organization.objects.create(name=name, **fields)
    for code, perms in DEFAULT_ROLES.items():
        Role.objects.create(
            organization=organization,
            name=code.title(),
            code=code,
            permissions=sorted(perms),
            is_system=True,
        )
    Membership.objects.create(
        organization=organization,
        user=owner,
        role_code="owner",
        role=Role.objects.get(organization=organization, code="owner"),
        is_owner=True,
        is_active=True,
        joined_at=timezone.now(),
    )
    OrgFeatureSetting.objects.get_or_create(organization=organization)
    record_audit_event(
        organization=organization,
        actor=owner,
        action="organization.created",
        target_type="Organization",
        target_id=str(organization.id),
        metadata={"name": name},
    )
    return organization


@transaction.atomic
def invite_member(*, organization, email, role_code, invited_by, project=None, message=""):
    email = email.lower()
    if Membership.objects.filter(organization=organization, user__email=email, is_active=True).exists():
        raise ValueError("That user is already a member of this organization.")
    if role_code not in DEFAULT_ROLES:
        raise ValueError("Unknown role code.")

    token = secrets.token_urlsafe(32)
    invitation = Invitation.objects.create(
        organization=organization,
        email=email,
        role_code=role_code,
        role=Role.objects.filter(organization=organization, code=role_code).first(),
        token_hash=_hash(token),
        invited_by=invited_by,
        project=project,
        expires_at=timezone.now() + timedelta(days=INVITATION_TTL_DAYS),
    )
    accept_url = f"{settings.FRONTEND_URL}/accept-invitation?token={token}"
    send_mail(
        subject=f"You're invited to {organization.name} on SiteForge",
        message=f"{invited_by.full_name} invited you to join {organization.name}.\n\n{accept_url}\n",
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[email],
        fail_silently=True,
    )
    record_audit_event(
        organization=organization,
        actor=invited_by,
        action="invitation.created",
        target_type="Invitation",
        target_id=str(invitation.id),
        metadata={"email": email, "role_code": role_code},
    )
    return invitation


@transaction.atomic
def accept_invitation(*, token: str, user: User):
    invitation = (
        Invitation.objects.select_for_update()
        .select_related("organization")
        .filter(token_hash=_hash(token))
        .first()
    )
    if invitation is None or invitation.status != "pending":
        raise ValueError("Invitation not found or no longer valid.")
    if invitation.expires_at < timezone.now():
        invitation.status = "expired"
        invitation.save(update_fields=["status"])
        raise ValueError("This invitation has expired.")
    if invitation.email.lower() != user.email.lower():
        raise ValueError("This invitation was issued to a different email address.")

    membership, created = Membership.objects.get_or_create(
        organization=invitation.organization,
        user=user,
        defaults={
            "role_code": invitation.role_code,
            "role": invitation.role,
            "is_active": True,
            "joined_at": timezone.now(),
        },
    )
    if not created:
        membership.is_active = True
        membership.role_code = invitation.role_code
        membership.role = invitation.role
        membership.joined_at = membership.joined_at or timezone.now()
        membership.save(update_fields=["is_active", "role_code", "role", "joined_at"])

    if invitation.project_id:
        from apps.projects.models import ProjectMember

        ProjectMember.objects.get_or_create(
            project=invitation.project, user=user, defaults={"role_code": invitation.role_code}
        )

    invitation.status = "accepted"
    invitation.accepted_at = timezone.now()
    invitation.save(update_fields=["status", "accepted_at"])
    record_audit_event(
        organization=invitation.organization,
        actor=user,
        action="invitation.accepted",
        target_type="Invitation",
        target_id=str(invitation.id),
        metadata={"email": user.email},
    )
    return membership
