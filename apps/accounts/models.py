import uuid
from datetime import timedelta

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone


# Primary entity — one Company per registered account
class Company(models.Model):
    class Role(models.TextChoices):
        SHIPPER = 'shipper', 'Shipper'
        BROKER = 'broker', 'Broker'
        CARRIER = 'carrier', 'Carrier'

    class Tier(models.TextChoices):
        BULLETIN = 'bulletin', 'Bulletin'
        MARKETPLACE = 'marketplace', 'Marketplace'

    class VerificationStatus(models.TextChoices):
        VERIFIED = 'verified', 'Verified'
        PENDING = 'pending', 'Pending'
        BASIC = 'basic', 'Basic'
        REJECTED = 'rejected', 'Rejected'
        NEEDS_INFO = 'needs_info', 'Needs Info'
        UNVERIFIED = 'unverified', 'Unverified'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=30)
    address_line1 = models.CharField(max_length=255)
    address_line2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    zip_code = models.CharField(max_length=20)
    website = models.CharField(max_length=255, blank=True)
    role = models.CharField(max_length=10, choices=Role.choices)
    tier = models.CharField(max_length=15, choices=Tier.choices, default=Tier.BULLETIN)
    verification_status = models.CharField(
        max_length=15,
        choices=VerificationStatus.choices,
        default=VerificationStatus.UNVERIFIED,
    )
    rejection_reason = models.TextField(blank=True)
    info_requested = models.TextField(blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    has_seen_onboarding = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = 'companies'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.name} ({self.role})'


# Custom manager that uses email as the unique identifier instead of username
class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('Email is required.')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')
        return self.create_user(email, password, **extra_fields)


# Auth user — one-to-one with Company, email is the login credential
class User(AbstractBaseUser, PermissionsMixin):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.OneToOneField(
        Company,
        on_delete=models.CASCADE,
        related_name='user',
        null=True,
        blank=True,
    )
    email = models.EmailField(unique=True)
    is_active = models.BooleanField(default=False)  # activated after email OTP verification
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(auto_now_add=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    objects = UserManager()

    def __str__(self):
        return self.email


# DOT and MC compliance numbers for carriers and brokers
class DotMcInfo(models.Model):
    company = models.OneToOneField(Company, on_delete=models.CASCADE, related_name='dot_mc_info')
    dot_number = models.CharField(max_length=20, blank=True)
    mc_number = models.CharField(max_length=20, blank=True)
    business_license_number = models.CharField(max_length=50, blank=True)
    state_of_incorporation = models.CharField(max_length=100, blank=True)

    class Meta:
        verbose_name = 'DOT/MC Info'
        verbose_name_plural = 'DOT/MC Info'

    def __str__(self):
        return f'DOT/MC — {self.company.name}'


# Namespaces uploads under company_id to avoid filename collisions
def compliance_document_upload_path(instance, filename):
    return f'{instance.company_id}/accounts/{filename}'


# Compliance documents uploaded during registration or re-submission
class ComplianceDocument(models.Model):
    class DocType(models.TextChoices):
        INSURANCE = 'insurance', 'Insurance'
        AUTHORITY = 'authority', 'Authority'
        BUSINESS_LICENSE = 'business_license', 'Business License'
        COI = 'coi', 'Certificate of Insurance'
        OTHER = 'other', 'Other'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='compliance_documents')
    doc_type = models.CharField(max_length=20, choices=DocType.choices)
    file = models.FileField(upload_to=compliance_document_upload_path)
    file_name = models.CharField(max_length=255)
    file_size = models.IntegerField(help_text='File size in bytes')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-uploaded_at']

    def __str__(self):
        return f'{self.doc_type} — {self.company.name}'


# Returns expiry 15 minutes from now — used as the OtpCode default
def _otp_expiry():
    return timezone.now() + timedelta(minutes=15)


# Short-lived one-time codes for email verification, login 2FA, and password reset
class OtpCode(models.Model):
    class Purpose(models.TextChoices):
        EMAIL_VERIFICATION = 'email_verification', 'Email Verification'
        LOGIN_2FA = 'login_2fa', 'Login 2FA'
        PASSWORD_RESET = 'password_reset', 'Password Reset'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='otp_codes')
    code = models.CharField(max_length=6)
    purpose = models.CharField(max_length=20, choices=Purpose.choices)
    # Issued after OTP is verified for password_reset — used by /password/reset/
    reset_token = models.UUIDField(null=True, blank=True, default=None)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(default=_otp_expiry)
    used = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_at']

    def is_valid(self):
        return not self.used and timezone.now() < self.expires_at

    def __str__(self):
        return f'OTP {self.code} ({self.purpose}) — {self.user.email}'
