from rest_framework.routers import DefaultRouter

from .views import (
    CorrectiveActionViewSet,
    DefectViewSet,
    InspectionItemViewSet,
    InspectionViewSet,
    PunchListItemViewSet,
    PunchListListViewSet,
    SafetyIncidentViewSet,
)

router = DefaultRouter()
router.register("inspections", InspectionViewSet, basename="inspection")
router.register("inspection-items", InspectionItemViewSet, basename="inspection-item")
router.register("defects", DefectViewSet, basename="defect")
router.register("punch-lists", PunchListListViewSet, basename="punch-list")
router.register("punch-list-items", PunchListItemViewSet, basename="punch-list-item")
router.register("safety-incidents", SafetyIncidentViewSet, basename="safety-incident")
router.register("corrective-actions", CorrectiveActionViewSet, basename="corrective-action")

urlpatterns = router.urls
