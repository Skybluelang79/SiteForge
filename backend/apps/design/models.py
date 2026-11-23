from django.contrib.auth import get_user_model
from django.db import models

from apps.common.models import Base

User = get_user_model()


class CanvasBoard(Base):
    project = models.ForeignKey(
        "projects.Project", on_delete=models.CASCADE, related_name="canvas_boards"
    )
    name = models.CharField(max_length=255)
    state = models.JSONField(default=dict, blank=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="canvas_boards_created",
    )

    class Meta:
        ordering = ["-updated_at", "-created_at"]
        indexes = [
            models.Index(fields=["project", "-updated_at"], name="idx_canvas_project_updated"),
        ]

    def __str__(self):
        return self.name
