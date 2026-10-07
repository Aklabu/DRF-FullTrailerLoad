from rest_framework import serializers

from .models import (
    CommunityMessage,
    CommunityMessageAttachment,
    Conversation,
    Message,
    MessageAttachment,
)


# attachment download info embedded inside a direct message
class MessageAttachmentSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()

    def get_url(self, obj):
        request = self.context.get('request')
        if obj.file and request:
            return request.build_absolute_uri(obj.file.url)
        return obj.file.url if obj.file else None

    class Meta:
        model = MessageAttachment
        fields = ('id', 'name', 'url', 'size')


# full message object used in conversation thread and WS broadcast payloads
class MessageSerializer(serializers.ModelSerializer):
    sender_id = serializers.UUIDField(source='sender.id', read_only=True)
    sender_name = serializers.CharField(source='sender.company.name', read_only=True)
    attachments = MessageAttachmentSerializer(many=True, read_only=True)

    class Meta:
        model = Message
        fields = ('id', 'sender_id', 'sender_name', 'body', 'attachments', 'sent_at', 'status')


# counterparty summary shown in the inbox list and conversation header
class CounterpartySerializer(serializers.Serializer):
    id = serializers.UUIDField(source='company.id', read_only=True)
    company_name = serializers.CharField(source='company.name', read_only=True)
    role = serializers.CharField(source='company.role', read_only=True)
    verification_status = serializers.CharField(source='company.verification_status', read_only=True)


# inbox card — one entry per conversation with unread count and last message preview
class ConversationInboxSerializer(serializers.ModelSerializer):
    counterparty = serializers.SerializerMethodField()
    job_id = serializers.SerializerMethodField()
    job_status = serializers.SerializerMethodField()
    last_message = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()

    def get_counterparty(self, obj):
        user = self.context['request'].user
        other = obj.other_participant(user)
        return CounterpartySerializer(other, context=self.context).data

    def get_job_id(self, obj):
        return obj.load.job_id if obj.load else None

    def get_job_status(self, obj):
        return obj.load.status if obj.load else None

    def get_last_message(self, obj):
        last = obj.messages.order_by('-sent_at').first()
        if not last:
            return None
        return last.body[:50] if last.body else None

    def get_unread_count(self, obj):
        user = self.context['request'].user
        receipt = obj.read_receipts.filter(user=user).first()
        if not receipt:
            return obj.messages.exclude(sender=user).count()
        return obj.messages.filter(
            sent_at__gt=receipt.last_read_at
        ).exclude(sender=user).count()

    class Meta:
        model = Conversation
        fields = (
            'id', 'counterparty', 'job_id', 'job_status',
            'last_message', 'last_message_at', 'unread_count',
        )


# job context embedded in the conversation thread header
class ConversationJobSerializer(serializers.Serializer):
    job_id = serializers.CharField()
    origin = serializers.CharField()
    destination = serializers.CharField()
    pickup_date = serializers.DateField()
    status = serializers.CharField()
    load_id = serializers.UUIDField(source='id')


# full conversation detail for the thread view
class ConversationDetailSerializer(serializers.ModelSerializer):
    job = serializers.SerializerMethodField()
    counterparty = serializers.SerializerMethodField()

    def get_job(self, obj):
        if not obj.load:
            return None
        return ConversationJobSerializer(obj.load).data

    def get_counterparty(self, obj):
        user = self.context['request'].user
        other = obj.other_participant(user)
        return CounterpartySerializer(other, context=self.context).data

    class Meta:
        model = Conversation
        fields = ('id', 'job', 'counterparty')


# validates incoming direct message — supports new and existing conversations
class SendMessageSerializer(serializers.Serializer):
    conversation_id = serializers.UUIDField(required=False)
    load_id = serializers.UUIDField(required=False)
    capacity_id = serializers.UUIDField(required=False)
    board_post_id = serializers.UUIDField(required=False)
    recipient_id = serializers.UUIDField(required=False)
    body = serializers.CharField(required=False, allow_blank=True, default='')
    attachments = serializers.ListField(
        child=serializers.FileField(),
        required=False,
        allow_empty=True,
    )

    def validate(self, attrs):
        # must provide either conversation_id or recipient_id for a new conversation
        if not attrs.get('conversation_id') and not attrs.get('recipient_id'):
            raise serializers.ValidationError(
                'Provide conversation_id for existing or recipient_id for new conversation.'
            )
        if not attrs.get('body') and not attrs.get('attachments'):
            raise serializers.ValidationError('Message must have a body or at least one attachment.')
        return attrs


# attachment for community messages — includes type and size for render decisions
class CommunityMessageAttachmentSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()

    def get_url(self, obj):
        request = self.context.get('request')
        if obj.file and request:
            return request.build_absolute_uri(obj.file.url)
        return obj.file.url if obj.file else None

    class Meta:
        model = CommunityMessageAttachment
        fields = ('id', 'name', 'url', 'size', 'type')


# full community message — includes sender role for avatar colour mapping on the frontend
class CommunityMessageSerializer(serializers.ModelSerializer):
    sender_id = serializers.UUIDField(source='sender.id', read_only=True)
    sender_name = serializers.CharField(source='sender.company.name', read_only=True)
    sender_role = serializers.CharField(source='sender.company.role', read_only=True)
    attachments = CommunityMessageAttachmentSerializer(many=True, read_only=True)
    status = serializers.SerializerMethodField()

    def get_status(self, obj):
        # server-persisted messages are always sent
        return 'sent'

    class Meta:
        model = CommunityMessage
        fields = ('id', 'sender_id', 'sender_name', 'sender_role', 'body', 'attachments', 'sent_at', 'status')


# validates a new community message submission
class SendCommunityMessageSerializer(serializers.Serializer):
    body = serializers.CharField(required=False, allow_blank=True, default='')
    attachments = serializers.ListField(
        child=serializers.FileField(),
        required=False,
        allow_empty=True,
    )

    def validate(self, attrs):
        if not attrs.get('body') and not attrs.get('attachments'):
            raise serializers.ValidationError('Message must have a body or at least one attachment.')
        return attrs
