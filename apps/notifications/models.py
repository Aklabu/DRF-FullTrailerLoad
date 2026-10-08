import uuid
from django.db import models
from django.conf import settings


class Notification(models.Model):
    TYPE_CHOICES = [
        ('bid_placed', 'Bid Placed'),
        ('bid_countered', 'Bid Countered'),
        ('counter_accepted', 'Counter Accepted'),
        ('review_received', 'Review Received'),
        ('new_message', 'New Message'),
    ]

    CATEGORY_CHOICES = [
        ('bids', 'Bids'),
        ('messages', 'Messages'),
        ('reviews', 'Reviews'),
    ]

    PRIORITY_CHOICES = [
        ('normal', 'Normal'),
        ('high', 'High'),
    ]

    TARGET_KIND_CHOICES = [
        ('load', 'Load'),
        ('booking', 'Booking'),
        ('review', 'Review'),
        ('conversation', 'Conversation'),
    ]

    TYPE_TO_CATEGORY = {
        'bid_placed': 'bids',
        'bid_countered': 'bids',
        'counter_accepted': 'bids',
        'review_received': 'reviews',
        'new_message': 'messages',
    }

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications',
        db_index=True
    )
    type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    title = models.CharField(max_length=255)
    body = models.TextField()
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='normal')
    is_read = models.BooleanField(default=False, db_index=True)
    read_at = models.DateTimeField(null=True, blank=True)
    target_kind = models.CharField(max_length=20, choices=TARGET_KIND_CHOICES)
    target_id = models.UUIDField()
    meta = models.JSONField(default=dict, blank=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='notifications_caused'
    )
    group_key = models.CharField(max_length=255, null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['recipient', 'is_read', '-created_at'], name='notif_recip_read_created'),
            models.Index(fields=['recipient', 'category', 'is_read'], name='notif_recip_cat_read'),
            models.Index(fields=['recipient', 'group_key', 'is_read'], name='notif_recip_group_read'),
        ]

    def __str__(self):
        return f"{self.type} for {self.recipient.email} - {self.title}"

    def save(self, *args, **kwargs):
        if not self.category:
            self.category = self.TYPE_TO_CATEGORY.get(self.type, 'bids')
        super().save(*args, **kwargs)


class NotificationPreferences(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notification_preferences'
    )
    bid_placed = models.BooleanField(default=True)
    bid_countered = models.BooleanField(default=True)
    counter_accepted = models.BooleanField(default=True)
    review_received = models.BooleanField(default=True)
    new_message = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Notification Preferences"

    def __str__(self):
        return f"Preferences for {self.user.email}"
