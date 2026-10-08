from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from utils.response import CustomResponse
from apps.notifications.models import Notification, NotificationPreferences
from apps.notifications.serializers import (
    NotificationSerializer,
    NotificationPreferencesSerializer,
    UnreadCountSerializer
)
from apps.notifications.pagination import NotificationPagination
from apps.notifications import services


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def notification_list(request):
    queryset = Notification.objects.filter(recipient=request.user)
    
    is_read = request.query_params.get('is_read')
    if is_read is not None:
        is_read_bool = is_read.lower() == 'true'
        queryset = queryset.filter(is_read=is_read_bool)
    
    notification_type = request.query_params.get('type')
    if notification_type:
        queryset = queryset.filter(type=notification_type)
    
    category = request.query_params.get('category')
    if category:
        queryset = queryset.filter(category=category)
    
    paginator = NotificationPagination()
    page = paginator.paginate_queryset(queryset, request)
    
    if page is not None:
        serializer = NotificationSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)
    
    serializer = NotificationSerializer(queryset, many=True)
    return CustomResponse.success(
        message="Notifications retrieved successfully",
        data=serializer.data
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def unread_count(request):
    counts = services.get_unread_counts(request.user)
    serializer = UnreadCountSerializer(counts)
    
    return CustomResponse.success(
        message="Unread counts retrieved successfully",
        data=serializer.data
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def notification_detail(request, notification_id):
    notification = get_object_or_404(
        Notification,
        id=notification_id,
        recipient=request.user
    )
    
    serializer = NotificationSerializer(notification)
    return CustomResponse.success(
        message="Notification retrieved successfully",
        data=serializer.data
    )


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def mark_notification_read(request, notification_id):
    notification = get_object_or_404(
        Notification,
        id=notification_id,
        recipient=request.user
    )
    
    if not notification.is_read:
        services.mark_notification_read(notification_id, request.user)
    
    counts = services.get_unread_counts(request.user)
    
    return CustomResponse.success(
        message="Notification marked as read",
        data={
            'notification': NotificationSerializer(notification).data,
            'unread_counts': UnreadCountSerializer(counts).data
        }
    )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_all_read(request):
    category = request.query_params.get('category')
    
    count = services.mark_all_read(request.user, category=category)
    counts = services.get_unread_counts(request.user)
    
    message = f"Marked {count} notification(s) as read"
    if category:
        message = f"Marked {count} {category} notification(s) as read"
    
    return CustomResponse.success(
        message=message,
        data={
            'marked_count': count,
            'unread_counts': UnreadCountSerializer(counts).data
        }
    )


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_notification(request, notification_id):
    notification = get_object_or_404(
        Notification,
        id=notification_id,
        recipient=request.user
    )
    
    notification.delete()
    
    return CustomResponse.success(
        message="Notification deleted successfully",
        status_code=status.HTTP_200_OK
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_preferences(request):
    preferences, created = NotificationPreferences.objects.get_or_create(
        user=request.user
    )
    
    serializer = NotificationPreferencesSerializer(preferences)
    return CustomResponse.success(
        message="Preferences retrieved successfully",
        data=serializer.data
    )


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def update_preferences(request):
    preferences, created = NotificationPreferences.objects.get_or_create(
        user=request.user
    )
    
    serializer = NotificationPreferencesSerializer(
        preferences,
        data=request.data,
        partial=True
    )
    
    if serializer.is_valid():
        serializer.save()
        return CustomResponse.success(
            message="Preferences updated successfully",
            data=serializer.data
        )
    
    return CustomResponse.error(
        message="Invalid preferences data",
        status_code=status.HTTP_400_BAD_REQUEST,
        errors=serializer.errors
    )
