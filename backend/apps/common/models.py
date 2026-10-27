"""Shared abstract models and DB helpers."""
import uuid

from django.db import models


class UUIDModel(models.Model):
    """Abstract base with a UUID primary key."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True


class TimeStampedModel(models.Model):
    """Abstract created/updated timestamps."""

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Base(UUIDModel, TimeStampedModel):
    """UUID + timestamps."""

    class Meta:
        abstract = True


class SoftDeleteQuerySet(models.QuerySet):
    def alive(self):
        return self.filter(deleted_at__isnull=True)

    def deleted(self):
        return self.filter(deleted_at__isnull=False)

    def delete(self):
        return super().update(deleted_at=timezone_now())

    def hard_delete(self):
        return super().delete()


def timezone_now():
    from django.utils import timezone

    return timezone.now()


class SoftDeleteModel(Base):
    """Optional soft-delete support."""

    deleted_at = models.DateTimeField(null=True, blank=True, db_index=True)

    objects = SoftDeleteQuerySet.as_manager()

    class Meta:
        abstract = True


# ---------------------------------------------------------------------------
# Field helpers
# ---------------------------------------------------------------------------


class MoneyField(models.DecimalField):
    """Money: 14 digits, 2 decimal places."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("max_digits", 14)
        kwargs.setdefault("decimal_places", 2)
        super().__init__(*args, **kwargs)


class RateField(models.DecimalField):
    """Unit price / percentage rate with higher precision."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("max_digits", 12)
        kwargs.setdefault("decimal_places", 4)
        super().__init__(*args, **kwargs)


class IdempotencyKey(Base):
    """Stored replay guard for idempotent write requests."""

    user = models.ForeignKey(
        "accounts.User", on_delete=models.CASCADE, related_name="idempotency_keys"
    )
    key = models.CharField(max_length=255)
    endpoint = models.CharField(max_length=255)
    request_hash = models.CharField(max_length=64)
    response_status = models.PositiveSmallIntegerField(null=True, blank=True)
    response_body = models.JSONField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "key", "endpoint"], name="uniq_idempotency_user_key_endpoint"
            )
        ]
        indexes = [
            models.Index(fields=["user", "key"], name="idx_idem_user_key"),
        ]

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.user_id}:{self.key}:{self.endpoint}"
