"""Project activity feed helpers."""
from .models import ActivityFeedEntry, Project


def record_activity(*, project: Project, actor, verb: str, summary: str = "", target_type="", target_id="",
                    metadata=None):
    return ActivityFeedEntry.objects.create(
        project=project,
        organization_id=project.organization_id,
        actor=actor if getattr(actor, "is_authenticated", False) else None,
        verb=verb,
        summary=summary[:400],
        target_type=target_type,
        target_id=str(target_id),
        metadata=metadata or {},
    )
