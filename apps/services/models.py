import uuid
from django.conf import settings
from django.db import models


def _attachment_upload_path(instance, filename):
    # scopes uploads under ticket id to avoid filename collisions
    return f'services/support/{instance.ticket_id}/{filename}'


# a support request submitted via the public contact form
class SupportTicket(models.Model):
    class Urgency(models.TextChoices):
        NORMAL = 'normal', 'Normal'
        URGENT = 'urgent', 'Urgent'

    class Category(models.TextChoices):
        ACCOUNT_VERIFICATION = 'account_verification', 'Account & SAFER / COI Verification'
        RATE_DISPUTE = 'rate_dispute', 'Rate Confirmation Dispute'
        BILLING_ESCROW = 'billing_escrow', 'Billing & Escrow'
        TECHNICAL_ISSUE = 'technical_issue', 'Technical Issue'

    class Status(models.TextChoices):
        OPEN = 'open', 'Open'
        IN_PROGRESS = 'in_progress', 'In Progress'
        RESOLVED = 'resolved', 'Resolved'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    full_name = models.CharField(max_length=255)
    work_email = models.EmailField()
    # optional free-text e.g. "Apex Logistics Inc (Carrier)"
    company_name = models.CharField(max_length=255, blank=True)
    urgency = models.CharField(max_length=10, choices=Urgency.choices, default=Urgency.NORMAL)
    inquiry_category = models.CharField(max_length=25, choices=Category.choices)
    message = models.TextField()
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.OPEN)
    # staff member handling this ticket — null until assigned
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_tickets',
        limit_choices_to={'is_staff': True},
    )
    staff_notes = models.TextField(blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'Ticket {self.id} — {self.full_name} ({self.urgency})'


# a file attached to a support ticket — stored on S3
class SupportAttachment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ticket = models.ForeignKey(SupportTicket, on_delete=models.CASCADE, related_name='attachments')
    file = models.FileField(upload_to=_attachment_upload_path)
    file_name = models.CharField(max_length=255)
    # raw byte size kept for admin display and download hints
    file_size = models.IntegerField(help_text='File size in bytes')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.file_name} on ticket {self.ticket_id}'
