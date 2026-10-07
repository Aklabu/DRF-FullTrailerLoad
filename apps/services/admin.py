from django.contrib import admin
from django.utils import timezone

from .models import SupportAttachment, SupportTicket


# inline to show attachments alongside their ticket in the detail view
class SupportAttachmentInline(admin.TabularInline):
    model = SupportAttachment
    extra = 0
    readonly_fields = ('file_name', 'file_size', 'file', 'uploaded_at')

    def has_add_permission(self, request, obj=None):
        return False


# main admin for support tickets — filterable by status, urgency and category
@admin.register(SupportTicket)
class SupportTicketAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'full_name', 'work_email', 'inquiry_category',
        'urgency', 'status', 'assigned_to', 'created_at',
    )
    list_filter = ('status', 'urgency', 'inquiry_category')
    search_fields = ('full_name', 'work_email', 'company_name', 'message')
    readonly_fields = ('id', 'created_at')
    ordering = ('-created_at',)
    inlines = [SupportAttachmentInline]
    # staff_notes and assigned_to are the only fields staff routinely edit
    fieldsets = (
        ('Submitter', {
            'fields': ('id', 'full_name', 'work_email', 'company_name', 'created_at'),
        }),
        ('Request', {
            'fields': ('urgency', 'inquiry_category', 'message'),
        }),
        ('Triage', {
            'fields': ('status', 'assigned_to', 'staff_notes', 'resolved_at'),
        }),
    )

    def save_model(self, request, obj, form, change):
        # auto-stamp resolved_at when staff marks a ticket resolved
        if change and obj.status == SupportTicket.Status.RESOLVED and not obj.resolved_at:
            obj.resolved_at = timezone.now()
        super().save_model(request, obj, form, change)
