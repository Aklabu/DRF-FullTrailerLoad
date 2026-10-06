from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Company


@receiver(post_save, sender=Company)
def create_notification_preferences(sender, instance, created, **kwargs):
    # Placeholder — NotificationPreferences lives in the notifications app.
    # That app will register its own signal; nothing to do here yet.
    pass
