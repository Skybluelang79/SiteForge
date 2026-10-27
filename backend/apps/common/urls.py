from django.urls import path

from . import views

urlpatterns = [
    path("health/", views.liveness, name="health-liveness"),
    path("health/ready/", views.readiness, name="health-readiness"),
    path("permissions/", views.permission_catalog, name="permission-catalog"),
]
