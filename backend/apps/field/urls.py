from rest_framework.routers import DefaultRouter

from .views import (
    DailyLogViewSet,
    EquipmentEntryViewSet,
    FieldPhotoViewSet,
    LabourEntryViewSet,
    ObservationViewSet,
    WeatherRecordViewSet,
)

router = DefaultRouter()
router.register("daily-logs", DailyLogViewSet, basename="daily-log")
router.register("labour-entries", LabourEntryViewSet, basename="labour-entry")
router.register("equipment-entries", EquipmentEntryViewSet, basename="equipment-entry")
router.register("weather-records", WeatherRecordViewSet, basename="weather-record")
router.register("field-photos", FieldPhotoViewSet, basename="field-photo")
router.register("observations", ObservationViewSet, basename="observation")

urlpatterns = router.urls
