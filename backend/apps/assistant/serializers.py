"""Assistant serializers."""
from rest_framework import serializers

from .models import AssistantConversation, AssistantMessage


class AssistantMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = AssistantMessage
        fields = ["id", "role", "content", "model", "provider", "latency_ms", "created_at"]
        read_only_fields = fields


class AssistantConversationSerializer(serializers.ModelSerializer):
    messages = AssistantMessageSerializer(many=True, read_only=True)

    class Meta:
        model = AssistantConversation
        fields = ["id", "project", "title", "messages", "created_at", "updated_at"]
        read_only_fields = fields


class AssistantChatSerializer(serializers.Serializer):
    message = serializers.CharField(max_length=4000, trim_whitespace=True, required=False)
    messages = serializers.ListField(child=serializers.DictField(), required=False, write_only=True)
    conversation_id = serializers.UUIDField(required=False, allow_null=True)
    project_id = serializers.UUIDField(required=False, allow_null=True)

    def validate(self, attrs):
        messages = attrs.pop("messages", None)
        if not attrs.get("message") and messages:
            for item in reversed(messages):
                if item.get("role") == "user" and item.get("content"):
                    attrs["message"] = item["content"]
                    break
        if not attrs.get("message"):
            raise serializers.ValidationError({"message": "This field is required."})
        return attrs
