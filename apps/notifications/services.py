import logging
from typing import Optional, Dict, Any
from django.utils import timezone
from django.db import transaction
from django.db.models import Q
from apps.notifications.models import Notification, NotificationPreferences

logger = logging.getLogger(__name__)

MAX_NOTIFICATIONS_PER_USER = 50


def notify(
    recipient,
    notification_type: str,
    actor=None,
    target_kind: str = None,
    target_id: str = None,
    meta: Optional[Dict[str, Any]] = None,
    title: str = None,
    body: str = None,
    priority: str = 'normal',
    group_key: Optional[str] = None
):
    try:
        preferences = NotificationPreferences.objects.filter(user=recipient).first()
        if not preferences:
            preferences, _ = NotificationPreferences.objects.get_or_create(user=recipient)
        
        type_enabled = getattr(preferences, notification_type, True)
        if not type_enabled:
            logger.info(f"Notification {notification_type} disabled for user {recipient.id}")
            return None

        with transaction.atomic():
            if group_key:
                existing = Notification.objects.filter(
                    recipient=recipient,
                    group_key=group_key,
                    is_read=False
                ).first()
                
                if existing:
                    existing.body = body or existing.body
                    existing.title = title or existing.title
                    existing.created_at = timezone.now()
                    if meta:
                        existing_meta = existing.meta or {}
                        existing_meta.update(meta)
                        if 'count' in existing_meta:
                            existing_meta['count'] = existing_meta.get('count', 1) + 1
                        existing.meta = existing_meta
                    existing.save()
                    logger.info(f"Updated grouped notification {existing.id} for user {recipient.id}")
                    return existing

            notification = Notification.objects.create(
                recipient=recipient,
                type=notification_type,
                actor=actor,
                target_kind=target_kind or 'load',
                target_id=target_id,
                meta=meta or {},
                title=title or _build_title(notification_type, meta),
                body=body or _build_body(notification_type, meta),
                priority=priority,
                group_key=group_key
            )

            _prune_old_notifications(recipient)

            logger.info(f"Created notification {notification.id} for user {recipient.id}")
            return notification

    except Exception as e:
        logger.error(f"Failed to create notification for user {recipient.id}: {str(e)}", exc_info=True)
        return None


def _prune_old_notifications(recipient):
    count = Notification.objects.filter(recipient=recipient).count()
    
    if count > MAX_NOTIFICATIONS_PER_USER:
        keep_ids = list(
            Notification.objects.filter(recipient=recipient)
            .order_by('-created_at')
            .values_list('id', flat=True)[:MAX_NOTIFICATIONS_PER_USER]
        )
        
        deleted_count = Notification.objects.filter(
            recipient=recipient
        ).exclude(id__in=keep_ids).delete()[0]
        
        logger.info(f"Pruned {deleted_count} old notifications for user {recipient.id}")


def _build_title(notification_type: str, meta: Optional[Dict] = None) -> str:
    meta = meta or {}
    
    titles = {
        'bid_placed': f"New bid: ${meta.get('amount', '0')}",
        'bid_countered': f"Counter offer: ${meta.get('counter_amount', '0')}",
        'counter_accepted': "Counter accepted",
        'review_received': f"New {meta.get('rating', 5)}-star review",
        'new_message': f"New message from {meta.get('sender_name', 'someone')}",
    }
    
    return titles.get(notification_type, "New notification")


def _build_body(notification_type: str, meta: Optional[Dict] = None) -> str:
    meta = meta or {}
    
    bodies = {
        'bid_placed': f"{meta.get('carrier_name', 'A carrier')} placed a bid of ${meta.get('amount', '0')} on your load",
        'bid_countered': f"The load owner countered with ${meta.get('counter_amount', '0')}",
        'counter_accepted': f"{meta.get('carrier_name', 'The carrier')} accepted your counter offer of ${meta.get('agreed_price', '0')}",
        'review_received': f"{meta.get('reviewer_name', 'Someone')} left you a {meta.get('rating', 5)}-star review",
        'new_message': f"You have {meta.get('count', 1)} new message(s) from {meta.get('sender_name', 'someone')}",
    }
    
    return bodies.get(notification_type, "You have a new notification")


def mark_notification_read(notification_id, user):
    try:
        notification = Notification.objects.filter(
            id=notification_id,
            recipient=user
        ).first()
        
        if notification and not notification.is_read:
            notification.is_read = True
            notification.read_at = timezone.now()
            notification.save()
            logger.info(f"Marked notification {notification_id} as read")
        
        return notification
    except Exception as e:
        logger.error(f"Failed to mark notification {notification_id} as read: {str(e)}")
        return None


def mark_all_read(user, category=None):
    try:
        filters = {'recipient': user, 'is_read': False}
        if category:
            filters['category'] = category
        
        count = Notification.objects.filter(**filters).update(
            is_read=True,
            read_at=timezone.now()
        )
        
        logger.info(f"Marked {count} notifications as read for user {user.id}")
        return count
    except Exception as e:
        logger.error(f"Failed to mark all notifications as read: {str(e)}")
        return 0


def get_unread_counts(user):
    from django.db.models import Count, Q
    
    counts = Notification.objects.filter(
        recipient=user,
        is_read=False
    ).values('category').annotate(count=Count('id'))
    
    result = {'total': 0, 'bids': 0, 'messages': 0, 'reviews': 0}
    
    for item in counts:
        category = item['category']
        count = item['count']
        result[category] = count
        result['total'] += count
    
    return result


def mark_related_notifications_read(user, notification_type=None, meta_filters=None):
    try:
        filters = {'recipient': user, 'is_read': False}
        
        if notification_type:
            filters['type'] = notification_type
        
        notifications = Notification.objects.filter(**filters)
        
        if meta_filters:
            for key, value in meta_filters.items():
                notifications = notifications.filter(**{f'meta__{key}': value})
        
        count = notifications.update(is_read=True, read_at=timezone.now())
        logger.info(f"Marked {count} related notifications as read for user {user.id}")
        return count
    except Exception as e:
        logger.error(f"Failed to mark related notifications as read: {str(e)}")
        return 0


def mark_conversation_notifications_read(user, conversation_id):
    try:
        count = Notification.objects.filter(
            recipient=user,
            group_key=f'conv:{conversation_id}',
            is_read=False
        ).update(is_read=True, read_at=timezone.now())
        
        logger.info(f"Marked {count} conversation notifications as read for user {user.id}")
        return count
    except Exception as e:
        logger.error(f"Failed to mark conversation notifications as read: {str(e)}")
        return 0
