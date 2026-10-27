"""User model and identity-related models."""
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone

from apps.common.models import Base


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra):
        if not email:
            raise ValueError("An email address is required.")
        email = self.normalize_email(email).lower()
        user = self.model(email=email, **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra):
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra)

    def create_superuser(self, email, password=None, **extra):
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        if extra.get("is_staff") is not True or extra.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_staff and is_superuser set to True.")
        return self._create_user(email, password, **extra)


class User(Base, AbstractBaseUser, PermissionsMixin):
    """Platform user. Email is the unique identifier."""

    email = models.EmailField(unique=True, db_index=True)
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    phone = models.CharField(max_length=40, blank=True)
    job_title = models.CharField(max_length=150, blank=True)
    avatar = models.ImageField(upload_to="avatars/", null=True, blank=True)

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    mfa_enabled = models.BooleanField(default=False)
    email_verified_at = models.DateTimeField(null=True, blank=True)
    last_activity_at = models.DateTimeField(null=True, blank=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    class Meta:
        ordering = ["email"]
        indexes = [models.Index(fields=["is_active", "email"], name="idx_user_active_email")]

    def __str__(self) -> str:
        return self.email

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip() or self.email

    def touch_activity(self):
        self.last_activity_at = timezone.now()
        self.save(update_fields=["last_activity_at"])

    # --- tenancy helpers -------------------------------------------------
    def active_memberships(self):
        return self.memberships.select_related("organization").filter(
            is_active=True, organization__deleted_at__isnull=True
        )

    def can_access_project(self, project) -> bool:
        if project is None:
            return False
        membership = self.memberships.filter(
            organization_id=project.organization_id, is_active=True
        ).first()
        if membership is None:
            return False
        if membership.is_org_admin:
            return True
        return project.members.filter(user=self, is_active=True).exists() or project.is_public

    def project_role(self, project) -> str:
        member = project.members.filter(user=self, is_active=True).first()
        if member:
            return member.role_code
        membership = self.memberships.filter(
            organization_id=project.organization_id, is_active=True
        ).first()
        return membership.role_code if membership else "viewer"


class UserSession(Base):
    """Optional lightweight session/device record for auditing logins."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="sessions")
    refresh_jti = models.CharField(max_length=255, blank=True, db_index=True)
    user_agent = models.CharField(max_length=400, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=["user", "revoked_at"], name="idx_session_user_revoked")]

    def __str__(self) -> str:  # pragma: no cover
        return f"Session({self.user_id})"


class PasswordResetToken(Base):
    """Password reset request (signed token emailed to the user)."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="password_resets")
    token_hash = models.CharField(max_length=64, db_index=True)
    used_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField()

    class Meta:
        indexes = [models.Index(fields=["user", "used_at"], name="idx_pwreset_user_used")]

    def is_valid(self) -> bool:
        return self.used_at is None and self.expires_at > timezone.now()
