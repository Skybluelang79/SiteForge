from rest_framework import serializers

from apps.accounts.serializers import UserSummarySerializer

from .models import AuditEvent


class AuditEventSerializer(serializers.ModelSerializer):
    actor = UserSummarySerializer(read_only=True)

    class Meta:
        model = AuditEvent
        fields = [
            "id", "organization", "actor", "action", "target_type", "target_id",
            "project", "metadata", "ip_address", "user_agent", "created_at",
        ]
        read_only_fields = fields
