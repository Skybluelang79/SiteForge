"""Drawing revision services."""
import hashlib

from django.db import transaction

from .models import DrawingRevision


def calculate_checksum(uploaded_file):
    digest = hashlib.sha256()
    for chunk in uploaded_file.chunks():
        digest.update(chunk)
    uploaded_file.seek(0)
    return digest.hexdigest()


@transaction.atomic
def add_revision(*, drawing, uploaded_file, revision_code, revision_date, change_summary="", uploaded_by=None):
    revision = DrawingRevision.objects.create(
        drawing=drawing,
        revision_code=revision_code,
        revision_date=revision_date,
        file=uploaded_file,
        original_filename=getattr(uploaded_file, "name", "")[:400],
        content_type=getattr(uploaded_file, "content_type", ""),
        size_bytes=getattr(uploaded_file, "size", 0),
        checksum=calculate_checksum(uploaded_file),
        change_summary=change_summary,
        uploaded_by=uploaded_by,
    )
    drawing.current_revision = revision
    if drawing.status == "draft":
        drawing.status = "issued"
    drawing.save(update_fields=["current_revision", "status", "updated_at"])
    return revision
