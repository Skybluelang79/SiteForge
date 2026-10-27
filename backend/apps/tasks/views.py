"""Task and schedule endpoints."""
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from apps.audit.services import record_audit_event
from apps.common.viewsets import ProjectScopedViewSet

from .models import Task, TaskDependency
from .serializers import TaskDependencySerializer, TaskSerializer


class TaskViewSet(ProjectScopedViewSet):
    serializer_class = TaskSerializer
    filterset_fields = ["project", "status", "priority", "assignee", "milestone", "parent"]
    search_fields = ["title", "description", "tags"]
    ordering_fields = ["due_date", "created_at", "status", "priority", "progress_percent"]
    ordering = ["due_date", "-created_at"]
    action_permissions = {
        "read": ("tasks.view",),
        "create": ("tasks.create",),
        "update": ("tasks.edit",),
        "partial_update": ("tasks.edit",),
        "destroy": ("tasks.delete",),
        "write": ("tasks.create",),
    }

    def get_queryset(self):
        return super().get_queryset().select_related(
            "assignee", "created_by", "milestone", "parent"
        )

    def perform_create(self, serializer):
        assignee_id = serializer.validated_data.pop("assignee_id", None)
        task = serializer.save(created_by=self.request.user, assignee_id=assignee_id)
        self._sync_completion(task)
        record_audit_event(
            organization=task.project.organization,
            actor=self.request.user,
            action="task.created",
            target_type="Task",
            target_id=task.id,
            project=task.project,
            request=self.request,
        )

    def perform_update(self, serializer):
        assignee_id = serializer.validated_data.pop("assignee_id", None)
        task = serializer.save(assignee_id=assignee_id) if assignee_id else serializer.save()
        self._sync_completion(task)

    @staticmethod
    def _sync_completion(task):
        updates = []
        if task.status == "done" and task.completed_at is None:
            task.completed_at = timezone.now()
            updates.append("completed_at")
        if task.status != "done" and task.completed_at is not None:
            task.completed_at = None
            updates.append("completed_at")
        if updates:
            task.save(update_fields=[*updates, "updated_at"])


class TaskDependencyViewSet(ProjectScopedViewSet):
    serializer_class = TaskDependencySerializer
    filterset_fields = ["predecessor", "successor", "dependency_type"]
    ordering = ["created_at"]
    org_field = "successor__project__organization_id"
    project_field = "successor__project_id"
    action_permissions = {
        "read": ("tasks.view",),
        "create": ("tasks.create",),
        "update": ("tasks.edit",),
        "partial_update": ("tasks.edit",),
        "destroy": ("tasks.delete",),
    }

    def get_queryset(self):
        return super().get_queryset().select_related("predecessor", "successor")

    def perform_create(self, serializer):
        successor = serializer.validated_data.get("successor")
        if successor is None or not self.request.user.can_access_project(successor.project):
            raise PermissionDenied("You do not have access to this project.")
        serializer.save()
