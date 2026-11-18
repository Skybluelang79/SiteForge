"""Assistant admin."""
from django.contrib import admin

from .models import AssistantConversation, AssistantMessage


class AssistantMessageInline(admin.TabularInline):
    model = AssistantMessage
    extra = 0
    readonly_fields = ["role", "content", "model", "provider", "latency_ms", "created_at"]
    can_delete = False


@admin.register(AssistantConversation)
class AssistantConversationAdmin(admin.ModelAdmin):
    list_display = ["title", "user", "organization", "project", "updated_at"]
    list_filter = ["organization"]
    search_fields = ["title", "user__email"]
    readonly_fields = ["created_at", "updated_at"]
    inlines = [AssistantMessageInline]


@admin.register(AssistantMessage)
class AssistantMessageAdmin(admin.ModelAdmin):
    list_display = ["conversation", "role", "provider", "model", "latency_ms", "created_at"]
    list_filter = ["role", "provider"]
    search_fields = ["content"]
    readonly_fields = ["created_at"]
