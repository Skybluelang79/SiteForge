from rest_framework.routers import DefaultRouter

from .views import DashboardViewSet, ExportJobViewSet, MetricSnapshotViewSet, ReportDefinitionViewSet

router = DefaultRouter()
router.register("report-definitions", ReportDefinitionViewSet, basename="report-definition")
router.register("dashboards", DashboardViewSet, basename="dashboard")
router.register("export-jobs", ExportJobViewSet, basename="export-job")
router.register("metric-snapshots", MetricSnapshotViewSet, basename="metric-snapshot")

urlpatterns = router.urls
