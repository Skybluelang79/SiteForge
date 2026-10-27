"""Audit recording helpers."""
import logging

from .models import AuditEvent

logger = logging.getLogger("apps.audit")


def record_audit_event(
    *,
    action: str,
    organization=None,
    actor=None,
    target_type: str = "",
    target_id: str = "",
    project=None,
    metadata=None,
    request=None,
):
    """Create an audit event. Never raise from an audit failure."""
    try:
        ip = None
        ua = ""
        if request is not None:
            ip = request.META.get("REMOTE_ADDR")
            ua = request.META.get("HTTP_USER_AGENT", "")[:400]
        return AuditEvent.objects.create(
            organization=organization,
            actor=actor if getattr(actor, "is_authenticated", False) else None,
            action=action,
            target_type=target_type,
            target_id=str(target_id),
            project=project,
            metadata=metadata or {},
            ip_address=ip,
            user_agent=ua,
        )
    except Exception:  # pragma: no cover - audit must not break the request
        logger.exception("audit_write_failed", extra={"action": action})
        return None
