"""Celery tasks for report exports and daily metric snapshots."""
from celery import shared_task

from apps.organizations.models import Organization

from .models import ExportJob
from .services import collect_metrics_for_org, generate_export


@shared_task
def run_export_job(export_job_id):
    job = ExportJob.objects.filter(pk=export_job_id).first()
    if job is None:
        return {"status": "missing", "export_job_id": str(export_job_id)}
    generate_export(job)
    return {"status": job.status, "export_job_id": str(job.id), "row_count": job.row_count}


@shared_task
def collect_daily_metrics():
    total = 0
    for organization in Organization.objects.filter(is_active=True, deleted_at__isnull=True):
        total += collect_metrics_for_org(organization)
    return {"snapshots": total}
