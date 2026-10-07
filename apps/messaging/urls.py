from django.urls import path

from .views import (
    CommunityHistoryView,
    ConversationThreadView,
    InboxView,
    MarkReadView,
    SendCommunityMessageView,
    SendMessageView,
    UnreadCountView,
)

# direct message endpoints
urlpatterns = [
    path('messages/', InboxView.as_view(), name='messaging-inbox'),
    path('messages/send/', SendMessageView.as_view(), name='messaging-send'),
    path('messages/unread-count/', UnreadCountView.as_view(), name='messaging-unread-count'),
    path('messages/<uuid:conversation_id>/', ConversationThreadView.as_view(), name='messaging-thread'),
    path('messages/<uuid:conversation_id>/read/', MarkReadView.as_view(), name='messaging-mark-read'),

    # community chat endpoints
    path('community/messages/', CommunityHistoryView.as_view(), name='community-history'),
    path('community/messages/send/', SendCommunityMessageView.as_view(), name='community-send'),
]
