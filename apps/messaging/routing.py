from django.urls import re_path

from .consumers import CommunityConsumer, DirectMessageConsumer

# WebSocket URL patterns — mounted in config/asgi.py
websocket_urlpatterns = [
    re_path(r'^ws/community/$', CommunityConsumer.as_asgi()),
    re_path(r'^ws/messages/(?P<conversation_id>[0-9a-f-]+)/$', DirectMessageConsumer.as_asgi()),
]
