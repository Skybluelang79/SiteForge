"""Root URL configuration."""
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    path("admin/", admin.site.urls),
    # OAuth2 provider endpoints (authorization code + PKCE, token, revocation)
    path("o/", include("oauth2_provider.urls", namespace="oauth2_provider")),
    # OpenAPI schema + docs
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/schema/swagger-ui/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="api-docs"),
    # Versioned API
    path("api/v1/auth/", include("apps.accounts.urls")),
    path("api/v1/organizations/", include("apps.organizations.urls")),
    path("api/v1/", include("apps.projects.urls")),
    path("api/v1/", include("apps.documents.urls")),
    path("api/v1/", include("apps.drawings.urls")),
    path("api/v1/", include("apps.field.urls")),
    path("api/v1/", include("apps.tasks.urls")),
    path("api/v1/", include("apps.rfis.urls")),
    path("api/v1/", include("apps.financials.urls")),
    path("api/v1/", include("apps.quality.urls")),
    path("api/v1/", include("apps.reports.urls")),
    path("api/v1/", include("apps.integrations.urls")),
    path("api/v1/", include("apps.notifications.urls")),
    path("api/v1/", include("apps.audit.urls")),
    path("api/v1/", include("apps.common.urls")),
]
