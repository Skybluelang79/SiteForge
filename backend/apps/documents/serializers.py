"""Document serializers."""
from rest_framework import serializers

from apps.accounts.serializers import UserSummarySerializer

from .models import Document, DocumentAccessLog, DocumentFolder, DocumentVersion


class DocumentFolderSerializer(serializers.ModelSerializer):
    created_by = UserSummarySerializer(read_only=True)

    class Meta:
        model = DocumentFolder
        fields = ["id", "project", "name", "parent", "path", "created_by", "created_at", "updated_at"]
        read_only_fields = ["id", "path", "created_by", "created_at", "updated_at"]


class DocumentVersionSummarySerializer(serializers.ModelSerializer):
    uploaded_by = UserSummarySerializer(read_only=True)

    class Meta:
        model = DocumentVersion
        fields = [
            "id", "version_number", "original_filename", "content_type", "size_bytes",
            "checksum", "change_note", "is_current", "uploaded_by", "created_at",
        ]
        read_only_fields = fields


class DocumentVersionSerializer(serializers.ModelSerializer):
    uploaded_by = UserSummarySerializer(read_only=True)

    class Meta:
        model = DocumentVersion
        fields = [
            "id", "document", "version_number", "file", "original_filename", "content_type",
            "size_bytes", "checksum", "change_note", "uploaded_by", "is_current",
            "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "document", "version_number", "original_filename", "content_type",
            "size_bytes", "checksum", "uploaded_by", "is_current", "created_at", "updated_at",
        ]


class DocumentVersionUploadSerializer(serializers.Serializer):
    file = serializers.FileField()
    change_note = serializers.CharField(required=False, allow_blank=True, default="")


class DocumentSerializer(serializers.ModelSerializer):
    created_by = UserSummarySerializer(read_only=True)
    reviewed_by = UserSummarySerializer(read_only=True)
    current_version = DocumentVersionSummarySerializer(read_only=True)
    folder_name = serializers.CharField(source="folder.name", read_only=True)

    class Meta:
        model = Document
        fields = [
            "id", "project", "folder", "folder_name", "title", "description", "document_type",
            "status", "confidentiality", "tags", "metadata", "current_version", "created_by",
            "reviewed_by", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "current_version", "created_by", "reviewed_by", "created_at", "updated_at"]


class DocumentAccessLogSerializer(serializers.ModelSerializer):
    user = UserSummarySerializer(read_only=True)

    class Meta:
        model = DocumentAccessLog
        fields = ["id", "document", "version", "user", "ip_address", "action", "created_at"]
        read_only_fields = fields
