from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    ApiApplicationViewSet,
    HealthView,
    WebhookDeliveryViewSet,
    WebhookEventViewSet,
    WebhookSubscriptionViewSet,
)

router = DefaultRouter()
router.register("api-applications", ApiApplicationViewSet, basename="api-application")
router.register("webhooks", WebhookSubscriptionViewSet, basename="webhook")
router.register("webhook-events", WebhookEventViewSet, basename="webhook-event")
router.register("webhook-deliveries", WebhookDeliveryViewSet, basename="webhook-delivery")

urlpatterns = [
    path("integrations/health/", HealthView.as_view(), name="integration-health"),
] + router.urls
