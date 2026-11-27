"""Reporting serializers."""
from uuid import UUID

from rest_framework import serializers

from apps.accounts.serializers import UserSummarySerializer
from apps.projects.models import Project

from .models import Dashboard, ExportJob, MetricSnapshot, ReportDefinition
from .services import SUPPORTED_EXPORTS, SUPPORTED_FORMATS


class ReportDefinitionSerializer(serializers.ModelSerializer):
    created_by = UserSummarySerializer(read_only=True)

    class Meta:
        model = ReportDefinition
        fields = [
            "id", "organization", "project", "name", "report_type", "description",
            "parameters", "visibility", "created_by", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "organization", "created_by", "created_at", "updated_at"]

    def validate(self, attrs):
        organization = self.context["request"].membership.organization
        project = attrs.get("project") or getattr(self.instance, "project", None)
        if project is not None:
            if project.organization_id != organization.id:
                raise serializers.ValidationError({"project": "Project belongs to another organization."})
            if not self.context["request"].user.can_access_project(project):
                raise serializers.ValidationError({"project": "You do not have access to this project."})
        return attrs


class DashboardSerializer(serializers.ModelSerializer):
    created_by = UserSummarySerializer(read_only=True)

    class Meta:
        model = Dashboard
        fields = [
            "id", "organization", "project", "name", "layout", "is_default",
            "shared_with_org", "created_by", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "organization", "created_by", "created_at", "updated_at"]

    def validate(self, attrs):
        organization = self.context["request"].membership.organization
        project = attrs.get("project") or getattr(self.instance, "project", None)
        if project is not None:
            if project.organization_id != organization.id:
                raise serializers.ValidationError({"project": "Project belongs to another organization."})
            if not self.context["request"].user.can_access_project(project):
                raise serializers.ValidationError({"project": "You do not have access to this project."})
        return attrs


class ExportJobSerializer(serializers.ModelSerializer):
    requested_by = UserSummarySerializer(read_only=True)

    class Meta:
        model = ExportJob
        fields = [
            "id", "organization", "project", "report_definition", "export_type",
            "export_format", "status", "parameters", "file", "row_count", "error_message",
            "completed_at", "requested_by", "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "organization", "status", "file", "row_count", "error_message",
            "completed_at", "requested_by", "created_at", "updated_at",
        ]

    def validate_export_type(self, value):
        if value not in SUPPORTED_EXPORTS:
            raise serializers.ValidationError("Unsupported export type.")
        return value

    def validate_export_format(self, value):
        if value not in SUPPORTED_FORMATS:
            raise serializers.ValidationError("Unsupported export format.")
        return value

    def validate(self, attrs):
        attrs = super().validate(attrs)
        request = self.context["request"]
        membership = getattr(request, "membership", None)
        if membership is None:
            raise serializers.ValidationError("No active organization selected.")

        project = attrs.get("project") or getattr(self.instance, "project", None)
        if project is not None:
            self._validate_project(project, "project")

        report = attrs.get("report_definition") or getattr(self.instance, "report_definition", None)
        if report is not None:
            if report.organization_id != membership.organization_id:
                raise serializers.ValidationError({"report_definition": "Report belongs to another organization."})
            if not self._can_view_report(report):
                raise serializers.ValidationError({"report_definition": "You do not have access to this report."})

        parameters = attrs.get("parameters", getattr(self.instance, "parameters", None) or {})
        if not isinstance(parameters, dict):
            raise serializers.ValidationError({"parameters": "Must be an object."})
        project_id = parameters.get("project_id")
        if project_id:
            try:
                UUID(str(project_id))
            except (TypeError, ValueError):
                parameter_project = None
            else:
                parameter_project = Project.objects.filter(
                    pk=project_id, organization=membership.organization, deleted_at__isnull=True
                ).first()
            if parameter_project is None:
                raise serializers.ValidationError({"parameters": "Project belongs to another organization."})
            self._validate_project(parameter_project, "parameters")
        elif (
            not membership.is_org_admin
            and project is None
            and (report is None or report.project_id is None)
        ):
            raise serializers.ValidationError("Select a project to export.")

        return attrs

    def _validate_project(self, project, field):
        request = self.context["request"]
        membership = getattr(request, "membership", None)
        if membership is None or project.organization_id != membership.organization_id:
            raise serializers.ValidationError({field: "Project belongs to another organization."})
        if not request.user.can_access_project(project):
            raise serializers.ValidationError({field: "You do not have access to this project."})

    def _can_view_report(self, report):
        request = self.context["request"]
        membership = getattr(request, "membership", None)
        if membership is None:
            return False
        if membership.is_org_admin:
            return True
        user = request.user
        if report.visibility == "private":
            return report.created_by_id == user.id
        if report.visibility == "organization":
            return True
        if report.visibility != "project" or report.project_id is None:
            return False
        return report.project.is_public or report.project.members.filter(
            user=user, is_active=True
        ).exists()


class MetricSnapshotSerializer(serializers.ModelSerializer):
    class Meta:
        model = MetricSnapshot
        fields = [
            "id", "organization", "project", "metric_key", "captured_at", "value",
            "metadata", "created_at", "updated_at",
        ]
        read_only_fields = fields
