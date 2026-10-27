"""Notification serializers."""
from rest_framework import serializers

from .models import Notification, NotificationPreference


class NotificationSerializer(serializers.ModelSerializer):
    is_read = serializers.BooleanField(read_only=True)

    class Meta:
        model = Notification
        fields = [
            "id", "organization", "project", "verb", "title", "body", "level",
            "target_type", "target_id", "url", "metadata", "read_at", "is_read",
            "created_at",
        ]
        read_only_fields = fields


class NotificationPreferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationPreference
        fields = [
            "email_enabled", "in_app_enabled", "digest_frequency", "muted_verbs", "updated_at",
        ]
        read_only_fields = ["updated_at"]
