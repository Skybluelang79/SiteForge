"""Daily site reports, labour, weather, equipment, photos and observations."""
from django.contrib.auth import get_user_model
from django.db import models

from apps.common.models import Base, MoneyField

User = get_user_model()


class DailyLog(Base):
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("submitted", "Submitted"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]

    project = models.ForeignKey("projects.Project", on_delete=models.CASCADE, related_name="daily_logs")
    log_date = models.DateField(db_index=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft", db_index=True)
    weather_summary = models.CharField(max_length=255, blank=True)
    temperature_low_c = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
    temperature_high_c = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
    precipitation_mm = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    wind_speed_kph = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    work_activities = models.TextField(blank=True)
    delays = models.TextField(blank=True)
    safety_notes = models.TextField(blank=True)
    visitors = models.TextField(blank=True)
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="daily_logs_created"
    )
    approved_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="daily_logs_approved"
    )
    approved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-log_date"]
        constraints = [
            models.UniqueConstraint(fields=["project", "log_date"], name="uniq_dailylog_project_date")
        ]
        indexes = [
            models.Index(fields=["project", "-log_date"], name="idx_dailylog_project_date"),
            models.Index(fields=["project", "status"], name="idx_dailylog_project_status"),
        ]

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.project_id} {self.log_date}"


class LabourEntry(Base):
    daily_log = models.ForeignKey(DailyLog, on_delete=models.CASCADE, related_name="labour_entries")
    trade = models.CharField(max_length=120)
    company = models.CharField(max_length=255, blank=True)
    worker_count = models.PositiveIntegerField(default=0)
    hours_worked = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    overtime_hours = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    hourly_rate = MoneyField(default=0)
    notes = models.CharField(max_length=400, blank=True)

    class Meta:
        ordering = ["trade"]
        indexes = [models.Index(fields=["daily_log"], name="idx_labour_dailylog")]

    @property
    def total_cost(self):
        return (self.hours_worked * self.hourly_rate) + (self.overtime_hours * self.hourly_rate * 2)


class EquipmentEntry(Base):
    daily_log = models.ForeignKey(DailyLog, on_delete=models.CASCADE, related_name="equipment_entries")
    equipment_name = models.CharField(max_length=255)
    equipment_code = models.CharField(max_length=80, blank=True)
    owner = models.CharField(max_length=255, blank=True)
    hours_used = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    idle_hours = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    cost_per_hour = MoneyField(default=0)
    notes = models.CharField(max_length=400, blank=True)

    class Meta:
        ordering = ["equipment_name"]
        indexes = [models.Index(fields=["daily_log"], name="idx_equipment_dailylog")]


class WeatherRecord(Base):
    SOURCE_CHOICES = [("manual", "Manual"), ("api", "Weather API")]

    project = models.ForeignKey("projects.Project", on_delete=models.CASCADE, related_name="weather_records")
    record_date = models.DateField(db_index=True)
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default="manual")
    condition = models.CharField(max_length=120, blank=True)
    temperature_c = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
    humidity_percent = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    precipitation_mm = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    wind_speed_kph = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    raw_payload = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-record_date"]
        indexes = [models.Index(fields=["project", "-record_date"], name="idx_weather_project_date")]


class FieldPhoto(Base):
    daily_log = models.ForeignKey(
        DailyLog, on_delete=models.CASCADE, null=True, blank=True, related_name="photos"
    )
    project = models.ForeignKey("projects.Project", on_delete=models.CASCADE, related_name="field_photos")
    caption = models.CharField(max_length=400, blank=True)
    file = models.ImageField(upload_to="field-photos/%Y/%m/")
    taken_at = models.DateTimeField(null=True, blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    tags = models.JSONField(default=list, blank=True)
    uploaded_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="field_photos_uploaded"
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["project", "-created_at"], name="idx_photo_project_created")]


class Observation(Base):
    TYPE_CHOICES = [("positive", "Positive"), ("concern", "Concern"), ("violation", "Violation")]
    STATUS_CHOICES = [("open", "Open"), ("in_progress", "In Progress"), ("closed", "Closed")]

    project = models.ForeignKey("projects.Project", on_delete=models.CASCADE, related_name="observations")
    daily_log = models.ForeignKey(
        DailyLog, on_delete=models.SET_NULL, null=True, blank=True, related_name="observations"
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    observation_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default="concern", db_index=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="open", db_index=True)
    location = models.CharField(max_length=255, blank=True)
    assigned_to = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="observations_assigned"
    )
    due_date = models.DateField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="observations_created"
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["project", "status"], name="idx_obs_project_status"),
            models.Index(fields=["project", "observation_type"], name="idx_obs_project_type"),
        ]

    def __str__(self) -> str:  # pragma: no cover
        return self.title
