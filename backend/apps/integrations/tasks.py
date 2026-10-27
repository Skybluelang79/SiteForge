"""Celery tasks for webhook delivery."""
from celery import shared_task
from django.utils import timezone

from .models import WebhookDelivery
from .services import deliver


@shared_task
def deliver_webhook(delivery_id):
    delivery = deliver(delivery_id)
    return {
        "delivery_id": str(delivery_id),
        "status": getattr(delivery, "status", "missing"),
    }


@shared_task
def retry_pending_deliveries():
    now = timezone.now()
    pending = WebhookDelivery.objects.filter(
        status__in=["pending", "retrying"]
    ).filter(next_attempt_at__lte=now)
    delivered = 0
    for delivery in pending.iterator():
        deliver(str(delivery.id))
        delivered += 1
    return {"deliveries": delivered}
