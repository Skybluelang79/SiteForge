"""Persistence for AI assistant conversations."""
from django.conf import settings
from django.db import models

from apps.common.models import Base


class AssistantConversation(Base):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.CASCADE, related_name="assistant_conversations"
    )
    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assistant_conversations",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="assistant_conversations"
    )
    title = models.CharField(max_length=180, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-updated_at"]
        indexes = [
            models.Index(fields=["organization", "user"], name="idx_assistant_org_user"),
        ]

    def __str__(self) -> str:  # pragma: no cover
        return self.title or f"Conversation {self.pk}"


class AssistantMessage(Base):
    ROLE_CHOICES = [
        ("user", "User"),
        ("assistant", "Assistant"),
    ]

    conversation = models.ForeignKey(
        AssistantConversation, on_delete=models.CASCADE, related_name="messages"
    )
    role = models.CharField(max_length=12, choices=ROLE_CHOICES)
    content = models.TextField()
    model = models.CharField(max_length=80, blank=True)
    provider = models.CharField(max_length=40, blank=True)
    latency_ms = models.PositiveIntegerField(default=0)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["conversation", "created_at"], name="idx_assistant_msg_conv"),
        ]

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.role}: {self.content[:60]}"
