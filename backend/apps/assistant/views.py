from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.common.drf_permissions import HasPermission
from apps.projects.views import projects_for_user

from .services import ask_assistant


class ChatMessageSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=["user", "assistant"])
    content = serializers.CharField(max_length=4000)


class AssistantChatSerializer(serializers.Serializer):
    messages = ChatMessageSerializer(many=True, allow_empty=False)
    project_id = serializers.UUIDField(required=False, allow_null=True)

    def validate_messages(self, value):
        if len(value) > 20:
            raise serializers.ValidationError("A maximum of 20 messages is allowed.")
        if value[-1]["role"] != "user":
            raise serializers.ValidationError("The last message must be from the user.")
        if sum(len(item["content"]) for item in value) > 16000:
            raise serializers.ValidationError("Conversation is too large; start a new request.")
        return value


class AssistantChatView(APIView):
    """Ground an AI copilot response in the caller's accessible SiteForge data."""

    permission_classes = [HasPermission("projects.view")]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "assistant"

    @extend_schema(
        request=AssistantChatSerializer,
        responses={200: OpenApiTypes.OBJECT},
        tags=["assistant"],
    )
    def post(self, request):
        serializer = AssistantChatSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        organization_id = request.membership.organization_id
        project_id = data.get("project_id")

        if project_id and not projects_for_user(request.user, organization_id).filter(
            pk=project_id
        ).exists():
            return Response(
                {
                    "error": {
                        "code": "project_not_found",
                        "message": "Project not found or not accessible.",
                    }
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        result = ask_assistant(
            user=request.user,
            organization_id=organization_id,
            messages=data["messages"],
            project_id=project_id,
        )
        return Response(result)
