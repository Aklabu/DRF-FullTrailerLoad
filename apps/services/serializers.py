from rest_framework import serializers

from .models import SupportAttachment, SupportTicket

# accepted MIME types for support attachments
_ALLOWED_CONTENT_TYPES = ('application/pdf', 'image/png', 'image/jpeg')
_MAX_FILE_SIZE = 25 * 1024 * 1024  # 25 MB in bytes
_MAX_ATTACHMENTS = 5


def _validate_attachment(file):
    # rejects oversized files before they hit storage
    if file.size > _MAX_FILE_SIZE:
        raise serializers.ValidationError('File size must not exceed 25MB.')
    content_type = getattr(file, 'content_type', '')
    if content_type not in _ALLOWED_CONTENT_TYPES:
        raise serializers.ValidationError('Only PDF, PNG, and JPG files are accepted.')
    return file


# validates the public contact form submission — maps `name` → full_name, `email` → work_email
class ContactSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    email = serializers.EmailField()
    # optional free-text company field e.g. "Apex Logistics Inc (Carrier)"
    company = serializers.CharField(max_length=255, required=False, allow_blank=True, default='')
    urgency = serializers.ChoiceField(choices=SupportTicket.Urgency.choices)
    category = serializers.ChoiceField(choices=SupportTicket.Category.choices)
    message = serializers.CharField(max_length=1500)
    attachments = serializers.ListField(
        child=serializers.FileField(),
        required=False,
        allow_empty=True,
        default=list,
    )

    def validate_attachments(self, files):
        if len(files) > _MAX_ATTACHMENTS:
            raise serializers.ValidationError(f'You may upload at most {_MAX_ATTACHMENTS} files.')
        return [_validate_attachment(f) for f in files]

    def create(self, validated_data):
        # map frontend field names to model field names
        ticket = SupportTicket.objects.create(
            full_name=validated_data['name'],
            work_email=validated_data['email'],
            company_name=validated_data.get('company', ''),
            urgency=validated_data['urgency'],
            inquiry_category=validated_data['category'],
            message=validated_data['message'],
        )
        for f in validated_data.get('attachments', []):
            SupportAttachment.objects.create(
                ticket=ticket,
                file=f,
                file_name=f.name,
                file_size=f.size,
            )
        return ticket


# read-only serializer for a saved attachment — used in admin / future ticket detail endpoint
class SupportAttachmentSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()

    def get_url(self, obj):
        request = self.context.get('request')
        if obj.file and request:
            return request.build_absolute_uri(obj.file.url)
        return obj.file.url if obj.file else None

    class Meta:
        model = SupportAttachment
        fields = ('id', 'file_name', 'file_size', 'url', 'uploaded_at')


# filters the raw external tracking response to only safe public fields
class TrackingResultSerializer(serializers.Serializer):
    job_id = serializers.CharField(source='task.job_id')
    status = serializers.CharField(source='task.status')
    from_location = serializers.CharField(source='task.from_location')
    to_location = serializers.CharField(source='task.to_location')
    driver_name = serializers.CharField(source='loadsheet.driver_name', allow_null=True)
    # scheduled date shown in the "Scheduled Date" cell on the tracking page
    scheduled_date = serializers.DateField(source='loadsheet.date', allow_null=True)
