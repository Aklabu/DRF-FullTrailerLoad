from django.urls import path
from apps.notifications import views

app_name = 'notifications'

urlpatterns = [
    path('notifications/', views.notification_list, name='notification-list'),
    path('notifications/unread-count/', views.unread_count, name='unread-count'),
    path('notifications/read-all/', views.mark_all_read, name='mark-all-read'),
    path('notifications/preferences/', views.get_preferences, name='get-preferences'),
    path('notifications/<uuid:notification_id>/', views.notification_detail, name='notification-detail'),
    path('notifications/<uuid:notification_id>/read/', views.mark_notification_read, name='mark-read'),
    path('notifications/<uuid:notification_id>/delete/', views.delete_notification, name='delete-notification'),
]
