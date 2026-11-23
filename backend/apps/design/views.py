from rest_framework.exceptions import PermissionDenied

from apps.common.viewsets import ProjectScopedViewSet


from .models import CanvasBoard
from .serializers import CanvasBoardSerializer


class CanvasBoardViewSet(ProjectScopedViewSet):
    serializer_class = CanvasBoardSerializer
    filterset_fields = ["project"]
    search_fields = ["name"]
    ordering_fields = ["name", "created_at", "updated_at"]
    ordering = ["-updated_at"]
    action_permissions = {
        "read": ("drawings.view",),
        "create": ("drawings.create",),
        "update": ("drawings.edit",),
        "partial_update": ("drawings.edit",),
        "destroy": ("drawings.edit",),
    }

    def perform_create(self, serializer):
        project = serializer.validated_data.get("project")
        membership = getattr(self.request, "membership", None)
        if project is None or membership is None or project.organization_id != membership.organization_id:
            raise PermissionDenied("Project belongs to another organization.")
        if not self.request.user.can_access_project(project):
            raise PermissionDenied("You do not have access to this project.")
        serializer.save(created_by=self.request.user)
