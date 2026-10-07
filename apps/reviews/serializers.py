from rest_framework import serializers

from .models import CARRIER_SUB_RATING_KEYS, SHIPPER_BROKER_SUB_RATING_KEYS, SUB_RATING_LABELS, Review


# validates the incoming review submission including sub_ratings key check
class ReviewWriteSerializer(serializers.Serializer):
    overall_rating = serializers.IntegerField(min_value=1, max_value=5)
    sub_ratings = serializers.DictField(
        child=serializers.IntegerField(min_value=1, max_value=5),
        required=False,
        default=dict,
    )
    review_text = serializers.CharField(required=False, allow_blank=True, default='')

    def validate_sub_ratings(self, value):
        # key validation happens in the view after reviewee role is known
        return value


# read representation of a single review — sub_ratings returned as label/value array
class ReviewReadSerializer(serializers.ModelSerializer):
    reviewer_name = serializers.CharField(source='reviewer.name', read_only=True)
    reviewer_role = serializers.CharField(source='reviewer.role', read_only=True)
    sub_ratings = serializers.SerializerMethodField()
    date = serializers.DateTimeField(source='created_at', read_only=True)
    job_id = serializers.SerializerMethodField()

    def get_sub_ratings(self, obj):
        return [
            {'label': SUB_RATING_LABELS.get(k, k), 'value': v}
            for k, v in obj.sub_ratings.items()
        ]

    def get_job_id(self, obj):
        return obj.booking.load.job_id if obj.booking and obj.booking.load else None

    class Meta:
        model = Review
        fields = (
            'id', 'reviewer_name', 'reviewer_role',
            'overall_rating', 'sub_ratings', 'review_text',
            'date', 'job_id',
        )


# review submission response — returned after successful POST
class ReviewCreatedSerializer(serializers.ModelSerializer):
    reviewee_id = serializers.UUIDField(source='reviewee.id', read_only=True)
    job_id = serializers.SerializerMethodField()

    def get_job_id(self, obj):
        return obj.booking.load.job_id if obj.booking and obj.booking.load else None

    class Meta:
        model = Review
        fields = (
            'id', 'job_id', 'reviewee_id',
            'overall_rating', 'sub_ratings', 'review_text', 'created_at',
        )


# eligibility check response — tells the frontend which screen to render
class ReviewStatusSerializer(serializers.Serializer):
    eligible = serializers.BooleanField()
    already_reviewed = serializers.BooleanField()
    job_id = serializers.CharField()
    origin = serializers.CharField()
    destination = serializers.CharField()
    completed_at = serializers.DateTimeField(allow_null=True)
    counterparty = serializers.DictField()
    reviewer_role = serializers.CharField()


# public company profile — avg_rating and review_count from denormalized CompanyRating
class CompanyProfileSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    company_name = serializers.CharField(source='name')
    role = serializers.CharField()
    verification_status = serializers.CharField()
    avg_rating = serializers.SerializerMethodField()
    review_count = serializers.SerializerMethodField()
    member_since = serializers.DateTimeField(source='created_at')
    job_count = serializers.SerializerMethodField()

    def get_avg_rating(self, obj):
        rating = getattr(obj, 'rating', None)
        return float(rating.avg_rating) if rating else None

    def get_review_count(self, obj):
        rating = getattr(obj, 'rating', None)
        return rating.review_count if rating else 0

    def get_job_count(self, obj):
        from django.db.models import Q
        from apps.marketplace.models import Booking
        return Booking.objects.filter(
            Q(shipper=obj.user) | Q(carrier=obj.user),
            completed_at__isnull=False,
        ).count()
