"""Quality and safety serializers."""
from rest_framework import serializers

from apps.accounts.serializers import UserSummarySerializer

from .models import (
    CorrectiveAction,
    Defect,
    Inspection,
    InspectionItem,
    PunchList,
    PunchListItem,
    SafetyIncident,
)


class InspectionItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = InspectionItem
        fields = [
            "id", "inspection", "order", "description", "result", "notes", "photo",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class InspectionSerializer(serializers.ModelSerializer):
    inspector = UserSummarySerializer(read_only=True)
    signed_off_by = UserSummarySerializer(read_only=True)
    created_by = UserSummarySerializer(read_only=True)
    inspector_id = serializers.UUIDField(write_only=True, required=False, allow_null=True)
    items = InspectionItemSerializer(many=True, read_only=True)
    item_count = serializers.SerializerMethodField()

    class Meta:
        model = Inspection
        fields = [
            "id", "project", "number", "title", "inspection_type", "status", "description",
            "location", "checklist", "scheduled_date", "completed_date", "inspector",
            "inspector_id", "signed_off_by", "signed_off_at", "created_by", "items",
            "item_count", "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "signed_off_by", "signed_off_at", "created_by", "created_at", "updated_at",
        ]

    def get_item_count(self, obj):
        return obj.items.count()

    def validate(self, attrs):
        project = attrs.get("project") or getattr(self.instance, "project", None)
        number = attrs.get("number") or getattr(self.instance, "number", None)
        if project and number:
            qs = Inspection.objects.filter(project=project, number=number)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError({"number": "An inspection with this number exists."})
        return attrs


class InspectionSignoffSerializer(serializers.Serializer):
    status = serializers.ChoiceField(
        choices=[("passed", "Passed"), ("failed", "Failed"), ("conditional", "Conditional")]
    )
    comments = serializers.CharField(required=False, allow_blank=True, default="")


class DefectSerializer(serializers.ModelSerializer):
    assigned_to = UserSummarySerializer(read_only=True)
    created_by = UserSummarySerializer(read_only=True)
    assigned_to_id = serializers.UUIDField(write_only=True, required=False, allow_null=True)

    class Meta:
        model = Defect
        fields = [
            "id", "project", "inspection", "title", "description", "severity", "status",
            "location", "cost_code", "assigned_to", "assigned_to_id", "due_date", "photo",
            "resolved_at", "created_by", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "resolved_at", "created_by", "created_at", "updated_at"]


class PunchListItemSerializer(serializers.ModelSerializer):
    assigned_to = UserSummarySerializer(read_only=True)
    assigned_to_id = serializers.UUIDField(write_only=True, required=False, allow_null=True)

    class Meta:
        model = PunchListItem
        fields = [
            "id", "punch_list", "description", "location", "trade", "status",
            "assigned_to", "assigned_to_id", "due_date", "photo", "closed_at",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "closed_at", "created_at", "updated_at"]


class PunchListSerializer(serializers.ModelSerializer):
    assigned_to = UserSummarySerializer(read_only=True)
    created_by = UserSummarySerializer(read_only=True)
    assigned_to_id = serializers.UUIDField(write_only=True, required=False, allow_null=True)
    items = PunchListItemSerializer(many=True, read_only=True)
    item_count = serializers.SerializerMethodField()

    class Meta:
        model = PunchList
        fields = [
            "id", "project", "name", "description", "status", "target_date",
            "assigned_to", "assigned_to_id", "created_by", "items", "item_count",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_by", "created_at", "updated_at"]

    def get_item_count(self, obj):
        return obj.items.count()


class SafetyIncidentSerializer(serializers.ModelSerializer):
    reported_by = UserSummarySerializer(read_only=True)
    created_by = UserSummarySerializer(read_only=True)
    reported_by_id = serializers.UUIDField(write_only=True, required=False, allow_null=True)

    class Meta:
        model = SafetyIncident
        fields = [
            "id", "project", "number", "title", "description", "severity", "status",
            "occurred_at", "location", "injured_person", "witnesses", "root_cause",
            "immediate_actions", "osha_recordable", "days_lost", "reported_by",
            "reported_by_id", "created_by", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_by", "created_at", "updated_at"]

    def validate(self, attrs):
        project = attrs.get("project") or getattr(self.instance, "project", None)
        number = attrs.get("number") or getattr(self.instance, "number", None)
        if project and number:
            qs = SafetyIncident.objects.filter(project=project, number=number)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError({"number": "An incident with this number exists."})
        return attrs


class CorrectiveActionSerializer(serializers.ModelSerializer):
    assigned_to = UserSummarySerializer(read_only=True)
    verified_by = UserSummarySerializer(read_only=True)
    created_by = UserSummarySerializer(read_only=True)
    assigned_to_id = serializers.UUIDField(write_only=True, required=False, allow_null=True)

    class Meta:
        model = CorrectiveAction
        fields = [
            "id", "project", "incident", "inspection", "title", "description", "status",
            "assigned_to", "assigned_to_id", "due_date", "completed_at", "verified_by",
            "verified_at", "created_by", "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "completed_at", "verified_by", "verified_at", "created_by",
            "created_at", "updated_at",
        ]
