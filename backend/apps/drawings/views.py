"""Drawing sets, drawings, revisions and review workflow endpoints."""
from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from apps.audit.services import record_audit_event
from apps.common.viewsets import ProjectScopedViewSet
from apps.notifications.services import notify

from .models import Drawing, DrawingReview, DrawingRevision, DrawingSet
from .serializers import (
    DrawingDecisionSerializer,
    DrawingReviewSerializer,
    DrawingRevisionSerializer,
    DrawingRevisionSummarySerializer,
    DrawingRevisionUploadSerializer,
    DrawingSerializer,
    DrawingSetSerializer,
)
from .services import add_revision


class DrawingSetViewSet(ProjectScopedViewSet):
    serializer_class = DrawingSetSerializer
    filterset_fields = ["project", "discipline"]
    search_fields = ["name", "discipline", "description"]
    ordering_fields = ["name", "discipline", "created_at"]
    ordering = ["discipline", "name"]
    action_permissions = {
        "read": ("drawings.view",),
        "create": ("drawings.create",),
        "update": ("drawings.edit",),
        "partial_update": ("drawings.edit",),
        "destroy": ("drawings.edit",),
    }


class DrawingViewSet(ProjectScopedViewSet):
    serializer_class = DrawingSerializer
    filterset_fields = ["project", "drawing_set", "discipline", "status"]
    search_fields = ["title", "number", "discipline"]
    ordering_fields = ["number", "title", "created_at"]
    ordering = ["number"]
    action_permissions = {
        "read": ("drawings.view",),
        "create": ("drawings.create",),
        "update": ("drawings.edit",),
        "partial_update": ("drawings.edit",),
        "destroy": ("drawings.edit",),
        "write": ("drawings.create",),
    }

    def get_queryset(self):
        return super().get_queryset().select_related(
            "drawing_set", "created_by", "current_revision"
        )

    def perform_create(self, serializer):
        drawing = serializer.save(created_by=self.request.user)
        record_audit_event(
            organization=drawing.project.organization,
            actor=self.request.user,
            action="drawing.created",
            target_type="Drawing",
            target_id=drawing.id,
            project=drawing.project,
            request=self.request,
        )

    @action(detail=True, methods=["get", "post"], url_path="revisions")
    def revisions(self, request, pk=None):
        drawing = self.get_object()
        if request.method == "GET":
            revisions = drawing.revisions.select_related("uploaded_by", "reviewed_by")
            return Response(DrawingRevisionSerializer(revisions, many=True).data)

        if not request.membership.is_org_admin and "drawings.create" not in request.membership.effective_permissions:
            raise ValidationError("You cannot upload revisions.")
        upload = DrawingRevisionUploadSerializer(data=request.data)
        upload.is_valid(raise_exception=True)
        try:
            revision = add_revision(
                drawing=drawing,
                uploaded_file=upload.validated_data["file"],
                revision_code=upload.validated_data["revision_code"],
                revision_date=upload.validated_data["revision_date"],
                change_summary=upload.validated_data.get("change_summary", ""),
                uploaded_by=request.user,
            )
        except Exception as exc:
            if "uniq_revision_drawing_code" in str(exc):
                raise ValidationError({"revision_code": "This revision code already exists."})
            raise
        record_audit_event(
            organization=drawing.project.organization,
            actor=request.user,
            action="drawing.revision.created",
            target_type="DrawingRevision",
            target_id=revision.id,
            project=drawing.project,
            request=request,
        )
        return Response(DrawingRevisionSummarySerializer(revision).data, status=status.HTTP_201_CREATED)


class DrawingRevisionViewSet(ProjectScopedViewSet):
    serializer_class = DrawingRevisionSerializer
    http_method_names = ["get", "head", "options", "delete"]
    filterset_fields = ["drawing", "review_status"]
    search_fields = ["revision_code", "change_summary", "original_filename"]
    ordering_fields = ["revision_date", "created_at", "review_status"]
    ordering = ["-revision_date", "-created_at"]
    org_field = "drawing__project__organization_id"
    project_field = "drawing__project_id"
    action_permissions = {
        "read": ("drawings.view",),
        "destroy": ("drawings.edit",),
    }

    def get_queryset(self):
        return super().get_queryset().select_related("drawing", "uploaded_by", "reviewed_by")

    def get_permissions(self):
        from apps.common.drf_permissions import HasPermission

        if self.action in {"reviews", "decision"} and self.request.method == "POST":
            return [HasPermission("drawings.review")()]
        return super().get_permissions()

    @action(detail=True, methods=["get", "post"], url_path="reviews")
    def reviews(self, request, pk=None):
        revision = self.get_object()
        if request.method == "GET":
            reviews = revision.reviews.select_related("reviewer")
            return Response(DrawingReviewSerializer(reviews, many=True).data)

        serializer = DrawingReviewSerializer(data={**request.data, "revision": str(revision.id)})
        serializer.is_valid(raise_exception=True)
        reviewer_id = serializer.validated_data.pop("reviewer_id", None)
        review = serializer.save(
            revision=revision,
            reviewer_id=reviewer_id or request.user.id,
        )
        return Response(DrawingReviewSerializer(review).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="decision")
    def decision(self, request, pk=None):
        revision = self.get_object()
        serializer = DrawingDecisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        decision = serializer.validated_data["decision"]
        comments = serializer.validated_data.get("comments", "")
        with transaction.atomic():
            revision.review_status = decision
            revision.reviewed_by = request.user
            revision.reviewed_at = timezone.now()
            revision.review_comments = comments
            revision.save(
                update_fields=["review_status", "reviewed_by", "reviewed_at", "review_comments", "updated_at"]
            )
            DrawingReview.objects.create(
                revision=revision,
                reviewer=request.user,
                decision=decision,
                comments=comments,
                decided_at=timezone.now(),
            )
        record_audit_event(
            organization=revision.drawing.project.organization,
            actor=request.user,
            action="drawing.revision.reviewed",
            target_type="DrawingRevision",
            target_id=revision.id,
            project=revision.drawing.project,
            metadata={"decision": decision},
            request=request,
        )
        if revision.uploaded_by and revision.uploaded_by_id != request.user.id:
            notify(
                recipient=revision.uploaded_by,
                verb="drawing.revision.reviewed",
                title=f"Drawing {revision.drawing.number} reviewed",
                body=f"Revision {revision.revision_code}: {decision.replace('_', ' ')}",
                organization=revision.drawing.project.organization,
                project=revision.drawing.project,
                target_type="DrawingRevision",
                target_id=revision.id,
            )
        return Response(DrawingRevisionSerializer(revision).data)


class DrawingReviewViewSet(ProjectScopedViewSet):
    serializer_class = DrawingReviewSerializer
    filterset_fields = ["revision", "decision"]
    ordering_fields = ["created_at", "decided_at"]
    ordering = ["created_at"]
    org_field = "revision__drawing__project__organization_id"
    project_field = "revision__drawing__project_id"
    action_permissions = {
        "read": ("drawings.view",),
        "create": ("drawings.review",),
        "update": ("drawings.review",),
        "partial_update": ("drawings.review",),
        "destroy": ("drawings.review",),
    }

    def get_queryset(self):
        return super().get_queryset().select_related("reviewer", "revision")

    def perform_create(self, serializer):
        reviewer_id = serializer.validated_data.pop("reviewer_id", None)
        serializer.save(reviewer_id=reviewer_id or self.request.user.id)

    def perform_update(self, serializer):
        reviewer_id = serializer.validated_data.pop("reviewer_id", None)
        if reviewer_id:
            serializer.save(reviewer_id=reviewer_id)
        else:
            serializer.save()
