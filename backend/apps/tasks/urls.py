from rest_framework.routers import DefaultRouter

from .views import TaskDependencyViewSet, TaskViewSet

router = DefaultRouter()
router.register("tasks", TaskViewSet, basename="task")
router.register("task-dependencies", TaskDependencyViewSet, basename="task-dependency")

urlpatterns = router.urls
