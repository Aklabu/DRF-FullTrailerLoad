import uuid
from django.conf import settings
from django.db import models


def _attachment_upload_path(instance, filename):
    return f'messaging/direct/{instance.message.conversation_id}/{filename}'


def _community_attachment_upload_path(instance, filename):
    return f'messaging/community/{filename}'


# one conversation per (job/board_post/capacity, participant pair) — enforced via unique constraint
class Conversation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # participants — always exactly two users
    participant_a = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='conversations_as_a',
    )
    participant_b = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='conversations_as_b',
    )
    # optional FK to the load that spawned this conversation
    load = models.ForeignKey(
        'marketplace.Load',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='conversations',
    )
    # optional FK to a capacity posting that spawned this conversation
    capacity_posting = models.ForeignKey(
        'marketplace.CapacityPosting',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='conversations',
    )
    # optional FK to a board post (board app not yet built — nullable string fallback)
    board_post_id = models.UUIDField(null=True, blank=True)
    last_message_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-last_message_at']
        # one conversation per participant pair per job context
        constraints = [
            models.UniqueConstraint(
                fields=['participant_a', 'participant_b', 'load'],
                condition=models.Q(load__isnull=False),
                name='unique_conversation_per_load',
            ),
            models.UniqueConstraint(
                fields=['participant_a', 'participant_b', 'capacity_posting'],
                condition=models.Q(capacity_posting__isnull=False),
                name='unique_conversation_per_capacity',
            ),
        ]

    def __str__(self):
        return f'Conversation {self.id}'

    def other_participant(self, user):
        return self.participant_b if self.participant_a == user else self.participant_a


# a single message inside a direct conversation
class Message(models.Model):
    class Status(models.TextChoices):
        SENT = 'sent', 'Sent'
        FAILED = 'failed', 'Failed'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='sent_messages',
    )
    body = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.SENT)
    sent_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['sent_at']

    def __str__(self):
        return f'Message {self.id} in {self.conversation_id}'


# file or image attached to a direct message
class MessageAttachment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name='attachments')
    file = models.FileField(upload_to=_attachment_upload_path)
    name = models.CharField(max_length=255)
    size = models.IntegerField(help_text='File size in bytes')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.name} on {self.message_id}'


# tracks the last-read position per user per conversation for unread counts
class ConversationReadReceipt(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='read_receipts')
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='read_receipts',
    )
    last_read_at = models.DateTimeField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['conversation', 'user'],
                name='unique_read_receipt_per_user',
            )
        ]

    def __str__(self):
        return f'ReadReceipt for {self.user_id} in {self.conversation_id}'


# a message in the shared community chat room — visible to all authenticated users
class CommunityMessage(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='community_messages',
    )
    body = models.TextField(blank=True)
    sent_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['sent_at']

    def __str__(self):
        return f'CommunityMessage {self.id} by {self.sender_id}'


# file or image attached to a community message
class CommunityMessageAttachment(models.Model):
    class AttachmentType(models.TextChoices):
        IMAGE = 'image', 'Image'
        FILE = 'file', 'File'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    message = models.ForeignKey(CommunityMessage, on_delete=models.CASCADE, related_name='attachments')
    file = models.FileField(upload_to=_community_attachment_upload_path)
    name = models.CharField(max_length=255)
    size = models.IntegerField(help_text='File size in bytes')
    type = models.CharField(max_length=10, choices=AttachmentType.choices, default=AttachmentType.FILE)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.name} on community {self.message_id}'
