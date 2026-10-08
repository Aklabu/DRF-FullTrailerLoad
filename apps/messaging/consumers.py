import json

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.utils import timezone
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.exceptions import TokenError, InvalidToken


async def _get_user_from_token(token_str):
    from django.contrib.auth import get_user_model
    User = get_user_model()
    try:
        token = AccessToken(token_str)
        user_id = token['user_id']
        return await database_sync_to_async(User.objects.get)(id=user_id)
    except (TokenError, InvalidToken, User.DoesNotExist, KeyError):
        return None


# handles real-time direct messages for a single conversation channel
class DirectMessageConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        self.conversation_id = self.scope['url_route']['kwargs']['conversation_id']
        self.group_name = f'conversation_{self.conversation_id}'

        # authenticate via JWT token passed as query param
        token_str = self.scope['query_string'].decode().replace('token=', '').split('&')[0]
        self.user = await _get_user_from_token(token_str)

        if not self.user or not await self._is_participant():
            await self.close()
            return

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        if not text_data:
            return
        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            return

        body = data.get('body', '').strip()
        if not body:
            return

        message = await self._save_message(body)
        payload = await self._build_payload(message)

        # broadcast to all participants in this conversation
        await self.channel_layer.group_send(
            self.group_name,
            {'type': 'chat_message', 'payload': payload},
        )

    async def chat_message(self, event):
        await self.send(text_data=json.dumps(event['payload']))

    @database_sync_to_async
    def _is_participant(self):
        from .models import Conversation
        try:
            conv = Conversation.objects.get(id=self.conversation_id)
            return conv.participant_a == self.user or conv.participant_b == self.user
        except Conversation.DoesNotExist:
            return False

    @database_sync_to_async
    def _save_message(self, body):
        from .models import Conversation, Message
        from apps.notifications import services as notification_service
        
        conv = Conversation.objects.get(id=self.conversation_id)
        message = Message.objects.create(
            conversation=conv,
            sender=self.user,
            body=body,
        )
        conv.last_message_at = message.sent_at
        conv.save(update_fields=['last_message_at'])
        
        recipient = conv.other_participant(self.user)
        sender_company = getattr(self.user, 'company', None)
        sender_name = sender_company.name if sender_company else self.user.email
        
        notification_service.notify(
            recipient=recipient,
            notification_type='new_message',
            actor=self.user,
            target_kind='conversation',
            target_id=str(conv.id),
            group_key=f'conv:{conv.id}',
            meta={
                'sender_name': sender_name,
                'conversation_id': str(conv.id),
                'count': 1
            }
        )
        
        return message

    @database_sync_to_async
    def _build_payload(self, message):
        company = getattr(message.sender, 'company', None)
        return {
            'id': str(message.id),
            'sender_id': str(message.sender.id),
            'sender_name': company.name if company else message.sender.email,
            'body': message.body,
            'attachments': [],
            'sent_at': message.sent_at.isoformat(),
            'status': 'sent',
        }


# handles real-time broadcast for the shared community chat room
class CommunityConsumer(AsyncWebsocketConsumer):

    GROUP_NAME = 'community_chat'

    async def connect(self):
        # authenticate via JWT token passed as query param
        token_str = self.scope['query_string'].decode().replace('token=', '').split('&')[0]
        self.user = await _get_user_from_token(token_str)

        if not self.user or not self.user.is_active:
            await self.close()
            return

        await self.channel_layer.group_add(self.GROUP_NAME, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.GROUP_NAME, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        if not text_data:
            return
        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            return

        body = data.get('body', '').strip()
        if not body:
            return

        message = await self._save_message(body)
        payload = await self._build_payload(message)

        # broadcast to everyone in the community chat group
        await self.channel_layer.group_send(
            self.GROUP_NAME,
            {'type': 'community_message', 'payload': payload},
        )

    async def community_message(self, event):
        await self.send(text_data=json.dumps(event['payload']))

    @database_sync_to_async
    def _save_message(self, body):
        from .models import CommunityMessage
        return CommunityMessage.objects.create(sender=self.user, body=body)

    @database_sync_to_async
    def _build_payload(self, message):
        company = getattr(message.sender, 'company', None)
        return {
            'id': str(message.id),
            'sender_id': str(message.sender.id),
            'sender_name': company.name if company else message.sender.email,
            'sender_role': company.role if company else None,
            'body': message.body,
            'attachments': [],
            'sent_at': message.sent_at.isoformat(),
            'status': 'sent',
        }
