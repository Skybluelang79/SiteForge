from rest_framework import serializers

from apps.accounts.serializers import UserSummarySerializer

from .models import CanvasBoard


class CanvasBoardSerializer(serializers.ModelSerializer):
    created_by = UserSummarySerializer(read_only=True)

    class Meta:
        model = CanvasBoard
        fields = [
            "id",
            "project",
            "name",
            "state",
            "created_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_by", "created_at", "updated_at"]
