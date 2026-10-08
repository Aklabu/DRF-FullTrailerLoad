import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from apps.accounts.models import User
from apps.reviews.models import Review
from apps.notifications.models import NotificationPreferences
from apps.notifications import services

logger = logging.getLogger(__name__)


@receiver(post_save, sender=User)
def create_notification_preferences_for_user(sender, instance, created, **kwargs):
    if created:
        NotificationPreferences.objects.get_or_create(user=instance)
        logger.info(f"Created notification preferences for user {instance.id}")


@receiver(post_save, sender=Review)
def notify_review_received(sender, instance, created, **kwargs):
    if created:
        reviewee_company = instance.reviewee
        
        if hasattr(reviewee_company, 'user') and reviewee_company.user:
            reviewee_user = reviewee_company.user
            
            services.notify(
                recipient=reviewee_user,
                notification_type='review_received',
                actor=instance.reviewer.user if hasattr(instance.reviewer, 'user') and instance.reviewer.user else None,
                target_kind='review',
                target_id=str(instance.id),
                meta={
                    'rating': instance.overall_rating,
                    'reviewer_name': instance.reviewer.name,
                    'review_id': str(instance.id)
                }
            )
            
            logger.info(f"Notified user {reviewee_user.id} about new review {instance.id}")
