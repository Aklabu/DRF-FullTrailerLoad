import os
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

app = Celery('config')

app.config_from_object('django.conf:settings', namespace='CELERY')

app.autodiscover_tasks()

# scheduled tasks
app.conf.beat_schedule = {
    'prune-old-notifications-daily': {
        'task': 'apps.notifications.tasks.prune_old_notifications',
        'schedule': crontab(hour=2, minute=0),
    },
}

app.conf.timezone = 'UTC'
