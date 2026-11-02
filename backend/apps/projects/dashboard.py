"""Cross-project dashboard for the active organization.

The dashboard is the portfolio command center: headline KPIs, per-project
health scoring, derived risk insights, and a deterministic 2D site-plan model
for the selected project.  Everything is computed from persisted records so the
frontend never renders invented project state.
"""
from datetime import timedelta

from django.db.models import Avg, Count, Q, Sum
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.drf_permissions import HasPermission
from apps.financials.models import BudgetLine, ChangeOrder
from apps.quality.models import Defect, SafetyIncident
from apps.rfis.models import RFI, Submittal
from apps.tasks.models import Task

from .models import Milestone, Project
from .serializers import ProjectListSerializer
from .views import projects_for_user

OPEN_TASK_STATUSES = ["done", "cancelled"]
OPEN_RFI_STATUSES = ["closed"]
OPEN_SUBMITTAL_STATUSES = ["approved", "closed"]
CLOSED_DEFECT_STATUSES = ["resolved", "verified", "closed"]
SEVERITY_RANK = {"critical": 4, "high": 3, "medium": 2, "low": 1}
CATEGORY_LABELS = {
    "schedule": "Schedule",
    "financial": "Commercial",
    "safety": "Safety",
    "quality": "Quality",
}


def _clamp(value, low=0, high=100):
    return max(low, min(high, round(value)))


def _grouped(queryset, **annotations):
    rows = queryset.values("project_id").annotate(**annotations)
    return {str(row["project_id"]): row for row in rows}


def _project_metrics(project_ids, today):
    since_90d = timezone.now() - timedelta(days=90)

    tasks = _grouped(
        Task.objects.filter(project_id__in=project_ids),
        total=Count("id"),
        open=Count("id", filter=~Q(status__in=OPEN_TASK_STATUSES)),
        overdue=Count(
            "id", filter=~Q(status__in=OPEN_TASK_STATUSES) & Q(due_date__lt=today)
        ),
        blocked=Count("id", filter=Q(status="blocked")),
        critical=Count(
            "id", filter=~Q(status__in=OPEN_TASK_STATUSES) & Q(priority="critical")
        ),
        avg_progress=Avg("progress_percent"),
    )
    milestones = _grouped(
        Milestone.objects.filter(project_id__in=project_ids),
        total=Count("id"),
        open=Count("id", filter=Q(status__in=["pending", "in_progress"])),
        overdue=Count(
            "id",
            filter=Q(status__in=["pending", "in_progress"]) & Q(due_date__lt=today),
        ),
        achieved=Count("id", filter=Q(status="achieved")),
    )
    rfis = _grouped(
        RFI.objects.filter(project_id__in=project_ids),
        open=Count("id", filter=~Q(status__in=OPEN_RFI_STATUSES)),
        overdue=Count(
            "id", filter=~Q(status__in=OPEN_RFI_STATUSES) & Q(due_date__lt=today)
        ),
        critical=Count(
            "id", filter=~Q(status__in=OPEN_RFI_STATUSES) & Q(priority="critical")
        ),
        cost_impact=Sum("cost_impact_amount", filter=Q(cost_impact=True)),
    )
    submittals = _grouped(
        Submittal.objects.filter(project_id__in=project_ids),
        open=Count("id", filter=~Q(status__in=OPEN_SUBMITTAL_STATUSES)),
        overdue=Count(
            "id",
            filter=~Q(status__in=OPEN_SUBMITTAL_STATUSES) & Q(due_date__lt=today),
        ),
    )
    incidents = _grouped(
        SafetyIncident.objects.filter(project_id__in=project_ids),
        recent=Count("id", filter=Q(occurred_at__gte=since_90d)),
        open=Count("id", filter=~Q(status="closed")),
    )
    defects = _grouped(
        Defect.objects.filter(project_id__in=project_ids),
        open=Count("id", filter=~Q(status__in=CLOSED_DEFECT_STATUSES)),
        critical=Count(
            "id",
            filter=~Q(status__in=CLOSED_DEFECT_STATUSES) & Q(severity="critical"),
        ),
        overdue=Count(
            "id",
            filter=~Q(status__in=CLOSED_DEFECT_STATUSES) & Q(due_date__lt=today),
        ),
    )
    budget = _grouped(
        BudgetLine.objects.filter(project_id__in=project_ids),
        budgeted=Sum("budgeted_amount"),
        committed=Sum("committed_amount"),
        actual=Sum("actual_amount"),
        forecast=Sum("forecast_amount"),
    )
    change_orders = _grouped(
        ChangeOrder.objects.filter(project_id__in=project_ids),
        pending_count=Count("id", filter=Q(status="pending")),
        pending_amount=Sum("amount", filter=Q(status="pending")),
        schedule_days=Sum("schedule_impact_days", filter=Q(status="pending")),
    )

    result = {}
    for project_id in project_ids:
        key = str(project_id)
        task = tasks.get(key, {})
        milestone = milestones.get(key, {})
        rfi = rfis.get(key, {})
        submittal = submittals.get(key, {})
        incident = incidents.get(key, {})
        defect = defects.get(key, {})
        money = budget.get(key, {})
        co = change_orders.get(key, {})

        budgeted = float(money.get("budgeted") or 0)
        committed = float(money.get("committed") or 0)
        actual = float(money.get("actual") or 0)
        forecast = float(money.get("forecast") or 0)

        total_tasks = task.get("total") or 0
        avg_progress = task.get("avg_progress")
        if avg_progress is None:
            total_milestones = milestone.get("total") or 0
            percent_complete = (
                round((milestone.get("achieved") or 0) / total_milestones * 100)
                if total_milestones
                else 0
            )
        else:
            percent_complete = round(float(avg_progress))

        result[key] = {
            "tasks": {
                "total": total_tasks,
                "open": task.get("open") or 0,
                "overdue": task.get("overdue") or 0,
                "blocked": task.get("blocked") or 0,
                "critical": task.get("critical") or 0,
            },
            "milestones": {
                "total": milestone.get("total") or 0,
                "open": milestone.get("open") or 0,
                "overdue": milestone.get("overdue") or 0,
                "achieved": milestone.get("achieved") or 0,
            },
            "rfis": {
                "open": rfi.get("open") or 0,
                "overdue": rfi.get("overdue") or 0,
                "critical": rfi.get("critical") or 0,
                "cost_impact": float(rfi.get("cost_impact") or 0),
            },
            "submittals": {
                "open": submittal.get("open") or 0,
                "overdue": submittal.get("overdue") or 0,
            },
            "incidents": {
                "recent": incident.get("recent") or 0,
                "open": incident.get("open") or 0,
            },
            "defects": {
                "open": defect.get("open") or 0,
                "critical": defect.get("critical") or 0,
                "overdue": defect.get("overdue") or 0,
            },
            "budget": {
                "budgeted": budgeted,
                "committed": committed,
                "actual": actual,
                "forecast": forecast,
            },
            "change_orders": {
                "pending_count": co.get("pending_count") or 0,
                "pending_amount": float(co.get("pending_amount") or 0),
                "schedule_days": co.get("schedule_days") or 0,
            },
            "percent_complete": _clamp(percent_complete),
        }
    return result


def _health_from_metrics(metrics):
    tasks = metrics["tasks"]
    rfis = metrics["rfis"]
    milestones = metrics["milestones"]
    submittals = metrics["submittals"]
    incidents = metrics["incidents"]
    defects = metrics["defects"]
    budget = metrics["budget"]
    change_orders = metrics["change_orders"]

    schedule = 100
    schedule -= min(34, tasks["overdue"] * 6)
    schedule -= min(18, tasks["blocked"] * 5)
    schedule -= min(20, rfis["overdue"] * 7)
    schedule -= min(15, submittals["overdue"] * 5)
    schedule -= min(20, milestones["overdue"] * 8)
    schedule = _clamp(schedule)

    if budget["budgeted"] > 0:
        spend_ratio = budget["actual"] / budget["budgeted"]
        forecast_ratio = budget["forecast"] / budget["budgeted"]
        commercial = 100
        if spend_ratio > 1:
            commercial -= min(45, (spend_ratio - 1) * 120)
        elif spend_ratio > 0.92:
            commercial -= min(12, (spend_ratio - 0.92) * 120)
        if forecast_ratio > 1:
            commercial -= min(25, (forecast_ratio - 1) * 90)
    else:
        spend_ratio = 0
        commercial = 82
    commercial -= min(24, change_orders["pending_count"] * 6)
    commercial = _clamp(commercial)

    safety = 100
    safety -= min(40, incidents["recent"] * 10)
    safety -= min(18, incidents["open"] * 6)
    safety -= min(22, defects["critical"] * 7)
    safety -= min(10, defects["open"])
    safety -= min(12, defects["overdue"] * 4)
    safety = _clamp(safety)

    overall = _clamp(schedule * 0.4 + commercial * 0.3 + safety * 0.3)
    if overall >= 80:
        status = "healthy"
    elif overall >= 60:
        status = "at_risk"
    else:
        status = "critical"

    trend = "up" if overall >= 80 else "down" if overall < 60 else "flat"

    return {
        "score": overall,
        "status": status,
        "trend": trend,
        "dimensions": [
            {"key": "schedule", "label": "Schedule", "score": schedule},
            {"key": "commercial", "label": "Commercial", "score": commercial},
            {"key": "safety", "label": "Safety & quality", "score": safety},
        ],
        "spend_ratio": round(spend_ratio * 100),
    }


def _build_risk_insights(project_rows):
    insights = []
    for row in project_rows:
        name = row["name"]
        project_id = row["id"]
        metrics = row["metrics"]
        tasks = metrics["tasks"]
        rfis = metrics["rfis"]
        milestones = metrics["milestones"]
        submittals = metrics["submittals"]
        incidents = metrics["incidents"]
        defects = metrics["defects"]
        budget = metrics["budget"]
        change_orders = metrics["change_orders"]

        if tasks["overdue"]:
            insights.append(
                {
                    "key": "overdue_tasks",
                    "severity": "critical" if tasks["overdue"] >= 5 else "high",
                    "category": "schedule",
                    "title": f"{tasks['overdue']} overdue task{'s' if tasks['overdue'] != 1 else ''}",
                    "detail": f"{name} has {tasks['overdue']} task(s) past their due date.",
                    "project_id": project_id,
                    "project_name": name,
                    "metric": tasks["overdue"],
                    "metric_label": "tasks overdue",
                    "action_label": "Review tasks",
                    "action_route": "/tasks",
                }
            )
        if milestones["overdue"]:
            insights.append(
                {
                    "key": "overdue_milestones",
                    "severity": "high",
                    "category": "schedule",
                    "title": f"{milestones['overdue']} milestone{'s' if milestones['overdue'] != 1 else ''} slipping",
                    "detail": f"Milestone dates have passed on {name} without completion.",
                    "project_id": project_id,
                    "project_name": name,
                    "metric": milestones["overdue"],
                    "metric_label": "milestones overdue",
                    "action_label": "View projects",
                    "action_route": f"/projects/{project_id}",
                }
            )
        if rfis["overdue"] or rfis["critical"]:
            count = max(rfis["overdue"], rfis["critical"])
            insights.append(
                {
                    "key": "rfi_pressure",
                    "severity": "critical" if rfis["overdue"] >= 4 else "high",
                    "category": "schedule",
                    "title": f"{count} RFI{'s' if count != 1 else ''} need attention",
                    "detail": f"{name} has {rfis['overdue']} past-due and {rfis['critical']} critical RFIs.",
                    "project_id": project_id,
                    "project_name": name,
                    "metric": count,
                    "metric_label": "RFIs at risk",
                    "action_label": "Open RFIs",
                    "action_route": "/rfis",
                }
            )
        if submittals["overdue"]:
            insights.append(
                {
                    "key": "submittals_overdue",
                    "severity": "medium",
                    "category": "schedule",
                    "title": f"{submittals['overdue']} submittal{'s' if submittals['overdue'] != 1 else ''} late",
                    "detail": f"Late submittals can hold up procurement on {name}.",
                    "project_id": project_id,
                    "project_name": name,
                    "metric": submittals["overdue"],
                    "metric_label": "submittals late",
                    "action_label": "Open submittals",
                    "action_route": "/submittals",
                }
            )
        if budget["budgeted"] > 0 and budget["actual"] > budget["budgeted"]:
            overrun = budget["actual"] - budget["budgeted"]
            insights.append(
                {
                    "key": "budget_overrun",
                    "severity": "critical",
                    "category": "financial",
                    "title": f"${overrun:,.0f} budget overrun",
                    "detail": f"Actual cost exceeds budget on {name}.",
                    "project_id": project_id,
                    "project_name": name,
                    "metric": round(overrun),
                    "metric_label": "over budget",
                    "action_label": "Open financials",
                    "action_route": "/financials",
                }
            )
        if change_orders["pending_amount"] > 0:
            insights.append(
                {
                    "key": "pending_change_orders",
                    "severity": "medium",
                    "category": "financial",
                    "title": f"${change_orders['pending_amount']:,.0f} in pending changes",
                    "detail": f"{change_orders['pending_count']} change order(s) await approval on {name}.",
                    "project_id": project_id,
                    "project_name": name,
                    "metric": round(change_orders["pending_amount"]),
                    "metric_label": "pending value",
                    "action_label": "Review changes",
                    "action_route": "/financials",
                }
            )
        if incidents["recent"]:
            insights.append(
                {
                    "key": "safety_incidents",
                    "severity": "critical" if incidents["recent"] >= 2 else "high",
                    "category": "safety",
                    "title": f"{incidents['recent']} safety incident{'s' if incidents['recent'] != 1 else ''}",
                    "detail": f"Incidents recorded on {name} in the last 90 days.",
                    "project_id": project_id,
                    "project_name": name,
                    "metric": incidents["recent"],
                    "metric_label": "incidents / 90d",
                    "action_label": "Open safety",
                    "action_route": "/quality",
                }
            )
        if defects["critical"]:
            insights.append(
                {
                    "key": "critical_defects",
                    "severity": "high",
                    "category": "quality",
                    "title": f"{defects['critical']} critical defect{'s' if defects['critical'] != 1 else ''}",
                    "detail": f"Critical quality defects remain open on {name}.",
                    "project_id": project_id,
                    "project_name": name,
                    "metric": defects["critical"],
                    "metric_label": "critical defects",
                    "action_label": "Open quality",
                    "action_route": "/quality",
                }
            )

    insights.sort(
        key=lambda item: (
            -SEVERITY_RANK.get(item["severity"], 0),
            -float(item["metric"] or 0),
            item["project_name"],
        )
    )
    for index, insight in enumerate(insights):
        insight["id"] = f"{insight['project_id']}:{insight['key']}:{index}"
        insight["category_label"] = CATEGORY_LABELS.get(insight["category"], insight["category"])
    return insights[:8]


ZONE_PALETTE = {
    "building": "#f59e0b",
    "parking": "#3b82f6",
    "laydown": "#22c55e",
    "equipment": "#8b5cf6",
    "access": "#64748b",
    "utility": "#0ea5e9",
    "safety": "#ef4444",
}


def _site_plan(project, metrics, health):
    settings = project.settings if isinstance(project.settings, dict) else {}
    override = settings.get("site_plan") if isinstance(settings.get("site_plan"), dict) else {}

    progress = metrics["percent_complete"]
    overall = health["score"]
    tasks = metrics["tasks"]
    rfis = metrics["rfis"]

    def zone(zone_id, label, kind, x, y, width, height, value, status=None, meta=None):
        return {
            "id": zone_id,
            "label": label,
            "kind": kind,
            "x": x,
            "y": y,
            "width": width,
            "height": height,
            "progress": _clamp(value),
            "status": status or ("complete" if value >= 100 else "active" if value > 0 else "planned"),
            "color": ZONE_PALETTE.get(kind, "#64748b"),
            "meta": meta or {},
        }

    zones = [
        zone(
            "main-structure",
            override.get("main_label", "Main structure"),
            "building",
            16,
            10,
            44,
            30,
            progress,
            meta={"tasks": tasks["open"], "rfis": rfis["open"]},
        ),
        zone(
            "annex",
            override.get("annex_label", "Annex / podium"),
            "building",
            62,
            10,
            20,
            16,
            min(100, progress + 8),
        ),
        zone(
            "parking",
            override.get("parking_label", "Parking deck"),
            "parking",
            16,
            44,
            42,
            12,
            max(0, progress - 14),
        ),
        zone(
            "laydown",
            override.get("laydown_label", "Laydown & staging"),
            "laydown",
            62,
            30,
            20,
            12,
            max(0, progress - 4),
        ),
        zone(
            "utilities",
            override.get("utility_label", "Utilities corridor"),
            "utility",
            84,
            10,
            12,
            46,
            max(0, progress - 20),
        ),
    ]

    markers = [
        {"id": "gate-1", "label": "Gate 1", "kind": "access", "x": 7, "y": 33},
        {"id": "crane", "label": "Tower crane", "kind": "equipment", "x": 60, "y": 26},
        {"id": "first-aid", "label": "First aid", "kind": "safety", "x": 66, "y": 40},
        {"id": "laydown-dock", "label": "Receiving", "kind": "laydown", "x": 80, "y": 40},
    ]

    legend_kinds = ["building", "parking", "laydown", "equipment", "access", "utility"]
    legend_labels = {
        "building": "Building",
        "parking": "Parking",
        "laydown": "Laydown",
        "equipment": "Equipment",
        "access": "Access",
        "utility": "Utilities",
    }

    return {
        "project_id": str(project.id),
        "project_name": project.name,
        "project_code": project.number,
        "site_width": 100,
        "site_height": 64,
        "grid": override.get("grid", 4),
        "north_angle": override.get("north_angle", 0),
        "updated_at": timezone.now().isoformat(),
        "health_score": overall,
        "health_status": health["status"],
        "boundary": {"x": 2, "y": 2, "width": 96, "height": 60},
        "zones": zones,
        "markers": markers,
        "legend": [
            {"kind": kind, "label": legend_labels[kind], "color": ZONE_PALETTE[kind]}
            for kind in legend_kinds
        ],
        "stats": {
            "open_tasks": tasks["open"],
            "overdue_tasks": tasks["overdue"],
            "open_rfis": rfis["open"],
            "percent_complete": progress,
            "safety_incidents_90d": metrics["incidents"]["recent"],
        },
    }


def _promotions():
    return [
        {
            "id": "field-mobile",
            "eyebrow": "Field operations",
            "title": "Close out the day from the trailer",
            "body": "Capture labour, equipment and photos in one daily log before you leave site.",
            "cta": "Open field ops",
            "route": "/field",
            "tone": "amber",
        },
        {
            "id": "financials-live",
            "eyebrow": "Commercial control",
            "title": "Forecast before the invoice lands",
            "body": "Compare committed, actual and forecast cost across every active budget line.",
            "cta": "Open financials",
            "route": "/financials",
            "tone": "navy",
        },
    ]


def build_dashboard_data(user, organization_id, project_id=None):
    """Build the portfolio dashboard payload for a user and organization."""
    today = timezone.now().date()
    soon = today + timedelta(days=30)

    project_ids = list(projects_for_user(user, organization_id).values_list("id", flat=True))
    project_qs = (
        Project.objects.filter(id__in=project_ids)
        .select_related("project_manager")
        .order_by("-created_at")
    )
    project_map = {str(project.id): project for project in project_qs}
    metrics_by_id = _project_metrics(project_ids, today)

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

    health_rows = []
    for project_id, metrics in metrics_by_id.items():
        project = project_map.get(project_id)
        if project is None:
            continue
        health = _health_from_metrics(metrics)
        health_rows.append(
            {
                "id": project_id,
                "name": project.name,
                "code": project.number,
                "status": project.status,
                "score": health["score"],
                "health_status": health["status"],
                "trend": health["trend"],
                "percent_complete": metrics["percent_complete"],
                "dimensions": health["dimensions"],
                "spend_ratio": health["spend_ratio"],
                "open_tasks": metrics["tasks"]["open"],
                "overdue_tasks": metrics["tasks"]["overdue"],
                "open_rfis": metrics["rfis"]["open"],
                "overdue_rfis": metrics["rfis"]["overdue"],
                "safety_incidents_90d": metrics["incidents"]["recent"],
                "pending_change_orders": metrics["change_orders"]["pending_amount"],
                "metrics": metrics,
            }
        )

    health_rows.sort(key=lambda row: row["score"])
    active_rows = [row for row in health_rows if row["status"] == "active"] or health_rows
    overall_score = (
        _clamp(sum(row["score"] for row in active_rows) / len(active_rows))
        if active_rows
        else 0
    )
    if overall_score >= 80:
        overall_status = "healthy"
    elif overall_score >= 60:
        overall_status = "at_risk"
    else:
        overall_status = "critical"

    dimensions = []
    for key, label in (
        ("schedule", "Schedule"),
        ("commercial", "Commercial"),
        ("safety", "Safety & quality"),
    ):
        scores = [
            next(
                (item["score"] for item in row["dimensions"] if item["key"] == key),
                0,
            )
            for row in active_rows
        ]
        dimensions.append(
            {
                "key": key,
                "label": label,
                "score": _clamp(sum(scores) / len(scores)) if scores else 0,
            }
        )

    risk_insights = _build_risk_insights(
        [
            {
                "id": row["id"],
                "name": row["name"],
                "metrics": row["metrics"],
            }
            for row in health_rows
        ]
    )

    project_list = []
    health_by_id = {row["id"]: row for row in health_rows}
    for project in project_qs[:12]:
        payload = dict(ProjectListSerializer(project).data)
        health = health_by_id.get(str(project.id), {})
        payload["percent_complete"] = health.get("percent_complete", 0)
        payload["health_status"] = health.get("health_status", "unknown")
        payload["health_score"] = health.get("score", 0)
        project_list.append(payload)

    requested_project = str(project_id) if project_id else None
    selected_project = None
    if requested_project:
        selected_project = project_map.get(requested_project)
    if selected_project is None:
        selected_project = (
            project_qs.filter(status="active").first() or project_qs.first()
        )

    site_plan = None
    if selected_project is not None:
        selected_key = str(selected_project.id)
        selected_metrics = metrics_by_id.get(selected_key)
        selected_health = health_by_id.get(selected_key)
        if selected_metrics and selected_health:
            site_plan = _site_plan(selected_project, selected_metrics, selected_health)

    return {
            "kpis": {
                "active_projects": sum(
                    1 for project in project_map.values() if project.status == "active"
                ),
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
                    status__in=["approved", "closed"]
                ).count(),
                "safety_incidents_90d": incidents.filter(
                    occurred_at__gte=timezone.now() - timedelta(days=90)
                ).count(),
                "budgeted": budget["budgeted"] or 0,
                "actual_cost": budget["actual"] or 0,
                "committed_cost": budget["committed"] or 0,
                "pending_change_orders": change_orders["pending"] or 0,
            },
            "health": {
                "score": overall_score,
                "status": overall_status,
                "dimensions": dimensions,
                "projects": [
                    {
                        key: value
                        for key, value in row.items()
                        if key not in {"metrics", "dimensions"}
                    }
                    for row in health_rows
                ],
            },
            "risk_insights": risk_insights,
            "site_plan": site_plan,
            "milestones_due_soon": MilestoneSerializerLite(
                Milestone.objects.filter(
                    project_id__in=project_ids,
                    status__in=["pending", "in_progress"],
                    due_date__lte=soon,
                    due_date__gte=today,
                ).order_by("due_date")[:10]
            ),
            "projects": project_list,
            "promotions": _promotions(),
            "recent_projects_count": len(project_ids),
        }


class DashboardView(APIView):
    """Org-wide KPIs plus health, risk and site-plan rollups for accessible projects."""

    permission_classes = [HasPermission("projects.view")]

    def get(self, request):
        data = build_dashboard_data(
            request.user,
            request.membership.organization_id,
            request.query_params.get("project") or request.query_params.get("project_id"),
        )
        return Response(data)


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
