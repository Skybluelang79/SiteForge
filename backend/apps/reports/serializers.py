"""Reporting serializers."""
from rest_framework import serializers

from apps.accounts.serializers import UserSummarySerializer

from .models import Dashboard, ExportJob, MetricSnapshot, ReportDefinition


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


class MetricSnapshotSerializer(serializers.ModelSerializer):
    class Meta:
        model = MetricSnapshot
        fields = [
            "id", "organization", "project", "metric_key", "captured_at", "value",
            "metadata", "created_at", "updated_at",
        ]
        read_only_fields = fields
