"""Document services: versioning, checksums and access logging."""
import hashlib

from django.db import transaction

from .models import DocumentAccessLog, DocumentVersion


def calculate_checksum(uploaded_file):
    digest = hashlib.sha256()
    for chunk in uploaded_file.chunks():
        digest.update(chunk)
    uploaded_file.seek(0)
    return digest.hexdigest()


@transaction.atomic
def add_version(*, document, uploaded_file, uploaded_by=None, change_note="", content_type=""):
    """Create a new immutable version and make it current."""
    last = document.versions.order_by("-version_number").first()
    version = DocumentVersion.objects.create(
        document=document,
        version_number=(last.version_number + 1) if last else 1,
        file=uploaded_file,
        original_filename=getattr(uploaded_file, "name", "")[:400],
        content_type=content_type or getattr(uploaded_file, "content_type", ""),
        size_bytes=getattr(uploaded_file, "size", 0),
        checksum=calculate_checksum(uploaded_file),
        change_note=change_note,
        uploaded_by=uploaded_by,
        is_current=True,
    )
    document.versions.exclude(pk=version.pk).update(is_current=False)
    document.current_version = version
    document.save(update_fields=["current_version", "updated_at"])
    return version


def log_access(*, document, version, user, request=None, action="download"):
    return DocumentAccessLog.objects.create(
        document=document,
        version=version,
        user=user if getattr(user, "is_authenticated", False) else None,
        ip_address=request.META.get("REMOTE_ADDR") if request else None,
        action=action,
    )
