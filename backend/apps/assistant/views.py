"""AI assistant API: chat, context briefing and conversation history."""
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView

from apps.common.drf_permissions import HasPermission
from apps.projects.models import Project

from .context import build_context, suggested_prompts
from .models import AssistantConversation, AssistantMessage
from .serializers import AssistantConversationSerializer, AssistantChatSerializer
from .services import generate_reply, provider_configured


class AssistantChatThrottle(UserRateThrottle):
    scope = "assistant"


def _actions(context):
    actions = [
        {"label": "Open dashboard", "href": "/dashboard", "kind": "navigate"},
        {"label": "Review projects", "href": "/projects", "kind": "navigate"},
    ]
    project = context.get("project")
    if project and project.get("id"):
        pid = project["id"]
        actions.insert(0, {"label": f"Open {project['name']}", "href": f"/projects/{pid}", "kind": "navigate"})
    kpis = context.get("kpis") or {}
    if kpis.get("overdue_rfis"):
        actions.append({"label": "Review RFIs", "href": "/rfis", "kind": "navigate"})
    if kpis.get("open_tasks"):
        actions.append({"label": "Review tasks", "href": "/tasks", "kind": "navigate"})
    return actions[:4]


class AssistantChatView(APIView):
    permission_classes = [HasPermission("projects.view")]
    throttle_classes = [AssistantChatThrottle]

    def post(self, request):
        serializer = AssistantChatSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        message = serializer.validated_data["message"]
        conversation_id = serializer.validated_data.get("conversation_id")
        project_id = serializer.validated_data.get("project_id")
        membership = request.membership

        project = None
        if project_id:
            project = Project.objects.filter(
                id=project_id, organization_id=membership.organization_id
            ).first()
            if project is None or not request.user.can_access_project(project):
                return Response(
                    {"error": {"code": "project_not_found", "message": "Project not found."}},
                    status=status.HTTP_404_NOT_FOUND,
                )

        conversation = None
        if conversation_id:
            conversation = get_object_or_404(
                AssistantConversation,
                id=conversation_id,
                user=request.user,
                organization_id=membership.organization_id,
            )
        if conversation is None:
            conversation = AssistantConversation.objects.create(
                organization=membership.organization,
                project=project,
                user=request.user,
                title=message[:180],
            )
        elif project and conversation.project_id != project.id:
            conversation.project = project
            conversation.save(update_fields=["project", "updated_at"])

        history = list(
            conversation.messages.order_by("created_at").values("role", "content")
        )
        context = build_context(request, conversation.project_id)
        context_project = (context.get("project") or {}).get("id")
        scoped_project_id = conversation.project_id or context_project
        if not conversation.project_id and context_project:
            project_obj = Project.objects.filter(
                id=context_project, organization_id=membership.organization_id
            ).first()
            if project_obj and request.user.can_access_project(project_obj):
                conversation.project = project_obj
                conversation.save(update_fields=["project", "updated_at"])
                scoped_project_id = project_obj.id

        reply, provider, model, latency, usage, degraded = generate_reply(message, context, history)

        AssistantMessage.objects.create(
            conversation=conversation,
            role="user",
            content=message,
        )
        AssistantMessage.objects.create(
            conversation=conversation,
            role="assistant",
            content=reply,
            provider=provider,
            model=model,
            latency_ms=latency,
        )
        conversation.save(update_fields=["updated_at"])

        return Response(
            {
                "conversation_id": str(conversation.id),
                "reply": reply,
                "provider": provider,
                "model": model,
                "latency_ms": latency,
                "degraded": degraded,
                "usage": usage,
                "actions": _actions(context),
                "suggestions": suggested_prompts(context),
                "context": {
                    "scope": context["scope"],
                    "organization": context["organization"],
                    "project": context["project"]["name"] if context["project"] else None,
                    "selected_project_id": str(scoped_project_id) if scoped_project_id else None,
                },
            },
            status=status.HTTP_200_OK,
        )


class AssistantContextView(APIView):
    permission_classes = [HasPermission("projects.view")]

    def get(self, request):
        project_id = request.query_params.get("project_id") or None
        context = build_context(request, project_id)
        return Response(
            {
                "context": context,
                "suggestions": suggested_prompts(context),
                "provider_configured": provider_configured(),
            }
        )


class AssistantConversationListView(APIView):
    permission_classes = [HasPermission("projects.view")]

    def get(self, request):
        queryset = AssistantConversation.objects.filter(
            user=request.user, organization_id=request.membership.organization_id
        ).prefetch_related("messages")
        return Response(AssistantConversationSerializer(queryset[:30], many=True).data)


class AssistantConversationDetailView(APIView):
    permission_classes = [HasPermission("projects.view")]

    def get(self, request, pk):
        conversation = get_object_or_404(
            AssistantConversation.objects.prefetch_related("messages"),
            id=pk,
            user=request.user,
            organization_id=request.membership.organization_id,
        )
        return Response(AssistantConversationSerializer(conversation).data)

    def delete(self, request, pk):
        conversation = get_object_or_404(
            AssistantConversation,
            id=pk,
            user=request.user,
            organization_id=request.membership.organization_id,
        )
        conversation.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)