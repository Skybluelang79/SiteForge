"""Organization serializers."""
from django.contrib.auth import get_user_model
from django.utils.text import slugify
from rest_framework import serializers

from apps.accounts.serializers import UserSummarySerializer
from apps.common.permissions import DEFAULT_ROLES, PERMISSIONS

from .models import Invitation, Membership, OrgFeatureSetting, Organization, Role

User = get_user_model()


class OrganizationSerializer(serializers.ModelSerializer):
    member_count = serializers.SerializerMethodField()

    class Meta:
        model = Organization
        fields = [
            "id", "name", "slug", "legal_name", "tax_id", "timezone", "currency",
            "address_line1", "address_line2", "city", "region", "postal_code", "country",
            "logo", "is_active", "settings", "member_count", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "member_count"]

    def get_member_count(self, obj):
        return getattr(obj, "active_member_count", None) or obj.memberships.filter(is_active=True).count()

    def create(self, validated_data):
        validated_data.setdefault("slug", slugify(validated_data["name"])[:110])
        base_slug = validated_data["slug"]
        suffix = 1
        while Organization.objects.filter(slug=validated_data["slug"]).exists():
            suffix += 1
            validated_data["slug"] = f"{base_slug}-{suffix}"
        return super().create(validated_data)


class RoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Role
        fields = ["id", "name", "code", "description", "permissions", "is_system", "created_at"]
        read_only_fields = ["id", "is_system", "created_at"]

    def validate_permissions(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError("Permissions must be a list of permission keys.")
        unknown = set(value) - set(PERMISSIONS)
        if unknown:
            raise serializers.ValidationError(f"Unknown permission keys: {', '.join(sorted(unknown))}")
        return sorted(set(value))


class MembershipSerializer(serializers.ModelSerializer):
    user = UserSummarySerializer(read_only=True)
    organization_name = serializers.CharField(source="organization.name", read_only=True)
    organization_slug = serializers.CharField(source="organization.slug", read_only=True)

    class Meta:
        model = Membership
        fields = [
            "id", "organization", "organization_name", "organization_slug", "user",
            "role_code", "role", "is_active", "is_owner", "title",
            "joined_at", "created_at",
        ]
        read_only_fields = ["id", "organization", "user", "is_owner", "created_at"]


class MembershipWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Membership
        fields = ["id", "user", "role_code", "role", "is_active", "title"]
        read_only_fields = ["id"]

    def validate_role_code(self, value):
        if value not in DEFAULT_ROLES:
            raise serializers.ValidationError("Unknown role code.")
        return value


class MembershipCreateSerializer(serializers.Serializer):
    email = serializers.EmailField()
    role_code = serializers.CharField(default="member")
    title = serializers.CharField(required=False, allow_blank=True)

    def validate_role_code(self, value):
        if value not in DEFAULT_ROLES:
            raise serializers.ValidationError("Unknown role code.")
        return value


class InvitationSerializer(serializers.ModelSerializer):
    invited_by = UserSummarySerializer(read_only=True)
    is_expired = serializers.SerializerMethodField()

    class Meta:
        model = Invitation
        fields = [
            "id", "email", "role_code", "role", "status", "project",
            "invited_by", "expires_at", "accepted_at", "is_expired", "created_at",
        ]
        read_only_fields = ["id", "status", "invited_by", "accepted_at", "created_at", "expires_at"]

    def get_is_expired(self, obj):
        from django.utils import timezone

        return obj.expires_at < timezone.now() and obj.status == "pending"


class InvitationCreateSerializer(serializers.Serializer):
    email = serializers.EmailField()
    role_code = serializers.CharField(default="member")
    project = serializers.UUIDField(required=False)
    message = serializers.CharField(required=False, allow_blank=True)

    def validate_role_code(self, value):
        if value not in DEFAULT_ROLES:
            raise serializers.ValidationError("Unknown role code.")
        return value


class InvitationAcceptSerializer(serializers.Serializer):
    token = serializers.CharField()
    first_name = serializers.CharField(required=False, allow_blank=True)
    last_name = serializers.CharField(required=False, allow_blank=True)
    password = serializers.CharField(required=False, allow_blank=True)


class OrgFeatureSettingSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrgFeatureSetting
        fields = ["id", "flags", "updated_at"]
        read_only_fields = ["id", "updated_at"]
