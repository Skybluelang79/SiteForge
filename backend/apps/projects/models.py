"""Project, project team, milestone, contract and activity models."""
from django.contrib.auth import get_user_model
from django.db import models
from django.utils import timezone

from apps.common.models import Base, MoneyField, SoftDeleteModel

User = get_user_model()


class Project(SoftDeleteModel):
    STATUS_CHOICES = [
        ("planning", "Planning"),
        ("active", "Active"),
        ("on_hold", "On Hold"),
        ("closeout", "Closeout"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
    ]

    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.CASCADE, related_name="projects"
    )
    name = models.CharField(max_length=255)
    number = models.CharField(max_length=60, blank=True)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=24, choices=STATUS_CHOICES, default="planning", db_index=True)
    project_type = models.CharField(max_length=80, blank=True)
    address_line1 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=120, blank=True)
    region = models.CharField(max_length=120, blank=True)
    postal_code = models.CharField(max_length=40, blank=True)
    country = models.CharField(max_length=80, blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    start_date = models.DateField(null=True, blank=True)
    target_completion_date = models.DateField(null=True, blank=True)
    actual_completion_date = models.DateField(null=True, blank=True)
    contract_value = MoneyField(default=0)
    currency = models.CharField(max_length=3, default="USD")
    client_name = models.CharField(max_length=255, blank=True)
    project_manager = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="managed_projects"
    )
    is_public = models.BooleanField(
        default=False, help_text="If true, all organization members may view this project."
    )
    settings = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "number"],
                condition=models.Q(number__gt=""),
                name="uniq_project_org_number",
            )
        ]
        indexes = [
            models.Index(fields=["organization", "status"], name="idx_project_org_status"),
            models.Index(fields=["organization", "deleted_at"], name="idx_project_org_deleted"),
        ]

    def __str__(self) -> str:
        return f"{self.number or 'P'}: {self.name}"

    @property
    def is_overdue(self) -> bool:
        if self.actual_completion_date or not self.target_completion_date:
            return False
        return self.target_completion_date < timezone.now().date()


class ProjectMember(Base):
    ROLE_CHOICES = [
        ("owner", "Owner"),
        ("admin", "Admin"),
        ("member", "Member"),
        ("contractor", "Contractor"),
        ("viewer", "Viewer"),
    ]

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="members")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="project_memberships")
    role_code = models.CharField(max_length=32, choices=ROLE_CHOICES, default="member")
    title = models.CharField(max_length=150, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    added_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="project_members_added"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["project", "user"], name="uniq_project_member")
        ]
        indexes = [models.Index(fields=["project", "is_active"], name="idx_pm_project_active")]

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.user_id}@{self.project_id} ({self.role_code})"


class Milestone(Base):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("in_progress", "In Progress"),
        ("achieved", "Achieved"),
        ("missed", "Missed"),
    ]

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="milestones")
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    due_date = models.DateField(null=True, blank=True, db_index=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending", db_index=True)
    achieved_date = models.DateField(null=True, blank=True)
    weight = models.PositiveSmallIntegerField(default=1)
    owner = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="milestones_owned"
    )

    class Meta:
        ordering = ["due_date", "name"]
        indexes = [models.Index(fields=["project", "status"], name="idx_milestone_project_status")]

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.name} ({self.get_status_display()})"


class Contract(Base):
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("active", "Active"),
        ("completed", "Completed"),
        ("terminated", "Terminated"),
    ]
    TYPE_CHOICES = [
        ("owner", "Owner Agreement"),
        ("prime", "Prime Contract"),
        ("subcontract", "Subcontract"),
        ("consultant", "Consultant Agreement"),
        ("supply", "Supply Agreement"),
    ]

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="contracts")
    name = models.CharField(max_length=255)
    number = models.CharField(max_length=60, blank=True)
    contract_type = models.CharField(max_length=24, choices=TYPE_CHOICES, default="prime", db_index=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft", db_index=True)
    counterparty = models.CharField(max_length=255, blank=True)
    original_value = MoneyField(default=0)
    revised_value = MoneyField(default=0)
    currency = models.CharField(max_length=3, default="USD")
    retention_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    signed_date = models.DateField(null=True, blank=True)
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="contracts_created"
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["project", "status"], name="idx_contract_project_status"),
            models.Index(fields=["project", "contract_type"], name="idx_contract_project_type"),
        ]

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.number or 'C'}: {self.name}"


class ActivityFeedEntry(Base):
    """Project activity stream (append-only)."""

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="activity_entries")
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.CASCADE, related_name="activity_entries"
    )
    actor = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="activity_entries"
    )
    verb = models.CharField(max_length=80, db_index=True)
    summary = models.CharField(max_length=400, blank=True)
    target_type = models.CharField(max_length=120, blank=True)
    target_id = models.CharField(max_length=120, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["project", "-created_at"], name="idx_activity_project_created"),
            models.Index(fields=["organization", "-created_at"], name="idx_activity_org_created"),
        ]

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.verb}: {self.summary}"
