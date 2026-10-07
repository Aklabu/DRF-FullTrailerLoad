from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils import timezone
from django.utils.html import format_html
from unfold.admin import ModelAdmin as UnfoldModelAdmin

from .models import Company, ComplianceDocument, DotMcInfo, OtpCode, User
from .notifications import (
    send_verification_approved_email,
    send_verification_rejected_email,
    send_needs_info_email,
)


# Editable inline — lets admin view and update DOT/MC numbers on the Company page
class DotMcInfoInline(admin.StackedInline):
    model = DotMcInfo
    can_delete = False
    verbose_name_plural = 'DOT / MC Info'
    extra = 0


# Read-only inline — shows uploaded compliance docs with download links
class ComplianceDocumentInline(admin.TabularInline):
    model = ComplianceDocument
    extra = 0
    readonly_fields = ('doc_type', 'file_link', 'file_name', 'file_size', 'uploaded_at')
    fields = ('doc_type', 'file_link', 'file_name', 'file_size', 'uploaded_at')

    def file_link(self, obj):
        if obj.file:
            return format_html('<a href="{}" target="_blank">Download</a>', obj.file.url)
        return '—'
    file_link.short_description = 'File'

    def has_add_permission(self, request, obj=None):
        return False


# Placeholder — email will be sent once email templates are ready
def _send_verification_email(company, action_label):
    pass


@admin.action(description='✅ Approve as Basic (bulletin tier)')
def approve_as_basic(modeladmin, request, queryset):
    updated = queryset.update(
        verification_status=Company.VerificationStatus.BASIC,
        tier=Company.Tier.BULLETIN,
        reviewed_at=timezone.now(),
        rejection_reason='',
        info_requested='',
    )
    for company in queryset:
        send_verification_approved_email(company, 'Basic')
    messages.success(request, f'{updated} company/companies approved as Basic.')


@admin.action(description='⭐ Approve as Verified (marketplace tier)')
def approve_as_verified(modeladmin, request, queryset):
    updated = queryset.update(
        verification_status=Company.VerificationStatus.VERIFIED,
        tier=Company.Tier.MARKETPLACE,
        reviewed_at=timezone.now(),
        rejection_reason='',
        info_requested='',
    )
    for company in queryset:
        send_verification_approved_email(company, 'Verified')
    messages.success(request, f'{updated} company/companies approved as Verified.')


# Sets status to needs_info so admin can fill in the info_requested field on the change page
@admin.action(description='ℹ️ Request more info')
def request_more_info(modeladmin, request, queryset):
    updated = queryset.update(
        verification_status=Company.VerificationStatus.NEEDS_INFO,
        reviewed_at=timezone.now(),
    )
    for company in queryset:
        send_needs_info_email(company)
    messages.warning(request, f'{updated} company/companies marked as Needs Info.')


@admin.action(description='❌ Reject')
def reject_company(modeladmin, request, queryset):
    updated = queryset.update(
        verification_status=Company.VerificationStatus.REJECTED,
        reviewed_at=timezone.now(),
    )
    for company in queryset:
        send_verification_rejected_email(company)
    messages.error(request, f'{updated} company/companies rejected.')


@admin.register(Company)
class CompanyAdmin(UnfoldModelAdmin):
    list_display = ('name', 'email', 'role', 'tier', 'verification_status', 'submitted_at', 'reviewed_at')
    list_filter = ('role', 'tier', 'verification_status')
    search_fields = ('name', 'email')
    readonly_fields = ('id', 'created_at', 'updated_at', 'submitted_at', 'reviewed_at')
    inlines = [DotMcInfoInline, ComplianceDocumentInline]
    actions = [approve_as_basic, approve_as_verified, request_more_info, reject_company]

    fieldsets = (
        ('Identity', {
            'fields': ('id', 'name', 'email', 'phone', 'website'),
        }),
        ('Address', {
            'fields': ('address_line1', 'address_line2', 'city', 'state', 'zip_code'),
        }),
        ('Status', {
            'fields': (
                'role', 'tier', 'verification_status',
                'rejection_reason', 'info_requested',
                'submitted_at', 'reviewed_at', 'has_seen_onboarding',
            ),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )


# Extends Django's built-in UserAdmin, swapping username for email
@admin.register(User)
class UserAdmin(UnfoldModelAdmin, BaseUserAdmin):
    list_display = ('email', 'company', 'is_active', 'is_staff', 'date_joined')
    list_filter = ('is_active', 'is_staff')
    search_fields = ('email', 'company__name')
    ordering = ('-date_joined',)
    readonly_fields = ('id', 'date_joined', 'last_login')
    filter_horizontal = ('groups', 'user_permissions')

    fieldsets = (
        (None, {'fields': ('id', 'email', 'password')}),
        ('Company', {'fields': ('company',)}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Dates', {'fields': ('date_joined', 'last_login')}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password1', 'password2', 'company', 'is_staff', 'is_active'),
        }),
    )


# Read-only — exists for debugging OTP issues, not for editing
@admin.register(OtpCode)
class OtpCodeAdmin(UnfoldModelAdmin):
    list_display = ('user_email', 'code', 'purpose', 'expires_at', 'used')
    list_filter = ('purpose', 'used')
    search_fields = ('user__email',)
    readonly_fields = ('id', 'user', 'code', 'purpose', 'created_at', 'expires_at', 'used')

    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = 'User Email'
    user_email.admin_order_field = 'user__email'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
