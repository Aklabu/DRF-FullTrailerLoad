from django.conf import settings
from django.core.mail import send_mail


NOTIFY_EMAIL = 'FTLelelc@gmail.com'


# notification to the FTL team inbox on every new contact submission
def send_contact_notification_email(submission):
    send_mail(
        subject=f'New Contact Form Submission from {submission.full_name}',
        message=(
            f'Name:       {submission.full_name}\n'
            f'Email:      {submission.email}\n'
            f'Phone:      {submission.phone}\n'
            f'Company:    {submission.company_name or "—"}\n'
            f'Fleet Size: {submission.fleet_size or "—"}\n\n'
            f'Message:\n{submission.message}'
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[NOTIFY_EMAIL],
        fail_silently=True,
    )


# confirmation to the person who submitted the form
def send_contact_confirmation_email(submission):
    send_mail(
        subject='We received your message — FullTrailerLoad',
        message=(
            f'Hi {submission.full_name},\n\n'
            'Thanks for reaching out. Our team will get back to you shortly.\n\n'
            '— FullTrailerLoad Team'
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[submission.email],
        fail_silently=True,
    )


# sent to the submitter immediately after a ticket is created
def send_ticket_confirmation_email(ticket):
    send_mail(
        subject='We received your message — FullTrailerLoad Support',
        message=(
            f'Hi {ticket.full_name},\n\n'
            'Our freight operations team will respond within 2 business hours.\n\n'
            f'Ticket ID: {ticket.id}\n'
            f'Category: {ticket.get_inquiry_category_display()}\n\n'
            'If you need immediate assistance, reply to this email.\n\n'
            '— FullTrailerLoad Support Team'
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[ticket.work_email],
        fail_silently=True,
    )


# sent to the support team inbox when urgency is 'urgent' — triggers immediate triage
def send_urgent_alert_email(ticket):
    support_inbox = getattr(settings, 'SUPPORT_TEAM_EMAIL', settings.DEFAULT_FROM_EMAIL)
    send_mail(
        subject=f'[URGENT] New support ticket from {ticket.full_name}',
        message=(
            f'A new URGENT support ticket was submitted.\n\n'
            f'Name:     {ticket.full_name}\n'
            f'Email:    {ticket.work_email}\n'
            f'Company:  {ticket.company_name or "—"}\n'
            f'Category: {ticket.get_inquiry_category_display()}\n\n'
            f'Message:\n{ticket.message}\n\n'
            f'Ticket ID: {ticket.id}\n'
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[support_inbox],
        fail_silently=True,
    )
