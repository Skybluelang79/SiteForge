"""Shared DRF permission classes enforcing tenancy and role permissions."""
from rest_framework import permissions

from .permissions import permissions_for_role


class _PermissionEnforcer(permissions.BasePermission):
    """Require one or more platform permission keys for the active organization."""

    required: set[str] = set()

    def has_permission(self, request, view):
        membership = getattr(request, "membership", None)
        if membership is None:
            return False
        if membership.is_org_admin:
            return True
        granted = set(membership.effective_permissions)
        return self.required.issubset(granted)


def HasPermission(*required):
    """Factory: returns a permission class requiring the given permission keys.

    Usage: ``permission_classes = [HasPermission("projects.view")]``
    """
    return type(
        "HasPermission",
        (_PermissionEnforcer,),
        {"required": set(required), "__doc__": f"Requires {sorted(required)}"},
    )


class RequireAnyPermission(permissions.BasePermission):
    """Pass when the membership has any one of the configured keys."""

    def __init__(self, *required):
        self.required = set(required)

    def has_permission(self, request, view):
        membership = getattr(request, "membership", None)
        if membership is None:
            return False
        if membership.is_org_admin:
            return True
        granted = set(membership.effective_permissions)
        return bool(self.required & granted)


class IsOrganizationMember(permissions.BasePermission):
    def has_permission(self, request, view):
        return getattr(request, "membership", None) is not None


class IsOrganizationAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        membership = getattr(request, "membership", None)
        return membership is not None and membership.is_org_admin


class IsProjectMember(permissions.BasePermission):
    """Object-level: user must be a member of the object's project."""

    def has_object_permission(self, request, view, obj):
        project = getattr(obj, "project", None)
        if project is None:
            return False
        return request.user.can_access_project(project)


class HasProjectPermission(permissions.BasePermission):
    """Object-level permission key check against project membership."""

    def __init__(self, *required):
        self.required = set(required)

    def has_object_permission(self, request, view, obj):
        project = getattr(obj, "project", None)
        if project is None:
            return False
        if not request.user.can_access_project(project):
            return False
        membership = getattr(request, "membership", None)
        if membership and membership.is_org_admin:
            return True
        project_role = request.user.project_role(project)
        granted = set(permissions_for_role(project_role))
        if membership:
            granted |= set(membership.effective_permissions)
        return self.required.issubset(granted) or not self.required


class ReadOnlyOrPermission(permissions.BasePermission):
    """Authenticated read for anyone in the org; writes require given keys."""

    write_permissions: set[str] = set()

    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return getattr(request, "membership", None) is not None
        membership = getattr(request, "membership", None)
        if membership is None:
            return False
        if membership.is_org_admin:
            return True
        granted = set(membership.effective_permissions)
        return self.write_permissions.issubset(granted)
