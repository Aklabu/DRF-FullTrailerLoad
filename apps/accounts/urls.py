from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .views import (
    ChangePasswordView,
    DocumentDetailView,
    DocumentListView,
    ForgotPasswordView,
    LoginView,
    MeView,
    OnboardingSeenView,
    RegisterView,
    ResetPasswordView,
    VerificationStatusView,
    VerifyOtpView,
)

urlpatterns = [
    # Auth
    path('register/', RegisterView.as_view(), name='accounts-register'),
    path('login/', LoginView.as_view(), name='accounts-login'),
    path('token/refresh/', TokenRefreshView.as_view(), name='accounts-token-refresh'),
    # Universal OTP verification
    path('otp/verify/', VerifyOtpView.as_view(), name='accounts-otp-verify'),
    # Profile
    path('me/', MeView.as_view(), name='accounts-me'),
    path('me/documents/', DocumentListView.as_view(), name='accounts-me-documents'),
    path('me/documents/<uuid:doc_id>/', DocumentDetailView.as_view(), name='accounts-me-document-detail'),
    path('me/verification-status/', VerificationStatusView.as_view(), name='accounts-verification-status'),
    path('me/onboarding-seen/', OnboardingSeenView.as_view(), name='accounts-onboarding-seen'),
    # Password
    path('password/forgot/', ForgotPasswordView.as_view(), name='accounts-password-forgot'),
    path('password/reset/', ResetPasswordView.as_view(), name='accounts-password-reset'),
    path('password/change/', ChangePasswordView.as_view(), name='accounts-password-change'),
]
