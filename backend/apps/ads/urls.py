from django.urls import path

from .views import AdDeliveryView, AdEventView

urlpatterns = [
    path("ads/", AdDeliveryView.as_view(), name="ads-delivery"),
    path("ads/<uuid:pk>/events/", AdEventView.as_view(), name="ads-event"),
]
