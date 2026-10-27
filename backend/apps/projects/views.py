"""Project views: projects, team, milestones, contracts, activity, dashboard."""
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.utils import timezone
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit.services import record_audit_event
from apps.common.drf_permissions import HasPermission, IsOrganizationMember
from apps.common.viewsets import BaseModelViewSet

from .models import ActivityFeedEntry, Contract, Milestone, Project, ProjectMember
from .serializers import (
    ActivityFeedEntrySerializer,
    ContractSerializer,
    MilestoneSerializer,
    ProjectListSerializer,
    ProjectMemberSerializer,
    ProjectSerializer,
)
from .services import record_activity


def projects_for_user(user, organization_id):
    """All projects the user may access within an organization."""
    membership = user.memberships.filter(organization_id=organization_id, is_active=True).first()
    if membership is None:
        return Project.objects.none()
    qs = Project.objects.filter(organization_id=organization_id, deleted_at__isnull=True)
    if membership.is_org_admin:
        return qs
    return qs.filter(Q(is_public=True) | Q(members__user=user, members__is_active=True)).distinct()


class ProjectViewSet(BaseModelViewSet):
    serializer_class = ProjectSerializer
    filterset_fields = ["status", "project_type", "project_manager", "is_public"]
    search_fields = ["name", "number", "client_name", "city", "description"]
    ordering_fields = ["created_at", "name", "start_date", "target_completion_date", "contract_value"]
    ordering = ["-created_at"]

    def get_queryset(self):
        membership = getattr(self.request, "membership", None)
        if membership is None:
            return Project.objects.none()
        return (
            projects_for_user(self.request.user, membership.organization_id)
            .select_related("project_manager", "organization")
            .annotate(active_member_count=Count("members", filter=Q(members__is_active=True)))
        )

    def get_permissions(self):
        if self.action in {"create"}:
            return [HasPermission("projects.create")()]
        if self.action in {"update", "partial_update", "destroy"}:
            return [HasPermission("projects.edit")()]
        return [HasPermission("projects.view")()]

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        serializer = ProjectListSerializer(page if page is not None else queryset, many=True)
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)

    def perform_create(self, serializer):
        membership = self.request.membership
        with transaction.atomic():
            project = serializer.save(organization=membership.organization)
            ProjectMember.objects.create(
                project=project, user=self.request.user, role_code="owner", is_active=True, added_by=self.request.user
            )
        record_activity(
            project=project, actor=self.request.user, verb="project.created",
            summary=f"created project {project.name}", target_type="Project", target_id=project.id,
        )
        record_audit_event(
            organization=membership.organization, actor=self.request.user, action="project.created",
            target_type="Project", target_id=project.id, project=project, request=self.request,
        )
        return project

    def perform_update(self, serializer):
        project = serializer.save()
        record_activity(
            project=project, actor=self.request.user, verb="project.updated",
            summary=f"updated project {project.name}", target_type="Project", target_id=project.id,
        )
        return project

    def perform_destroy(self, instance):
        instance.deleted_at = timezone.now()
        instance.save(update_fields=["deleted_at"])
        record_audit_event(
            organization=instance.organization, actor=self.request.user, action="project.archived",
            target_type="Project", target_id=instance.id, project=instance, request=self.request,
        )

    @action(detail=True, methods=["get", "post"], url_path="members")
    def members(self, request, pk=None):
        project = self.get_object()
        if request.method == "GET":
            members = project.members.select_related("user").all()
            return Response(ProjectMemberSerializer(members, many=True).data)

        if not request.membership.is_org_admin and not _has_project_perm(request, project, "projects.team.manage"):
            raise PermissionDenied("You cannot manage this project's team.")
        serializer = ProjectMemberSerializer(data={**request.data, "project": str(project.id)})
        serializer.is_valid(raise_exception=True)
        user_id = serializer.validated_data.pop("user_id")
        membership = project.organization.memberships.filter(user_id=user_id, is_active=True).first()
        if membership is None:
            raise ValidationError({"user_id": "That user is not a member of this organization."})
        member, _ = ProjectMember.objects.update_or_create(
            project=project, user_id=user_id,
            defaults={**serializer.validated_data, "added_by": request.user, "is_active": True},
        )
        record_activity(
            project=project, actor=request.user, verb="project.member.added",
            summary=f"added {member.user.full_name} to the team",
            target_type="ProjectMember", target_id=member.id,
        )
        return Response(ProjectMemberSerializer(member).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="members/(?P<member_id>[^/.]+)/remove")
    def remove_member(self, request, pk=None, member_id=None):
        project = self.get_object()
        if not request.membership.is_org_admin and not _has_project_perm(request, project, "projects.team.manage"):
            raise PermissionDenied("You cannot manage this project's team.")
        ProjectMember.objects.filter(project=project, id=member_id).update(is_active=False)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["get"])
    def activity(self, request, pk=None):
        project = self.get_object()
        entries = project.activity_entries.select_related("actor")[:100]
        return Response(ActivityFeedEntrySerializer(entries, many=True).data)

    @action(detail=True, methods=["get"])
    def summary(self, request, pk=None):
        project = self.get_object()
        from apps.financials.models import BudgetLine
        from apps.rfis.models import RFI
        from apps.tasks.models import Task

        budget_total = (
            BudgetLine.objects.filter(project=project).aggregate(total=Sum("budgeted_amount"))["total"]
            or 0
        )
        actual_total = (
            BudgetLine.objects.filter(project=project).aggregate(total=Sum("actual_amount"))["total"] or 0
        )
        return Response(
            {
                "project": ProjectSerializer(project).data,
                "milestones": {
                    "total": project.milestones.count(),
                    "achieved": project.milestones.filter(status="achieved").count(),
                    "overdue": project.milestones.filter(
                        status__in=["pending", "in_progress"], due_date__lt=timezone.now().date()
                    ).count(),
                },
                "tasks": {
                    "total": Task.objects.filter(project=project).count(),
                    "open": Task.objects.filter(project=project).exclude(status="done").count(),
                    "overdue": Task.objects.filter(project=project)
                    .exclude(status="done")
                    .filter(due_date__lt=timezone.now().date())
                    .count(),
                },
                "rfis": {
                    "total": RFI.objects.filter(project=project).count(),
                    "open": RFI.objects.filter(project=project).exclude(status="closed").count(),
                },
                "budget": {"budgeted": budget_total, "actual": actual_total},
                "team_size": project.members.filter(is_active=True).count(),
            }
        )


def _has_project_perm(request, project, key):
    from apps.common.permissions import permissions_for_role

    role = request.user.project_role(project)
    return key in permissions_for_role(role) or key in request.membership.effective_permissions


class MilestoneViewSet(BaseModelViewSet):
    serializer_class = MilestoneSerializer
    permission_classes = [HasPermission("projects.view")]
    filterset_fields = ["status", "project"]
    search_fields = ["name", "description"]
    ordering_fields = ["due_date", "created_at", "status"]
    ordering = ["due_date"]

    def get_queryset(self):
        membership = getattr(self.request, "membership", None)
        if membership is None:
            return Milestone.objects.none()
        return Milestone.objects.filter(project__organization_id=membership.organization_id).select_related(
            "owner", "project"
        )

    def check_project_access(self, project):
        if project.organization_id != self.request.membership.organization_id:
            raise PermissionDenied("Not your organization's project.")
        if not self.request.user.can_access_project(project):
            raise PermissionDenied("You do not have access to this project.")

    def perform_create(self, serializer):
        project = serializer.validated_data["project"]
        self.check_project_access(project)
        milestone = serializer.save()
        record_activity(
            project=project, actor=self.request.user, verb="milestone.created",
            summary=f"created milestone {milestone.name}", target_type="Milestone", target_id=milestone.id,
        )


class ContractViewSet(BaseModelViewSet):
    serializer_class = ContractSerializer
    permission_classes = [HasPermission("financials.view")]
    filterset_fields = ["status", "contract_type", "project"]
    search_fields = ["name", "number", "counterparty"]
    ordering = ["-created_at"]

    def get_queryset(self):
        membership = getattr(self.request, "membership", None)
        if membership is None:
            return Contract.objects.none()
        return Contract.objects.filter(project__organization_id=membership.organization_id).select_related(
            "created_by", "project"
        )

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class GlobalActivityView(mixins.ListModelMixin, viewsets.GenericViewSet):
    serializer_class = ActivityFeedEntrySerializer
    permission_classes = [IsOrganizationMember]

    def get_queryset(self):
        membership = getattr(self.request, "membership", None)
        if membership is None:
            return ActivityFeedEntry.objects.none()
        qs = ActivityFeedEntry.objects.filter(
            organization_id=membership.organization_id
        ).select_related("actor")
        org_id = membership.organization_id
        allowed = projects_for_user(self.request.user, org_id).values_list("id", flat=True)
        return qs.filter(project_id__in=list(allowed))
