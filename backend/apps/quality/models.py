"""Quality management, inspections, defects, punch lists and safety incidents."""
from django.contrib.auth import get_user_model
from django.db import models

from apps.common.models import Base

User = get_user_model()


class Inspection(Base):
    STATUS_CHOICES = [
        ("scheduled", "Scheduled"),
        ("in_progress", "In Progress"),
        ("passed", "Passed"),
        ("failed", "Failed"),
        ("conditional", "Conditionally Passed"),
        ("cancelled", "Cancelled"),
    ]
    TYPE_CHOICES = [
        ("quality", "Quality"),
        ("safety", "Safety"),
        ("environmental", "Environmental"),
        ("handover", "Handover"),
        ("other", "Other"),
    ]

    project = models.ForeignKey("projects.Project", on_delete=models.CASCADE, related_name="inspections")
    number = models.CharField(max_length=40, db_index=True)
    title = models.CharField(max_length=255)
    inspection_type = models.CharField(max_length=24, choices=TYPE_CHOICES, default="quality", db_index=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="scheduled", db_index=True)
    description = models.TextField(blank=True)
    location = models.CharField(max_length=255, blank=True)
    checklist = models.JSONField(default=list, blank=True)
    scheduled_date = models.DateField(null=True, blank=True, db_index=True)
    completed_date = models.DateField(null=True, blank=True)
    inspector = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="inspections_performed"
    )
    signed_off_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="inspections_signed"
    )
    signed_off_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="inspections_created"
    )

    class Meta:
        ordering = ["-scheduled_date", "-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["project", "number"], name="uniq_inspection_project_number")
        ]
        indexes = [
            models.Index(fields=["project", "status"], name="idx_inspection_project_status"),
            models.Index(fields=["project", "inspection_type"], name="idx_inspection_project_type"),
        ]

    def __str__(self) -> str:  # pragma: no cover
        return f"Inspection {self.number}"


class InspectionItem(Base):
    RESULT_CHOICES = [
        ("pending", "Pending"),
        ("pass", "Pass"),
        ("fail", "Fail"),
        ("na", "Not Applicable"),
    ]

    inspection = models.ForeignKey(Inspection, on_delete=models.CASCADE, related_name="items")
    order = models.PositiveSmallIntegerField(default=1)
    description = models.CharField(max_length=400)
    result = models.CharField(max_length=12, choices=RESULT_CHOICES, default="pending")
    notes = models.TextField(blank=True)
    photo = models.ImageField(upload_to="inspection-items/%Y/%m/", null=True, blank=True)

    class Meta:
        ordering = ["order"]
        indexes = [models.Index(fields=["inspection"], name="idx_inspectionitem_inspection")]


class Defect(Base):
    SEVERITY_CHOICES = [("low", "Low"), ("medium", "Medium"), ("high", "High"), ("critical", "Critical")]
    STATUS_CHOICES = [
        ("open", "Open"),
        ("in_progress", "In Progress"),
        ("resolved", "Resolved"),
        ("verified", "Verified"),
        ("closed", "Closed"),
    ]

    project = models.ForeignKey("projects.Project", on_delete=models.CASCADE, related_name="defects")
    inspection = models.ForeignKey(
        Inspection, on_delete=models.SET_NULL, null=True, blank=True, related_name="defects"
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    severity = models.CharField(max_length=12, choices=SEVERITY_CHOICES, default="medium", db_index=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="open", db_index=True)
    location = models.CharField(max_length=255, blank=True)
    cost_code = models.ForeignKey(
        "financials.CostCode", on_delete=models.SET_NULL, null=True, blank=True, related_name="defects"
    )
    assigned_to = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="defects_assigned"
    )
    due_date = models.DateField(null=True, blank=True)
    photo = models.ImageField(upload_to="defects/%Y/%m/", null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="defects_created"
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["project", "status"], name="idx_defect_project_status"),
            models.Index(fields=["project", "severity"], name="idx_defect_project_severity"),
        ]

    def __str__(self) -> str:  # pragma: no cover
        return self.title


class PunchList(Base):
    STATUS_CHOICES = [("open", "Open"), ("in_progress", "In Progress"), ("completed", "Completed"), ("closed", "Closed")]

    project = models.ForeignKey("projects.Project", on_delete=models.CASCADE, related_name="punch_lists")
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="open", db_index=True)
    target_date = models.DateField(null=True, blank=True)
    assigned_to = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="punch_lists_assigned"
    )
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="punch_lists_created"
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["project", "status"], name="idx_punchlist_project_status")]

    def __str__(self) -> str:  # pragma: no cover
        return self.name


class PunchListItem(Base):
    STATUS_CHOICES = [
        ("open", "Open"),
        ("in_progress", "In Progress"),
        ("ready_for_review", "Ready for Review"),
        ("closed", "Closed"),
        ("rejected", "Rejected"),
    ]

    punch_list = models.ForeignKey(PunchList, on_delete=models.CASCADE, related_name="items")
    description = models.CharField(max_length=500)
    location = models.CharField(max_length=255, blank=True)
    trade = models.CharField(max_length=120, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="open", db_index=True)
    assigned_to = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="punch_items_assigned"
    )
    due_date = models.DateField(null=True, blank=True)
    photo = models.ImageField(upload_to="punch-items/%Y/%m/", null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [models.Index(fields=["punch_list", "status"], name="idx_punchitem_list_status")]


class SafetyIncident(Base):
    SEVERITY_CHOICES = [
        ("near_miss", "Near Miss"),
        ("first_aid", "First Aid"),
        ("medical", "Medical Treatment"),
        ("lost_time", "Lost Time"),
        ("fatality", "Fatality"),
        ("property_damage", "Property Damage"),
    ]
    STATUS_CHOICES = [
        ("reported", "Reported"),
        ("investigating", "Investigating"),
        ("corrective_action", "Corrective Action"),
        ("closed", "Closed"),
    ]

    project = models.ForeignKey("projects.Project", on_delete=models.CASCADE, related_name="safety_incidents")
    number = models.CharField(max_length=40, db_index=True)
    title = models.CharField(max_length=255)
    description = models.TextField()
    severity = models.CharField(max_length=24, choices=SEVERITY_CHOICES, default="near_miss", db_index=True)
    status = models.CharField(max_length=24, choices=STATUS_CHOICES, default="reported", db_index=True)
    occurred_at = models.DateTimeField(db_index=True)
    location = models.CharField(max_length=255, blank=True)
    injured_person = models.CharField(max_length=255, blank=True)
    witnesses = models.TextField(blank=True)
    root_cause = models.TextField(blank=True)
    immediate_actions = models.TextField(blank=True)
    osha_recordable = models.BooleanField(default=False)
    days_lost = models.PositiveIntegerField(default=0)
    reported_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="incidents_reported"
    )
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="incidents_created"
    )

    class Meta:
        ordering = ["-occurred_at"]
        constraints = [
            models.UniqueConstraint(fields=["project", "number"], name="uniq_incident_project_number")
        ]
        indexes = [
            models.Index(fields=["project", "status"], name="idx_incident_project_status"),
            models.Index(fields=["project", "severity"], name="idx_incident_project_severity"),
        ]

    def __str__(self) -> str:  # pragma: no cover
        return f"Incident {self.number}: {self.title}"


class CorrectiveAction(Base):
    STATUS_CHOICES = [
        ("open", "Open"),
        ("in_progress", "In Progress"),
        ("completed", "Completed"),
        ("verified", "Verified"),
        ("overdue", "Overdue"),
    ]

    project = models.ForeignKey("projects.Project", on_delete=models.CASCADE, related_name="corrective_actions")
    incident = models.ForeignKey(
        SafetyIncident, on_delete=models.SET_NULL, null=True, blank=True, related_name="corrective_actions"
    )
    inspection = models.ForeignKey(
        Inspection, on_delete=models.SET_NULL, null=True, blank=True, related_name="corrective_actions"
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="open", db_index=True)
    assigned_to = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="corrective_actions_assigned"
    )
    due_date = models.DateField(null=True, blank=True, db_index=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    verified_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="corrective_actions_verified"
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="corrective_actions_created"
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["project", "status"], name="idx_ca_project_status")]

    def __str__(self) -> str:  # pragma: no cover
        return self.title
