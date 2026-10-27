"""Inspections, defects, punch lists and safety endpoints."""
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from apps.audit.services import record_audit_event
from apps.common.viewsets import ProjectScopedViewSet

from .models import (
    CorrectiveAction,
    Defect,
    Inspection,
    InspectionItem,
    PunchList,
    PunchListItem,
    SafetyIncident,
)
from .serializers import (
    CorrectiveActionSerializer,
    DefectSerializer,
    InspectionItemSerializer,
    InspectionSerializer,
    InspectionSignoffSerializer,
    PunchListItemSerializer,
    PunchListSerializer,
    SafetyIncidentSerializer,
)


def _pop(validated_data, key):
    return validated_data.pop(key, None)


class InspectionViewSet(ProjectScopedViewSet):
    serializer_class = InspectionSerializer
    filterset_fields = ["project", "status", "inspection_type", "inspector", "scheduled_date"]
    search_fields = ["number", "title", "description", "location"]
    ordering_fields = ["scheduled_date", "created_at", "status"]
    action_permissions = {
        "read": ("quality.view",),
        "create": ("quality.create",),
        "update": ("quality.edit",),
        "partial_update": ("quality.edit",),
        "destroy": ("quality.edit",),
        "write": ("quality.create",),
        "signoff": ("quality.approve",),
    }

    def get_queryset(self):
        return super().get_queryset().select_related(
            "inspector", "signed_off_by", "created_by"
        ).prefetch_related("items")

    def perform_create(self, serializer):
        inspector_id = _pop(serializer.validated_data, "inspector_id")
        inspection = serializer.save(created_by=self.request.user, inspector_id=inspector_id)
        record_audit_event(
            organization=inspection.project.organization,
            actor=self.request.user,
            action="inspection.created",
            target_type="Inspection",
            target_id=inspection.id,
            project=inspection.project,
            request=self.request,
        )

    def perform_update(self, serializer):
        inspector_id = _pop(serializer.validated_data, "inspector_id")
        if inspector_id:
            serializer.save(inspector_id=inspector_id)
        else:
            serializer.save()

    @action(detail=True, methods=["get", "post"], url_path="items")
    def items(self, request, pk=None):
        inspection = self.get_object()
        if request.method == "GET":
            return Response(InspectionItemSerializer(inspection.items.all(), many=True).data)
        serializer = InspectionItemSerializer(data={**request.data, "inspection": str(inspection.id)})
        serializer.is_valid(raise_exception=True)
        item = serializer.save()
        return Response(InspectionItemSerializer(item).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="signoff")
    def signoff(self, request, pk=None):
        inspection = self.get_object()
        serializer = InspectionSignoffSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        inspection.status = serializer.validated_data["status"]
        inspection.signed_off_by = request.user
        inspection.signed_off_at = timezone.now()
        inspection.completed_date = timezone.now().date()
        inspection.save(
            update_fields=["status", "signed_off_by", "signed_off_at", "completed_date", "updated_at"]
        )
        record_audit_event(
            organization=inspection.project.organization,
            actor=request.user,
            action="inspection.signed_off",
            target_type="Inspection",
            target_id=inspection.id,
            project=inspection.project,
            metadata={
                "status": inspection.status,
                "comments": serializer.validated_data.get("comments", ""),
            },
            request=request,
        )
        return Response(InspectionSerializer(inspection).data)


class InspectionItemViewSet(ProjectScopedViewSet):
    serializer_class = InspectionItemSerializer
    filterset_fields = ["inspection", "result"]
    ordering = ["order"]
    org_field = "inspection__project__organization_id"
    project_field = "inspection__project_id"
    action_permissions = {
        "read": ("quality.view",),
        "create": ("quality.create",),
        "update": ("quality.edit",),
        "partial_update": ("quality.edit",),
        "destroy": ("quality.edit",),
    }

    def perform_create(self, serializer):
        inspection = serializer.validated_data.get("inspection")
        if inspection is None or not self.request.user.can_access_project(inspection.project):
            raise PermissionDenied("You do not have access to this inspection's project.")
        serializer.save()


class DefectViewSet(ProjectScopedViewSet):
    serializer_class = DefectSerializer
    filterset_fields = ["project", "inspection", "severity", "status", "assigned_to", "cost_code"]
    search_fields = ["title", "description", "location"]
    ordering_fields = ["created_at", "severity", "status", "due_date"]
    action_permissions = {
        "read": ("quality.view",),
        "create": ("quality.create",),
        "update": ("quality.edit",),
        "partial_update": ("quality.edit",),
        "destroy": ("quality.edit",),
        "write": ("quality.create",),
        "resolve": ("quality.edit",),
    }

    def get_queryset(self):
        return super().get_queryset().select_related("assigned_to", "created_by", "inspection")

    def perform_create(self, serializer):
        assigned_to_id = _pop(serializer.validated_data, "assigned_to_id")
        serializer.save(created_by=self.request.user, assigned_to_id=assigned_to_id)

    def perform_update(self, serializer):
        assigned_to_id = _pop(serializer.validated_data, "assigned_to_id")
        if assigned_to_id:
            serializer.save(assigned_to_id=assigned_to_id)
        else:
            serializer.save()

    @action(detail=True, methods=["post"], url_path="resolve")
    def resolve(self, request, pk=None):
        defect = self.get_object()
        defect.status = "resolved"
        defect.resolved_at = timezone.now()
        defect.save(update_fields=["status", "resolved_at", "updated_at"])
        return Response(DefectSerializer(defect).data)


class PunchListListViewSet(ProjectScopedViewSet):
    serializer_class = PunchListSerializer
    filterset_fields = ["project", "status", "assigned_to"]
    search_fields = ["name", "description"]
    ordering_fields = ["created_at", "target_date", "status"]
    action_permissions = {
        "read": ("quality.view",),
        "create": ("quality.create",),
        "update": ("quality.edit",),
        "partial_update": ("quality.edit",),
        "destroy": ("quality.edit",),
        "write": ("quality.create",),
    }

    def get_queryset(self):
        return super().get_queryset().select_related("assigned_to", "created_by").prefetch_related("items")

    def perform_create(self, serializer):
        assigned_to_id = _pop(serializer.validated_data, "assigned_to_id")
        serializer.save(created_by=self.request.user, assigned_to_id=assigned_to_id)

    def perform_update(self, serializer):
        assigned_to_id = _pop(serializer.validated_data, "assigned_to_id")
        if assigned_to_id:
            serializer.save(assigned_to_id=assigned_to_id)
        else:
            serializer.save()

    @action(detail=True, methods=["get", "post"], url_path="items")
    def items(self, request, pk=None):
        punch_list = self.get_object()
        if request.method == "GET":
            return Response(PunchListItemSerializer(punch_list.items.all(), many=True).data)
        serializer = PunchListItemSerializer(data={**request.data, "punch_list": str(punch_list.id)})
        serializer.is_valid(raise_exception=True)
        assigned_to_id = _pop(serializer.validated_data, "assigned_to_id")
        item = serializer.save(assigned_to_id=assigned_to_id)
        return Response(PunchListItemSerializer(item).data, status=status.HTTP_201_CREATED)


class PunchListItemViewSet(ProjectScopedViewSet):
    serializer_class = PunchListItemSerializer
    filterset_fields = ["punch_list", "status", "assigned_to", "trade"]
    search_fields = ["description", "location", "trade"]
    ordering = ["created_at"]
    org_field = "punch_list__project__organization_id"
    project_field = "punch_list__project_id"
    action_permissions = {
        "read": ("quality.view",),
        "create": ("quality.create",),
        "update": ("quality.edit",),
        "partial_update": ("quality.edit",),
        "destroy": ("quality.edit",),
        "close": ("quality.edit",),
    }

    def perform_create(self, serializer):
        punch_list = serializer.validated_data.get("punch_list")
        if punch_list is None or not self.request.user.can_access_project(punch_list.project):
            raise PermissionDenied("You do not have access to this punch list's project.")
        assigned_to_id = _pop(serializer.validated_data, "assigned_to_id")
        serializer.save(assigned_to_id=assigned_to_id)

    def perform_update(self, serializer):
        assigned_to_id = _pop(serializer.validated_data, "assigned_to_id")
        if assigned_to_id:
            serializer.save(assigned_to_id=assigned_to_id)
        else:
            serializer.save()

    @action(detail=True, methods=["post"], url_path="close")
    def close(self, request, pk=None):
        item = self.get_object()
        item.status = "closed"
        item.closed_at = timezone.now()
        item.save(update_fields=["status", "closed_at", "updated_at"])
        return Response(PunchListItemSerializer(item).data)


class SafetyIncidentViewSet(ProjectScopedViewSet):
    serializer_class = SafetyIncidentSerializer
    filterset_fields = ["project", "severity", "status", "osha_recordable"]
    search_fields = ["number", "title", "description", "location", "root_cause"]
    ordering_fields = ["occurred_at", "created_at", "severity"]
    ordering = ["-occurred_at"]
    action_permissions = {
        "read": ("quality.view",),
        "create": ("quality.create",),
        "update": ("quality.edit",),
        "partial_update": ("quality.edit",),
        "destroy": ("quality.edit",),
        "write": ("quality.create",),
        "close": ("quality.approve",),
    }

    def get_queryset(self):
        return super().get_queryset().select_related("reported_by", "created_by")

    def perform_create(self, serializer):
        reported_by_id = _pop(serializer.validated_data, "reported_by_id")
        incident = serializer.save(created_by=self.request.user, reported_by_id=reported_by_id)
        record_audit_event(
            organization=incident.project.organization,
            actor=self.request.user,
            action="safety_incident.created",
            target_type="SafetyIncident",
            target_id=incident.id,
            project=incident.project,
            metadata={"severity": incident.severity},
            request=self.request,
        )

    def perform_update(self, serializer):
        reported_by_id = _pop(serializer.validated_data, "reported_by_id")
        if reported_by_id:
            serializer.save(reported_by_id=reported_by_id)
        else:
            serializer.save()

    @action(detail=True, methods=["post"], url_path="close")
    def close(self, request, pk=None):
        incident = self.get_object()
        incident.status = "closed"
        incident.save(update_fields=["status", "updated_at"])
        return Response(SafetyIncidentSerializer(incident).data)


class CorrectiveActionViewSet(ProjectScopedViewSet):
    serializer_class = CorrectiveActionSerializer
    filterset_fields = ["project", "incident", "inspection", "status", "assigned_to"]
    search_fields = ["title", "description"]
    ordering_fields = ["created_at", "due_date", "status"]
    action_permissions = {
        "read": ("quality.view",),
        "create": ("quality.create",),
        "update": ("quality.edit",),
        "partial_update": ("quality.edit",),
        "destroy": ("quality.edit",),
        "write": ("quality.create",),
        "complete": ("quality.edit",),
        "verify": ("quality.approve",),
    }

    def get_queryset(self):
        return super().get_queryset().select_related(
            "assigned_to", "verified_by", "created_by", "incident", "inspection"
        )

    def perform_create(self, serializer):
        assigned_to_id = _pop(serializer.validated_data, "assigned_to_id")
        serializer.save(created_by=self.request.user, assigned_to_id=assigned_to_id)

    def perform_update(self, serializer):
        assigned_to_id = _pop(serializer.validated_data, "assigned_to_id")
        if assigned_to_id:
            serializer.save(assigned_to_id=assigned_to_id)
        else:
            serializer.save()

    @action(detail=True, methods=["post"], url_path="complete")
    def complete(self, request, pk=None):
        action = self.get_object()
        action.status = "completed"
        action.completed_at = timezone.now()
        action.save(update_fields=["status", "completed_at", "updated_at"])
        return Response(CorrectiveActionSerializer(action).data)

    @action(detail=True, methods=["post"], url_path="verify")
    def verify(self, request, pk=None):
        action = self.get_object()
        action.status = "verified"
        action.verified_by = request.user
        action.verified_at = timezone.now()
        action.save(update_fields=["status", "verified_by", "verified_at", "updated_at"])
        return Response(CorrectiveActionSerializer(action).data)
