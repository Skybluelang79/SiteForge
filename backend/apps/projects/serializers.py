"""Project serializers."""
from django.contrib.auth import get_user_model
from rest_framework import serializers

from apps.accounts.serializers import UserSummarySerializer

from .models import ActivityFeedEntry, Contract, Milestone, Project, ProjectMember

User = get_user_model()


class ProjectMemberSerializer(serializers.ModelSerializer):
    user = UserSummarySerializer(read_only=True)
    user_id = serializers.UUIDField(write_only=True, required=False)

    class Meta:
        model = ProjectMember
        fields = ["id", "project", "user", "user_id", "role_code", "title", "is_active", "created_at"]
        read_only_fields = ["id", "project", "user", "created_at"]

    def validate(self, attrs):
        if self.instance is None and not attrs.get("user_id"):
            raise serializers.ValidationError({"user_id": "This field is required."})
        return attrs


class ProjectListSerializer(serializers.ModelSerializer):
    project_manager = UserSummarySerializer(read_only=True)
    member_count = serializers.SerializerMethodField()

    class Meta:
        model = Project
        fields = [
            "id", "organization", "name", "number", "status", "project_type", "city", "region",
            "start_date", "target_completion_date", "contract_value", "currency",
            "project_manager", "member_count", "created_at", "updated_at",
        ]
        read_only_fields = fields

    def get_member_count(self, obj):
        return getattr(obj, "active_member_count", None) or obj.members.filter(is_active=True).count()


class ProjectSerializer(serializers.ModelSerializer):
    project_manager = UserSummarySerializer(read_only=True)
    project_manager_id = serializers.UUIDField(write_only=True, required=False, allow_null=True)

    class Meta:
        model = Project
        fields = [
            "id", "organization", "name", "number", "description", "status", "project_type",
            "address_line1", "city", "region", "postal_code", "country", "latitude", "longitude",
            "start_date", "target_completion_date", "actual_completion_date", "contract_value",
            "currency", "client_name", "project_manager", "project_manager_id", "is_public",
            "settings", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "organization", "created_at", "updated_at"]

    def validate_number(self, value):
        request = self.context.get("request")
        if not value or not request:
            return value
        qs = Project.objects.filter(organization_id=request.membership.organization_id, number=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("A project with this number already exists.")
        return value

    def validate_target_completion_date(self, value):
        start = self.initial_data.get("start_date") or getattr(self.instance, "start_date", None)
        if value and start and str(value) < str(start):
            raise serializers.ValidationError("Target completion date cannot be before the start date.")
        return value


class MilestoneSerializer(serializers.ModelSerializer):
    owner = UserSummarySerializer(read_only=True)
    owner_id = serializers.UUIDField(write_only=True, required=False, allow_null=True)

    class Meta:
        model = Milestone
        fields = [
            "id", "project", "name", "description", "due_date", "status",
            "achieved_date", "weight", "owner", "owner_id", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class ContractSerializer(serializers.ModelSerializer):
    created_by = UserSummarySerializer(read_only=True)

    class Meta:
        model = Contract
        fields = [
            "id", "project", "name", "number", "contract_type", "status", "counterparty",
            "original_value", "revised_value", "currency", "retention_percent",
            "start_date", "end_date", "signed_date", "created_by", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_by", "created_at", "updated_at"]


class ActivityFeedEntrySerializer(serializers.ModelSerializer):
    actor = UserSummarySerializer(read_only=True)

    class Meta:
        model = ActivityFeedEntry
        fields = [
            "id", "project", "actor", "verb", "summary", "target_type", "target_id",
            "metadata", "created_at",
        ]
        read_only_fields = fields
