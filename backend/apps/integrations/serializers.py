"""Integration developer portal serializers."""
from rest_framework import serializers

from apps.accounts.serializers import UserSummarySerializer

from .models import ApiApplication, WebhookDelivery, WebhookEvent, WebhookSubscription


class ApiApplicationSerializer(serializers.ModelSerializer):
    created_by = UserSummarySerializer(read_only=True)
    has_credentials = serializers.SerializerMethodField()

    class Meta:
        model = ApiApplication
        fields = [
            "id", "organization", "name", "description", "environment", "client_id",
            "scopes", "is_active", "last_used_at", "has_credentials", "created_by",
            "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "organization", "client_id", "last_used_at", "has_credentials",
            "created_by", "created_at", "updated_at",
        ]

    def get_has_credentials(self, obj):
        return bool(obj.client_id and obj.client_secret_hash)

    def validate_scopes(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError("Scopes must be a list of strings.")
        return value


class WebhookSubscriptionSerializer(serializers.ModelSerializer):
    created_by = UserSummarySerializer(read_only=True)
    secret = serializers.CharField(write_only=True, required=False, allow_blank=True)
    has_secret = serializers.SerializerMethodField()

    class Meta:
        model = WebhookSubscription
        fields = [
            "id", "organization", "application", "name", "target_url", "secret",
            "has_secret", "event_types", "is_active", "failure_count", "last_success_at",
            "last_failure_at", "disabled_at", "created_by", "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "organization", "has_secret", "failure_count", "last_success_at",
            "last_failure_at", "disabled_at", "created_by", "created_at", "updated_at",
        ]

    def get_has_secret(self, obj):
        return bool(obj.secret)

    def validate_event_types(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError("event_types must be a list.")
        allowed = {choice[0] for choice in WebhookSubscription.EVENT_CHOICES}
        unknown = [event for event in value if event not in allowed]
        if unknown:
            raise serializers.ValidationError(f"Unknown event types: {', '.join(unknown)}")
        return value

    def validate_application(self, value):
        if value is None:
            return value
        organization = self.context["request"].membership.organization
        if value.organization_id != organization.id:
            raise serializers.ValidationError("Application belongs to another organization.")
        return value


class WebhookEventSerializer(serializers.ModelSerializer):
    delivery_count = serializers.SerializerMethodField()

    class Meta:
        model = WebhookEvent
        fields = [
            "id", "organization", "event_id", "event_type", "project", "payload",
            "delivery_count", "created_at", "updated_at",
        ]
        read_only_fields = fields

    def get_delivery_count(self, obj):
        return obj.deliveries.count()


class WebhookDeliverySerializer(serializers.ModelSerializer):
    event_type = serializers.CharField(source="event.event_type", read_only=True)
    event_id = serializers.UUIDField(source="event.event_id", read_only=True)

    class Meta:
        model = WebhookDelivery
        fields = [
            "id", "subscription", "event", "event_type", "event_id", "status",
            "attempt_count", "response_status", "response_body", "error_message",
            "duration_ms", "next_attempt_at", "delivered_at", "created_at",
        ]
        read_only_fields = fields
