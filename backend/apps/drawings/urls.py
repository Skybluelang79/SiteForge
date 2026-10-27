from rest_framework.routers import DefaultRouter

from .views import DrawingReviewViewSet, DrawingRevisionViewSet, DrawingSetViewSet, DrawingViewSet

router = DefaultRouter()
router.register("drawing-sets", DrawingSetViewSet, basename="drawing-set")
router.register("drawings", DrawingViewSet, basename="drawing")
router.register("drawing-revisions", DrawingRevisionViewSet, basename="drawing-revision")
router.register("drawing-reviews", DrawingReviewViewSet, basename="drawing-review")

urlpatterns = router.urls
