"""RFIs, submittals, comments and approval chains."""
from django.contrib.auth import get_user_model
from django.db import models

from apps.common.models import Base

User = get_user_model()


class RFI(Base):
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("open", "Open"),
        ("answered", "Answered"),
        ("closed", "Closed"),
        ("overdue", "Overdue"),
    ]
    PRIORITY_CHOICES = [
        ("low", "Low"),
        ("medium", "Medium"),
        ("high", "High"),
        ("critical", "Critical"),
    ]

    project = models.ForeignKey("projects.Project", on_delete=models.CASCADE, related_name="rfis")
    number = models.CharField(max_length=40, db_index=True)
    subject = models.CharField(max_length=255)
    question = models.TextField()
    official_response = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft", db_index=True)
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default="medium", db_index=True)
    cost_impact = models.BooleanField(default=False)
    schedule_impact = models.BooleanField(default=False)
    cost_impact_amount = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    schedule_impact_days = models.IntegerField(null=True, blank=True)
    drawing = models.ForeignKey(
        "drawings.Drawing", on_delete=models.SET_NULL, null=True, blank=True, related_name="rfis"
    )
    assigned_to = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="rfis_assigned"
    )
    ball_in_court = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="rfis_ball_in_court"
    )
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="rfis_created"
    )
    due_date = models.DateField(null=True, blank=True, db_index=True)
    answered_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["project", "number"], name="uniq_rfi_project_number")
        ]
        indexes = [
            models.Index(fields=["project", "status"], name="idx_rfi_project_status"),
            models.Index(fields=["project", "assigned_to"], name="idx_rfi_project_assignee"),
        ]

    def __str__(self) -> str:  # pragma: no cover
        return f"RFI {self.number}: {self.subject}"


class RFIComment(Base):
    rfi = models.ForeignKey(RFI, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="rfi_comments"
    )
    body = models.TextField()
    is_official = models.BooleanField(default=False)

    class Meta:
        ordering = ["created_at"]
        indexes = [models.Index(fields=["rfi", "created_at"], name="idx_rficomment_rfi_created")]


class Submittal(Base):
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("submitted", "Submitted"),
        ("under_review", "Under Review"),
        ("approved", "Approved"),
        ("approved_as_noted", "Approved as Noted"),
        ("revise_resubmit", "Revise and Resubmit"),
        ("rejected", "Rejected"),
        ("closed", "Closed"),
    ]
    TYPE_CHOICES = [
        ("shop_drawing", "Shop Drawing"),
        ("product_data", "Product Data"),
        ("sample", "Sample"),
        ("mockup", "Mock-up"),
        ("method_statement", "Method Statement"),
        ("certificate", "Certificate"),
        ("other", "Other"),
    ]

    project = models.ForeignKey("projects.Project", on_delete=models.CASCADE, related_name="submittals")
    number = models.CharField(max_length=40, db_index=True)
    title = models.CharField(max_length=255)
    submittal_type = models.CharField(max_length=24, choices=TYPE_CHOICES, default="product_data", db_index=True)
    spec_section = models.CharField(max_length=120, blank=True)
    revision = models.CharField(max_length=20, default="0")
    status = models.CharField(max_length=24, choices=STATUS_CHOICES, default="draft", db_index=True)
    description = models.TextField(blank=True)
    submitted_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="submittals_submitted"
    )
    reviewer = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="submittals_reviewing"
    )
    due_date = models.DateField(null=True, blank=True, db_index=True)
    required_by = models.DateField(null=True, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    final_approval = models.ForeignKey(
        "SubmittalApproval", on_delete=models.SET_NULL, null=True, blank=True, related_name="final_for"
    )

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["project", "number", "revision"], name="uniq_submittal_project_number_rev"
            )
        ]
        indexes = [
            models.Index(fields=["project", "status"], name="idx_submittal_project_status"),
            models.Index(fields=["project", "submittal_type"], name="idx_submittal_project_type"),
        ]

    def __str__(self) -> str:  # pragma: no cover
        return f"Submittal {self.number}: {self.title}"


class SubmittalItem(Base):
    """Line items / attachments within a submittal."""

    submittal = models.ForeignKey(Submittal, on_delete=models.CASCADE, related_name="items")
    description = models.CharField(max_length=400)
    spec_reference = models.CharField(max_length=120, blank=True)
    file = models.FileField(upload_to="submittals/%Y/%m/", null=True, blank=True)
    status = models.CharField(max_length=24, choices=Submittal.STATUS_CHOICES, default="submitted")
    review_notes = models.TextField(blank=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [models.Index(fields=["submittal"], name="idx_submittalitem_submittal")]


class ApprovalChain(Base):
    """Ordered approval steps bound to any approval workflow target."""

    project = models.ForeignKey("projects.Project", on_delete=models.CASCADE, related_name="approval_chains")
    name = models.CharField(max_length=255)
    target_type = models.CharField(max_length=80, default="submittal", db_index=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        indexes = [models.Index(fields=["project", "target_type"], name="idx_chain_project_target")]


class ApprovalChainStep(Base):
    chain = models.ForeignKey(ApprovalChain, on_delete=models.CASCADE, related_name="steps")
    order = models.PositiveSmallIntegerField(default=1)
    approver = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="approval_steps"
    )
    role_code = models.CharField(max_length=32, blank=True)
    is_required = models.BooleanField(default=True)

    class Meta:
        ordering = ["order"]
        constraints = [
            models.UniqueConstraint(fields=["chain", "order"], name="uniq_chain_step_order")
        ]


class SubmittalApproval(Base):
    """A single approval action recorded against a submittal."""

    DECISION_CHOICES = [
        ("approved", "Approved"),
        ("approved_as_noted", "Approved as Noted"),
        ("revise_resubmit", "Revise and Resubmit"),
        ("rejected", "Rejected"),
    ]

    submittal = models.ForeignKey(Submittal, on_delete=models.CASCADE, related_name="approvals")
    step = models.ForeignKey(
        ApprovalChainStep, on_delete=models.SET_NULL, null=True, blank=True, related_name="actions"
    )
    approver = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="submittal_approvals"
    )
    decision = models.CharField(max_length=24, choices=DECISION_CHOICES, db_index=True)
    comments = models.TextField(blank=True)
    decided_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-decided_at"]
        indexes = [models.Index(fields=["submittal", "-decided_at"], name="idx_subappr_submittal_date")]


class Comment(Base):
    """Generic threaded comment for any target (RFIs, submittals, documents, tasks)."""

    project = models.ForeignKey("projects.Project", on_delete=models.CASCADE, related_name="comments")
    target_type = models.CharField(max_length=80, db_index=True)
    target_id = models.CharField(max_length=64, db_index=True)
    author = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="comments"
    )
    body = models.TextField()
    parent = models.ForeignKey(
        "self", on_delete=models.CASCADE, null=True, blank=True, related_name="replies"
    )

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["project", "target_type", "target_id"], name="idx_comment_target"),
        ]
