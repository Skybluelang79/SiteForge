"""Organizations admin."""
from django.contrib import admin

from .models import Invitation, Membership, OrgFeatureSetting, Organization, Role


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "is_active", "created_at"]
    search_fields = ["name", "slug", "legal_name"]
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ["user", "organization", "role_code", "is_active", "is_owner"]
    list_filter = ["role_code", "is_active", "is_owner"]
    search_fields = ["user__email", "organization__name"]


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ["name", "code", "organization", "is_system"]
    list_filter = ["is_system"]


@admin.register(Invitation)
class InvitationAdmin(admin.ModelAdmin):
    list_display = ["email", "organization", "role_code", "status", "expires_at"]
    list_filter = ["status", "role_code"]
    search_fields = ["email"]


@admin.register(OrgFeatureSetting)
class OrgFeatureSettingAdmin(admin.ModelAdmin):
    list_display = ["organization", "updated_at"]
