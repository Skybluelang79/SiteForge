"""Authentication, MFA and profile endpoints."""
import base64
import io

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from django_otp import devices_for_user
from django_otp.plugins.otp_static.models import StaticDevice, StaticToken
from django_otp.plugins.otp_totp.models import TOTPDevice
from rest_framework import generics, permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView

from apps.common.drf_permissions import IsOrganizationMember

from .models import UserSession
from .serializers import (
    LoginSerializer,
    MFADisableSerializer,
    MFASetupSerializer,
    MFAVerifySerializer,
    PasswordChangeSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    RegisterSerializer,
    UserSerializer,
    UserSessionSerializer,
)
from .services import consume_password_reset, create_password_reset, resolve_mfa_token, send_password_reset_email

User = get_user_model()


def _tokens_for_user(user):
    refresh = RefreshToken.for_user(user)
    return {"access": str(refresh.access_token), "refresh": str(refresh), "user": UserSerializer(user).data}


class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]
    throttle_scope = "auth"

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            user = serializer.save()
            user.email_verified_at = timezone.now()
            user.save(update_fields=["email_verified_at"])
        return Response(_tokens_for_user(user), status=status.HTTP_201_CREATED)


class LoginView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_scope = "auth"

    def post(self, request):
        serializer = LoginSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        return Response(serializer.validated_data)


class RefreshView(TokenRefreshView):
    permission_classes = [permissions.AllowAny]


class LogoutView(APIView):
    def post(self, request):
        refresh = request.data.get("refresh")
        if refresh:
            try:
                RefreshToken(refresh).blacklist()
            except Exception:
                pass
        UserSession.objects.filter(user=request.user, revoked_at__isnull=True).update(
            revoked_at=timezone.now()
        )
        return Response(status=status.HTTP_205_RESET_CONTENT)


class MeView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer

    def get_object(self):
        return self.request.user


class MFASetupView(APIView):
    """Start TOTP enrollment; returns secret + otpauth URI + QR data URL."""

    def post(self, request):
        serializer = MFASetupSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if not request.user.check_password(serializer.validated_data["password"]):
            return Response(
                {"error": {"code": "validation_error", "message": "Password is incorrect.", "details": {}}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        device, _ = TOTPDevice.objects.get_or_create(
            user=request.user, name="default", defaults={"confirmed": False}
        )
        config_url = device.config_url
        qr_data_url = ""
        try:
            import qrcode

            img = qrcode.make(config_url)
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            qr_data_url = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
        except Exception:
            pass
        return Response({"secret": device.key, "otpauth_url": config_url, "qr_code": qr_data_url})


class MFAVerifyView(APIView):
    """Complete MFA login using TOTP or a static recovery code."""

    permission_classes = [permissions.AllowAny]
    throttle_scope = "auth"

    def post(self, request):
        serializer = MFAVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = resolve_mfa_token(serializer.validated_data["mfa_token"])
        code = serializer.validated_data["code"].strip()
        device = _verify_device(user, code)
        if not device:
            return Response(
                {"error": {"code": "invalid_otp", "message": "Invalid verification code.", "details": {}}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not TOTPDevice.objects.filter(user=user, confirmed=True).exists():
            _enable_mfa(user)
        user.touch_activity()
        return Response(_tokens_for_user(user))


class MFAConfirmView(APIView):
    """Confirm initial TOTP enrollment and mint recovery codes."""

    def post(self, request):
        serializer = MFAVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        code = serializer.validated_data["code"].strip()
        device = TOTPDevice.objects.filter(user=request.user, name="default").first()
        if device is None or not device.verify_token(code):
            return Response(
                {"error": {"code": "invalid_otp", "message": "Invalid verification code.", "details": {}}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        device.confirmed = True
        device.save(update_fields=["confirmed"])
        recovery = _mint_recovery_codes(request.user)
        _enable_mfa(request.user)
        return Response({"detail": "MFA enabled.", "recovery_codes": recovery})


class MFADisableView(APIView):
    def post(self, request):
        serializer = MFADisableSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if not request.user.check_password(serializer.validated_data["password"]):
            return Response(
                {"error": {"code": "validation_error", "message": "Password is incorrect.", "details": {}}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        TOTPDevice.objects.filter(user=request.user).delete()
        StaticDevice.objects.filter(user=request.user).delete()
        request.user.mfa_enabled = False
        request.user.save(update_fields=["mfa_enabled"])
        return Response({"detail": "MFA disabled."})


class PasswordChangeView(APIView):
    def post(self, request):
        serializer = PasswordChangeSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        request.user.set_password(serializer.validated_data["new_password"])
        request.user.save(update_fields=["password"])
        return Response({"detail": "Password updated."})


class PasswordResetRequestView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_scope = "auth"

    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = User.objects.filter(email=serializer.validated_data["email"], is_active=True).first()
        if user:
            raw = create_password_reset(user)
            send_password_reset_email(user, raw)
        return Response({"detail": "If the account exists, a reset link has been sent."})


class PasswordResetConfirmView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_scope = "auth"

    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        consume_password_reset(
            serializer.validated_data["token"], serializer.validated_data["new_password"]
        )
        return Response({"detail": "Password has been reset."})


class SessionListView(generics.ListAPIView):
    serializer_class = UserSessionSerializer

    def get_queryset(self):
        return UserSession.objects.filter(user=self.request.user).order_by("-created_at")


class SessionRevokeView(APIView):
    def post(self, request, pk):
        updated = UserSession.objects.filter(pk=pk, user=request.user).update(
            revoked_at=timezone.now()
        )
        if not updated:
            return Response(status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(["GET"])
@permission_classes([IsOrganizationMember])
def my_context(request):
    """Everything the SPA needs on boot: user, orgs, memberships, active org."""
    from apps.organizations.serializers import MembershipSerializer

    memberships = request.user.active_memberships()
    return Response(
        {
            "user": UserSerializer(request.user).data,
            "memberships": MembershipSerializer(memberships, many=True).data,
            "active_organization_id": str(request.membership.organization_id),
            "permissions": sorted(request.membership.effective_permissions),
        }
    )


# --- helpers ---------------------------------------------------------------

def _verify_device(user, code):
    for device in devices_for_user(user, confirmed=True):
        if device.verify_token(code):
            return device
    return None


def _enable_mfa(user):
    if not user.mfa_enabled:
        user.mfa_enabled = True
        user.save(update_fields=["mfa_enabled"])


def _mint_recovery_codes(user, count=8):
    device, _ = StaticDevice.objects.get_or_create(user=user, name="recovery")
    device.token_set.all().delete()
    codes = []
    for _ in range(count):
        token = StaticToken.random_token()
        device.token_set.create(token=token)
        codes.append(token)
    return codes
