"""API credentials, webhook signing and delivery services."""
import hashlib
import hmac
import json
import secrets
import uuid
from datetime import timedelta

import httpx
from django.utils import timezone

from .models import ApiApplication, WebhookDelivery, WebhookEvent, WebhookSubscription

MAX_ATTEMPTS = 5
REQUEST_TIMEOUT = 10.0


def _hash_secret(raw_secret):
    return hashlib.sha256(raw_secret.encode("utf-8")).hexdigest()


def issue_credentials(application):
    client_id = secrets.token_hex(16)
    raw_secret = secrets.token_urlsafe(40)
    application.client_id = client_id
    application.client_secret_hash = _hash_secret(raw_secret)
    application.save(update_fields=["client_id", "client_secret_hash", "updated_at"])
    return client_id, raw_secret


def verify_secret(application, raw_secret):
    if not application.client_secret_hash:
        return False
    return hmac.compare_digest(application.client_secret_hash, _hash_secret(raw_secret))


def generate_webhook_secret():
    return secrets.token_urlsafe(32)


def _signature(secret, body):
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def dispatch_event(*, organization, event_type, payload, project=None):
    event = WebhookEvent.objects.create(
        organization=organization,
        event_id=uuid.uuid4(),
        event_type=event_type,
        project=project,
        payload=payload,
    )
    subscriptions = WebhookSubscription.objects.filter(
        organization=organization, is_active=True
    )
    deliveries = []
    for subscription in subscriptions:
        if event_type not in (subscription.event_types or []):
            continue
        delivery, _ = WebhookDelivery.objects.get_or_create(
            subscription=subscription,
            event=event,
            defaults={"status": "pending"},
        )
        deliveries.append(delivery)

    from .tasks import deliver_webhook

    for delivery in deliveries:
        try:
            deliver_webhook.delay(str(delivery.id))
        except Exception:
            pass
    return event, deliveries


def deliver(delivery_id):
    from .tasks import deliver_webhook

    delivery = (
        WebhookDelivery.objects.select_related("subscription", "event")
        .filter(pk=delivery_id)
        .first()
    )
    if delivery is None or delivery.status in {"success", "exhausted"}:
        return delivery

    if not delivery.subscription.is_active:
        delivery.status = "exhausted"
        delivery.error_message = "Subscription is disabled."
        delivery.save(update_fields=["status", "error_message"])
        return delivery

    event = delivery.event
    payload = {
        "event_id": str(event.event_id),
        "event_type": event.event_type,
        "organization_id": str(event.organization_id),
        "project_id": str(event.project_id) if event.project_id else None,
        "payload": event.payload,
        "created_at": event.created_at.isoformat(),
    }
    body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "SiteForge-Webhooks/1.0",
        "X-SiteForge-Event": event.event_type,
        "X-SiteForge-Delivery": str(event.event_id),
        "X-SiteForge-Signature": f"sha256={_signature(delivery.subscription.secret, body)}",
    }

    delivery.attempt_count += 1
    started = timezone.now()
    try:
        response = httpx.post(
            delivery.subscription.target_url,
            content=body,
            headers=headers,
            timeout=REQUEST_TIMEOUT,
        )
        duration = int((timezone.now() - started).total_seconds() * 1000)
        delivery.response_status = response.status_code
        delivery.response_body = response.text[:4000]
        delivery.duration_ms = duration
        if 200 <= response.status_code < 300:
            delivery.status = "success"
            delivery.delivered_at = timezone.now()
            delivery.error_message = ""
            subscription = delivery.subscription
            subscription.last_success_at = timezone.now()
            subscription.failure_count = 0
            subscription.save(update_fields=["last_success_at", "failure_count"])
        else:
            delivery.status = "failed"
            delivery.error_message = f"HTTP {response.status_code}"
            _handle_failure(delivery)
    except Exception as exc:
        delivery.status = "failed"
        delivery.error_message = str(exc)[:500]
        _handle_failure(delivery)

    delivery.save(
        update_fields=[
            "status", "attempt_count", "response_status", "response_body",
            "duration_ms", "delivered_at", "error_message", "next_attempt_at",
        ]
    )

    if delivery.status == "failed" and delivery.attempt_count < MAX_ATTEMPTS:
        delivery.status = "retrying"
        delivery.next_attempt_at = timezone.now() + timedelta(
            seconds=min(3600, 60 * (2 ** delivery.attempt_count))
        )
        delivery.save(update_fields=["status", "next_attempt_at"])
        try:
            deliver_webhook.apply_async(args=[str(delivery.id)], countdown=60 * (2 ** delivery.attempt_count))
        except Exception:
            pass
    elif delivery.status == "failed":
        delivery.status = "exhausted"
        delivery.save(update_fields=["status"])
    return delivery


def _handle_failure(delivery):
    subscription = delivery.subscription
    subscription.failure_count += 1
    subscription.last_failure_at = timezone.now()
    update_fields = ["failure_count", "last_failure_at"]
    if subscription.failure_count >= 20:
        subscription.is_active = False
        subscription.disabled_at = timezone.now()
        update_fields.extend(["is_active", "disabled_at"])
    subscription.save(update_fields=update_fields)
