from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from utils.response import CustomResponse

from .serializers import (
    CompanyMeSerializer,
    CompanyMeUpdateSerializer,
    ComplianceDocumentSerializer,
    CustomTokenObtainPairSerializer,
    ForgotPasswordSerializer,
    RegisterSerializer,
    ResetPasswordSerializer,
    VerificationStatusSerializer,
)


class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        company, user = serializer.create(serializer.validated_data)
        return CustomResponse.success(
            message='Registration successful.',
            data={'company_id': str(company.id)},
            status_code=status.HTTP_201_CREATED,
        )


# Accepts multipart form data for compliance document uploads
class RegisterDocumentUploadView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        company = request.user.company
        if not company:
            return CustomResponse.error(
                message='No company associated with this account.',
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        serializer = ComplianceDocumentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        doc = serializer.save(company=company)
        return CustomResponse.success(
            message='Document uploaded successfully.',
            data=ComplianceDocumentSerializer(doc).data,
            status_code=status.HTTP_201_CREATED,
        )


# Uses custom serializer to embed company claims directly in the token
class LoginView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer


# Returns and updates the authenticated user's company profile
class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        company = request.user.company
        if not company:
            return CustomResponse.error(
                message='No company found.',
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return CustomResponse.success(
            message='Profile retrieved.',
            data=CompanyMeSerializer(company).data,
        )

    def patch(self, request):
        company = request.user.company
        if not company:
            return CustomResponse.error(
                message='No company found.',
                status_code=status.HTTP_404_NOT_FOUND,
            )
        serializer = CompanyMeUpdateSerializer(company, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return CustomResponse.success(
            message='Profile updated.',
            data=CompanyMeSerializer(company).data,
        )


class VerificationStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        company = request.user.company
        if not company:
            return CustomResponse.error(
                message='No company found.',
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return CustomResponse.success(
            message='Verification status retrieved.',
            data=VerificationStatusSerializer(company).data,
        )


# Fire-and-forget — marks onboarding modal as dismissed
class OnboardingSeenView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        company = request.user.company
        if company:
            company.has_seen_onboarding = True
            company.save(update_fields=['has_seen_onboarding'])
        return CustomResponse.success(
            message='Onboarding marked as seen.',
            status_code=status.HTTP_204_NO_CONTENT,
        )


# Always returns 200 to avoid leaking whether an email is registered
class ForgotPasswordView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.send_otp()
        return CustomResponse.success(
            message='If an account with that email exists, a reset code has been sent.',
        )


class ResetPasswordView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return CustomResponse.success(message='Password reset successful.')
