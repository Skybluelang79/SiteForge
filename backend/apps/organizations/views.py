"""Organization, role, membership and invitation views."""
from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from apps.accounts.serializers import UserSerializer, UserSummarySerializer
from apps.common.drf_permissions import HasPermission, IsOrganizationAdmin, IsOrganizationMember
from apps.common.permissions import DEFAULT_ROLES, PERMISSIONS
from apps.common.viewsets import TenantViewSet

from .models import Invitation, Membership, OrgFeatureSetting, Organization, Role
from .serializers import (
    InvitationAcceptSerializer,
    InvitationCreateSerializer,
    InvitationSerializer,
    MembershipCreateSerializer,
    MembershipSerializer,
    MembershipWriteSerializer,
    OrgFeatureSettingSerializer,
    OrganizationSerializer,
    RoleSerializer,
)
from .services import accept_invitation, create_organization, invite_member


class OrganizationViewSet(viewsets.ModelViewSet):
    serializer_class = OrganizationSerializer

    def get_queryset(self):
        user = self.request.user
        return (
            Organization.objects.filter(memberships__user=user, memberships__is_active=True)
            .annotate(active_member_count=Count("memberships", filter=Q(memberships__is_active=True)))
            .distinct()
        )

    def get_permissions(self):
        if self.action == "create":
            return [IsAuthenticated()]
        if self.action in {"update", "partial_update"}:
            return [HasPermission("org.edit")()]
        if self.action == "destroy":
            return [IsOrganizationAdmin()]
        return [IsOrganizationMember()]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        organization = create_organization(name=serializer.validated_data["name"], owner=request.user,
                                           **{k: v for k, v in serializer.validated_data.items() if k != "name"})
        return Response(OrganizationSerializer(organization).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get", "patch"], url_path="features")
    def features(self, request, pk=None):
        organization = self.get_object()
        setting, _ = OrgFeatureSetting.objects.get_or_create(organization=organization)
        if request.method == "PATCH":
            if not getattr(request, "membership", None) or not request.membership.is_org_admin:
                raise PermissionDenied("Only administrators may change feature settings.")
            serializer = OrgFeatureSettingSerializer(setting, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(serializer.data)
        return Response(OrgFeatureSettingSerializer(setting).data)


class RoleViewSet(TenantViewSet):
    serializer_class = RoleSerializer
    permission_classes = [HasPermission("org.roles.manage")]
    search_fields = ["name", "code"]
    filterset_fields = ["is_system"]

    def get_queryset(self):
        return Role.objects.all()

    def perform_destroy(self, instance):
        if instance.is_system:
            raise ValidationError("System roles cannot be deleted.")
        if instance.memberships.exists():
            raise ValidationError("Role is assigned to members and cannot be deleted.")
        instance.delete()


class MembershipViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.UpdateModelMixin, viewsets.GenericViewSet
):
    serializer_class = MembershipSerializer
    permission_classes = [IsOrganizationMember]
    filterset_fields = ["role_code", "is_active"]
    search_fields = ["user__email", "user__first_name", "user__last_name", "title"]
    ordering_fields = ["created_at", "role_code"]
    ordering = ["user__email"]

    def get_queryset(self):
        membership = getattr(self.request, "membership", None)
        if membership is None:
            return Membership.objects.none()
        return Membership.objects.filter(organization_id=membership.organization_id).select_related(
            "user", "organization"
        )

    def get_object(self):
        obj = super().get_object()
        # Non-admins can always retrieve themselves.
        if not self.request.membership.is_org_admin and obj.user_id != self.request.user.id:
            raise PermissionDenied("You may only view your own membership.")
        return obj

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        if not request.membership.is_org_admin and instance.user_id != request.user.id:
            raise PermissionDenied("Only administrators may change memberships.")
        if not request.membership.is_org_admin:
            # Self-service: only title may change.
            serializer = MembershipWriteSerializer(instance, data={"title": request.data.get("title", instance.title)},
                                                    partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(MembershipSerializer(instance).data)
        serializer = MembershipWriteSerializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        new_role = serializer.validated_data.get("role_code")
        if instance.is_owner and new_role and new_role != "owner":
            raise ValidationError("The organization owner role cannot be downgraded.")
        serializer.save()
        return Response(MembershipSerializer(instance).data)

    @action(detail=False, methods=["post"], url_path="invite")
    def invite(self, request):
        if not request.membership.is_org_admin and not request.membership.is_owner:
            raise PermissionDenied("Only administrators may invite members.")
        serializer = MembershipCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            invitation = invite_member(
                organization=request.membership.organization,
                email=serializer.validated_data["email"],
                role_code=serializer.validated_data["role_code"],
                invited_by=request.user,
            )
        except ValueError as exc:
            raise ValidationError(str(exc))
        return Response(InvitationSerializer(invitation).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="deactivate")
    def deactivate(self, request, pk=None):
        instance = self.get_object()
        if not request.membership.is_org_admin:
            raise PermissionDenied("Only administrators may deactivate members.")
        if instance.is_owner:
            raise ValidationError("The organization owner cannot be deactivated.")
        if instance.user_id == request.user.id:
            raise ValidationError("You cannot deactivate your own membership.")
        instance.is_active = False
        instance.save(update_fields=["is_active"])
        return Response(MembershipSerializer(instance).data)


class InvitationViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet
):
    serializer_class = InvitationSerializer
    permission_classes = [HasPermission("org.members.manage")]
    filterset_fields = ["status", "role_code"]
    search_fields = ["email"]
    ordering = ["-created_at"]

    def get_queryset(self):
        membership = getattr(self.request, "membership", None)
        if membership is None:
            return Invitation.objects.none()
        return Invitation.objects.filter(organization_id=membership.organization_id).select_related(
            "invited_by"
        )

    def create(self, request, *args, **kwargs):
        serializer = InvitationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        project = None
        project_id = serializer.validated_data.get("project")
        if project_id:
            from apps.projects.models import Project

            project = Project.objects.filter(
                id=project_id, organization_id=request.membership.organization_id
            ).first()
            if project is None:
                raise ValidationError({"project": "Project not found in this organization."})
        try:
            invitation = invite_member(
                organization=request.membership.organization,
                email=serializer.validated_data["email"],
                role_code=serializer.validated_data["role_code"],
                invited_by=request.user,
                project=project,
            )
        except ValueError as exc:
            raise ValidationError(str(exc))
        return Response(InvitationSerializer(invitation).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def revoke(self, request, pk=None):
        invitation = self.get_object()
        if invitation.status != "pending":
            raise ValidationError("Only pending invitations can be revoked.")
        invitation.status = "revoked"
        invitation.save(update_fields=["status"])
        return Response(InvitationSerializer(invitation).data)


class InvitationAcceptView(viewsets.ViewSet):
    permission_classes = [AllowAny]
    authentication_classes = []

    @action(detail=False, methods=["post"])
    def accept(self, request):
        from django.contrib.auth import get_user_model

        serializer = InvitationAcceptSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        token = serializer.validated_data["token"]

        user = request.user if request.user.is_authenticated else None
        if user is None:
            # Create or resolve an account by invitation token's target email.
            from .services import _hash  # local import to avoid cycle

            invitation = Invitation.objects.filter(token_hash=_hash(token)).first()
            if invitation is None:
                raise ValidationError({"token": "Invitation not found or no longer valid."})
            User = get_user_model()
            user = User.objects.filter(email__iexact=invitation.email).first()
            if user is None:
                password = serializer.validated_data.get("password")
                if not password:
                    raise ValidationError({"password": "A password is required to create your account."})
                user = User.objects.create_user(
                    email=invitation.email,
                    password=password,
                    first_name=serializer.validated_data.get("first_name", ""),
                    last_name=serializer.validated_data.get("last_name", ""),
                    email_verified_at=timezone.now(),
                )
        try:
            membership = accept_invitation(token=token, user=user)
        except ValueError as exc:
            raise ValidationError({"token": str(exc)})
        return Response(
            {
                "detail": "Invitation accepted.",
                "user": UserSerializer(user).data,
                "membership": MembershipSerializer(membership).data,
            }
        )
