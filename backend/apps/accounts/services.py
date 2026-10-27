"""Accounts domain services: MFA, password reset, activity."""
import hashlib
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import signing
from django.core.mail import send_mail
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from .models import PasswordResetToken

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


def send_password_reset_email(user, raw_token: str) -> None:
    link = f"{settings.FRONTEND_URL}/reset-password?token={raw_token}"
    send_mail(
        subject="Reset your SiteForge password",
        message=f"Use this link to reset your password (valid 1 hour):\n\n{link}",
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=True,
    )


def consume_password_reset(raw_token: str, new_password: str):
    token_hash = _hash_token(raw_token)
    record = (
        PasswordResetToken.objects.select_related("user")
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
    return record.user
