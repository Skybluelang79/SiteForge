from django.urls import path
from rest_framework.routers import DefaultRouter

from .dashboard import DashboardView
from .views import (
    ContractViewSet,
    GlobalActivityView,
    MilestoneViewSet,
    ProjectViewSet,
)

router = DefaultRouter()
router.register("projects", ProjectViewSet, basename="project")
router.register("milestones", MilestoneViewSet, basename="milestone")
router.register("contracts", ContractViewSet, basename="contract")
router.register("activity", GlobalActivityView, basename="activity")

urlpatterns = [
    path("dashboard/", DashboardView.as_view(), name="dashboard"),
] + router.urls
