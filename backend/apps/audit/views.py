"""Audit log views (admin console)."""
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, mixins, viewsets

from apps.common.drf_permissions import HasPermission

from .models import AuditEvent
from .serializers import AuditEventSerializer


class AuditEventViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = AuditEventSerializer
    permission_classes = [HasPermission("org.audit.view")]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["action", "target_type", "target_id", "actor", "project"]
    search_fields = ["action", "target_type", "target_id", "metadata"]
    ordering_fields = ["created_at", "action"]
    ordering = ["-created_at"]

    def get_queryset(self):
        membership = getattr(self.request, "membership", None)
        if membership is None:
            return AuditEvent.objects.none()
        return AuditEvent.objects.filter(organization_id=membership.organization_id).select_related("actor")
