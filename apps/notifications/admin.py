from django.contrib import admin
from apps.notifications.models import Notification, NotificationPreferences


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'recipient', 'type', 'category', 'title',
        'priority', 'is_read', 'created_at'
    ]
    list_filter = ['type', 'category', 'priority', 'is_read', 'created_at']
    search_fields = ['recipient__email', 'title', 'body']
    readonly_fields = ['id', 'created_at', 'updated_at']
    date_hierarchy = 'created_at'
    ordering = ['-created_at']
    
    fieldsets = (
        ('Basic Info', {
            'fields': ('id', 'recipient', 'type', 'category', 'priority')
        }),
        ('Content', {
            'fields': ('title', 'body', 'meta')
        }),
        ('Target', {
            'fields': ('target_kind', 'target_id')
        }),
        ('Status', {
            'fields': ('is_read', 'read_at', 'actor', 'group_key')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )


@admin.register(NotificationPreferences)
class NotificationPreferencesAdmin(admin.ModelAdmin):
    list_display = [
        'user', 'bid_placed', 'bid_countered', 'counter_accepted',
        'review_received', 'new_message', 'updated_at'
    ]
    search_fields = ['user__email']
    list_filter = ['updated_at']
    readonly_fields = ['updated_at']
    
    fieldsets = (
        ('User', {
            'fields': ('user',)
        }),
        ('Notification Preferences', {
            'fields': (
                'bid_placed', 'bid_countered', 'counter_accepted',
                'review_received', 'new_message'
            )
        }),
        ('Metadata', {
            'fields': ('updated_at',)
        }),
    )
