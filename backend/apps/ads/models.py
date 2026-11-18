"""Advertising slots managed in Django admin or via the API."""
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from apps.common.models import Base


class Advertisement(Base):
    """A house ad or an externally supplied ad snippet.

    ``organization`` is null for platform-wide placements (landing page, login)
    and set for tenant-scoped placements (dashboard, canvas workspace).
    """

    PLACEMENT_CHOICES = [
        ("landing_hero", "Landing hero"),
        ("landing_strip", "Landing strip"),
        ("login_aside", "Login aside"),
        ("dashboard_rail", "Dashboard rail"),
        ("dashboard_inline", "Dashboard inline"),
        ("canvas_sidebar", "Canvas sidebar"),
    ]
    TYPE_CHOICES = [
        ("house", "House ad"),
        ("external", "External snippet"),
    ]

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="advertisements",
        help_text="Leave blank for platform-wide placements.",
    )
    name = models.CharField(max_length=160, help_text="Internal campaign name.")
    placement = models.CharField(max_length=32, choices=PLACEMENT_CHOICES, db_index=True)
    ad_type = models.CharField(max_length=12, choices=TYPE_CHOICES, default="house")
    sponsor = models.CharField(max_length=120, blank=True)
    headline = models.CharField(max_length=180, blank=True)
    body = models.TextField(blank=True)
    cta_label = models.CharField(max_length=60, blank=True, default="Learn more")
    link_url = models.URLField(blank=True)
    image = models.ImageField(upload_to="ads/", blank=True, null=True)
    image_url = models.URLField(blank=True, help_text="Optional remote creative image.")
    html_snippet = models.TextField(
        blank=True,
        help_text="Third-party ad markup. Rendered inside a sandboxed iframe.",
    )
    accent = models.CharField(
        max_length=7,
        default="#f59e0b",
        help_text="Hex accent colour used by house ad cards.",
    )
    priority = models.PositiveSmallIntegerField(default=10, validators=[MinValueValidator(0)])
    is_active = models.BooleanField(default=True, db_index=True)
    start_at = models.DateTimeField(null=True, blank=True)
    end_at = models.DateTimeField(null=True, blank=True)
    impressions = models.PositiveIntegerField(default=0)
    clicks = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-priority", "-created_at"]
        indexes = [
            models.Index(fields=["placement", "is_active"], name="idx_ad_placement_active"),
            models.Index(fields=["organization", "placement"], name="idx_ad_org_placement"),
        ]

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.name} ({self.get_placement_display()})"

    @property
    def is_live(self) -> bool:
        now = timezone.now()
        if not self.is_active:
            return False
        if self.start_at and self.start_at > now:
            return False
        if self.end_at and self.end_at < now:
            return False
        return True


class AdEvent(Base):
    """Impression/click telemetry for a placement."""

    EVENT_CHOICES = [
        ("impression", "Impression"),
        ("click", "Click"),
    ]

    advertisement = models.ForeignKey(
        Advertisement, on_delete=models.CASCADE, related_name="events"
    )
    event_type = models.CharField(max_length=12, choices=EVENT_CHOICES, db_index=True)
    session_key = models.CharField(max_length=80, blank=True)
    referrer = models.CharField(max_length=500, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["advertisement", "event_type"], name="idx_adevent_ad_type"),
        ]

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.event_type}:{self.advertisement_id}"
