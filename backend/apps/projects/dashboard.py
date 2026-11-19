"""Cross-project dashboard for the active organization.

The dashboard is the portfolio command centre: KPI rollups, a weighted project
health score, prioritised risk signals and the data required to draw a 2D site
plan of every project in the active organization.
"""
from datetime import timedelta

from django.db.models import Count, Q, Sum
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.drf_permissions import HasPermission
from apps.financials.models import BudgetLine, ChangeOrder
from apps.quality.models import Defect, PunchListItem, SafetyIncident
from apps.rfis.models import RFI, Submittal
from apps.tasks.models import Task

from .models import Milestone, Project
from .serializers import ProjectListSerializer
from .views import projects_for_user

OPEN_TASK_STATUSES = ["done", "cancelled"]
OPEN_DEFECT_STATUSES = ["resolved", "verified", "closed"]
OPEN_PUNCH_STATUSES = ["completed", "closed"]
CLOSED_SUBMITTAL_STATUSES = ["approved", "closed"]


def _risk_level(score: int) -> str:
    if score >= 80:
        return "healthy"
    if score >= 65:
        return "watch"
    if score >= 45:
        return "at_risk"
    return "critical"


def _percent(part, total) -> int:
    total = float(total or 0)
    if not total:
        return 0
    return max(0, min(100, round(float(part or 0) / total * 100)))


def _grouped(queryset, field: str, **annotations):
    return {
        row[field]: row
        for row in queryset.values(field).annotate(**annotations)
    }


def _project_rollups(project_ids, today):
    """Grouped operational counts, one query per module."""
    tasks = _grouped(
        Task.objects.filter(project_id__in=project_ids),
        "project_id",
        total=Count("id"),
        done=Count("id", filter=Q(status="done")),
        open=Count("id", filter=~Q(status__in=OPEN_TASK_STATUSES)),
        overdue=Count(
            "id",
            filter=Q(due_date__lt=today) & ~Q(status__in=OPEN_TASK_STATUSES),
        ),
    )
    rfis = _grouped(
        RFI.objects.filter(project_id__in=project_ids),
        "project_id",
        open=Count("id", filter=~Q(status="closed")),
        overdue=Count("id", filter=Q(due_date__lt=today) & ~Q(status="closed")),
    )
    submittals = _grouped(
        Submittal.objects.filter(project_id__in=project_ids),
        "project_id",
        open=Count("id", filter=~Q(status__in=CLOSED_SUBMITTAL_STATUSES)),
    )
    defects = _grouped(
        Defect.objects.filter(project_id__in=project_ids),
        "project_id",
        open=Count("id", filter=~Q(status__in=OPEN_DEFECT_STATUSES)),
        critical=Count(
            "id",
            filter=Q(severity="critical") & ~Q(status__in=OPEN_DEFECT_STATUSES),
        ),
    )
    punch = _grouped(
        PunchListItem.objects.filter(punch_list__project_id__in=project_ids),
        "punch_list__project_id",
        open=Count("id", filter=~Q(status__in=OPEN_PUNCH_STATUSES)),
    )
    budgets = _grouped(
        BudgetLine.objects.filter(project_id__in=project_ids),
        "project_id",
        budgeted=Sum("budgeted_amount"),
        committed=Sum("committed_amount"),
        actual=Sum("actual_amount"),
    )
    change_orders = _grouped(
        ChangeOrder.objects.filter(project_id__in=project_ids),
        "project_id",
        pending=Sum("amount", filter=Q(status="pending")),
    )
    milestones = _grouped(
        Milestone.objects.filter(project_id__in=project_ids),
        "project_id",
        open=Count("id", filter=Q(status__in=["pending", "in_progress"])),
        overdue=Count(
            "id",
            filter=Q(status__in=["pending", "in_progress"]) & Q(due_date__lt=today),
        ),
    )
    incidents = _grouped(
        SafetyIncident.objects.filter(
            project_id__in=project_ids,
            occurred_at__gte=timezone.now() - timedelta(days=90),
        ),
        "project_id",
        total=Count("id"),
    )
    return {
        "tasks": tasks,
        "rfis": rfis,
        "submittals": submittals,
        "defects": defects,
        "punch": punch,
        "budgets": budgets,
        "change_orders": change_orders,
        "milestones": milestones,
        "incidents": incidents,
    }


def _project_health(project, rollups, today):
    key = project.id
    tasks = rollups["tasks"].get(key, {})
    rfis = rollups["rfis"].get(key, {})
    submittals = rollups["submittals"].get(key, {})
    defects = rollups["defects"].get(key, {})
    punch = rollups["punch"].get(key, {})
    budget = rollups["budgets"].get(key, {})
    change_orders = rollups["change_orders"].get(key, {})
    milestones = rollups["milestones"].get(key, {})
    incidents = rollups["incidents"].get(key, {})

    open_tasks = tasks.get("open") or 0
    overdue_tasks = tasks.get("overdue") or 0
    open_rfis = rfis.get("open") or 0
    overdue_rfis = rfis.get("overdue") or 0
    open_defects = defects.get("open") or 0
    critical_defects = defects.get("critical") or 0
    open_punch = punch.get("open") or 0
    overdue_milestones = milestones.get("overdue") or 0

    budgeted = budget.get("budgeted") or 0
    actual = budget.get("actual") or 0
    utilization = _percent(actual, budgeted)
    pending_change_orders = change_orders.get("pending") or 0

    progress = _percent(tasks.get("done") or 0, tasks.get("total") or 0)
    overdue_items = overdue_tasks + overdue_rfis + critical_defects + overdue_milestones
    open_items = open_tasks + open_rfis + open_defects + open_punch

    score = 100
    score -= min(30, overdue_tasks * 3)
    score -= min(25, overdue_rfis * 4)
    score -= min(18, critical_defects * 6)
    score -= min(12, open_defects // 3)
    score -= min(10, overdue_milestones * 5)
    if utilization > 95:
        score -= min(15, (utilization - 95) * 2)
    if project.is_overdue:
        score -= 15
    score = max(0, min(100, score))

    return {
        "id": str(project.id),
        "name": project.name,
        "number": project.number,
        "status": project.status,
        "project_type": project.project_type,
        "city": project.city,
        "region": project.region,
        "currency": project.currency,
        "contract_value": float(project.contract_value or 0),
        "target_completion_date": (
            project.target_completion_date.isoformat()
            if project.target_completion_date
            else None
        ),
        "percent_complete": progress,
        "risk_score": score,
        "risk_level": _risk_level(score),
        "open_items": open_items,
        "overdue_items": overdue_items,
        "tasks": {
            "open": open_tasks,
            "overdue": overdue_tasks,
        },
        "rfis": {
            "open": open_rfis,
            "overdue": overdue_rfis,
        },
        "submittals": {"open": submittals.get("open") or 0},
        "defects": {
            "open": open_defects,
            "critical": critical_defects,
        },
        "punch_items": {"open": open_punch},
        "milestones": {
            "open": milestones.get("open") or 0,
            "overdue": overdue_milestones,
        },
        "safety_incidents_90d": incidents.get("total") or 0,
        "budget": {
            "budgeted": float(budgeted or 0),
            "committed": float(budget.get("committed") or 0),
            "actual": float(actual or 0),
            "utilization_pct": utilization,
            "pending_change_orders": float(pending_change_orders or 0),
        },
    }


def _risk_signals(project_health):
    signals = []
    for item in project_health:
        if item["tasks"]["overdue"]:
            signals.append(
                {
                    "project_id": item["id"],
                    "project": item["name"],
                    "title": f"{item['tasks']['overdue']} overdue task"
                    f"{'s' if item['tasks']['overdue'] != 1 else ''}",
                    "detail": "Work items past their planned finish date.",
                    "category": "Delivery",
                    "severity": "high" if item["tasks"]["overdue"] >= 3 else "medium",
                    "weight": 20 + item["tasks"]["overdue"] * 2,
                }
            )
        if item["rfis"]["overdue"]:
            signals.append(
                {
                    "project_id": item["id"],
                    "project": item["name"],
                    "title": f"{item['rfis']['overdue']} overdue RFI"
                    f"{'s' if item['rfis']['overdue'] != 1 else ''}",
                    "detail": "Requests for information awaiting a response.",
                    "category": "Information",
                    "severity": "high" if item["rfis"]["overdue"] >= 2 else "medium",
                    "weight": 24 + item["rfis"]["overdue"] * 3,
                }
            )
        if item["defects"]["critical"]:
            signals.append(
                {
                    "project_id": item["id"],
                    "project": item["name"],
                    "title": f"{item['defects']['critical']} critical defect"
                    f"{'s' if item['defects']['critical'] != 1 else ''}",
                    "detail": "Critical quality defects still open.",
                    "category": "Quality",
                    "severity": "critical",
                    "weight": 30 + item["defects"]["critical"] * 4,
                }
            )
        if item["milestones"]["overdue"]:
            signals.append(
                {
                    "project_id": item["id"],
                    "project": item["name"],
                    "title": f"{item['milestones']['overdue']} milestone"
                    f"{'s' if item['milestones']['overdue'] != 1 else ''} overdue",
                    "detail": "Milestones past their planned date.",
                    "category": "Schedule",
                    "severity": "high",
                    "weight": 26 + item["milestones"]["overdue"] * 3,
                }
            )
        if item["budget"]["utilization_pct"] >= 95 and item["budget"]["budgeted"]:
            signals.append(
                {
                    "project_id": item["id"],
                    "project": item["name"],
                    "title": f"Budget utilisation at {item['budget']['utilization_pct']}%",
                    "detail": "Actual cost is close to or above the approved budget.",
                    "category": "Commercial",
                    "severity": "high",
                    "weight": 22,
                }
            )
    signals.sort(key=lambda signal: signal["weight"], reverse=True)
    return signals


def _risk_insights(signals, project_health):
    insights = []
    for signal in signals:
        category = signal.get("category", "").lower()
        insights.append({**signal, "category": category})
    for item in project_health:
        if item["tasks"]["overdue"] and not any(
            i.get("project_id") == item["id"] and i.get("category") == "schedule" for i in insights
        ):
            insights.append(
                {
                    "project_id": item["id"],
                    "project": item["name"],
                    "title": f"{item['tasks']['overdue']} overdue task"
                    f"{'s' if item['tasks']['overdue'] != 1 else ''}",
                    "detail": "Schedule impact from overdue work.",
                    "category": "schedule",
                    "severity": "high" if item["tasks"]["overdue"] >= 3 else "medium",
                }
            )
    return insights


def _legacy_site_plan(project):
    if not project:
        return None
    return {
        "project_id": project["id"],
        "name": project["name"],
        "zones": [
            {
                "id": "main-structure",
                "name": "Main structure",
                "status": project.get("risk_level", "healthy"),
                "meta": {
                    "tasks": project.get("tasks", {}).get("open", 0),
                    "overdue": project.get("overdue_items", 0),
                    "progress": project.get("percent_complete", 0),
                },
            }
        ],
    }


def _promotions(project_health):
    items = []
    for project in project_health[:3]:
        if project.get("overdue_items"):
            items.append(
                {
                    "project_id": project["id"],
                    "title": f"Review {project['name']} risks",
                    "detail": f"{project['overdue_items']} overdue item(s) need attention.",
                }
            )
    if not items and project_health:
        items.append(
            {
                "project_id": project_health[0]["id"],
                "title": "Portfolio on track",
                "detail": "No urgent promotions detected.",
            }
        )
    return items


def _health_summary(project_health, signals):
    if not project_health:
        return {
            "score": 100,
            "label": "healthy",
            "headline": "No projects yet. Create a project to start tracking health.",
            "projects_at_risk": 0,
            "signals": [],
            "risks": [],
            "projects": [],
            "counts": {"healthy": 0, "watch": 0, "at_risk": 0, "critical": 0},
        }

    weight_total = sum(max(item["contract_value"], 1) for item in project_health)
    weighted = sum(
        item["risk_score"] * max(item["contract_value"], 1) for item in project_health
    )
    score = round(weighted / weight_total) if weight_total else 0
    counts = {"healthy": 0, "watch": 0, "at_risk": 0, "critical": 0}
    for item in project_health:
        counts[item["risk_level"]] = counts.get(item["risk_level"], 0) + 1

    signals_out = [
        {
            "label": "Overdue tasks",
            "value": sum(item["tasks"]["overdue"] for item in project_health),
            "severity": "high",
            "hint": "Past planned finish",
        },
        {
            "label": "Overdue RFIs",
            "value": sum(item["rfis"]["overdue"] for item in project_health),
            "severity": "high",
            "hint": "Awaiting response",
        },
        {
            "label": "Critical defects",
            "value": sum(item["defects"]["critical"] for item in project_health),
            "severity": "critical",
            "hint": "Open quality exposure",
        },
        {
            "label": "Budget pressure",
            "value": sum(
                1
                for item in project_health
                if item["budget"]["utilization_pct"] >= 95 and item["budget"]["budgeted"]
            ),
            "severity": "medium",
            "hint": "Projects at 95%+ utilisation",
        },
        {
            "label": "Overdue milestones",
            "value": sum(item["milestones"]["overdue"] for item in project_health),
            "severity": "high",
            "hint": "Schedule slippage",
        },
    ]
    signals_out = [signal for signal in signals_out if signal["value"]]
    risks = signals[:6]
    if risks:
        headline = f"{len(signals)} priority signal{'s' if len(signals) != 1 else ''} across {len(project_health)} project{'s' if len(project_health) != 1 else ''}."
    else:
        headline = "Every project is tracking within tolerance."

    return {
        "score": score,
        "label": _risk_level(score),
        "headline": headline,
        "projects_at_risk": counts["at_risk"] + counts["critical"],
        "signals": signals_out,
        "risks": [
            {
                "project_id": signal["project_id"],
                "project": signal["project"],
                "title": signal["title"],
                "detail": signal["detail"],
                "category": signal["category"],
                "severity": signal["severity"],
            }
            for signal in risks
        ],
        "projects": project_health,
        "counts": counts,
    }


class DashboardView(APIView):
    """Org-wide KPIs, health scoring and per-project rollups."""

    permission_classes = [HasPermission("projects.view")]

    def get(self, request):
        membership = request.membership
        org_id = membership.organization_id
        today = timezone.now().date()
        soon = today + timedelta(days=30)

        project_ids = list(projects_for_user(request.user, org_id).values_list("id", flat=True))
        requested_project = request.query_params.get("project")
        accessible_projects = list(
            Project.objects.filter(id__in=project_ids).select_related("project_manager")
        )
        rollups = _project_rollups(project_ids, today)
        health_by_id = {
            str(project.id): _project_health(project, rollups, today)
            for project in accessible_projects
        }
        site_plan = sorted(
            health_by_id.values(),
            key=lambda item: (item["risk_score"], -item["overdue_items"], item["name"].lower()),
        )
        signals = _risk_signals(site_plan)
        scoped_site_plan = site_plan
        if requested_project and requested_project in health_by_id:
            scoped_site_plan = [health_by_id[requested_project]]
            signals = _risk_signals(scoped_site_plan)
        health = _health_summary(scoped_site_plan, signals)
        project_rows = sorted(
            accessible_projects,
            key=lambda project: project.created_at or timezone.now(),
            reverse=True,
        )[:12]
        project_health = [health_by_id[str(project.id)] for project in project_rows]
        risk_insights = _risk_insights(signals, scoped_site_plan)
        legacy_site_plan = _legacy_site_plan(scoped_site_plan[0] if requested_project and scoped_site_plan else None)
        promotions = _promotions(scoped_site_plan)

        tasks = Task.objects.filter(project_id__in=project_ids)
        rfis = RFI.objects.filter(project_id__in=project_ids)
        submittals = Submittal.objects.filter(project_id__in=project_ids)
        incidents = SafetyIncident.objects.filter(project_id__in=project_ids)
        budget = BudgetLine.objects.filter(project_id__in=project_ids).aggregate(
            budgeted=Sum("budgeted_amount"),
            actual=Sum("actual_amount"),
            committed=Sum("committed_amount"),
        )
        change_orders = ChangeOrder.objects.filter(project_id__in=project_ids).aggregate(
            pending=Sum("amount", filter=Q(status="pending"))
        )

        projects = ProjectListSerializer(project_rows, many=True).data
        for project_obj, project in zip(project_rows, projects):
            details = health_by_id.get(str(project_obj.id))
            if details:
                project["percent_complete"] = details["percent_complete"]
                project["risk_level"] = details["risk_level"]
                project["risk_score"] = details["risk_score"]
                project["overdue_items"] = details["overdue_items"]
                project["open_items"] = details["open_items"]
            else:
                project["percent_complete"] = 0
                project["risk_level"] = "healthy"
                project["risk_score"] = 100
                project["overdue_items"] = 0
                project["open_items"] = 0

        return Response(
            {
                "kpis": {
                    "active_projects": Project.objects.filter(
                        id__in=project_ids, status="active"
                    ).count(),
                    "total_projects": len(project_ids),
                    "open_tasks": tasks.exclude(status__in=OPEN_TASK_STATUSES).count(),
                    "overdue_tasks": tasks.exclude(status__in=OPEN_TASK_STATUSES)
                    .filter(due_date__lt=today)
                    .count(),
                    "open_rfis": rfis.exclude(status="closed").count(),
                    "overdue_rfis": rfis.exclude(status="closed")
                    .filter(due_date__lt=today)
                    .count(),
                    "open_submittals": submittals.exclude(
                        status__in=CLOSED_SUBMITTAL_STATUSES
                    ).count(),
                    "safety_incidents_90d": incidents.filter(
                        occurred_at__gte=timezone.now() - timedelta(days=90)
                    ).count(),
                    "budgeted": budget["budgeted"] or 0,
                    "actual_cost": budget["actual"] or 0,
                    "committed_cost": budget["committed"] or 0,
                    "pending_change_orders": change_orders["pending"] or 0,
                },
                "health": health,
                "site_plan": legacy_site_plan if legacy_site_plan is not None else project_health,
                "risk_insights": risk_insights,
                "promotions": promotions,
                "milestones_due_soon": MilestoneSerializerLite(
                    Milestone.objects.filter(
                        project_id__in=project_ids,
                        status__in=["pending", "in_progress"],
                        due_date__lte=soon,
                        due_date__gte=today,
                    ).order_by("due_date")[:8]
                ),
                "projects": projects,
                "recent_projects_count": len(project_ids),
                "generated_at": timezone.now().isoformat(),
            }
        )


def MilestoneSerializerLite(queryset):
    return [
        {
            "id": str(m.id),
            "project": str(m.project_id),
            "name": m.name,
            "due_date": m.due_date,
            "status": m.status,
        }
        for m in queryset.select_related("project")
    ]


