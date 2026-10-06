from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.views import APIView

from utils.response import CustomResponse

from .models import ComplianceDocument
from .serializers import (
    ChangePasswordSerializer,
    CompanyMeSerializer,
    CompanyMeUpdateSerializer,
    ComplianceDocumentSerializer,
    ForgotPasswordSerializer,
    LoginOtpSerializer,
    RegisterSerializer,
    ResetPasswordSerializer,
    VerificationStatusSerializer,
    VerifyOtpSerializer,
)


class RegisterView(APIView):
    permission_classes = [AllowAny]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        company, user = serializer.create(serializer.validated_data)
        return CustomResponse.success(
            message='Registration initiated. Please check your email for a 6-digit verification code.',
            data={'email': user.email},
            status_code=status.HTTP_201_CREATED,
        )


# Step 1 of login — verify credentials, send 2FA OTP
class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginOtpSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.send_otp()
        email = serializer.validated_data['_user'].email
        return CustomResponse.success(
            message='Credentials verified. A login code has been sent to your email.',
            data={'email': email},
        )


# Universal OTP verification — handles email_verification, login_2fa, password_reset
class VerifyOtpView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = VerifyOtpSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = serializer.save()
        purpose = serializer.validated_data['purpose']

        if purpose == 'login_2fa':
            return CustomResponse.success(
                message='Login successful.',
                data=result,
            )
        if purpose == 'email_verification':
            return CustomResponse.success(
                message='Email verified. Your account is now active.',
                data=result,
                status_code=status.HTTP_200_OK,
            )
        if purpose == 'password_reset':
            return CustomResponse.success(
                message='OTP verified. Use the reset_token to set your new password.',
                data=result,
            )


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


# GET — list all documents, POST — upload a new document
class DocumentListView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def get(self, request):
        company = request.user.company
        if not company:
            return CustomResponse.error(
                message='No company found.',
                status_code=status.HTTP_404_NOT_FOUND,
            )
        documents = company.compliance_documents.all()
        return CustomResponse.success(
            message='Documents retrieved.',
            data=ComplianceDocumentSerializer(
                documents, many=True, context={'request': request}
            ).data,
        )

    def post(self, request):
        company = request.user.company
        if not company:
            return CustomResponse.error(
                message='No company found.',
                status_code=status.HTTP_404_NOT_FOUND,
            )
        serializer = ComplianceDocumentSerializer(
            data=request.data, context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        doc = serializer.save(company=company)
        return CustomResponse.success(
            message='Document uploaded successfully.',
            data=ComplianceDocumentSerializer(doc, context={'request': request}).data,
            status_code=status.HTTP_201_CREATED,
        )


# DELETE — remove a specific document by id
class DocumentDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, doc_id):
        company = request.user.company
        if not company:
            return CustomResponse.error(
                message='No company found.',
                status_code=status.HTTP_404_NOT_FOUND,
            )
        try:
            doc = company.compliance_documents.get(id=doc_id)
        except ComplianceDocument.DoesNotExist:
            return CustomResponse.error(
                message='Document not found.',
                status_code=status.HTTP_404_NOT_FOUND,
            )
        # Delete the file from storage then the record
        doc.file.delete(save=False)
        doc.delete()
        return CustomResponse.success(
            message='Document deleted.',
            status_code=status.HTTP_204_NO_CONTENT,
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


# Accepts reset_token (from otp/verify/) + new_password + confirm_password
class ResetPasswordView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return CustomResponse.success(message='Password reset successful.')


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(user=request.user)
        return CustomResponse.success(message='Password changed successfully.')
