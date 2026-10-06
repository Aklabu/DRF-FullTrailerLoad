from django.utils import timezone
from rest_framework import serializers

from apps.accounts.models import Company
from .models import AuditLog, Bid, Booking, CapacityOffer, CapacityPosting, Load


# safe carrier summary — never exposes email or phone
class CarrierSummarySerializer(serializers.Serializer):
    id = serializers.UUIDField(source='company.id', read_only=True)
    company_name = serializers.CharField(source='company.name', read_only=True)
    verification_status = serializers.CharField(source='company.verification_status', read_only=True)
    avg_rating = serializers.SerializerMethodField()

    def get_avg_rating(self, obj):
        # ratings system not yet built
        return None


# safe poster summary for carrier-facing load views
class PosterSummarySerializer(serializers.Serializer):
    id = serializers.UUIDField(source='company.id', read_only=True)
    company_name = serializers.CharField(source='company.name', read_only=True)
    verification_status = serializers.CharField(source='company.verification_status', read_only=True)
    avg_rating = serializers.SerializerMethodField()

    def get_avg_rating(self, obj):
        return None


# read-only serializer for load audit trail entries
class AuditLogSerializer(serializers.ModelSerializer):
    actor = serializers.CharField(source='actor.company.name', read_only=True)

    class Meta:
        model = AuditLog
        fields = ('id', 'action', 'actor', 'timestamp')


# full bid representation including nested carrier info
class BidSerializer(serializers.ModelSerializer):
    carrier = CarrierSummarySerializer(read_only=True)

    class Meta:
        model = Bid
        fields = (
            'id', 'carrier', 'amount', 'counter_amount',
            'status', 'note', 'placed_at',
        )
        read_only_fields = ('id', 'carrier', 'counter_amount', 'status', 'placed_at')


# validates a new bid submitted by a carrier
class PlaceBidSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    note = serializers.CharField(required=False, allow_blank=True, default='')

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError('Bid amount must be positive.')
        return value


# validates a counter offer amount from the shipper/broker
class CounterBidSerializer(serializers.Serializer):
    counter_amount = serializers.DecimalField(max_digits=10, decimal_places=2)

    def validate_counter_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError('Counter amount must be positive.')
        return value


# handles create and partial update of a load
class LoadWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Load
        fields = (
            'origin', 'destination', 'pickup_date', 'delivery_date',
            'cubic_feet', 'weight', 'equipment_type', 'pricing_mode',
            'fixed_price', 'special_requirements',
        )

    def validate(self, attrs):
        if attrs.get('delivery_date') and attrs.get('pickup_date'):
            if attrs['delivery_date'] <= attrs['pickup_date']:
                raise serializers.ValidationError(
                    {'delivery_date': 'Delivery date must be after pickup date.'}
                )
        if attrs.get('pricing_mode') == Load.PricingMode.FIXED:
            if not attrs.get('fixed_price'):
                raise serializers.ValidationError(
                    {'fixed_price': 'Fixed price is required when pricing mode is fixed.'}
                )
        if attrs.get('fixed_price') is not None and attrs.get('fixed_price') <= 0:
            raise serializers.ValidationError(
                {'fixed_price': 'Fixed price must be positive.'}
            )
        return attrs


# full load detail with bids and audit log — only for the load owner
class LoadDetailSerializer(serializers.ModelSerializer):
    bids = BidSerializer(many=True, read_only=True)
    audit_log = AuditLogSerializer(many=True, read_only=True)
    bid_count = serializers.IntegerField(source='bids.count', read_only=True)

    class Meta:
        model = Load
        fields = (
            'id', 'job_id', 'status', 'pricing_mode', 'visibility',
            'origin', 'destination', 'pickup_date', 'delivery_date',
            'cubic_feet', 'weight', 'equipment_type',
            'fixed_price', 'special_requirements',
            'posted_at', 'bid_count', 'bids', 'audit_log',
        )


# list serializer for the poster's dashboard — includes active bid count for Edit button logic
class MyLoadListSerializer(serializers.ModelSerializer):
    bid_count = serializers.IntegerField(source='bids.count', read_only=True)
    # only active bids returned so frontend can check bids.length === 0 for Edit button
    bids = serializers.SerializerMethodField()

    def get_bids(self, obj):
        return list(
            obj.bids.filter(
                status__in=[Bid.Status.PENDING, Bid.Status.COUNTERED]
            ).values('id')
        )

    class Meta:
        model = Load
        fields = (
            'id', 'job_id', 'status', 'origin', 'destination',
            'cubic_feet', 'equipment_type', 'pickup_date',
            'pricing_mode', 'fixed_price', 'bid_count', 'bids', 'posted_at',
        )


# privacy-limited load card for carrier browse list — no bids, no audit log
class LoadCarrierListSerializer(serializers.ModelSerializer):
    bid_count = serializers.IntegerField(source='bids.count', read_only=True)
    poster = PosterSummarySerializer(read_only=True)

    class Meta:
        model = Load
        fields = (
            'id', 'job_id', 'status', 'origin', 'destination',
            'cubic_feet', 'equipment_type', 'pickup_date',
            'pricing_mode', 'fixed_price', 'posted_at',
            'bid_count', 'poster',
        )


# carrier load detail — bids and audit_log intentionally omitted
class LoadCarrierDetailSerializer(serializers.ModelSerializer):
    bid_count = serializers.IntegerField(source='bids.count', read_only=True)
    poster = PosterSummarySerializer(read_only=True)

    class Meta:
        model = Load
        fields = (
            'id', 'job_id', 'status', 'pricing_mode', 'visibility',
            'origin', 'destination', 'pickup_date', 'delivery_date',
            'cubic_feet', 'weight', 'equipment_type',
            'fixed_price', 'special_requirements',
            'posted_at', 'bid_count', 'poster',
        )


# exposes full contact info — only shown on booking confirmation (contact-reveal gate)
class BookingPartySerializer(serializers.Serializer):
    company_name = serializers.CharField(source='company.name', read_only=True)
    email = serializers.EmailField(source='email', read_only=True)
    phone = serializers.CharField(source='company.phone', read_only=True)


# minimal load snapshot embedded inside a booking response
class BookingLoadSerializer(serializers.ModelSerializer):
    class Meta:
        model = Load
        fields = (
            'origin', 'destination', 'pickup_date', 'delivery_date',
            'cubic_feet', 'equipment_type',
        )


# full booking detail including contact info for both parties
class BookingSerializer(serializers.ModelSerializer):
    load = BookingLoadSerializer(read_only=True)
    shipper = BookingPartySerializer(read_only=True)
    carrier = BookingPartySerializer(read_only=True)
    job_id = serializers.CharField(source='load.job_id', read_only=True)

    class Meta:
        model = Booking
        fields = (
            'id', 'booking_ref', 'job_id', 'confirmed_at',
            'agreed_price', 'load', 'shipper', 'carrier',
        )


# validates and creates/updates a capacity posting
class CapacityPostingWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = CapacityPosting
        fields = (
            'origin', 'destination', 'available_from', 'available_to',
            'cubic_feet', 'equipment_type', 'notes',
        )

    def validate(self, attrs):
        if attrs.get('available_to') and attrs.get('available_from'):
            if attrs['available_to'] <= attrs['available_from']:
                raise serializers.ValidationError(
                    {'available_to': 'available_to must be after available_from.'}
                )
        return attrs


# read representation of a capacity posting including offer count
class CapacityPostingReadSerializer(serializers.ModelSerializer):
    offers_received = serializers.IntegerField(source='offers.count', read_only=True)

    class Meta:
        model = CapacityPosting
        fields = (
            'id', 'origin', 'destination', 'available_from', 'available_to',
            'cubic_feet', 'equipment_type', 'notes', 'status',
            'posted_at', 'offers_received',
        )


# represents an offer made on a capacity posting, including the offering company's public info
class CapacityOfferSerializer(serializers.ModelSerializer):
    offered_by = serializers.SerializerMethodField()

    def get_offered_by(self, obj):
        company = getattr(obj.offered_by, 'company', None)
        if not company:
            return {}
        return {
            'id': str(company.id),
            'company_name': company.name,
            'role': company.role,
            'verification_status': company.verification_status,
        }

    class Meta:
        model = CapacityOffer
        fields = ('id', 'offered_by', 'message', 'offered_at')


# response shape for the my-loads dashboard endpoint
class MyLoadsResponseSerializer(serializers.Serializer):
    stats = serializers.DictField()
    loads = MyLoadListSerializer(many=True)


# flattened bid item for the carrier's my-bids list — merges bid and load fields
class MyBidItemSerializer(serializers.ModelSerializer):
    load_id = serializers.UUIDField(source='load.id', read_only=True)
    job_id = serializers.CharField(source='load.job_id', read_only=True)
    origin = serializers.CharField(source='load.origin', read_only=True)
    destination = serializers.CharField(source='load.destination', read_only=True)
    pickup_date = serializers.DateField(source='load.pickup_date', read_only=True)
    equipment_type = serializers.CharField(source='load.equipment_type', read_only=True)
    bid_amount = serializers.DecimalField(source='amount', max_digits=10, decimal_places=2, read_only=True)
    bid_status = serializers.CharField(source='status', read_only=True)
    load_status = serializers.CharField(source='load.status', read_only=True)

    class Meta:
        model = Bid
        fields = (
            'id', 'load_id', 'job_id', 'origin', 'destination',
            'pickup_date', 'equipment_type',
            'bid_amount', 'counter_amount', 'bid_status', 'load_status',
            'placed_at',
        )
