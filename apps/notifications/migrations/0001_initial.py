import uuid
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='NotificationPreferences',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('bid_placed', models.BooleanField(default=True)),
                ('bid_countered', models.BooleanField(default=True)),
                ('counter_accepted', models.BooleanField(default=True)),
                ('review_received', models.BooleanField(default=True)),
                ('new_message', models.BooleanField(default=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='notification_preferences', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name_plural': 'Notification Preferences',
            },
        ),
        migrations.CreateModel(
            name='Notification',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('type', models.CharField(choices=[('bid_placed', 'Bid Placed'), ('bid_countered', 'Bid Countered'), ('counter_accepted', 'Counter Accepted'), ('review_received', 'Review Received'), ('new_message', 'New Message')], max_length=20)),
                ('category', models.CharField(choices=[('bids', 'Bids'), ('messages', 'Messages'), ('reviews', 'Reviews')], max_length=20)),
                ('title', models.CharField(max_length=255)),
                ('body', models.TextField()),
                ('priority', models.CharField(choices=[('normal', 'Normal'), ('high', 'High')], default='normal', max_length=10)),
                ('is_read', models.BooleanField(db_index=True, default=False)),
                ('read_at', models.DateTimeField(blank=True, null=True)),
                ('target_kind', models.CharField(choices=[('load', 'Load'), ('booking', 'Booking'), ('review', 'Review'), ('conversation', 'Conversation')], max_length=20)),
                ('target_id', models.UUIDField()),
                ('meta', models.JSONField(blank=True, default=dict)),
                ('group_key', models.CharField(blank=True, db_index=True, max_length=255, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('actor', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='notifications_caused', to=settings.AUTH_USER_MODEL)),
                ('recipient', models.ForeignKey(db_index=True, on_delete=django.db.models.deletion.CASCADE, related_name='notifications', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-created_at'],
                'indexes': [
                    models.Index(fields=['recipient', 'is_read', '-created_at'], name='notif_recip_read_created'),
                    models.Index(fields=['recipient', 'category', 'is_read'], name='notif_recip_cat_read'),
                    models.Index(fields=['recipient', 'group_key', 'is_read'], name='notif_recip_group_read'),
                ],
            },
        ),
    ]
