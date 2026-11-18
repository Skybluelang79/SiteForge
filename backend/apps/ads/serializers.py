"""Advertising serializers."""
from rest_framework import serializers

from .models import Advertisement


class AdvertisementSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()
    placement_label = serializers.CharField(source="get_placement_display", read_only=True)

    class Meta:
        model = Advertisement
        fields = [
            "id",
            "name",
            "placement",
            "placement_label",
            "ad_type",
            "sponsor",
            "headline",
            "body",
            "cta_label",
            "link_url",
            "image_url",
            "html_snippet",
            "accent",
            "priority",
        ]

    def get_image_url(self, obj):
        if obj.image:
            request = self.context.get("request")
            url = obj.image.url
            return request.build_absolute_uri(url) if request else url
        return obj.image_url or ""
