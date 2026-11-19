"""Accounts domain services: MFA, password reset, activity."""
import hashlib
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import signing
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from rest_framework_simplejwt.token_blacklist.models import OutstandingToken
from rest_framework_simplejwt.tokens import RefreshToken

from .models import PasswordResetToken, UserSession

User = get_user_model()

MFA_TOKEN_SALT = "siteforge.mfa.login"
MFA_TOKEN_TTL_SECONDS = 300
PASSWORD_RESET_SALT = "siteforge.password.reset"
PASSWORD_RESET_TTL_SECONDS = 3600


def issue_mfa_token(user) -> str:
    """Short-lived token proving password step succeeded."""
    return signing.dumps({"uid": str(user.pk)}, salt=MFA_TOKEN_SALT)


def resolve_mfa_token(token: str):
    try:
        data = signing.loads(token, salt=MFA_TOKEN_SALT, max_age=MFA_TOKEN_TTL_SECONDS)
    except signing.BadSignature:
        raise ValidationError({"mfa_token": "Invalid or expired MFA token."})
    try:
        return User.objects.get(pk=data["uid"], is_active=True)
    except (User.DoesNotExist, KeyError):
        raise ValidationError({"mfa_token": "Invalid or expired MFA token."})


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_password_reset(user) -> str:
    raw = secrets.token_urlsafe(32)
    PasswordResetToken.objects.create(
        user=user,
        token_hash=_hash_token(raw),
        expires_at=timezone.now() + timedelta(seconds=PASSWORD_RESET_TTL_SECONDS),
    )
    return raw


def revoke_all_sessions(user) -> None:
    sessions = list(UserSession.objects.filter(user=user, revoked_at__isnull=True))
    if not sessions:
        return
    jtis = [session.refresh_jti for session in sessions if session.refresh_jti]
    UserSession.objects.filter(user=user, revoked_at__isnull=True).update(revoked_at=timezone.now())
    if jtis:
        for token in OutstandingToken.objects.filter(jti__in=jtis):
            try:
                RefreshToken(token.token).blacklist()
            except Exception:
                pass


def send_password_reset_email(user, raw_token: str) -> None:
    link = f"{settings.FRONTEND_URL}/reset-password?token={raw_token}"
    send_mail(
        subject="Reset your SiteForge password",
        message=f"Use this link to reset your password (valid 1 hour):\n\n{link}",
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=True,
    )


@transaction.atomic
def consume_password_reset(raw_token: str, new_password: str):
    token_hash = _hash_token(raw_token)
    record = (
        PasswordResetToken.objects.select_for_update()
        .select_related("user")
        .filter(token_hash=token_hash, used_at__isnull=True)
        .order_by("-created_at")
        .first()
    )
    if record is None or not record.is_valid():
        raise ValidationError({"token": "This reset link is invalid or has expired."})
    record.user.set_password(new_password)
    record.user.save(update_fields=["password"])
    record.used_at = timezone.now()
    record.save(update_fields=["used_at"])
    revoke_all_sessions(record.user)
    return record.user
