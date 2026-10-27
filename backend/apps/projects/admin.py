"""Projects admin."""
from django.contrib import admin

from .models import ActivityFeedEntry, Contract, Milestone, Project, ProjectMember


class ProjectMemberInline(admin.TabularInline):
    model = ProjectMember
    extra = 0


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ["name", "number", "organization", "status", "contract_value", "start_date"]
    list_filter = ["status", "project_type", "organization"]
    search_fields = ["name", "number", "client_name"]
    inlines = [ProjectMemberInline]


@admin.register(Milestone)
class MilestoneAdmin(admin.ModelAdmin):
    list_display = ["name", "project", "due_date", "status"]
    list_filter = ["status"]


@admin.register(Contract)
class ContractAdmin(admin.ModelAdmin):
    list_display = ["name", "number", "project", "contract_type", "status", "revised_value"]
    list_filter = ["status", "contract_type"]


@admin.register(ActivityFeedEntry)
class ActivityFeedEntryAdmin(admin.ModelAdmin):
    list_display = ["verb", "project", "actor", "created_at"]
    list_filter = ["verb"]
