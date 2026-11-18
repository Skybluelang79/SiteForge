"""Advertising admin."""
from django.contrib import admin

from .models import AdEvent, Advertisement


class AdEventInline(admin.TabularInline):
    model = AdEvent
    extra = 0
    readonly_fields = ["event_type", "session_key", "referrer", "created_at"]
    can_delete = False


@admin.register(Advertisement)
class AdvertisementAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "placement",
        "ad_type",
        "organization",
        "is_active",
        "priority",
        "impressions",
        "clicks",
        "start_at",
        "end_at",
    ]
    list_filter = ["placement", "ad_type", "is_active", "organization"]
    search_fields = ["name", "sponsor", "headline"]
    readonly_fields = ["impressions", "clicks", "created_at", "updated_at"]
    inlines = [AdEventInline]


@admin.register(AdEvent)
class AdEventAdmin(admin.ModelAdmin):
    list_display = ["advertisement", "event_type", "created_at"]
    list_filter = ["event_type"]
    search_fields = ["advertisement__name"]
    readonly_fields = ["advertisement", "event_type", "session_key", "referrer", "created_at"]
