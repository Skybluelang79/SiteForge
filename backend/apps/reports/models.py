"""Saved report definitions, dashboards and export jobs."""
from django.contrib.auth import get_user_model
from django.db import models

from apps.common.models import Base

User = get_user_model()


class ReportDefinition(Base):
    REPORT_TYPE_CHOICES = [
        ("budget_summary", "Budget Summary"),
        ("cost_to_date", "Cost to Date"),
        ("rfi_aging", "RFI Aging"),
        ("submittal_status", "Submittal Status"),
        ("task_progress", "Task Progress"),
        ("safety_log", "Safety Log"),
        ("inspections", "Inspections"),
        ("daily_log_summary", "Daily Log Summary"),
        ("change_order_log", "Change Order Log"),
    ]
    VISIBILITY_CHOICES = [("private", "Private"), ("project", "Project"), ("organization", "Organization")]

    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.CASCADE, related_name="report_definitions"
    )
    project = models.ForeignKey(
        "projects.Project", on_delete=models.CASCADE, null=True, blank=True, related_name="report_definitions"
    )
    name = models.CharField(max_length=255)
    report_type = models.CharField(max_length=40, choices=REPORT_TYPE_CHOICES, db_index=True)
    description = models.TextField(blank=True)
    parameters = models.JSONField(default=dict, blank=True)
    visibility = models.CharField(max_length=20, choices=VISIBILITY_CHOICES, default="private")
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="report_definitions_created"
    )

    class Meta:
        ordering = ["name"]
        indexes = [models.Index(fields=["organization", "report_type"], name="idx_report_org_type")]

    def __str__(self) -> str:  # pragma: no cover
        return self.name


class Dashboard(Base):
    """Configurable dashboard composed of widget definitions."""

    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.CASCADE, related_name="dashboards"
    )
    project = models.ForeignKey(
        "projects.Project", on_delete=models.CASCADE, null=True, blank=True, related_name="dashboards"
    )
    name = models.CharField(max_length=255)
    layout = models.JSONField(default=list, blank=True)
    is_default = models.BooleanField(default=False)
    shared_with_org = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="dashboards_created"
    )

    class Meta:
        ordering = ["name"]
        indexes = [models.Index(fields=["organization"], name="idx_dashboard_org")]


class ExportJob(Base):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("processing", "Processing"),
        ("completed", "Completed"),
        ("failed", "Failed"),
    ]
    FORMAT_CHOICES = [("csv", "CSV"), ("xlsx", "Excel"), ("pdf", "PDF"), ("json", "JSON")]

    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.CASCADE, related_name="export_jobs"
    )
    project = models.ForeignKey(
        "projects.Project", on_delete=models.SET_NULL, null=True, blank=True, related_name="export_jobs"
    )
    report_definition = models.ForeignKey(
        ReportDefinition, on_delete=models.SET_NULL, null=True, blank=True, related_name="exports"
    )
    export_type = models.CharField(max_length=60, db_index=True)
    export_format = models.CharField(max_length=12, choices=FORMAT_CHOICES, default="csv")
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="pending", db_index=True)
    parameters = models.JSONField(default=dict, blank=True)
    file = models.FileField(upload_to="exports/%Y/%m/", null=True, blank=True)
    row_count = models.PositiveIntegerField(default=0)
    error_message = models.CharField(max_length=500, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    requested_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="export_jobs"
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["organization", "status"], name="idx_export_org_status")]

    def __str__(self) -> str:  # pragma: no cover
        return f"Export({self.export_type}, {self.status})"


class MetricSnapshot(Base):
    """Time-series operational metrics for dashboards/analytics."""

    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.CASCADE, related_name="metric_snapshots"
    )
    project = models.ForeignKey(
        "projects.Project", on_delete=models.CASCADE, null=True, blank=True, related_name="metric_snapshots"
    )
    metric_key = models.CharField(max_length=80, db_index=True)
    captured_at = models.DateTimeField(db_index=True)
    value = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-captured_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "project", "metric_key", "captured_at"],
                name="uniq_metric_org_project_key_time",
            )
        ]
        indexes = [models.Index(fields=["organization", "metric_key"], name="idx_metric_org_key")]
