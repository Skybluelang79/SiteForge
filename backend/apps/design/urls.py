from rest_framework.routers import DefaultRouter

from .views import CanvasBoardViewSet

router = DefaultRouter()
router.register("canvas-boards", CanvasBoardViewSet, basename="canvas-board")

urlpatterns = router.urls
