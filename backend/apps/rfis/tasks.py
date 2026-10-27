"""Background sweeps for overdue RFIs and submittals."""
from celery import shared_task
from django.utils import timezone

from apps.notifications.services import notify

from .models import RFI, Submittal


@shared_task
def sweep_due_dates():
    today = timezone.now().date()
    overdue_rfis = RFI.objects.filter(
        due_date__lt=today,
        status__in=["open", "draft", "answered"],
    ).select_related("project", "assigned_to", "created_by")

    rfi_count = 0
    for rfi in overdue_rfis:
        rfi.status = "overdue"
        rfi.save(update_fields=["status", "updated_at"])
        rfi_count += 1
        for recipient in {rfi.assigned_to, rfi.created_by} - {None}:
            notify(
                recipient=recipient,
                verb="rfi.overdue",
                title=f"RFI {rfi.number} is overdue",
                body=rfi.subject,
                level="warning",
                organization=rfi.project.organization,
                project=rfi.project,
                target_type="RFI",
                target_id=rfi.id,
            )

    overdue_submittals = Submittal.objects.filter(
        due_date__lt=today,
        status__in=["draft", "submitted", "under_review"],
    ).select_related("project", "submitted_by", "reviewer")
    for submittal in overdue_submittals:
        for recipient in {submittal.submitted_by, submittal.reviewer} - {None}:
            notify(
                recipient=recipient,
                verb="submittal.overdue",
                title=f"Submittal {submittal.number} is overdue",
                body=submittal.title,
                level="warning",
                organization=submittal.project.organization,
                project=submittal.project,
                target_type="Submittal",
                target_id=submittal.id,
            )
    return {"overdue_rfis": rfi_count, "overdue_submittals": overdue_submittals.count()}
