"""Task and dependency serializers."""
from rest_framework import serializers

from apps.accounts.serializers import UserSummarySerializer

from .models import Task, TaskDependency


class TaskSerializer(serializers.ModelSerializer):
    assignee = UserSummarySerializer(read_only=True)
    assignee_id = serializers.UUIDField(write_only=True, required=False, allow_null=True)
    created_by = UserSummarySerializer(read_only=True)

    class Meta:
        model = Task
        fields = [
            "id", "project", "parent", "milestone", "title", "description", "status",
            "priority", "assignee", "assignee_id", "start_date", "due_date", "completed_at",
            "progress_percent", "estimated_hours", "actual_hours", "tags", "created_by",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "completed_at", "created_by", "created_at", "updated_at"]

    def validate(self, attrs):
        start = attrs.get("start_date") or getattr(self.instance, "start_date", None)
        due = attrs.get("due_date") or getattr(self.instance, "due_date", None)
        if start and due and due < start:
            raise serializers.ValidationError({"due_date": "Due date cannot be before the start date."})
        progress = attrs.get("progress_percent")
        if progress is not None and progress > 100:
            raise serializers.ValidationError({"progress_percent": "Progress cannot exceed 100%."})
        project = attrs.get("project") or getattr(self.instance, "project", None)
        milestone = attrs.get("milestone") or getattr(self.instance, "milestone", None)
        if project and milestone and milestone.project_id != project.id:
            raise serializers.ValidationError({"milestone": "Milestone belongs to a different project."})
        return attrs


class TaskDependencySerializer(serializers.ModelSerializer):
    class Meta:
        model = TaskDependency
        fields = [
            "id", "predecessor", "successor", "dependency_type", "lag_days",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate(self, attrs):
        predecessor = attrs.get("predecessor") or getattr(self.instance, "predecessor", None)
        successor = attrs.get("successor") or getattr(self.instance, "successor", None)
        if predecessor and successor:
            if predecessor.id == successor.id:
                raise serializers.ValidationError("A task cannot depend on itself.")
            if predecessor.project_id != successor.project_id:
                raise serializers.ValidationError("Tasks must belong to the same project.")
        return attrs
