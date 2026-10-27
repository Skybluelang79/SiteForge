"""Integration developer portal: API applications, credentials, webhooks."""
from django.contrib.auth import get_user_model
from django.db import models

from apps.common.models import Base, UUIDModel

User = get_user_model()


class ApiApplication(Base):
    """A developer-registered application (optionally linked to an OAuth client)."""

    ENVIRONMENT_CHOICES = [("development", "Development"), ("staging", "Staging"), ("production", "Production")]

    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.CASCADE, related_name="api_applications"
    )
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    environment = models.CharField(max_length=20, choices=ENVIRONMENT_CHOICES, default="development", db_index=True)
    client_id = models.CharField(max_length=120, blank=True, db_index=True)
    client_secret_hash = models.CharField(max_length=128, blank=True)
    scopes = models.JSONField(default=list, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="api_applications_created"
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["organization", "is_active"], name="idx_apiapp_org_active")]

    def __str__(self) -> str:  # pragma: no cover
        return self.name


class WebhookSubscription(Base):
    EVENT_CHOICES = [
        ("project.created", "Project created"),
        ("project.updated", "Project updated"),
        ("document.uploaded", "Document uploaded"),
        ("document.version.created", "Document version created"),
        ("rfi.created", "RFI created"),
        ("rfi.answered", "RFI answered"),
        ("submittal.created", "Submittal created"),
        ("submittal.approved", "Submittal approved"),
        ("change_order.approved", "Change order approved"),
        ("invoice.approved", "Invoice approved"),
        ("incident.created", "Safety incident created"),
        ("inspection.failed", "Inspection failed"),
    ]

    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.CASCADE, related_name="webhook_subscriptions"
    )
    application = models.ForeignKey(
        ApiApplication, on_delete=models.SET_NULL, null=True, blank=True, related_name="webhooks"
    )
    name = models.CharField(max_length=255)
    target_url = models.URLField(max_length=500)
    secret = models.CharField(max_length=128)
    event_types = models.JSONField(default=list, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    failure_count = models.PositiveIntegerField(default=0)
    last_success_at = models.DateTimeField(null=True, blank=True)
    last_failure_at = models.DateTimeField(null=True, blank=True)
    disabled_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="webhooks_created"
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["organization", "is_active"], name="idx_webhook_org_active"),
        ]

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.name} -> {self.target_url}"


class WebhookEvent(Base):
    """An event enqueued for delivery. event_id prevents duplicate processing."""

    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.CASCADE, related_name="webhook_events"
    )
    event_id = models.UUIDField(unique=True, db_index=True)
    event_type = models.CharField(max_length=120, db_index=True)
    project = models.ForeignKey(
        "projects.Project", on_delete=models.SET_NULL, null=True, blank=True, related_name="webhook_events"
    )
    payload = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["organization", "event_type"], name="idx_webhookevent_org_type")]


class WebhookDelivery(Base):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("success", "Success"),
        ("failed", "Failed"),
        ("retrying", "Retrying"),
        ("exhausted", "Exhausted"),
    ]

    subscription = models.ForeignKey(WebhookSubscription, on_delete=models.CASCADE, related_name="deliveries")
    event = models.ForeignKey(WebhookEvent, on_delete=models.CASCADE, related_name="deliveries")
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="pending", db_index=True)
    attempt_count = models.PositiveIntegerField(default=0)
    response_status = models.IntegerField(null=True, blank=True)
    response_body = models.TextField(blank=True)
    error_message = models.CharField(max_length=500, blank=True)
    duration_ms = models.PositiveIntegerField(null=True, blank=True)
    next_attempt_at = models.DateTimeField(null=True, blank=True, db_index=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["subscription", "event"], name="uniq_delivery_subscription_event"
            )
        ]
        indexes = [
            models.Index(fields=["subscription", "status"], name="idx_delivery_sub_status"),
            models.Index(fields=["status", "next_attempt_at"], name="idx_delivery_status_next"),
        ]

    def __str__(self) -> str:  # pragma: no cover
        return f"Delivery({self.subscription_id}, {self.status})"
