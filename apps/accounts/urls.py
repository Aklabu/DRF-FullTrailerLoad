from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .views import (
    ForgotPasswordView,
    LoginView,
    MeView,
    OnboardingSeenView,
    RegisterDocumentUploadView,
    RegisterView,
    ResetPasswordView,
    VerificationStatusView,
)

urlpatterns = [
    # Auth
    path('register/', RegisterView.as_view(), name='accounts-register'),
    path('register/documents/', RegisterDocumentUploadView.as_view(), name='accounts-register-documents'),
    path('login/', LoginView.as_view(), name='accounts-login'),
    path('token/refresh/', TokenRefreshView.as_view(), name='accounts-token-refresh'),
    # Profile
    path('me/', MeView.as_view(), name='accounts-me'),
    path('me/verification-status/', VerificationStatusView.as_view(), name='accounts-verification-status'),
    path('me/onboarding-seen/', OnboardingSeenView.as_view(), name='accounts-onboarding-seen'),
    # Password
    path('password/forgot/', ForgotPasswordView.as_view(), name='accounts-password-forgot'),
    path('password/reset/', ResetPasswordView.as_view(), name='accounts-password-reset'),
]
