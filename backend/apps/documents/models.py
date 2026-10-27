"""Document management: folders, documents, versions, metadata and access."""
from django.contrib.auth import get_user_model
from django.db import models

from apps.common.models import Base

User = get_user_model()


class DocumentFolder(Base):
    project = models.ForeignKey(
        "projects.Project", on_delete=models.CASCADE, related_name="document_folders"
    )
    name = models.CharField(max_length=255)
    parent = models.ForeignKey(
        "self", on_delete=models.CASCADE, null=True, blank=True, related_name="children"
    )
    path = models.CharField(max_length=1024, blank=True, db_index=True)
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="folders_created"
    )

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["project", "parent", "name"], name="uniq_folder_project_parent_name"
            )
        ]

    def __str__(self) -> str:  # pragma: no cover
        return self.name


class Document(Base):
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("in_review", "In Review"),
        ("approved", "Approved"),
        ("superseded", "Superseded"),
        ("archived", "Archived"),
    ]
    CONFIDENTIALITY_CHOICES = [
        ("standard", "Standard"),
        ("confidential", "Confidential"),
        ("restricted", "Restricted"),
    ]

    project = models.ForeignKey("projects.Project", on_delete=models.CASCADE, related_name="documents")
    folder = models.ForeignKey(
        DocumentFolder, on_delete=models.SET_NULL, null=True, blank=True, related_name="documents"
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    document_type = models.CharField(max_length=80, blank=True, db_index=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft", db_index=True)
    confidentiality = models.CharField(
        max_length=20, choices=CONFIDENTIALITY_CHOICES, default="standard", db_index=True
    )
    tags = models.JSONField(default=list, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    current_version = models.ForeignKey(
        "DocumentVersion", on_delete=models.SET_NULL, null=True, blank=True, related_name="current_for"
    )
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="documents_created"
    )
    reviewed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="documents_reviewed"
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["project", "status"], name="idx_doc_project_status"),
            models.Index(fields=["project", "document_type"], name="idx_doc_project_type"),
            models.Index(fields=["project", "confidentiality"], name="idx_doc_project_conf"),
        ]

    def __str__(self) -> str:  # pragma: no cover
        return self.title


class DocumentVersion(Base):
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name="versions")
    version_number = models.PositiveIntegerField()
    file = models.FileField(upload_to="documents/%Y/%m/")
    original_filename = models.CharField(max_length=400)
    content_type = models.CharField(max_length=120, blank=True)
    size_bytes = models.BigIntegerField(default=0)
    checksum = models.CharField(max_length=64, blank=True, db_index=True)
    change_note = models.CharField(max_length=400, blank=True)
    uploaded_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="document_versions_uploaded"
    )
    is_current = models.BooleanField(default=False, db_index=True)

    class Meta:
        ordering = ["-version_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["document", "version_number"], name="uniq_doc_version_number"
            )
        ]
        indexes = [models.Index(fields=["document", "-version_number"], name="idx_docver_doc_number")]

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.document_id} v{self.version_number}"


class DocumentAccessLog(Base):
    """Record every download for audit and access reporting."""

    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name="access_logs")
    version = models.ForeignKey(
        DocumentVersion, on_delete=models.SET_NULL, null=True, blank=True, related_name="access_logs"
    )
    user = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="document_access_logs"
    )
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    action = models.CharField(max_length=40, default="download")

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["document", "-created_at"], name="idx_doclog_doc_created")]
