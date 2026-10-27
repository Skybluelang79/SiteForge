from django.urls import path
from rest_framework_simplejwt.views import TokenVerifyView

from . import views

urlpatterns = [
    path("register/", views.RegisterView.as_view(), name="auth-register"),
    path("login/", views.LoginView.as_view(), name="auth-login"),
    path("refresh/", views.RefreshView.as_view(), name="auth-refresh"),
    path("verify/", TokenVerifyView.as_view(), name="auth-verify"),
    path("logout/", views.LogoutView.as_view(), name="auth-logout"),
    path("me/", views.MeView.as_view(), name="auth-me"),
    path("context/", views.my_context, name="auth-context"),
    path("password/change/", views.PasswordChangeView.as_view(), name="auth-password-change"),
    path("password/reset/", views.PasswordResetRequestView.as_view(), name="auth-password-reset"),
    path("password/reset/confirm/", views.PasswordResetConfirmView.as_view(), name="auth-password-reset-confirm"),
    path("mfa/setup/", views.MFASetupView.as_view(), name="auth-mfa-setup"),
    path("mfa/verify/", views.MFAVerifyView.as_view(), name="auth-mfa-verify"),
    path("mfa/confirm/", views.MFAConfirmView.as_view(), name="auth-mfa-confirm"),
    path("mfa/disable/", views.MFADisableView.as_view(), name="auth-mfa-disable"),
    path("sessions/", views.SessionListView.as_view(), name="auth-sessions"),
    path("sessions/<uuid:pk>/revoke/", views.SessionRevokeView.as_view(), name="auth-session-revoke"),
]
