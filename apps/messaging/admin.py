from django.contrib import admin
from unfold.admin import ModelAdmin as UnfoldModelAdmin

from .models import (
    CommunityMessage,
    CommunityMessageAttachment,
    Conversation,
    ConversationReadReceipt,
    Message,
    MessageAttachment,
)


# read-only inline showing messages inside a conversation
class MessageInline(admin.TabularInline):
    model = Message
    extra = 0
    readonly_fields = ('id', 'sender', 'body', 'status', 'sent_at')
    fields = ('sender', 'body', 'status', 'sent_at')
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


# admin view for direct message conversations with message inline
@admin.register(Conversation)
class ConversationAdmin(UnfoldModelAdmin):
    list_display = ('id', 'participant_a_email', 'participant_b_email', 'job_id', 'last_message_at')
    search_fields = ('participant_a__email', 'participant_b__email', 'load__job_id')
    readonly_fields = ('id', 'created_at', 'last_message_at')
    inlines = [MessageInline]

    def participant_a_email(self, obj):
        return obj.participant_a.email
    participant_a_email.short_description = 'Participant A'

    def participant_b_email(self, obj):
        return obj.participant_b.email
    participant_b_email.short_description = 'Participant B'

    def job_id(self, obj):
        return obj.load.job_id if obj.load else '-'
    job_id.short_description = 'Load'


# admin view for individual direct messages
@admin.register(Message)
class MessageAdmin(UnfoldModelAdmin):
    list_display = ('id', 'conversation_id', 'sender_email', 'body_preview', 'status', 'sent_at')
    list_filter = ('status',)
    search_fields = ('sender__email', 'body')
    readonly_fields = ('id', 'sent_at')

    def sender_email(self, obj):
        return obj.sender.email
    sender_email.short_description = 'Sender'

    def body_preview(self, obj):
        return obj.body[:60] if obj.body else '-'
    body_preview.short_description = 'Body'


# admin view for community chat messages
@admin.register(CommunityMessage)
class CommunityMessageAdmin(UnfoldModelAdmin):
    list_display = ('id', 'sender_email', 'body_preview', 'sent_at')
    search_fields = ('sender__email', 'body')
    readonly_fields = ('id', 'sent_at')

    def sender_email(self, obj):
        return obj.sender.email
    sender_email.short_description = 'Sender'

    def body_preview(self, obj):
        return obj.body[:60] if obj.body else '-'
    body_preview.short_description = 'Body'
