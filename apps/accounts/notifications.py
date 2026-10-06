from django.core.mail import send_mail


# Email notifications 

def send_welcome_email(user, company):
    subject = 'Welcome to FullTrailerLoad'
    if company.tier == 'marketplace':
        body = (
            f'Hi {company.name},\n\n'
            'Your registration is received and your account is pending verification. '
            'Our team will review your documents and notify you within 1–2 business days.'
        )
    else:
        body = f'Hi {company.name},\n\nWelcome to FullTrailerLoad! Your bulletin board account is active.'
    send_mail(subject, body, None, [user.email], fail_silently=True)


def send_otp_email(user, code):
    send_mail(
        'Your FullTrailerLoad password reset code',
        f'Your one-time code is: {code}\n\nIt expires in 15 minutes.',
        None,
        [user.email],
        fail_silently=True,
    )


def send_verification_approved_email(company, tier_label):
    send_mail(
        'Your FullTrailerLoad account has been approved',
        f'Hi {company.name},\n\nYour account has been approved as {tier_label}. You can now log in.',
        None,
        [company.email],
        fail_silently=True,
    )


def send_verification_rejected_email(company):
    send_mail(
        'FullTrailerLoad account verification update',
        f'Hi {company.name},\n\nUnfortunately your account verification was not approved. '
        'Please contact support if you have any questions.',
        None,
        [company.email],
        fail_silently=True,
    )


def send_needs_info_email(company):
    send_mail(
        'Additional information required for your FullTrailerLoad account',
        f'Hi {company.name},\n\nOur team needs additional information to complete your verification.\n\n'
        f'Details: {company.info_requested}',
        None,
        [company.email],
        fail_silently=True,
    )

