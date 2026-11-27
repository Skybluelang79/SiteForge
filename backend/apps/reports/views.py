"""Reports, dashboards, export jobs and metric snapshots."""
from django.db.models import Q
from django.http import FileResponse, Http404
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from apps.common.viewsets import OrgScopedViewSet

from .models import Dashboard, ExportJob, MetricSnapshot, ReportDefinition
from .serializers import (
    DashboardSerializer,
    ExportJobSerializer,
    MetricSnapshotSerializer,
    ReportDefinitionSerializer,
)
from .services import enqueue_export


def visible_report_definitions(queryset, request):
    membership = getattr(request, "membership", None)
    if membership is None:
        return queryset.none()
    if membership.is_org_admin:
        return queryset
    return queryset.filter(
        Q(visibility="organization")
        | Q(visibility="private", created_by=request.user)
        | Q(visibility="project", project__is_public=True)
        | Q(
            visibility="project",
            project__members__user=request.user,
            project__members__is_active=True,
        )
    ).distinct()


class ReportDefinitionViewSet(OrgScopedViewSet):
    serializer_class = ReportDefinitionSerializer
    filterset_fields = ["project", "report_type", "visibility", "created_by"]
    search_fields = ["name", "description"]
    ordering_fields = ["name", "created_at"]
    ordering = ["name"]
    action_permissions = {
        "read": ("reports.view",),
        "create": ("reports.create",),
        "update": ("reports.create",),
        "partial_update": ("reports.create",),
        "destroy": ("reports.create",),
    }

    def get_queryset(self):
        queryset = super().get_queryset().select_related("project", "created_by")
        return visible_report_definitions(queryset, self.request)

    def perform_create(self, serializer):
        serializer.save(
            organization=self.request.membership.organization,
            created_by=self.request.user,
        )


class DashboardViewSet(OrgScopedViewSet):
    serializer_class = DashboardSerializer
    filterset_fields = ["project", "is_default", "shared_with_org", "created_by"]
    search_fields = ["name"]
    ordering = ["name"]
    action_permissions = {
        "read": ("reports.view",),
        "create": ("reports.create",),
        "update": ("reports.create",),
        "partial_update": ("reports.create",),
        "destroy": ("reports.create",),
    }

    def get_queryset(self):
        queryset = super().get_queryset().select_related("project", "created_by")
        membership = getattr(self.request, "membership", None)
        if membership is None or membership.is_org_admin:
            return queryset
        return queryset.filter(
            Q(shared_with_org=True)
            | Q(created_by=self.request.user)
            | Q(
                project__members__user=self.request.user,
                project__members__is_active=True,
            )
        ).distinct()

    def perform_create(self, serializer):
        serializer.save(
            organization=self.request.membership.organization,
            created_by=self.request.user,
        )


class ExportJobViewSet(OrgScopedViewSet):
    serializer_class = ExportJobSerializer
    filterset_fields = ["project", "status", "export_type", "export_format", "report_definition"]
    ordering = ["-created_at"]
    http_method_names = ["get", "post", "delete", "head", "options"]
    action_permissions = {
        "read": ("reports.view",),
        "create": ("reports.export",),
        "destroy": ("reports.export",),
        "download": ("reports.view",),
    }

    def get_queryset(self):
        queryset = super().get_queryset().select_related(
            "project", "report_definition", "requested_by"
        )
        membership = getattr(self.request, "membership", None)
        if membership is None:
            return queryset.none()
        if membership.is_org_admin:
            return queryset
        user = self.request.user
        report_visible = (
            Q(report_definition__visibility="organization")
            | Q(report_definition__visibility="private", report_definition__created_by=user)
            | Q(report_definition__visibility="project", report_definition__project__is_public=True)
            | Q(
                report_definition__visibility="project",
                report_definition__project__members__user=user,
                report_definition__project__members__is_active=True,
            )
        )
        project_access = (
            Q(project__isnull=True)
            | Q(project__is_public=True)
            | Q(project__members__user=user, project__members__is_active=True)
        )
        return queryset.filter(
            Q(requested_by=user)
            | (Q(report_definition__isnull=False) & report_visible & project_access)
        ).distinct()

    def perform_create(self, serializer):
        membership = self.request.membership
        job = serializer.save(
            organization=membership.organization,
            requested_by=self.request.user,
        )
        enqueue_export(job)

    def perform_destroy(self, instance):
        membership = getattr(self.request, "membership", None)
        if (
            membership is not None
            and not membership.is_org_admin
            and instance.requested_by_id != self.request.user.id
        ):
            raise PermissionDenied("You can only delete your own exports.")
        super().perform_destroy(instance)

    @action(detail=True, methods=["get"], url_path="download")
    def download(self, request, pk=None):
        job = self.get_object()
        if not job.file or job.status != "completed":
            raise Http404("Export is not ready.")
        return FileResponse(job.file.open("rb"), as_attachment=True, filename=job.file.name.split("/")[-1])


class MetricSnapshotViewSet(OrgScopedViewSet):
    serializer_class = MetricSnapshotSerializer
    filterset_fields = ["project", "metric_key"]
    ordering = ["-captured_at"]
    http_method_names = ["get", "head", "options"]
    action_permissions = {"read": ("reports.view",)}

    def get_queryset(self):
        return super().get_queryset().select_related("project")

    @action(detail=False, methods=["get"], url_path="series")
    def series(self, request):
        queryset = self.get_queryset()
        metric_key = request.query_params.get("metric_key")
        if metric_key:
            queryset = queryset.filter(metric_key=metric_key)
        project_id = request.query_params.get("project")
        if project_id:
            queryset = queryset.filter(project_id=project_id)
        data = list(
            queryset.order_by("captured_at").values(
                "metric_key", "captured_at", "value", "project_id"
            )
        )
        return Response(data)
