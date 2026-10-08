from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from utils.response import CustomResponse
from apps.notifications import services as notification_service

from .models import (
    CommunityMessage,
    CommunityMessageAttachment,
    Conversation,
    ConversationReadReceipt,
    Message,
    MessageAttachment,
)
from .serializers import (
    CommunityMessageSerializer,
    ConversationDetailSerializer,
    ConversationInboxSerializer,
    MessageSerializer,
    SendCommunityMessageSerializer,
    SendMessageSerializer,
)


def _participant_filter(user):
    return Q(participant_a=user) | Q(participant_b=user)


# returns all conversations for the current user ordered by last message, with total unread count
class InboxView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = Conversation.objects.filter(
            _participant_filter(request.user)
        ).select_related(
            'participant_a__company',
            'participant_b__company',
            'load',
        ).prefetch_related('messages', 'read_receipts')

        q = request.query_params.get('q', '').strip()
        if q:
            qs = qs.filter(
                Q(load__job_id__icontains=q) |
                Q(participant_a__company__name__icontains=q) |
                Q(participant_b__company__name__icontains=q)
            )

        serializer = ConversationInboxSerializer(
            qs, many=True, context={'request': request}
        )

        # aggregate unread count for the tab badge
        total_unread = sum(c['unread_count'] for c in serializer.data)

        return CustomResponse.success(
            message='Inbox retrieved.',
            data={
                'total_unread': total_unread,
                'conversations': serializer.data,
            },
        )


# returns conversation header + paginated message history (cursor-based, 30 per page)
class ConversationThreadView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, conversation_id):
        try:
            conv = Conversation.objects.select_related(
                'participant_a__company',
                'participant_b__company',
                'load',
            ).get(id=conversation_id)
        except Conversation.DoesNotExist:
            return CustomResponse.error('Conversation not found.', status_code=status.HTTP_404_NOT_FOUND)

        if conv.participant_a != request.user and conv.participant_b != request.user:
            return CustomResponse.error('You are not a participant.', status_code=status.HTTP_403_FORBIDDEN)

        messages_qs = conv.messages.select_related('sender__company').prefetch_related('attachments')

        # cursor — load messages older than the given message id
        before = request.query_params.get('before')
        if before:
            try:
                pivot = Message.objects.get(id=before, conversation=conv)
                messages_qs = messages_qs.filter(sent_at__lt=pivot.sent_at)
            except Message.DoesNotExist:
                pass

        messages_qs = messages_qs.order_by('-sent_at')[:30]
        # reverse to return oldest-first in the response
        messages = list(reversed(list(messages_qs)))

        return CustomResponse.success(
            message='Thread retrieved.',
            data={
                'conversation': ConversationDetailSerializer(conv, context={'request': request}).data,
                'messages': MessageSerializer(messages, many=True, context={'request': request}).data,
            },
        )


# creates or finds a conversation, saves the message, handles attachments, and broadcasts via WS
class SendMessageView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    @transaction.atomic
    def post(self, request):
        serializer = SendMessageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        conv = self._get_or_create_conversation(request.user, data)
        if conv is None:
            return CustomResponse.error(
                'Recipient not found or invalid.',
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        message = Message.objects.create(
            conversation=conv,
            sender=request.user,
            body=data.get('body', ''),
        )

        for f in data.get('attachments', []):
            MessageAttachment.objects.create(
                message=message,
                file=f,
                name=f.name,
                size=f.size,
            )

        conv.last_message_at = message.sent_at
        conv.save(update_fields=['last_message_at'])

        self._broadcast(conv, message, request)

        recipient = conv.other_participant(request.user)
        sender_company = getattr(request.user, 'company', None)
        sender_name = sender_company.name if sender_company else request.user.email
        
        notification_service.notify(
            recipient=recipient,
            notification_type='new_message',
            actor=request.user,
            target_kind='conversation',
            target_id=str(conv.id),
            group_key=f'conv:{conv.id}',
            meta={
                'sender_name': sender_name,
                'conversation_id': str(conv.id),
                'count': 1
            }
        )

        return CustomResponse.success(
            message='Message sent.',
            data={
                'conversation_id': str(conv.id),
                'message': MessageSerializer(message, context={'request': request}).data,
            },
            status_code=status.HTTP_201_CREATED,
        )

    def _get_or_create_conversation(self, sender, data):
        from django.contrib.auth import get_user_model
        User = get_user_model()

        if data.get('conversation_id'):
            try:
                conv = Conversation.objects.get(id=data['conversation_id'])
                if conv.participant_a != sender and conv.participant_b != sender:
                    return None
                return conv
            except Conversation.DoesNotExist:
                return None

        # resolve recipient
        try:
            recipient = User.objects.get(company__id=data['recipient_id'])
        except User.DoesNotExist:
            return None

        # normalise participant order to avoid duplicate conversations from both directions
        a, b = (sender, recipient) if sender.id < recipient.id else (recipient, sender)

        load_id = data.get('load_id')
        capacity_id = data.get('capacity_id')
        board_post_id = data.get('board_post_id')

        lookup = {'participant_a': a, 'participant_b': b}
        if load_id:
            lookup['load_id'] = load_id
        elif capacity_id:
            lookup['capacity_posting_id'] = capacity_id
        elif board_post_id:
            lookup['board_post_id'] = board_post_id

        conv, _ = Conversation.objects.get_or_create(**lookup)
        return conv

    def _broadcast(self, conv, message, request):
        channel_layer = get_channel_layer()
        if not channel_layer:
            return
        company = getattr(message.sender, 'company', None)
        payload = {
            'id': str(message.id),
            'sender_id': str(message.sender.id),
            'sender_name': company.name if company else message.sender.email,
            'body': message.body,
            'attachments': [],
            'sent_at': message.sent_at.isoformat(),
            'status': 'sent',
        }
        try:
            async_to_sync(channel_layer.group_send)(
                f'conversation_{conv.id}',
                {'type': 'chat_message', 'payload': payload},
            )
        except Exception:
            # Redis unavailable — message is already saved, WS broadcast is best-effort
            pass


# upserts a read receipt for the current user — drives unread_count to zero in the inbox
class MarkReadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, conversation_id):
        try:
            conv = Conversation.objects.get(id=conversation_id)
        except Conversation.DoesNotExist:
            return CustomResponse.error('Conversation not found.', status_code=status.HTTP_404_NOT_FOUND)

        if conv.participant_a != request.user and conv.participant_b != request.user:
            return CustomResponse.error('You are not a participant.', status_code=status.HTTP_403_FORBIDDEN)

        ConversationReadReceipt.objects.update_or_create(
            conversation=conv,
            user=request.user,
            defaults={'last_read_at': timezone.now()},
        )
        
        notification_service.mark_conversation_notifications_read(
            user=request.user,
            conversation_id=str(conversation_id)
        )
        
        return CustomResponse.success(
            message='Marked as read.',
            status_code=status.HTTP_204_NO_CONTENT,
        )


# lightweight endpoint for the navbar bell — returns only the total unread direct message count
class UnreadCountView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        conversations = Conversation.objects.filter(_participant_filter(request.user)).prefetch_related(
            'messages', 'read_receipts'
        )
        total = 0
        for conv in conversations:
            receipt = conv.read_receipts.filter(user=request.user).first()
            if not receipt:
                total += conv.messages.exclude(sender=request.user).count()
            else:
                total += conv.messages.filter(
                    sent_at__gt=receipt.last_read_at
                ).exclude(sender=request.user).count()

        return CustomResponse.success(
            message='Unread count retrieved.',
            data={'count': total},
        )


# returns paginated community chat history — latest 30, cursor-based for infinite scroll
class CommunityHistoryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = CommunityMessage.objects.select_related(
            'sender__company'
        ).prefetch_related('attachments').order_by('-sent_at')

        before = request.query_params.get('before')
        if before:
            try:
                pivot = CommunityMessage.objects.get(id=before)
                qs = qs.filter(sent_at__lt=pivot.sent_at)
            except CommunityMessage.DoesNotExist:
                pass

        limit = min(int(request.query_params.get('limit', 30)), 100)
        messages = list(reversed(list(qs[:limit])))
        has_more = qs.count() > limit

        return CustomResponse.success(
            message='Community messages retrieved.',
            data={
                'messages': CommunityMessageSerializer(messages, many=True, context={'request': request}).data,
                'has_more': has_more,
                'oldest_id': str(messages[0].id) if messages else None,
            },
        )


# saves a community message, handles attachments, and broadcasts to all WS clients
class SendCommunityMessageView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    @transaction.atomic
    def post(self, request):
        serializer = SendCommunityMessageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        message = CommunityMessage.objects.create(
            sender=request.user,
            body=data.get('body', ''),
        )

        for f in data.get('attachments', []):
            content_type = getattr(f, 'content_type', '')
            att_type = (
                CommunityMessageAttachment.AttachmentType.IMAGE
                if content_type.startswith('image/')
                else CommunityMessageAttachment.AttachmentType.FILE
            )
            CommunityMessageAttachment.objects.create(
                message=message,
                file=f,
                name=f.name,
                size=f.size,
                type=att_type,
            )

        self._broadcast(message, request)

        return CustomResponse.success(
            message='Message sent.',
            data=CommunityMessageSerializer(message, context={'request': request}).data,
            status_code=status.HTTP_201_CREATED,
        )

    def _broadcast(self, message, request):
        channel_layer = get_channel_layer()
        if not channel_layer:
            return
        company = getattr(message.sender, 'company', None)
        # build attachment list for the broadcast payload
        attachments = []
        for att in message.attachments.all():
            url = request.build_absolute_uri(att.file.url) if att.file else None
            attachments.append({
                'id': str(att.id),
                'name': att.name,
                'url': url,
                'size': att.size,
                'type': att.type,
            })
        payload = {
            'id': str(message.id),
            'sender_id': str(message.sender.id),
            'sender_name': company.name if company else message.sender.email,
            'sender_role': company.role if company else None,
            'body': message.body,
            'attachments': attachments,
            'sent_at': message.sent_at.isoformat(),
            'status': 'sent',
        }
        try:
            async_to_sync(channel_layer.group_send)(
                'community_chat',
                {'type': 'community_message', 'payload': payload},
            )
        except Exception:
            # Redis unavailable — message is already saved, WS broadcast is best-effort
            pass
