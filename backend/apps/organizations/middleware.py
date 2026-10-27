"""Active organization resolution middleware.

Resolves `request.membership` / `request.organization` for the current request.

DRF resolves JWT authentication during view dispatch (after Django middleware),
so this middleware also validates a bearer token itself. That guarantees
`request.membership` is available to permission classes and querysets.
"""
from django.contrib.auth.models import AnonymousUser
from django.utils.deprecation import MiddlewareMixin
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError


class ActiveOrganizationMiddleware(MiddlewareMixin):
    def process_request(self, request):
        request.membership = None
        request.organization = None

        user = getattr(request, "user", None)
        if user is None or not getattr(user, "is_authenticated", False):
            # Attempt JWT authentication from the Authorization header.
            header = request.META.get("HTTP_AUTHORIZATION", "")
            if header.lower().startswith("bearer "):
                try:
                    authenticator = JWTAuthentication()
                    validated = authenticator.get_validated_token(header.split(" ", 1)[1])
                    user = authenticator.get_user(validated)
                    if user is not None:
                        request.user = user
                except (InvalidToken, TokenError):
                    pass

        user = getattr(request, "user", None)
        if user is None or not getattr(user, "is_authenticated", False):
            return None

        org_id = request.META.get("HTTP_X_ORGANIZATION_ID")
        if not org_id:
            session = getattr(request, "session", None)
            if session is not None:
                org_id = session.get("active_organization_id")

        memberships = user.active_memberships()
        membership = None
        if org_id:
            membership = memberships.filter(organization_id=org_id).first()
        if membership is None and org_id is None:
            membership = memberships.first()
        if membership is not None:
            request.membership = membership
            request.organization = membership.organization
        return None
