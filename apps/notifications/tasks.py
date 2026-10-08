import logging
from celery import shared_task
from django.contrib.auth import get_user_model
from apps.notifications.models import Notification
from apps.notifications.services import MAX_NOTIFICATIONS_PER_USER

logger = logging.getLogger(__name__)

User = get_user_model()


@shared_task
def prune_old_notifications():
    users_with_notifications = Notification.objects.values_list('recipient', flat=True).distinct()
    
    pruned_count = 0
    users_processed = 0
    
    for user_id in users_with_notifications:
        count = Notification.objects.filter(recipient_id=user_id).count()
        
        if count > MAX_NOTIFICATIONS_PER_USER:
            keep_ids = list(
                Notification.objects.filter(recipient_id=user_id)
                .order_by('-created_at')
                .values_list('id', flat=True)[:MAX_NOTIFICATIONS_PER_USER]
            )
            
            deleted = Notification.objects.filter(
                recipient_id=user_id
            ).exclude(id__in=keep_ids).delete()[0]
            
            pruned_count += deleted
            users_processed += 1
            
            logger.info(f"Pruned {deleted} notifications for user {user_id}")
    
    logger.info(f"Daily notification cleanup: pruned {pruned_count} notifications for {users_processed} users")
    
    return {
        'users_processed': users_processed,
        'notifications_pruned': pruned_count
    }
