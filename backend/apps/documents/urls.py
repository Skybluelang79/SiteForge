from rest_framework.routers import DefaultRouter

from .views import DocumentFolderViewSet, DocumentVersionViewSet, DocumentViewSet

router = DefaultRouter()
router.register("document-folders", DocumentFolderViewSet, basename="document-folder")
router.register("documents", DocumentViewSet, basename="document")
router.register("document-versions", DocumentVersionViewSet, basename="document-version")

urlpatterns = router.urls
