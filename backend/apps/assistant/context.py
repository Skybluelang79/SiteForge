"""Build a compact, permission-aware project briefing for the assistant."""
from datetime import timedelta
from decimal import Decimal

from django.db.models import Q, Sum
from django.utils import timezone

from apps.financials.models import BudgetLine, ChangeOrder
from apps.projects.models import Milestone, Project
from apps.projects.views import projects_for_user
from apps.quality.models import Defect, PunchListItem, SafetyIncident
from apps.rfis.models import RFI, Submittal
from apps.tasks.models import Task


def _money(value):
    return float(value or 0)


def build_context(request, project_id=None):
    membership = request.membership
    organization = membership.organization
    project_ids = list(
        projects_for_user(request.user, organization.id).values_list("id", flat=True)
    )
    all_projects = Project.objects.filter(id__in=project_ids).select_related("project_manager")
    projects = all_projects
    if project_id:
        projects = projects.filter(id=project_id)
        scope_project = projects.first()
    else:
        scope_project = all_projects.first() if len(project_ids) == 1 else None
    scoped_ids = [scope_project.id] if scope_project else project_ids

    today = timezone.now().date()
    soon = today + timedelta(days=30)
    ninety_days_ago = timezone.now() - timedelta(days=90)

    tasks = Task.objects.filter(project_id__in=scoped_ids)
    rfis = RFI.objects.filter(project_id__in=scoped_ids)
    submittals = Submittal.objects.filter(project_id__in=scoped_ids)
    incidents = SafetyIncident.objects.filter(project_id__in=scoped_ids)
    defects = Defect.objects.filter(project_id__in=scoped_ids)
    punch_items = PunchListItem.objects.filter(punch_list__project_id__in=scoped_ids)
    budget = BudgetLine.objects.filter(project_id__in=scoped_ids).aggregate(
        budgeted=Sum("budgeted_amount"),
        committed=Sum("committed_amount"),
        actual=Sum("actual_amount"),
        forecast=Sum("forecast_amount"),
    )
    pending_cos = ChangeOrder.objects.filter(
        project_id__in=scoped_ids, status="pending"
    ).aggregate(total=Sum("amount"))

    task_total = tasks.exclude(status__in=["cancelled"]).count()
    task_done = tasks.filter(status="done").count()
    progress = round((task_done / task_total) * 100) if task_total else 0

    upcoming = list(
        Milestone.objects.filter(
            project_id__in=scoped_ids,
            status__in=["pending", "in_progress"],
            due_date__gte=today,
            due_date__lte=soon,
        )
        .order_by("due_date")[:8]
        .values("name", "due_date", "status", "project__name")
    )

    overdue_tasks = list(
        tasks.exclude(status__in=["done", "cancelled"])
        .filter(due_date__lt=today)
        .order_by("due_date")[:6]
        .values("title", "due_date", "status", "project__name")
    )
    overdue_rfis = list(
        rfis.exclude(status="closed")
        .filter(due_date__lt=today)
        .order_by("due_date")[:6]
        .values("number", "subject", "due_date", "priority", "project__name")
    )

    budgeted = budget["budgeted"] or Decimal("0")
    actual = budget["actual"] or Decimal("0")
    committed = budget["committed"] or Decimal("0")

    return {
        "organization": organization.name,
        "scope": "project" if scope_project else "portfolio",
        "project_count": len(project_ids),
        "project": (
            {
                "id": str(scope_project.id),
                "name": scope_project.name,
                "number": scope_project.number,
                "status": scope_project.status,
                "city": scope_project.city,
                "region": scope_project.region,
                "client_name": scope_project.client_name,
                "contract_value": _money(scope_project.contract_value),
                "currency": scope_project.currency,
                "target_completion_date": (
                    scope_project.target_completion_date.isoformat()
                    if scope_project.target_completion_date
                    else None
                ),
            }
            if scope_project
            else None
        ),
        "projects": list(
            projects.order_by("-created_at")[:12].values("name", "number", "status", "city", "region")
        ),
        "kpis": {
            "budgeted": _money(budgeted),
            "committed": _money(committed),
            "actual": _money(actual),
            "forecast": _money(budget["forecast"]),
            "remaining": _money(budgeted - actual),
            "utilization_pct": round(_money(actual) / _money(budgeted) * 100) if budgeted else 0,
            "pending_change_orders": _money(pending_cos["total"]),
            "open_tasks": tasks.exclude(status__in=["done", "cancelled"]).count(),
            "overdue_tasks": tasks.exclude(status__in=["done", "cancelled"])
            .filter(due_date__lt=today)
            .count(),
            "task_progress_pct": progress,
            "open_rfis": rfis.exclude(status="closed").count(),
            "overdue_rfis": rfis.exclude(status="closed").filter(due_date__lt=today).count(),
            "open_submittals": submittals.exclude(status__in=["approved", "closed"]).count(),
            "safety_incidents_90d": incidents.filter(occurred_at__gte=ninety_days_ago).count(),
            "open_defects": defects.exclude(status__in=["resolved", "verified", "closed"]).count(),
            "open_punch_items": punch_items.exclude(status__in=["completed", "closed"]).count(),
        },
        "upcoming_milestones": [
            {
                "name": item["name"],
                "due_date": item["due_date"].isoformat() if item["due_date"] else None,
                "status": item["status"],
                "project": item["project__name"],
            }
            for item in upcoming
        ],
        "overdue_tasks": [
            {
                "title": item["title"],
                "due_date": item["due_date"].isoformat() if item["due_date"] else None,
                "status": item["status"],
                "project": item["project__name"],
            }
            for item in overdue_tasks
        ],
        "overdue_rfis": [
            {
                "number": item["number"],
                "subject": item["subject"],
                "due_date": item["due_date"].isoformat() if item["due_date"] else None,
                "priority": item["priority"],
                "project": item["project__name"],
            }
            for item in overdue_rfis
        ],
    }


def suggested_prompts(context):
    if context["scope"] == "project":
        return [
            "What are the biggest risks on this project right now?",
            "Summarise the commercial position and change orders.",
            "Which RFIs and tasks are overdue?",
            "What should the site team focus on this week?",
        ]
    return [
        "Give me a portfolio health summary.",
        "Where are we over budget or behind schedule?",
        "What is overdue across all projects?",
        "Draft a daily briefing for the leadership team.",
    ]
