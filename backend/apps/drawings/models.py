"""Construction drawings with revision tracking and review workflows."""
from django.contrib.auth import get_user_model
from django.db import models
from django.utils import timezone

from apps.common.models import Base

User = get_user_model()


class DrawingSet(Base):
    """A discipline-based set of drawings (e.g. Architectural, Structural)."""

    project = models.ForeignKey("projects.Project", on_delete=models.CASCADE, related_name="drawing_sets")
    name = models.CharField(max_length=255)
    discipline = models.CharField(max_length=100, blank=True, db_index=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["discipline", "name"]
        constraints = [
            models.UniqueConstraint(fields=["project", "name"], name="uniq_drawingset_project_name")
        ]

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.name} ({self.discipline})"


class Drawing(Base):
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("issued", "Issued for Construction"),
        ("superseded", "Superseded"),
        ("void", "Void"),
    ]

    project = models.ForeignKey("projects.Project", on_delete=models.CASCADE, related_name="drawings")
    drawing_set = models.ForeignKey(
        DrawingSet, on_delete=models.SET_NULL, null=True, blank=True, related_name="drawings"
    )
    title = models.CharField(max_length=255)
    number = models.CharField(max_length=80, db_index=True)
    discipline = models.CharField(max_length=100, blank=True, db_index=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft", db_index=True)
    current_revision = models.ForeignKey(
        "DrawingRevision", on_delete=models.SET_NULL, null=True, blank=True, related_name="current_for"
    )
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="drawings_created"
    )

    class Meta:
        ordering = ["number"]
        constraints = [
            models.UniqueConstraint(fields=["project", "number"], name="uniq_drawing_project_number")
        ]
        indexes = [
            models.Index(fields=["project", "discipline"], name="idx_drawing_project_discipline"),
            models.Index(fields=["project", "status"], name="idx_drawing_project_status"),
        ]

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.number} - {self.title}"


class DrawingRevision(Base):
    REVIEW_STATUS_CHOICES = [
        ("pending", "Pending Review"),
        ("in_review", "In Review"),
        ("approved", "Approved"),
        ("approved_as_noted", "Approved as Noted"),
        ("revise_resubmit", "Revise and Resubmit"),
        ("rejected", "Rejected"),
    ]

    drawing = models.ForeignKey(Drawing, on_delete=models.CASCADE, related_name="revisions")
    revision_code = models.CharField(max_length=20)
    revision_date = models.DateField(default=timezone.now)
    file = models.FileField(upload_to="drawings/%Y/%m/")
    original_filename = models.CharField(max_length=400, blank=True)
    content_type = models.CharField(max_length=120, blank=True)
    size_bytes = models.BigIntegerField(default=0)
    checksum = models.CharField(max_length=64, blank=True, db_index=True)
    change_summary = models.TextField(blank=True)
    review_status = models.CharField(
        max_length=24, choices=REVIEW_STATUS_CHOICES, default="pending", db_index=True
    )
    reviewed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="drawing_revisions_reviewed"
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_comments = models.TextField(blank=True)
    uploaded_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="drawing_revisions_uploaded"
    )

    class Meta:
        ordering = ["-revision_date", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["drawing", "revision_code"], name="uniq_revision_drawing_code"
            )
        ]
        indexes = [
            models.Index(fields=["drawing", "-revision_date"], name="idx_rev_drawing_date"),
            models.Index(fields=["review_status"], name="idx_rev_review_status"),
        ]

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.drawing_id} {self.revision_code}"


class DrawingReview(Base):
    """Individual review step assigned to a stakeholder."""

    DECISION_CHOICES = DrawingRevision.REVIEW_STATUS_CHOICES

    revision = models.ForeignKey(DrawingRevision, on_delete=models.CASCADE, related_name="reviews")
    reviewer = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="drawing_reviews", null=True, blank=True
    )
    decision = models.CharField(max_length=24, choices=DECISION_CHOICES, default="pending", db_index=True)
    comments = models.TextField(blank=True)
    due_date = models.DateField(null=True, blank=True)
    decided_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [models.Index(fields=["revision", "decision"], name="idx_drawreview_rev_decision")]

    def __str__(self) -> str:  # pragma: no cover
        return f"Review({self.revision_id}, {self.decision})"
