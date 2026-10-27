"""RFI, submittal, approval chain and comment endpoints."""
from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from apps.audit.services import record_audit_event
from apps.common.viewsets import ProjectScopedViewSet
from apps.notifications.services import notify

from .models import (
    ApprovalChain,
    ApprovalChainStep,
    Comment,
    RFI,
    RFIComment,
    Submittal,
    SubmittalApproval,
    SubmittalItem,
)
from .serializers import (
    ApprovalChainSerializer,
    ApprovalChainStepSerializer,
    CommentSerializer,
    RFICommentSerializer,
    RFIResponseSerializer,
    RFISerializer,
    SubmittalApprovalSerializer,
    SubmittalDecisionSerializer,
    SubmittalItemSerializer,
    SubmittalSerializer,
)


def _pop_user_ids(validated_data, *keys):
    values = {key: validated_data.pop(key, None) for key in keys}
    return {key: value for key, value in values.items() if value is not None}


class RFIViewSet(ProjectScopedViewSet):
    serializer_class = RFISerializer
    filterset_fields = ["project", "status", "priority", "assigned_to", "ball_in_court", "drawing"]
    search_fields = ["number", "subject", "question", "official_response"]
    ordering_fields = ["created_at", "due_date", "priority", "status", "number"]
    action_permissions = {
        "read": ("rfis.view",),
        "create": ("rfis.create",),
        "update": ("rfis.edit",),
        "partial_update": ("rfis.edit",),
        "destroy": ("rfis.edit",),
        "write": ("rfis.create",),
        "respond": ("rfis.respond",),
        "close": ("rfis.approve",),
    }

    def get_queryset(self):
        return super().get_queryset().select_related(
            "assigned_to", "ball_in_court", "created_by", "drawing"
        ).prefetch_related("comments__author")

    def perform_create(self, serializer):
        users = _pop_user_ids(serializer.validated_data, "assigned_to_id", "ball_in_court_id")
        rfi = serializer.save(created_by=self.request.user, **users)
        record_audit_event(
            organization=rfi.project.organization,
            actor=self.request.user,
            action="rfi.created",
            target_type="RFI",
            target_id=rfi.id,
            project=rfi.project,
            request=self.request,
        )

    def perform_update(self, serializer):
        users = _pop_user_ids(serializer.validated_data, "assigned_to_id", "ball_in_court_id")
        serializer.save(**users)

    @action(detail=True, methods=["post"], url_path="respond")
    def respond(self, request, pk=None):
        rfi = self.get_object()
        serializer = RFIResponseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        rfi.official_response = serializer.validated_data["official_response"]
        rfi.status = serializer.validated_data["status"]
        rfi.answered_at = timezone.now()
        if rfi.status == "closed":
            rfi.closed_at = timezone.now()
        rfi.save(update_fields=["official_response", "status", "answered_at", "closed_at", "updated_at"])
        record_audit_event(
            organization=rfi.project.organization,
            actor=request.user,
            action="rfi.responded",
            target_type="RFI",
            target_id=rfi.id,
            project=rfi.project,
            metadata={"status": rfi.status},
            request=request,
        )
        for recipient in {rfi.created_by, rfi.assigned_to} - {None, request.user}:
            notify(
                recipient=recipient,
                verb="rfi.responded",
                title=f"RFI {rfi.number} answered",
                body=rfi.subject,
                organization=rfi.project.organization,
                project=rfi.project,
                target_type="RFI",
                target_id=rfi.id,
            )
        return Response(RFISerializer(rfi).data)

    @action(detail=True, methods=["post"], url_path="close")
    def close(self, request, pk=None):
        rfi = self.get_object()
        rfi.status = "closed"
        rfi.closed_at = timezone.now()
        rfi.save(update_fields=["status", "closed_at", "updated_at"])
        return Response(RFISerializer(rfi).data)

    @action(detail=True, methods=["get", "post"], url_path="comments")
    def comments(self, request, pk=None):
        rfi = self.get_object()
        if request.method == "GET":
            return Response(RFICommentSerializer(rfi.comments.select_related("author"), many=True).data)
        serializer = RFICommentSerializer(data={**request.data, "rfi": str(rfi.id)})
        serializer.is_valid(raise_exception=True)
        comment = serializer.save(author=request.user)
        return Response(RFICommentSerializer(comment).data, status=status.HTTP_201_CREATED)


class RFICommentViewSet(ProjectScopedViewSet):
    serializer_class = RFICommentSerializer
    filterset_fields = ["rfi", "is_official"]
    search_fields = ["body"]
    ordering = ["created_at"]
    org_field = "rfi__project__organization_id"
    project_field = "rfi__project_id"
    action_permissions = {
        "read": ("rfis.view",),
        "create": ("rfis.respond",),
        "update": ("rfis.edit",),
        "partial_update": ("rfis.edit",),
        "destroy": ("rfis.edit",),
    }

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)


class SubmittalViewSet(ProjectScopedViewSet):
    serializer_class = SubmittalSerializer
    filterset_fields = ["project", "status", "submittal_type", "reviewer", "spec_section"]
    search_fields = ["number", "title", "description", "spec_section"]
    ordering_fields = ["created_at", "due_date", "status", "number"]
    action_permissions = {
        "read": ("rfis.view",),
        "create": ("rfis.create",),
        "update": ("rfis.edit",),
        "partial_update": ("rfis.edit",),
        "destroy": ("rfis.edit",),
        "write": ("rfis.create",),
        "submit": ("rfis.create",),
        "approve": ("rfis.approve",),
    }

    def get_queryset(self):
        return super().get_queryset().select_related(
            "submitted_by", "reviewer", "final_approval"
        ).prefetch_related("items", "approvals")

    def perform_create(self, serializer):
        reviewer_id = serializer.validated_data.pop("reviewer_id", None)
        submittal = serializer.save(submitted_by=self.request.user, reviewer_id=reviewer_id)
        record_audit_event(
            organization=submittal.project.organization,
            actor=self.request.user,
            action="submittal.created",
            target_type="Submittal",
            target_id=submittal.id,
            project=submittal.project,
            request=self.request,
        )

    def perform_update(self, serializer):
        reviewer_id = serializer.validated_data.pop("reviewer_id", None)
        if reviewer_id:
            serializer.save(reviewer_id=reviewer_id)
        else:
            serializer.save()

    @action(detail=True, methods=["post"], url_path="submit")
    def submit(self, request, pk=None):
        submittal = self.get_object()
        submittal.status = "submitted"
        submittal.submitted_at = timezone.now()
        submittal.save(update_fields=["status", "submitted_at", "updated_at"])
        return Response(SubmittalSerializer(submittal).data)

    @action(detail=True, methods=["post"], url_path="approve")
    def approve(self, request, pk=None):
        submittal = self.get_object()
        serializer = SubmittalDecisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        decision = serializer.validated_data["decision"]
        comments = serializer.validated_data.get("comments", "")
        with transaction.atomic():
            approval = SubmittalApproval.objects.create(
                submittal=submittal,
                approver=request.user,
                decision=decision,
                comments=comments,
            )
            submittal.status = decision
            submittal.reviewer = request.user
            submittal.reviewed_at = timezone.now()
            submittal.final_approval = approval
            submittal.save(
                update_fields=["status", "reviewer", "reviewed_at", "final_approval", "updated_at"]
            )
        record_audit_event(
            organization=submittal.project.organization,
            actor=request.user,
            action="submittal.reviewed",
            target_type="Submittal",
            target_id=submittal.id,
            project=submittal.project,
            metadata={"decision": decision},
            request=request,
        )
        if submittal.submitted_by and submittal.submitted_by_id != request.user.id:
            notify(
                recipient=submittal.submitted_by,
                verb="submittal.reviewed",
                title=f"Submittal {submittal.number} reviewed",
                body=f"{submittal.title}: {decision.replace('_', ' ')}",
                organization=submittal.project.organization,
                project=submittal.project,
                target_type="Submittal",
                target_id=submittal.id,
            )
        return Response(SubmittalSerializer(submittal).data)

    @action(detail=True, methods=["get", "post"], url_path="items")
    def items(self, request, pk=None):
        submittal = self.get_object()
        if request.method == "GET":
            return Response(SubmittalItemSerializer(submittal.items.all(), many=True).data)
        serializer = SubmittalItemSerializer(data={**request.data, "submittal": str(submittal.id)})
        serializer.is_valid(raise_exception=True)
        item = serializer.save()
        return Response(SubmittalItemSerializer(item).data, status=status.HTTP_201_CREATED)


class SubmittalItemViewSet(ProjectScopedViewSet):
    serializer_class = SubmittalItemSerializer
    filterset_fields = ["submittal", "status"]
    search_fields = ["description", "spec_reference"]
    ordering = ["created_at"]
    org_field = "submittal__project__organization_id"
    project_field = "submittal__project_id"
    action_permissions = {
        "read": ("rfis.view",),
        "create": ("rfis.create",),
        "update": ("rfis.edit",),
        "partial_update": ("rfis.edit",),
        "destroy": ("rfis.edit",),
    }

    def perform_create(self, serializer):
        submittal = serializer.validated_data.get("submittal")
        if submittal is None or not self.request.user.can_access_project(submittal.project):
            raise PermissionDenied("You do not have access to this submittal's project.")
        serializer.save()


class ApprovalChainViewSet(ProjectScopedViewSet):
    serializer_class = ApprovalChainSerializer
    filterset_fields = ["project", "target_type", "is_active"]
    search_fields = ["name"]
    ordering = ["name"]
    action_permissions = {
        "read": ("rfis.view",),
        "create": ("rfis.approve",),
        "update": ("rfis.approve",),
        "partial_update": ("rfis.approve",),
        "destroy": ("rfis.approve",),
        "write": ("rfis.approve",),
    }

    @action(detail=True, methods=["get", "post"], url_path="steps")
    def steps(self, request, pk=None):
        chain = self.get_object()
        if request.method == "GET":
            steps = chain.steps.select_related("approver")
            return Response(ApprovalChainStepSerializer(steps, many=True).data)
        serializer = ApprovalChainStepSerializer(data={**request.data, "chain": str(chain.id)})
        serializer.is_valid(raise_exception=True)
        approver_id = serializer.validated_data.pop("approver_id", None)
        step = serializer.save(chain=chain, approver_id=approver_id)
        return Response(ApprovalChainStepSerializer(step).data, status=status.HTTP_201_CREATED)


class ApprovalChainStepViewSet(ProjectScopedViewSet):
    serializer_class = ApprovalChainStepSerializer
    filterset_fields = ["chain", "approver", "is_required"]
    ordering = ["order"]
    org_field = "chain__project__organization_id"
    project_field = "chain__project_id"
    action_permissions = {
        "read": ("rfis.view",),
        "create": ("rfis.approve",),
        "update": ("rfis.approve",),
        "partial_update": ("rfis.approve",),
        "destroy": ("rfis.approve",),
    }

    def perform_create(self, serializer):
        approver_id = serializer.validated_data.pop("approver_id", None)
        serializer.save(approver_id=approver_id)

    def perform_update(self, serializer):
        approver_id = serializer.validated_data.pop("approver_id", None)
        if approver_id:
            serializer.save(approver_id=approver_id)
        else:
            serializer.save()


class SubmittalApprovalViewSet(ProjectScopedViewSet):
    serializer_class = SubmittalApprovalSerializer
    http_method_names = ["get", "head", "options"]
    filterset_fields = ["submittal", "decision", "approver"]
    ordering = ["-decided_at"]
    org_field = "submittal__project__organization_id"
    project_field = "submittal__project_id"
    action_permissions = {"read": ("rfis.view",)}

    def get_queryset(self):
        return super().get_queryset().select_related("approver", "submittal", "step")


class CommentViewSet(ProjectScopedViewSet):
    serializer_class = CommentSerializer
    filterset_fields = ["project", "target_type", "target_id", "parent"]
    search_fields = ["body"]
    ordering = ["created_at"]
    action_permissions = {
        "read": ("rfis.view",),
        "create": ("rfis.create",),
        "update": ("rfis.edit",),
        "partial_update": ("rfis.edit",),
        "destroy": ("rfis.edit",),
    }

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)
