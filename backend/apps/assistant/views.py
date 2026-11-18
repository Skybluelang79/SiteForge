"""AI assistant API: chat, context briefing and conversation history."""
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.exceptions import PermissionDenied
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
    rate = "40/min"


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
                raise PermissionDenied("You do not have access to this project.")

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
        scoped_project_id = conversation.project_id
        context = build_context(request, scoped_project_id)
        reply, provider, model, latency = generate_reply(message, context, history)

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
                "suggestions": suggested_prompts(context),
                "context": {
                    "scope": context["scope"],
                    "organization": context["organization"],
                    "project": context["project"]["name"] if context["project"] else None,
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
