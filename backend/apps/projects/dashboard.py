"""Cross-project dashboard for the active organization."""
from datetime import timedelta

from django.db.models import Count, Sum
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.drf_permissions import HasPermission
from apps.financials.models import BudgetLine, ChangeOrder, Invoice
from apps.quality.models import SafetyIncident
from apps.rfis.models import RFI, Submittal
from apps.tasks.models import Task

from .models import Milestone, Project
from .serializers import ProjectListSerializer
from .views import projects_for_user


class DashboardView(APIView):
    """Org-wide KPIs plus per-project rollups for accessible projects."""

    permission_classes = [HasPermission("projects.view")]

    def get(self, request):
        membership = request.membership
        org_id = membership.organization_id
        today = timezone.now().date()
        soon = today + timedelta(days=30)

        project_ids = list(projects_for_user(request.user, org_id).values_list("id", flat=True))

        tasks = Task.objects.filter(project_id__in=project_ids)
        rfis = RFI.objects.filter(project_id__in=project_ids)
        submittals = Submittal.objects.filter(project_id__in=project_ids)
        incidents = SafetyIncident.objects.filter(project_id__in=project_ids)
        budget = BudgetLine.objects.filter(project_id__in=project_ids).aggregate(
            budgeted=Sum("budgeted_amount"), actual=Sum("actual_amount"), committed=Sum("committed_amount")
        )
        change_orders = ChangeOrder.objects.filter(project_id__in=project_ids).aggregate(
            pending=Sum("amount", filter=Q_pending())
        )

        projects = ProjectListSerializer(
            Project.objects.filter(id__in=project_ids).select_related("project_manager")[:12], many=True
        ).data

        return Response(
            {
                "kpis": {
                    "active_projects": Project.objects.filter(
                        id__in=project_ids, status="active"
                    ).count(),
                    "total_projects": len(project_ids),
                    "open_tasks": tasks.exclude(status="done").count(),
                    "overdue_tasks": tasks.exclude(status="done").filter(due_date__lt=today).count(),
                    "open_rfis": rfis.exclude(status="closed").count(),
                    "overdue_rfis": rfis.exclude(status="closed").filter(due_date__lt=today).count(),
                    "open_submittals": submittals.exclude(status__in=["approved", "closed"]).count(),
                    "safety_incidents_90d": incidents.filter(
                        occurred_at__gte=timezone.now() - timedelta(days=90)
                    ).count(),
                    "budgeted": budget["budgeted"] or 0,
                    "actual_cost": budget["actual"] or 0,
                    "committed_cost": budget["committed"] or 0,
                    "pending_change_orders": change_orders["pending"] or 0,
                },
                "milestones_due_soon": MilestoneSerializerLite(
                    Milestone.objects.filter(
                        project_id__in=project_ids, status__in=["pending", "in_progress"],
                        due_date__lte=soon, due_date__gte=today,
                    ).order_by("due_date")[:10]
                ),
                "projects": projects,
                "recent_projects_count": len(project_ids),
            }
        )


def Q_pending():
    from django.db.models import Q

    return Q(status="pending")


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
