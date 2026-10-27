"""Field report serializers."""
from rest_framework import serializers

from apps.accounts.serializers import UserSummarySerializer

from .models import DailyLog, EquipmentEntry, FieldPhoto, LabourEntry, Observation, WeatherRecord


class LabourEntrySerializer(serializers.ModelSerializer):
    total_cost = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)

    class Meta:
        model = LabourEntry
        fields = [
            "id", "daily_log", "trade", "company", "worker_count", "hours_worked",
            "overtime_hours", "hourly_rate", "total_cost", "notes", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "total_cost", "created_at", "updated_at"]


class EquipmentEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = EquipmentEntry
        fields = [
            "id", "daily_log", "equipment_name", "equipment_code", "owner", "hours_used",
            "idle_hours", "cost_per_hour", "notes", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class FieldPhotoSerializer(serializers.ModelSerializer):
    uploaded_by = UserSummarySerializer(read_only=True)

    class Meta:
        model = FieldPhoto
        fields = [
            "id", "project", "daily_log", "caption", "file", "taken_at", "latitude",
            "longitude", "tags", "uploaded_by", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "uploaded_by", "created_at", "updated_at"]


class WeatherRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = WeatherRecord
        fields = [
            "id", "project", "record_date", "source", "condition", "temperature_c",
            "humidity_percent", "precipitation_mm", "wind_speed_kph", "raw_payload",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class DailyLogSerializer(serializers.ModelSerializer):
    created_by = UserSummarySerializer(read_only=True)
    approved_by = UserSummarySerializer(read_only=True)
    labour_entries = LabourEntrySerializer(many=True, read_only=True)
    equipment_entries = EquipmentEntrySerializer(many=True, read_only=True)
    labour_count = serializers.SerializerMethodField()
    equipment_count = serializers.SerializerMethodField()

    class Meta:
        model = DailyLog
        fields = [
            "id", "project", "log_date", "status", "weather_summary", "temperature_low_c",
            "temperature_high_c", "precipitation_mm", "wind_speed_kph", "work_activities",
            "delays", "safety_notes", "visitors", "created_by", "approved_by", "approved_at",
            "labour_entries", "equipment_entries", "labour_count", "equipment_count",
            "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "status", "created_by", "approved_by", "approved_at", "created_at", "updated_at",
        ]

    def get_labour_count(self, obj):
        return obj.labour_entries.count()

    def get_equipment_count(self, obj):
        return obj.equipment_entries.count()

    def validate(self, attrs):
        project = attrs.get("project") or getattr(self.instance, "project", None)
        log_date = attrs.get("log_date") or getattr(self.instance, "log_date", None)
        if project and log_date:
            qs = DailyLog.objects.filter(project=project, log_date=log_date)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError({"log_date": "A daily log already exists for this date."})
        return attrs


class ObservationSerializer(serializers.ModelSerializer):
    assigned_to = UserSummarySerializer(read_only=True)
    assigned_to_id = serializers.UUIDField(write_only=True, required=False, allow_null=True)
    created_by = UserSummarySerializer(read_only=True)

    class Meta:
        model = Observation
        fields = [
            "id", "project", "daily_log", "title", "description", "observation_type", "status",
            "location", "assigned_to", "assigned_to_id", "due_date", "closed_at", "created_by",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "closed_at", "created_by", "created_at", "updated_at"]
