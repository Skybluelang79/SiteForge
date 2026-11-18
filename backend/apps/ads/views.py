"""Public ad delivery endpoints."""
from django.db.models import F, Q
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView

from .models import AdEvent, Advertisement
from .serializers import AdvertisementSerializer


class AdDeliveryView(APIView):
    """Return live ads for a placement.

    Public placements (landing/login) return platform-wide campaigns. Pass
    ``organization`` to include tenant campaigns for a workspace.
    """

    permission_classes = [AllowAny]
    throttle_classes = [AnonRateThrottle]

    def get(self, request):
        placement = request.query_params.get("placement", "").strip()
        organization = request.query_params.get("organization", "").strip()
        now = timezone.now()

        queryset = Advertisement.objects.filter(is_active=True).filter(
            Q(start_at__isnull=True) | Q(start_at__lte=now)
        ).filter(Q(end_at__isnull=True) | Q(end_at__gte=now))
        if placement:
            queryset = queryset.filter(placement=placement)
        if organization:
            queryset = queryset.filter(
                Q(organization__isnull=True) | Q(organization_id=organization)
            )
        else:
            queryset = queryset.filter(organization__isnull=True)

        limit = min(int(request.query_params.get("limit", 3) or 3), 10)
        serializer = AdvertisementSerializer(
            queryset[:limit], many=True, context={"request": request}
        )
        return Response({"results": serializer.data})


class AdEventView(APIView):
    """Record an impression or click for a live ad."""

    permission_classes = [AllowAny]
    throttle_classes = [AnonRateThrottle]

    def post(self, request, pk):
        event_type = request.data.get("event_type", "impression")
        if event_type not in {"impression", "click"}:
            return Response(
                {"detail": "event_type must be impression or click."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            ad = Advertisement.objects.get(pk=pk)
        except (Advertisement.DoesNotExist, ValueError, TypeError):
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        if not ad.is_live:
            return Response({"detail": "Campaign is not live."}, status=status.HTTP_409_CONFLICT)

        AdEvent.objects.create(
            advertisement=ad,
            event_type=event_type,
            session_key=str(request.data.get("session_key", ""))[:80],
            referrer=(request.META.get("HTTP_REFERER") or "")[:500],
        )
        field = "impressions" if event_type == "impression" else "clicks"
        Advertisement.objects.filter(pk=ad.pk).update(**{field: F(field) + 1})
        return Response({"recorded": event_type}, status=status.HTTP_201_CREATED)
