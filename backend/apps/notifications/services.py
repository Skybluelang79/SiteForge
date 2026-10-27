"""Notification creation and real-time fan-out."""
import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import transaction

from .models import Notification

logger = logging.getLogger("apps.notifications")


def notify(
    *,
    recipient,
    verb,
    title,
    body="",
    level="info",
    organization=None,
    project=None,
    target_type="",
    target_id="",
    url="",
    metadata=None,
):
    """Create an in-app notification and broadcast it to the user's socket."""
    prefs = getattr(recipient, "notification_preferences", None)
    if prefs is not None and not prefs.in_app_enabled:
        return None

    notification = Notification.objects.create(
        recipient=recipient,
        organization=organization,
        project=project,
        verb=verb,
        title=title,
        body=body,
        level=level,
        target_type=target_type,
        target_id=str(target_id or ""),
        url=url,
        metadata=metadata or {},
    )
    payload = {
        "type": "notification.message",
        "message": {
            "type": "notification",
            "event": verb,
            "payload": {
                "id": str(notification.id),
                "title": title,
                "body": body,
                "level": level,
                "verb": verb,
                "target_type": target_type,
                "target_id": str(target_id or ""),
                "url": url,
                "created_at": notification.created_at.isoformat(),
            },
        },
    }

    def _send():
        try:
            channel_layer = get_channel_layer()
            if channel_layer is None:
                return
            async_to_sync(channel_layer.group_send)(f"notifications_{recipient.pk}", payload)
        except Exception:  # pragma: no cover - real-time must not break writes
            logger.exception("notification_broadcast_failed")

    transaction.on_commit(_send)
    return notification


def notify_project_members(*, project, verb, title, body="", exclude_user=None, **kwargs):
    """Fan out a notification to active project members (optionally excluding one)."""
    from apps.projects.models import ProjectMember

    members = (
        ProjectMember.objects.filter(project=project, is_active=True)
        .select_related("user", "user__notification_preferences")
        .exclude(user=exclude_user)
    )
    created = []
    for member in members:
        created.append(
            notify(
                recipient=member.user,
                verb=verb,
                title=title,
                body=body,
                organization=project.organization,
                project=project,
                **kwargs,
            )
        )
    return created
