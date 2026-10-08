from rest_framework import serializers
from apps.notifications.models import Notification, NotificationPreferences


class ActorSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField(source='get_full_name')


class TargetSerializer(serializers.Serializer):
    kind = serializers.CharField()
    id = serializers.UUIDField()


class NotificationSerializer(serializers.ModelSerializer):
    actor = serializers.SerializerMethodField()
    target = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = [
            'id', 'type', 'category', 'title', 'body', 'priority',
            'is_read', 'created_at', 'target', 'meta', 'actor'
        ]
        read_only_fields = fields

    def get_actor(self, obj):
        if obj.actor:
            return {
                'id': str(obj.actor.id),
                'name': obj.actor.get_full_name() if hasattr(obj.actor, 'get_full_name') else obj.actor.email
            }
        return None

    def get_target(self, obj):
        return {
            'kind': obj.target_kind,
            'id': str(obj.target_id)
        }


class NotificationPreferencesSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationPreferences
        fields = [
            'bid_placed', 'bid_countered', 'counter_accepted',
            'review_received', 'new_message', 'updated_at'
        ]
        read_only_fields = ['updated_at']

    def validate(self, attrs):
        valid_fields = {
            'bid_placed', 'bid_countered', 'counter_accepted',
            'review_received', 'new_message'
        }
        
        for key in attrs.keys():
            if key not in valid_fields:
                raise serializers.ValidationError(f"Unknown preference field: {key}")
        
        return attrs


class UnreadCountSerializer(serializers.Serializer):
    total = serializers.IntegerField()
    bids = serializers.IntegerField()
    messages = serializers.IntegerField()
    reviews = serializers.IntegerField()
