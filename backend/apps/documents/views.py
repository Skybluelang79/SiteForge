"""Document library, folder and version endpoints."""
from django.http import FileResponse
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound
from rest_framework.response import Response

from apps.audit.services import record_audit_event
from apps.common.viewsets import ProjectScopedViewSet
from apps.notifications.services import notify_project_members

from .models import Document, DocumentFolder, DocumentVersion
from .serializers import (
    DocumentFolderSerializer,
    DocumentSerializer,
    DocumentVersionSerializer,
    DocumentVersionSummarySerializer,
    DocumentVersionUploadSerializer,
)
from .services import add_version, log_access


class DocumentFolderViewSet(ProjectScopedViewSet):
    serializer_class = DocumentFolderSerializer
    filterset_fields = ["project", "parent"]
    search_fields = ["name", "path"]
    ordering_fields = ["name", "created_at"]
    ordering = ["name"]
    action_permissions = {
        "read": ("documents.view",),
        "create": ("documents.create",),
        "update": ("documents.edit",),
        "partial_update": ("documents.edit",),
        "destroy": ("documents.delete",),
    }

    def perform_create(self, serializer):
        project = serializer.validated_data["project"]
        if not self.request.user.can_access_project(project):
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied("You do not have access to this project.")
        parent = serializer.validated_data.get("parent")
        name = serializer.validated_data["name"]
        path = f"{parent.path}/{name}" if parent and parent.path else name
        serializer.save(created_by=self.request.user, path=path)


class DocumentViewSet(ProjectScopedViewSet):
    serializer_class = DocumentSerializer
    filterset_fields = ["project", "folder", "status", "document_type", "confidentiality"]
    search_fields = ["title", "description", "document_type", "tags"]
    ordering_fields = ["created_at", "title", "status", "document_type"]
    action_permissions = {
        "read": ("documents.view",),
        "create": ("documents.create",),
        "update": ("documents.edit",),
        "partial_update": ("documents.edit",),
        "destroy": ("documents.delete",),
        "write": ("documents.create",),
    }

    def get_queryset(self):
        return super().get_queryset().select_related(
            "folder", "created_by", "reviewed_by", "current_version", "current_version__uploaded_by"
        )

    def perform_create(self, serializer):
        document = serializer.save(created_by=self.request.user)
        record_audit_event(
            organization=document.project.organization,
            actor=self.request.user,
            action="document.created",
            target_type="Document",
            target_id=document.id,
            project=document.project,
            request=self.request,
        )

    @action(detail=True, methods=["get", "post"], url_path="versions")
    def versions(self, request, pk=None):
        document = self.get_object()
        if request.method == "GET":
            versions = document.versions.select_related("uploaded_by")
            return Response(DocumentVersionSerializer(versions, many=True).data)

        upload = DocumentVersionUploadSerializer(data=request.data)
        upload.is_valid(raise_exception=True)
        version = add_version(
            document=document,
            uploaded_file=upload.validated_data["file"],
            uploaded_by=request.user,
            change_note=upload.validated_data.get("change_note", ""),
            content_type=getattr(upload.validated_data["file"], "content_type", ""),
        )
        record_audit_event(
            organization=document.project.organization,
            actor=request.user,
            action="document.version.created",
            target_type="DocumentVersion",
            target_id=version.id,
            project=document.project,
            request=request,
        )
        notify_project_members(
            project=document.project,
            verb="document.version.created",
            title=f"New version: {document.title}",
            body=f"Version {version.version_number} was uploaded.",
            target_type="Document",
            target_id=document.id,
            exclude_user=request.user,
        )
        return Response(DocumentVersionSummarySerializer(version).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"], url_path="download")
    def download(self, request, pk=None):
        document = self.get_object()
        version = document.current_version
        if version is None or not version.file:
            raise NotFound("This document has no file.")
        try:
            handle = version.file.open("rb")
        except FileNotFoundError:
            raise NotFound("The stored file is missing.")
        log_access(document=document, version=version, user=request.user, request=request)
        filename = version.original_filename or version.file.name.rsplit("/", 1)[-1]
        return FileResponse(
            handle,
            as_attachment=True,
            filename=filename,
            content_type=version.content_type or "application/octet-stream",
        )

    @action(detail=True, methods=["get"], url_path="access-logs")
    def access_logs(self, request, pk=None):
        document = self.get_object()
        from .serializers import DocumentAccessLogSerializer

        logs = document.access_logs.select_related("user", "version")[:200]
        return Response(DocumentAccessLogSerializer(logs, many=True).data)


class DocumentVersionViewSet(ProjectScopedViewSet):
    serializer_class = DocumentVersionSerializer
    http_method_names = ["get", "head", "options", "delete"]
    filterset_fields = ["document", "is_current"]
    search_fields = ["original_filename", "change_note"]
    ordering_fields = ["version_number", "created_at"]
    ordering = ["-version_number"]
    org_field = "document__project__organization_id"
    project_field = "document__project_id"
    action_permissions = {
        "read": ("documents.view",),
        "destroy": ("documents.delete",),
    }

    def get_queryset(self):
        return super().get_queryset().select_related("document", "uploaded_by")
