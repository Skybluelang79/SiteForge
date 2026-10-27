"""Integration developer portal endpoints."""
from django.db import connection
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.viewsets import OrgScopedViewSet

from .models import ApiApplication, WebhookDelivery, WebhookEvent, WebhookSubscription
from .serializers import (
    ApiApplicationSerializer,
    WebhookDeliverySerializer,
    WebhookEventSerializer,
    WebhookSubscriptionSerializer,
)
from .services import dispatch_event, generate_webhook_secret, issue_credentials


class ApiApplicationViewSet(OrgScopedViewSet):
    serializer_class = ApiApplicationSerializer
    filterset_fields = ["environment", "is_active"]
    search_fields = ["name", "description", "client_id"]
    ordering = ["-created_at"]
    action_permissions = {
        "read": ("integrations.view",),
        "create": ("integrations.manage",),
        "update": ("integrations.manage",),
        "partial_update": ("integrations.manage",),
        "destroy": ("integrations.manage",),
        "rotate": ("integrations.manage",),
    }

    def get_queryset(self):
        return super().get_queryset().select_related("created_by")

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        application = serializer.save(
            organization=request.membership.organization,
            created_by=request.user,
        )
        client_id, raw_secret = issue_credentials(application)
        data = self.get_serializer(application).data
        data["client_secret"] = raw_secret
        headers = self.get_success_headers(data)
        return Response(data, status=status.HTTP_201_CREATED, headers=headers)

    @action(detail=True, methods=["post"], url_path="rotate")
    def rotate(self, request, pk=None):
        application = self.get_object()
        client_id, raw_secret = issue_credentials(application)
        return Response({"client_id": client_id, "client_secret": raw_secret})


class WebhookSubscriptionViewSet(OrgScopedViewSet):
    serializer_class = WebhookSubscriptionSerializer
    filterset_fields = ["application", "is_active"]
    search_fields = ["name", "target_url"]
    ordering = ["-created_at"]
    action_permissions = {
        "read": ("integrations.view",),
        "create": ("integrations.manage",),
        "update": ("integrations.manage",),
        "partial_update": ("integrations.manage",),
        "destroy": ("integrations.manage",),
        "test": ("integrations.manage",),
        "deliveries": ("integrations.view",),
        "rotate_secret": ("integrations.manage",),
    }

    def get_queryset(self):
        return super().get_queryset().select_related("application", "created_by")

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        raw_secret = request.data.get("secret") or generate_webhook_secret()
        subscription = serializer.save(
            organization=request.membership.organization,
            created_by=request.user,
            secret=raw_secret,
        )
        data = self.get_serializer(subscription).data
        data["secret"] = raw_secret
        headers = self.get_success_headers(data)
        return Response(data, status=status.HTTP_201_CREATED, headers=headers)

    @action(detail=True, methods=["post"], url_path="test")
    def test(self, request, pk=None):
        subscription = self.get_object()
        event_type = (subscription.event_types or ["project.updated"])[0]
        event, deliveries = dispatch_event(
            organization=subscription.organization,
            event_type=event_type,
            payload={"test": True, "subscription_id": str(subscription.id)},
        )
        return Response(
            {
                "event_id": str(event.event_id),
                "event_type": event.event_type,
                "deliveries": [str(delivery.id) for delivery in deliveries],
            },
            status=status.HTTP_202_ACCEPTED,
        )

    @action(detail=True, methods=["get"], url_path="deliveries")
    def deliveries(self, request, pk=None):
        subscription = self.get_object()
        queryset = subscription.deliveries.select_related("event").order_by("-created_at")
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = WebhookDeliverySerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        return Response(WebhookDeliverySerializer(queryset, many=True).data)

    @action(detail=True, methods=["post"], url_path="rotate-secret")
    def rotate_secret(self, request, pk=None):
        subscription = self.get_object()
        raw_secret = generate_webhook_secret()
        subscription.secret = raw_secret
        subscription.save(update_fields=["secret", "updated_at"])
        return Response({"secret": raw_secret})


class WebhookEventViewSet(OrgScopedViewSet):
    serializer_class = WebhookEventSerializer
    filterset_fields = ["event_type", "project"]
    ordering = ["-created_at"]
    http_method_names = ["get", "head", "options"]
    action_permissions = {
        "read": ("integrations.view",),
        "deliveries": ("integrations.view",),
    }

    def get_queryset(self):
        return super().get_queryset().select_related("project").prefetch_related("deliveries")

    @action(detail=True, methods=["get"], url_path="deliveries")
    def deliveries(self, request, pk=None):
        event = self.get_object()
        queryset = event.deliveries.select_related("subscription").order_by("-created_at")
        return Response(WebhookDeliverySerializer(queryset, many=True).data)


class WebhookDeliveryViewSet(OrgScopedViewSet):
    serializer_class = WebhookDeliverySerializer
    filterset_fields = ["subscription", "event", "status"]
    ordering = ["-created_at"]
    org_field = "subscription__organization_id"
    http_method_names = ["get", "head", "options", "post"]
    action_permissions = {
        "read": ("integrations.view",),
        "retry": ("integrations.manage",),
    }

    def get_queryset(self):
        return super().get_queryset().select_related("subscription", "event")

    @action(detail=True, methods=["post"], url_path="retry")
    def retry(self, request, pk=None):
        delivery = self.get_object()
        delivery.status = "pending"
        delivery.next_attempt_at = None
        delivery.save(update_fields=["status", "next_attempt_at"])
        from .services import deliver
        from .tasks import deliver_webhook

        try:
            deliver_webhook.delay(str(delivery.id))
        except Exception:
            deliver(str(delivery.id))
        delivery.refresh_from_db()
        return Response(WebhookDeliverySerializer(delivery).data, status=status.HTTP_202_ACCEPTED)


class HealthView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        database_ok = True
        error = ""
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
        except Exception as exc:
            database_ok = False
            error = str(exc)
        payload = {
            "status": "ok" if database_ok else "degraded",
            "database": "ok" if database_ok else "error",
        }
        if error:
            payload["error"] = error
        return Response(payload, status=200 if database_ok else 503)
