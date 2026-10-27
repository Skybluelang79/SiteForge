"""Report export generation and metric collection helpers."""
import csv
import io
import json
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from django.core.files.base import ContentFile
from django.utils import timezone

from apps.drawings.models import Drawing
from apps.financials.models import BudgetLine, ChangeOrder
from apps.field.models import DailyLog
from apps.quality.models import Inspection, SafetyIncident
from apps.rfis.models import RFI, Submittal
from apps.tasks.models import Task

from .models import ExportJob

SUPPORTED_FORMATS = {"csv", "json"}


def _serialize(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, UUID):
        return str(value)
    return value


def _rows_for(job):
    project_id = job.project_id or job.parameters.get("project_id")
    export_type = job.export_type

    def scoped(queryset, project_field="project_id"):
        queryset = queryset.filter(project__organization_id=job.organization_id)
        if project_id:
            queryset = queryset.filter(**{project_field: project_id})
        return queryset

    if export_type in {"budget_summary", "cost_to_date"}:
        return list(
            scoped(BudgetLine.objects.all())
            .values(
                "project__name",
                "cost_code__code",
                "cost_code__name",
                "budgeted_amount",
                "committed_amount",
                "actual_amount",
                "forecast_amount",
            )
            .order_by("project__name", "cost_code__code")
        )
    if export_type == "rfi_aging":
        return list(
            scoped(RFI.objects.all())
            .values(
                "number", "subject", "status", "priority", "due_date",
                "project__name", "assigned_to__email",
            )
            .order_by("due_date")
        )
    if export_type == "submittal_status":
        return list(
            scoped(Submittal.objects.all())
            .values(
                "number", "title", "submittal_type", "status", "due_date",
                "project__name", "reviewer__email",
            )
            .order_by("due_date")
        )
    if export_type == "task_progress":
        return list(
            scoped(Task.objects.all())
            .values(
                "title", "status", "priority", "progress_percent", "start_date",
                "due_date", "project__name", "assignee__email",
            )
            .order_by("due_date")
        )
    if export_type == "safety_log":
        return list(
            scoped(SafetyIncident.objects.all())
            .values(
                "number", "title", "severity", "status", "occurred_at",
                "project__name", "osha_recordable",
            )
            .order_by("-occurred_at")
        )
    if export_type == "inspections":
        return list(
            scoped(Inspection.objects.all())
            .values(
                "number", "title", "inspection_type", "status", "scheduled_date",
                "completed_date", "project__name", "inspector__email",
            )
            .order_by("-created_at")
        )
    if export_type == "daily_log_summary":
        return list(
            scoped(DailyLog.objects.all())
            .values(
                "log_date", "status", "weather_summary", "work_activities",
                "project__name",
            )
            .order_by("-log_date")
        )
    if export_type == "change_order_log":
        return list(
            scoped(ChangeOrder.objects.all())
            .values(
                "number", "title", "status", "amount", "schedule_impact_days",
                "submitted_date", "approved_date", "project__name",
            )
            .order_by("-created_at")
        )
    if export_type == "drawing_register":
        return list(
            scoped(Drawing.objects.all())
            .values(
                "number", "title", "discipline", "status", "current_revision",
                "project__name",
            )
            .order_by("number")
        )
    return []


def generate_export(job):
    job.status = "processing"
    job.error_message = ""
    job.save(update_fields=["status", "error_message", "updated_at"])

    if job.export_format not in SUPPORTED_FORMATS:
        job.status = "failed"
        job.error_message = f"Unsupported export format: {job.export_format}"
        job.completed_at = timezone.now()
        job.save(update_fields=["status", "error_message", "completed_at", "updated_at"])
        return job

    try:
        rows = _rows_for(job)
        normalized = [{key: _serialize(value) for key, value in row.items()} for row in rows]

        if job.export_format == "json":
            payload = json.dumps(normalized, indent=2, ensure_ascii=False).encode("utf-8")
            extension = "json"
        else:
            buffer = io.StringIO()
            headers = list(normalized[0].keys()) if normalized else ["message"]
            writer = csv.DictWriter(buffer, fieldnames=headers)
            writer.writeheader()
            if normalized:
                writer.writerows(normalized)
            else:
                writer.writerow({"message": "No data"})
            payload = buffer.getvalue().encode("utf-8")
            extension = "csv"

        filename = f"{job.export_type}-{job.id}.{extension}"
        job.file.save(filename, ContentFile(payload), save=False)
        job.row_count = len(normalized)
        job.status = "completed"
        job.error_message = ""
        job.completed_at = timezone.now()
        job.save(
            update_fields=[
                "file", "row_count", "status", "error_message", "completed_at", "updated_at",
            ]
        )
    except Exception as exc:
        job.status = "failed"
        job.error_message = str(exc)[:500]
        job.completed_at = timezone.now()
        job.save(update_fields=["status", "error_message", "completed_at", "updated_at"])
    return job


def enqueue_export(job):
    from .tasks import run_export_job

    try:
        run_export_job.delay(str(job.id))
    except Exception:
        generate_export(job)
    return job


def collect_metrics_for_org(organization, captured_at=None):
    from apps.projects.models import Project
    from .models import MetricSnapshot

    captured_at = (captured_at or timezone.now()).replace(minute=0, second=0, microsecond=0)
    today = captured_at.date()
    projects = Project.objects.filter(organization=organization, deleted_at__isnull=True)
    created = 0
    for project in projects:
        metrics = {
            "open_rfis": RFI.objects.filter(
                project=project, status__in=["draft", "open", "answered"]
            ).count(),
            "overdue_rfis": RFI.objects.filter(
                project=project, due_date__lt=today, status__in=["draft", "open", "answered"]
            ).count(),
            "open_submittals": Submittal.objects.filter(
                project=project, status__in=["draft", "submitted", "under_review"]
            ).count(),
            "open_tasks": Task.objects.filter(project=project).exclude(
                status__in=["done", "cancelled"]
            ).count(),
            "completed_tasks": Task.objects.filter(project=project, status="done").count(),
            "open_defects": project.defects.exclude(status__in=["resolved", "verified", "closed"]).count(),
            "open_incidents": project.safety_incidents.exclude(status="closed").count(),
            "open_change_orders": project.change_orders.filter(status__in=["draft", "pending"]).count(),
        }
        for key, value in metrics.items():
            _, was_created = MetricSnapshot.objects.update_or_create(
                organization=organization,
                project=project,
                metric_key=key,
                captured_at=captured_at,
                defaults={"value": value},
            )
            created += 1 if was_created else 0
    return created
