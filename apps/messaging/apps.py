from django.apps import AppConfig


# messaging app — direct messages, community chat, and WebSocket consumers
class MessagingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.messaging'
    label = 'messaging'
