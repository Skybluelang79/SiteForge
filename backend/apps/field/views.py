"""Daily logs, labour, equipment, weather, photos and observations."""
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from apps.audit.services import record_audit_event
from apps.common.viewsets import ProjectScopedViewSet

from .models import DailyLog, EquipmentEntry, FieldPhoto, LabourEntry, Observation, WeatherRecord
from .serializers import (
    DailyLogSerializer,
    EquipmentEntrySerializer,
    FieldPhotoSerializer,
    LabourEntrySerializer,
    ObservationSerializer,
    WeatherRecordSerializer,
)


class DailyLogViewSet(ProjectScopedViewSet):
    serializer_class = DailyLogSerializer
    filterset_fields = ["project", "status", "log_date"]
    search_fields = ["work_activities", "delays", "safety_notes", "visitors"]
    ordering_fields = ["log_date", "created_at"]
    ordering = ["-log_date"]
    action_permissions = {
        "read": ("field.view",),
        "create": ("field.create",),
        "update": ("field.edit",),
        "partial_update": ("field.edit",),
        "destroy": ("field.edit",),
        "approve": ("field.approve",),
        "reject": ("field.approve",),
    }

    def get_queryset(self):
        return super().get_queryset().select_related("created_by", "approved_by").prefetch_related(
            "labour_entries", "equipment_entries"
        )

    def perform_create(self, serializer):
        log = serializer.save(created_by=self.request.user)
        record_audit_event(
            organization=log.project.organization,
            actor=self.request.user,
            action="daily_log.created",
            target_type="DailyLog",
            target_id=log.id,
            project=log.project,
            request=self.request,
        )

    @action(detail=True, methods=["post"], url_path="submit")
    def submit(self, request, pk=None):
        log = self.get_object()
        if log.status not in {"draft", "rejected"}:
            return Response({"detail": "Only draft or rejected logs can be submitted."}, status=400)
        log.status = "submitted"
        log.save(update_fields=["status", "updated_at"])
        return Response(DailyLogSerializer(log).data)

    @action(detail=True, methods=["post"], url_path="approve")
    def approve(self, request, pk=None):
        log = self.get_object()
        log.status = "approved"
        log.approved_by = request.user
        log.approved_at = timezone.now()
        log.save(update_fields=["status", "approved_by", "approved_at", "updated_at"])
        record_audit_event(
            organization=log.project.organization,
            actor=request.user,
            action="daily_log.approved",
            target_type="DailyLog",
            target_id=log.id,
            project=log.project,
            request=request,
        )
        return Response(DailyLogSerializer(log).data)

    @action(detail=True, methods=["post"], url_path="reject")
    def reject(self, request, pk=None):
        log = self.get_object()
        log.status = "rejected"
        log.approved_by = request.user
        log.approved_at = timezone.now()
        log.save(update_fields=["status", "approved_by", "approved_at", "updated_at"])
        return Response(DailyLogSerializer(log).data)


class _DailyLogChildViewSet(ProjectScopedViewSet):
    org_field = "daily_log__project__organization_id"
    project_field = "daily_log__project_id"
    parent_field = "daily_log"

    def perform_create(self, serializer):
        parent = serializer.validated_data.get(self.parent_field)
        if parent is None or not self.request.user.can_access_project(parent.project):
            raise PermissionDenied("You do not have access to this daily log's project.")
        serializer.save()


class LabourEntryViewSet(_DailyLogChildViewSet):
    serializer_class = LabourEntrySerializer
    filterset_fields = ["daily_log", "trade", "company"]
    search_fields = ["trade", "company", "notes"]
    ordering = ["trade"]
    action_permissions = {
        "read": ("field.view",),
        "create": ("field.create",),
        "update": ("field.edit",),
        "partial_update": ("field.edit",),
        "destroy": ("field.edit",),
    }


class EquipmentEntryViewSet(_DailyLogChildViewSet):
    serializer_class = EquipmentEntrySerializer
    filterset_fields = ["daily_log", "equipment_name"]
    search_fields = ["equipment_name", "equipment_code", "owner", "notes"]
    ordering = ["equipment_name"]
    action_permissions = {
        "read": ("field.view",),
        "create": ("field.create",),
        "update": ("field.edit",),
        "partial_update": ("field.edit",),
        "destroy": ("field.edit",),
    }


class WeatherRecordViewSet(ProjectScopedViewSet):
    serializer_class = WeatherRecordSerializer
    filterset_fields = ["project", "source", "record_date"]
    ordering_fields = ["record_date", "created_at"]
    ordering = ["-record_date"]
    action_permissions = {
        "read": ("field.view",),
        "create": ("field.create",),
        "update": ("field.edit",),
        "partial_update": ("field.edit",),
        "destroy": ("field.edit",),
        "write": ("field.create",),
    }


class FieldPhotoViewSet(ProjectScopedViewSet):
    serializer_class = FieldPhotoSerializer
    filterset_fields = ["project", "daily_log"]
    search_fields = ["caption", "tags"]
    ordering_fields = ["created_at", "taken_at"]
    action_permissions = {
        "read": ("field.view",),
        "create": ("field.create",),
        "update": ("field.edit",),
        "partial_update": ("field.edit",),
        "destroy": ("field.edit",),
        "write": ("field.create",),
    }

    def perform_create(self, serializer):
        project = serializer.validated_data["project"]
        if not self.request.user.can_access_project(project):
            raise PermissionDenied("You do not have access to this project.")
        photo = serializer.save(uploaded_by=self.request.user)
        record_audit_event(
            organization=project.organization,
            actor=self.request.user,
            action="field_photo.uploaded",
            target_type="FieldPhoto",
            target_id=photo.id,
            project=project,
            request=self.request,
        )


class ObservationViewSet(ProjectScopedViewSet):
    serializer_class = ObservationSerializer
    filterset_fields = ["project", "status", "observation_type", "assigned_to", "daily_log"]
    search_fields = ["title", "description", "location"]
    ordering_fields = ["created_at", "due_date", "status"]
    action_permissions = {
        "read": ("field.view",),
        "create": ("field.create",),
        "update": ("field.edit",),
        "partial_update": ("field.edit",),
        "destroy": ("field.edit",),
        "write": ("field.create",),
        "close": ("field.edit",),
    }

    def get_queryset(self):
        return super().get_queryset().select_related("assigned_to", "created_by", "daily_log")

    def perform_create(self, serializer):
        assigned_to_id = serializer.validated_data.pop("assigned_to_id", None)
        observation = serializer.save(
            created_by=self.request.user,
            assigned_to_id=assigned_to_id,
        )
        record_audit_event(
            organization=observation.project.organization,
            actor=self.request.user,
            action="observation.created",
            target_type="Observation",
            target_id=observation.id,
            project=observation.project,
            request=self.request,
        )

    def perform_update(self, serializer):
        assigned_to_id = serializer.validated_data.pop("assigned_to_id", None)
        if assigned_to_id:
            serializer.save(assigned_to_id=assigned_to_id)
        else:
            serializer.save()

    @action(detail=True, methods=["post"], url_path="close")
    def close(self, request, pk=None):
        observation = self.get_object()
        observation.status = "closed"
        observation.closed_at = timezone.now()
        observation.save(update_fields=["status", "closed_at", "updated_at"])
        return Response(ObservationSerializer(observation).data, status=status.HTTP_200_OK)
