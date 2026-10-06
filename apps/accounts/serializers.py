import random
import string

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from django.utils import timezone

from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import Company, ComplianceDocument, DotMcInfo, OtpCode
from .notifications import send_welcome_email, send_otp_email

User = get_user_model()

ALLOWED_DOC_MIME_TYPES = ('application/pdf', 'image/png', 'image/jpeg')
MAX_DOC_SIZE_BYTES = 25 * 1024 * 1024  # 25 MB


# Embeds company claims so the frontend can boot without a separate /me call
class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        company = getattr(user, 'company', None)
        if company:
            token['role'] = company.role
            token['tier'] = company.tier
            token['verification_status'] = company.verification_status
            token['company_name'] = company.name
            token['has_seen_onboarding'] = company.has_seen_onboarding
        token['user_id'] = str(user.id)
        token['email'] = user.email
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        company = getattr(self.user, 'company', None)

        # Block marketplace accounts that haven't completed verification
        if company:
            blocked_statuses = (
                Company.VerificationStatus.PENDING,
                Company.VerificationStatus.NEEDS_INFO,
            )
            if company.tier == Company.Tier.MARKETPLACE and company.verification_status in blocked_statuses:
                raise serializers.ValidationError({
                    'detail': 'Your account is pending verification.',
                    'code': 'account_not_verified',
                })

        if company:
            data['role'] = company.role
            data['tier'] = company.tier
            data['verification_status'] = company.verification_status
            data['company_name'] = company.name
            data['has_seen_onboarding'] = company.has_seen_onboarding
        data['user_id'] = str(self.user.id)
        data['email'] = self.user.email
        return data


class RegisterSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=Company.Role.choices)
    tier = serializers.ChoiceField(choices=Company.Tier.choices)
    company_name = serializers.CharField(max_length=255)
    email = serializers.EmailField()
    phone = serializers.CharField(max_length=30)
    address_line1 = serializers.CharField(max_length=255)
    address_line2 = serializers.CharField(max_length=255, required=False, allow_blank=True)
    city = serializers.CharField(max_length=100)
    state = serializers.CharField(max_length=100)
    zip_code = serializers.CharField(max_length=20)
    country = serializers.CharField(max_length=100, default='US')
    website = serializers.CharField(max_length=255, required=False, allow_blank=True)
    dot_number = serializers.CharField(max_length=20, required=False, allow_blank=True)
    mc_number = serializers.CharField(max_length=20, required=False, allow_blank=True)
    business_license_number = serializers.CharField(max_length=50, required=False, allow_blank=True)
    state_of_incorporation = serializers.CharField(max_length=100, required=False, allow_blank=True)
    password = serializers.CharField(write_only=True, min_length=8)

    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError('An account with this email already exists.')
        return value.lower()

    def validate_password(self, value):
        validate_password(value)
        return value

    @transaction.atomic
    def create(self, validated_data):
        tier = validated_data['tier']
        now = timezone.now()

        company = Company.objects.create(
            name=validated_data['company_name'],
            email=validated_data['email'],
            phone=validated_data['phone'],
            address_line1=validated_data['address_line1'],
            address_line2=validated_data.get('address_line2', ''),
            city=validated_data['city'],
            state=validated_data['state'],
            zip_code=validated_data['zip_code'],
            country=validated_data.get('country', 'US'),
            website=validated_data.get('website', ''),
            role=validated_data['role'],
            tier=tier,
            # Marketplace accounts start as pending; bulletin gets basic access immediately
            verification_status=(
                Company.VerificationStatus.PENDING
                if tier == Company.Tier.MARKETPLACE
                else Company.VerificationStatus.BASIC
            ),
            submitted_at=now if tier == Company.Tier.MARKETPLACE else None,
        )

        DotMcInfo.objects.create(
            company=company,
            dot_number=validated_data.get('dot_number', ''),
            mc_number=validated_data.get('mc_number', ''),
            business_license_number=validated_data.get('business_license_number', ''),
            state_of_incorporation=validated_data.get('state_of_incorporation', ''),
        )

        user = User.objects.create_user(
            email=validated_data['email'],
            password=validated_data['password'],
            company=company,
        )

        self._send_welcome_email(user, company)
        return company, user

    def _send_welcome_email(self, user, company):
        send_welcome_email(user, company)


# Validates file type and size before saving compliance docs
class ComplianceDocumentSerializer(serializers.ModelSerializer):
    file = serializers.FileField(write_only=True)

    class Meta:
        model = ComplianceDocument
        fields = ('id', 'doc_type', 'file', 'file_name', 'file_size', 'uploaded_at')
        read_only_fields = ('id', 'file_name', 'file_size', 'uploaded_at')

    def validate_file(self, value):
        if value.size > MAX_DOC_SIZE_BYTES:
            raise serializers.ValidationError('File size must not exceed 25 MB.')
        if getattr(value, 'content_type', '') not in ALLOWED_DOC_MIME_TYPES:
            raise serializers.ValidationError('Only PDF, PNG, and JPG files are accepted.')
        return value

    def create(self, validated_data):
        file = validated_data['file']
        validated_data['file_name'] = file.name
        validated_data['file_size'] = file.size
        return super().create(validated_data)


# Full read serializer for GET /me/
class CompanyMeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = (
            'id', 'email', 'role', 'tier', 'verification_status',
            'name', 'has_seen_onboarding', 'phone',
            'address_line1', 'address_line2', 'city', 'state',
            'zip_code', 'country', 'website',
            'submitted_at', 'reviewed_at',
        )
        read_only_fields = (
            'id', 'email', 'role', 'tier', 'verification_status',
            'has_seen_onboarding', 'submitted_at', 'reviewed_at',
        )


# Restricted update serializer — email and role are not editable
class CompanyMeUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = ('name', 'phone', 'address_line1', 'address_line2', 'city', 'state', 'zip_code', 'website')


class VerificationStatusSerializer(serializers.ModelSerializer):
    status = serializers.CharField(source='verification_status', read_only=True)

    class Meta:
        model = Company
        fields = ('status', 'rejection_reason', 'info_requested', 'submitted_at', 'reviewed_at')


class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def send_otp(self):
        email = self.validated_data['email']
        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            return  # silently do nothing to avoid email enumeration

        # Invalidate any existing unused codes before issuing a new one
        OtpCode.objects.filter(user=user, purpose=OtpCode.Purpose.PASSWORD_RESET, used=False).update(used=True)

        code = ''.join(random.choices(string.digits, k=6))
        OtpCode.objects.create(user=user, code=code, purpose=OtpCode.Purpose.PASSWORD_RESET)

        send_otp_email(user, code)


class ResetPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp_code = serializers.CharField(max_length=6)
    new_password = serializers.CharField(write_only=True, min_length=8)

    def validate_new_password(self, value):
        validate_password(value)
        return value

    def validate(self, attrs):
        try:
            user = User.objects.get(email__iexact=attrs['email'])
        except User.DoesNotExist:
            raise serializers.ValidationError({'email': 'No account found with this email.'})

        try:
            otp = OtpCode.objects.get(user=user, code=attrs['otp_code'], purpose=OtpCode.Purpose.PASSWORD_RESET)
        except OtpCode.DoesNotExist:
            raise serializers.ValidationError({'otp_code': 'Invalid code.'})

        if not otp.is_valid():
            raise serializers.ValidationError({'otp_code': 'Code has expired or already been used.'})

        attrs['_user'] = user
        attrs['_otp'] = otp
        return attrs

    def save(self):
        user = self.validated_data['_user']
        otp = self.validated_data['_otp']
        user.set_password(self.validated_data['new_password'])
        user.save(update_fields=['password'])
        otp.used = True
        otp.save(update_fields=['used'])
