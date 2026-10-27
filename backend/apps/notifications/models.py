"""In-app notifications and user preferences."""
from django.contrib.auth import get_user_model
from django.db import models

from apps.common.models import UUIDModel

User = get_user_model()


class Notification(UUIDModel):
    LEVEL_CHOICES = [
        ("info", "Info"),
        ("success", "Success"),
        ("warning", "Warning"),
        ("error", "Error"),
    ]

    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name="notifications")
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.CASCADE, related_name="notifications",
        null=True, blank=True,
    )
    project = models.ForeignKey(
        "projects.Project", on_delete=models.CASCADE, related_name="notifications", null=True, blank=True
    )
    verb = models.CharField(max_length=120, db_index=True)
    title = models.CharField(max_length=255)
    body = models.TextField(blank=True)
    level = models.CharField(max_length=12, choices=LEVEL_CHOICES, default="info")
    target_type = models.CharField(max_length=120, blank=True)
    target_id = models.CharField(max_length=120, blank=True)
    url = models.CharField(max_length=500, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    read_at = models.DateTimeField(null=True, blank=True, db_index=True)
    emailed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["recipient", "read_at"], name="idx_notif_recipient_read"),
            models.Index(fields=["recipient", "-created_at"], name="idx_notif_recipient_created"),
        ]

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.title} -> {self.recipient_id}"

    @property
    def is_read(self) -> bool:
        return self.read_at is not None


class NotificationPreference(UUIDModel):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="notification_preferences")
    email_enabled = models.BooleanField(default=True)
    in_app_enabled = models.BooleanField(default=True)
    digest_frequency = models.CharField(
        max_length=16,
        choices=[("realtime", "Real-time"), ("daily", "Daily"), ("weekly", "Weekly"), ("never", "Never")],
        default="realtime",
    )
    muted_verbs = models.JSONField(default=list, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:  # pragma: no cover
        return f"Prefs({self.user_id})"
