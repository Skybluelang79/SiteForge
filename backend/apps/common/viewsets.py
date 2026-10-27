"""Shared DRF viewsets, filters and mixins."""
from django.db import models
from django.db.models import Q
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, permissions, viewsets
from rest_framework.exceptions import PermissionDenied

from .drf_permissions import HasPermission, IsOrganizationMember


class MappedPermissionMixin:
    """Resolve permission keys per action.

    Viewsets define ``action_permissions`` mapping action names (or the generic
    ``read`` / ``write`` fallbacks) to tuples of permission keys.
    """

    action_permissions: dict[str, tuple[str, ...]] = {}

    def get_permissions(self):
        if not self.action_permissions:
            return super().get_permissions()
        if self.action in self.action_permissions:
            keys = self.action_permissions[self.action]
        elif self.request.method in permissions.SAFE_METHODS:
            keys = self.action_permissions.get("read", ())
        else:
            keys = self.action_permissions.get("write", ())
        if keys:
            return [HasPermission(*keys)()]
        return [IsOrganizationMember()]


class OrgScopedQuerySetMixin:
    """Scope every queryset to the active organization + project access.

    Subclasses set:
      - `org_field`: attribute/path on the model pointing at the organization
        (default "organization_id").
      - `project_field`: attribute/path to the project (optional).
    """

    org_field = "organization_id"
    project_field = "project_id"

    def get_active_org_id(self):
        membership = getattr(self.request, "membership", None)
        return membership.organization_id if membership else None

    def scope_queryset(self, queryset):
        org_id = self.get_active_org_id()
        if org_id is None:
            return queryset.none()
        queryset = queryset.filter(**{self.org_field: org_id})
        return queryset

    def get_queryset(self):
        queryset = super().get_queryset()
        return self.scope_queryset(queryset)


class ProjectScopedQuerySetMixin(OrgScopedQuerySetMixin):
    """Additionally filter by `?project=` / `?project_id=` query param."""

    project_query_param = "project"

    def scope_queryset(self, queryset):
        queryset = super().scope_queryset(queryset)
        project_id = self.request.query_params.get(self.project_query_param) or self.request.query_params.get(
            "project_id"
        )
        if project_id:
            queryset = queryset.filter(**{self.project_field: project_id})

        # Enforce project-level access for non-admins: public projects or
        # projects the user is an active member of.
        membership = getattr(self.request, "membership", None)
        if membership is not None and not membership.is_org_admin:
            project_path = self.project_field
            if project_path.endswith("_id"):
                project_path = project_path[:-3]
            queryset = queryset.filter(
                Q(**{f"{project_path}__is_public": True})
                | Q(
                    **{
                        f"{project_path}__members__user": self.request.user,
                        f"{project_path}__members__is_active": True,
                    }
                )
            ).distinct()
        return queryset


class BaseModelViewSet(viewsets.ModelViewSet):
    """ViewSet with filtering, search, ordering and org scoping."""

    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    ordering = ["-created_at"]
    permission_classes = [HasPermission("projects.view")]

    def perform_create(self, serializer):
        serializer.save()


class TenantViewSet(OrgScopedQuerySetMixin, BaseModelViewSet):
    """Organization-scoped CRUD viewset."""


class ProjectTenantViewSet(ProjectScopedQuerySetMixin, BaseModelViewSet):
    """Organization + project scoped CRUD viewset."""


class SiteForgeViewSet(MappedPermissionMixin, viewsets.ModelViewSet):
    """Standard CRUD viewset with filtering, search and ordering."""

    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    ordering = ["-created_at"]

    def get_queryset(self):
        queryset = getattr(self, "queryset", None)
        if queryset is not None:
            return queryset.all() if hasattr(queryset, "all") else queryset
        serializer_class = getattr(self, "serializer_class", None)
        model = getattr(getattr(serializer_class, "Meta", None), "model", None)
        if model is not None:
            return model.objects.all()
        return super().get_queryset()


class OrgScopedViewSet(OrgScopedQuerySetMixin, SiteForgeViewSet):
    """Organization-scoped CRUD viewset."""


class ProjectScopedViewSet(ProjectScopedQuerySetMixin, SiteForgeViewSet):
    """Project-scoped CRUD viewset (scope derived through the project FK)."""

    org_field = "project__organization_id"

    def perform_create(self, serializer):
        project = serializer.validated_data.get("project")
        if project is not None and not self.request.user.can_access_project(project):
            raise PermissionDenied("You do not have access to this project.")
        serializer.save()
