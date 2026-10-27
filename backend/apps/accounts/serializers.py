"""Accounts serializers: users, auth, MFA, sessions, password reset."""
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.utils import timezone
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import PasswordResetToken, UserSession

User = get_user_model()


class UserSummarySerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)

    class Meta:
        model = User
        fields = ["id", "email", "first_name", "last_name", "full_name", "job_title", "avatar"]
        read_only_fields = fields


class UserSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)

    class Meta:
        model = User
        fields = [
            "id", "email", "first_name", "last_name", "full_name", "phone", "job_title",
            "avatar", "is_active", "mfa_enabled", "email_verified_at", "last_activity_at",
            "is_staff", "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "email", "is_active", "mfa_enabled", "email_verified_at",
            "last_activity_at", "is_staff", "created_at", "updated_at",
        ]


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])
    password_confirm = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ["email", "first_name", "last_name", "password", "password_confirm"]

    def validate(self, attrs):
        if attrs["password"] != attrs.pop("password_confirm"):
            raise serializers.ValidationError({"password_confirm": "Passwords do not match."})
        return attrs

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)


class LoginSerializer(TokenObtainPairSerializer):
    """Email + password login. Returns MFA challenge when MFA is enabled."""

    username_field = "email"

    def validate(self, attrs):
        data = super().validate(attrs)
        user = self.user
        if user.mfa_enabled:
            # Do not hand out real tokens until MFA is verified.
            from .services import issue_mfa_token

            return {"mfa_required": True, "mfa_token": issue_mfa_token(user)}
        self.user.touch_activity()
        if request := self.context.get("request"):
            UserSession.objects.create(
                user=user,
                user_agent=request.META.get("HTTP_USER_AGENT", "")[:400],
                ip_address=request.META.get("REMOTE_ADDR"),
            )
        data["user"] = UserSerializer(user).data
        return data


class MFASetupSerializer(serializers.Serializer):
    password = serializers.CharField(write_only=True)


class MFAVerifySerializer(serializers.Serializer):
    mfa_token = serializers.CharField()
    code = serializers.CharField(max_length=12)


class MFADisableSerializer(serializers.Serializer):
    password = serializers.CharField(write_only=True)
    code = serializers.CharField(max_length=12, required=False)


class PasswordChangeSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, validators=[validate_password])

    def validate_current_password(self, value):
        if not self.context["request"].user.check_password(value):
            raise serializers.ValidationError("Current password is incorrect.")
        return value


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        return value.lower()


class PasswordResetConfirmSerializer(serializers.Serializer):
    token = serializers.CharField()
    new_password = serializers.CharField(write_only=True, validators=[validate_password])


class UserSessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserSession
        fields = ["id", "user_agent", "ip_address", "created_at", "revoked_at", "expires_at"]
        read_only_fields = fields
