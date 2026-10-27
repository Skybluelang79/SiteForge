"""Drawing serializers."""
from rest_framework import serializers

from apps.accounts.serializers import UserSummarySerializer

from .models import Drawing, DrawingReview, DrawingRevision, DrawingSet


class DrawingSetSerializer(serializers.ModelSerializer):
    class Meta:
        model = DrawingSet
        fields = ["id", "project", "name", "discipline", "description", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]


class DrawingRevisionSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = DrawingRevision
        fields = [
            "id", "revision_code", "revision_date", "review_status",
            "original_filename", "created_at",
        ]
        read_only_fields = fields


class DrawingSerializer(serializers.ModelSerializer):
    created_by = UserSummarySerializer(read_only=True)
    current_revision = DrawingRevisionSummarySerializer(read_only=True)
    drawing_set_name = serializers.CharField(source="drawing_set.name", read_only=True)

    class Meta:
        model = Drawing
        fields = [
            "id", "project", "drawing_set", "drawing_set_name", "title", "number",
            "discipline", "status", "current_revision", "created_by", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "current_revision", "created_by", "created_at", "updated_at"]

    def validate_number(self, value):
        request = self.context.get("request")
        project = self.initial_data.get("project")
        if not request or not project:
            return value
        qs = Drawing.objects.filter(project_id=project, number=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("A drawing with this number already exists on the project.")
        return value


class DrawingRevisionSerializer(serializers.ModelSerializer):
    uploaded_by = UserSummarySerializer(read_only=True)
    reviewed_by = UserSummarySerializer(read_only=True)

    class Meta:
        model = DrawingRevision
        fields = [
            "id", "drawing", "revision_code", "revision_date", "file", "original_filename",
            "content_type", "size_bytes", "checksum", "change_summary", "review_status",
            "reviewed_by", "reviewed_at", "review_comments", "uploaded_by",
            "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "original_filename", "content_type", "size_bytes", "checksum",
            "uploaded_by", "reviewed_by", "reviewed_at", "created_at", "updated_at",
        ]


class DrawingRevisionUploadSerializer(serializers.Serializer):
    file = serializers.FileField()
    revision_code = serializers.CharField(max_length=20)
    revision_date = serializers.DateField()
    change_summary = serializers.CharField(required=False, allow_blank=True, default="")


class DrawingReviewSerializer(serializers.ModelSerializer):
    reviewer = UserSummarySerializer(read_only=True)
    reviewer_id = serializers.UUIDField(write_only=True, required=False, allow_null=True)

    class Meta:
        model = DrawingReview
        fields = [
            "id", "revision", "reviewer", "reviewer_id", "decision", "comments",
            "due_date", "decided_at", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "reviewer", "created_at", "updated_at"]


class DrawingDecisionSerializer(serializers.Serializer):
    decision = serializers.ChoiceField(choices=DrawingRevision.REVIEW_STATUS_CHOICES)
    comments = serializers.CharField(required=False, allow_blank=True, default="")
