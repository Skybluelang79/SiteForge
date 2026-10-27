from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    InvitationAcceptView,
    InvitationViewSet,
    MembershipViewSet,
    OrganizationViewSet,
    RoleViewSet,
)

router = DefaultRouter()
router.register("", OrganizationViewSet, basename="organization")
router.register("roles", RoleViewSet, basename="role")
router.register("memberships", MembershipViewSet, basename="membership")
router.register("invitations", InvitationViewSet, basename="invitation")

urlpatterns = [
    path("invitations/accept/", InvitationAcceptView.as_view({"post": "accept"}), name="invitation-accept"),
] + router.urls
