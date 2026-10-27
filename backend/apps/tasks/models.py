"""Task management, scheduling and dependencies."""
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import models

from apps.common.models import Base

User = get_user_model()


class Task(Base):
    STATUS_CHOICES = [
        ("todo", "To Do"),
        ("in_progress", "In Progress"),
        ("blocked", "Blocked"),
        ("in_review", "In Review"),
        ("done", "Done"),
        ("cancelled", "Cancelled"),
    ]
    PRIORITY_CHOICES = [
        ("low", "Low"),
        ("medium", "Medium"),
        ("high", "High"),
        ("critical", "Critical"),
    ]

    project = models.ForeignKey("projects.Project", on_delete=models.CASCADE, related_name="tasks")
    parent = models.ForeignKey(
        "self", on_delete=models.CASCADE, null=True, blank=True, related_name="subtasks"
    )
    milestone = models.ForeignKey(
        "projects.Milestone", on_delete=models.SET_NULL, null=True, blank=True, related_name="tasks"
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="todo", db_index=True)
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default="medium", db_index=True)
    assignee = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="tasks_assigned"
    )
    start_date = models.DateField(null=True, blank=True)
    due_date = models.DateField(null=True, blank=True, db_index=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    progress_percent = models.PositiveSmallIntegerField(default=0)
    estimated_hours = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    actual_hours = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    tags = models.JSONField(default=list, blank=True)
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="tasks_created"
    )

    class Meta:
        ordering = ["due_date", "-created_at"]
        indexes = [
            models.Index(fields=["project", "status"], name="idx_task_project_status"),
            models.Index(fields=["project", "assignee"], name="idx_task_project_assignee"),
            models.Index(fields=["project", "due_date"], name="idx_task_project_due"),
        ]

    def __str__(self) -> str:  # pragma: no cover
        return self.title

    def clean(self):
        if self.progress_percent > 100:
            raise ValidationError({"progress_percent": "Progress cannot exceed 100%."})
        if self.start_date and self.due_date and self.due_date < self.start_date:
            raise ValidationError({"due_date": "Due date cannot be before the start date."})


class TaskDependency(Base):
    TYPE_CHOICES = [
        ("finish_to_start", "Finish to Start"),
        ("start_to_start", "Start to Start"),
        ("finish_to_finish", "Finish to Finish"),
        ("start_to_finish", "Start to Finish"),
    ]

    predecessor = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="dependents")
    successor = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="dependencies")
    dependency_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default="finish_to_start")
    lag_days = models.IntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["predecessor", "successor"], name="uniq_task_dependency_pair"
            ),
            models.CheckConstraint(
                condition=~models.Q(predecessor=models.F("successor")),
                name="chk_task_dependency_not_self",
            ),
        ]
        indexes = [models.Index(fields=["successor"], name="idx_dep_successor")]

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.predecessor_id} -> {self.successor_id}"

    def clean(self):
        if self.predecessor_id == self.successor_id:
            raise ValidationError("A task cannot depend on itself.")
        if (
            self.predecessor_id
            and self.successor_id
            and self.predecessor.project_id != self.successor.project_id
        ):
            raise ValidationError("Tasks must belong to the same project.")
