from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from utils.response import CustomResponse
from apps.notifications import services as notification_service

from .models import AuditLog, Bid, Booking, CapacityOffer, CapacityPosting, Load
from .permissions import (
    IsBookingParty,
    IsCapacityOwner,
    IsLoadOwner,
    IsVerifiedCarrier,
    IsVerifiedShipperOrBroker,
)
from .serializers import (
    BidSerializer,
    BookingSerializer,
    CapacityOfferSerializer,
    CapacityPostingReadSerializer,
    CapacityPostingWriteSerializer,
    CounterBidSerializer,
    LoadCarrierDetailSerializer,
    LoadCarrierListSerializer,
    LoadDetailSerializer,
    LoadWriteSerializer,
    MyBidItemSerializer,
    MyLoadListSerializer,
    PlaceBidSerializer,
)


def _log(load, actor, action):
    AuditLog.objects.create(load=load, actor=actor, action=action)


# shipper or broker posts a new load to the marketplace
class LoadCreateView(APIView):
    permission_classes = [IsAuthenticated, IsVerifiedShipperOrBroker]

    def post(self, request):
        serializer = LoadWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        load = serializer.save(
            poster=request.user,
            status=Load.Status.OPEN,
            visibility=Load.Visibility.PUBLIC,
        )
        _log(load, request.user, f'Load {load.job_id} posted.')
        return CustomResponse.success(
            message='Load posted successfully.',
            data=LoadDetailSerializer(load).data,
            status_code=status.HTTP_201_CREATED,
        )


# returns the poster's own loads with dashboard stats and optional tab/search filters
class MyLoadListView(APIView):
    permission_classes = [IsAuthenticated, IsVerifiedShipperOrBroker]

    def get(self, request):
        qs = Load.objects.filter(poster=request.user)

        status_filter = request.query_params.get('status', 'all')
        if status_filter != 'all':
            qs = qs.filter(status=status_filter)

        q = request.query_params.get('q', '').strip()
        if q:
            qs = qs.filter(
                Q(job_id__icontains=q) |
                Q(origin__icontains=q) |
                Q(destination__icontains=q)
            )

        all_loads = Load.objects.filter(poster=request.user)
        active_bids_count = Bid.objects.filter(
            load__poster=request.user,
            status__in=[Bid.Status.PENDING, Bid.Status.COUNTERED],
        ).count()

        stats = {
            'total': all_loads.count(),
            'active_bids': active_bids_count,
            'booked': all_loads.filter(status=Load.Status.BOOKED).count(),
            'completed': all_loads.filter(status=Load.Status.COMPLETED).count(),
        }

        return CustomResponse.success(
            message='Loads retrieved.',
            data={
                'stats': stats,
                'loads': MyLoadListSerializer(qs, many=True).data,
            },
        )


# role-aware GET returns full detail for owner or privacy-limited view for carrier; PATCH edits open loads
class LoadDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def _get_load(self, load_id):
        try:
            return Load.objects.get(id=load_id)
        except Load.DoesNotExist:
            return None

    def get(self, request, load_id):
        load = self._get_load(load_id)
        if not load:
            return CustomResponse.error('Load not found.', status_code=status.HTTP_404_NOT_FOUND)

        company = getattr(request.user, 'company', None)
        if not company:
            return CustomResponse.error('No company found.', status_code=status.HTTP_403_FORBIDDEN)

        from apps.accounts.models import Company
        if company.role == Company.Role.CARRIER:
            return CustomResponse.success(
                message='Load retrieved.',
                data=LoadCarrierDetailSerializer(load, context={'request': request}).data,
            )

        # shipper/broker must own the load to see full detail
        if load.poster != request.user:
            return CustomResponse.error('You do not own this load.', status_code=status.HTTP_403_FORBIDDEN)

        return CustomResponse.success(
            message='Load retrieved.',
            data=LoadDetailSerializer(load, context={'request': request}).data,
        )

    def patch(self, request, load_id):
        load = self._get_load(load_id)
        if not load:
            return CustomResponse.error('Load not found.', status_code=status.HTTP_404_NOT_FOUND)

        if load.poster != request.user:
            return CustomResponse.error('You do not own this load.', status_code=status.HTTP_403_FORBIDDEN)

        if load.status != Load.Status.OPEN:
            return CustomResponse.error(
                'Only open loads can be edited.',
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        active_bids = load.bids.filter(status__in=[Bid.Status.PENDING, Bid.Status.COUNTERED]).count()
        if active_bids > 0:
            return CustomResponse.error(
                'Cannot edit a load that has active bids.',
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        serializer = LoadWriteSerializer(load, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        _log(load, request.user, f'Load {load.job_id} edited.')
        return CustomResponse.success(
            message='Load updated.',
            data=LoadDetailSerializer(load).data,
        )


# shipper/broker accepts a bid, books the load, and creates a booking record
class BidAcceptView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, load_id, bid_id):
        try:
            load = Load.objects.select_for_update().get(id=load_id)
        except Load.DoesNotExist:
            return CustomResponse.error('Load not found.', status_code=status.HTTP_404_NOT_FOUND)

        if load.poster != request.user:
            return CustomResponse.error('You do not own this load.', status_code=status.HTTP_403_FORBIDDEN)

        if load.status == Load.Status.BOOKED:
            return CustomResponse.error('Load is already booked.', status_code=status.HTTP_400_BAD_REQUEST)

        try:
            bid = load.bids.get(id=bid_id)
        except Bid.DoesNotExist:
            return CustomResponse.error('Bid not found.', status_code=status.HTTP_404_NOT_FOUND)

        if bid.status not in (Bid.Status.PENDING, Bid.Status.COUNTERED):
            return CustomResponse.error('This bid cannot be accepted.', status_code=status.HTTP_400_BAD_REQUEST)

        # accept this bid, reject all others atomically
        load.bids.exclude(id=bid_id).update(status=Bid.Status.REJECTED)
        bid.status = Bid.Status.ACCEPTED
        bid.save(update_fields=['status'])

        load.status = Load.Status.BOOKED
        load.save(update_fields=['status'])

        agreed_price = bid.counter_amount if bid.counter_amount else bid.amount
        booking = Booking.objects.create(
            load=load,
            bid=bid,
            shipper=request.user,
            carrier=bid.carrier,
            agreed_price=agreed_price,
        )

        carrier_name = getattr(bid.carrier, 'company', None)
        carrier_name = carrier_name.name if carrier_name else bid.carrier.email
        _log(load, request.user, f'Bid of ${bid.amount} by {carrier_name} accepted. Load booked.')

        return CustomResponse.success(
            message='Bid accepted. Load is now booked.',
            data={'booking_id': str(booking.id)},
            status_code=status.HTTP_201_CREATED,
        )


# shipper/broker sends a counter offer price back to the carrier
class BidCounterView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, load_id, bid_id):
        try:
            load = Load.objects.get(id=load_id)
        except Load.DoesNotExist:
            return CustomResponse.error('Load not found.', status_code=status.HTTP_404_NOT_FOUND)

        if load.poster != request.user:
            return CustomResponse.error('You do not own this load.', status_code=status.HTTP_403_FORBIDDEN)

        if load.status == Load.Status.BOOKED:
            return CustomResponse.error('Load is already booked.', status_code=status.HTTP_400_BAD_REQUEST)

        try:
            bid = load.bids.get(id=bid_id)
        except Bid.DoesNotExist:
            return CustomResponse.error('Bid not found.', status_code=status.HTTP_404_NOT_FOUND)

        serializer = CounterBidSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        bid.counter_amount = serializer.validated_data['counter_amount']
        bid.status = Bid.Status.COUNTERED
        bid.save(update_fields=['counter_amount', 'status'])

        carrier_name = getattr(bid.carrier, 'company', None)
        carrier_name = carrier_name.name if carrier_name else bid.carrier.email
        _log(load, request.user, f'Counter offer of ${bid.counter_amount} sent to {carrier_name}.')

        notification_service.notify(
            recipient=bid.carrier,
            notification_type='bid_countered',
            actor=request.user,
            target_kind='load',
            target_id=str(load.id),
            priority='high',
            meta={
                'bid_id': str(bid.id),
                'counter_amount': str(bid.counter_amount),
                'load_id': str(load.id)
            }
        )

        notification_service.mark_related_notifications_read(
            user=request.user,
            notification_type='bid_placed',
            meta_filters={'bid_id': str(bid.id)}
        )

        return CustomResponse.success(
            message='Counter offer sent.',
            data=BidSerializer(bid).data,
        )


# shipper/broker rejects a specific bid
class BidRejectView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, load_id, bid_id):
        try:
            load = Load.objects.get(id=load_id)
        except Load.DoesNotExist:
            return CustomResponse.error('Load not found.', status_code=status.HTTP_404_NOT_FOUND)

        if load.poster != request.user:
            return CustomResponse.error('You do not own this load.', status_code=status.HTTP_403_FORBIDDEN)

        try:
            bid = load.bids.get(id=bid_id)
        except Bid.DoesNotExist:
            return CustomResponse.error('Bid not found.', status_code=status.HTTP_404_NOT_FOUND)

        bid.status = Bid.Status.REJECTED
        bid.save(update_fields=['status'])

        carrier_name = getattr(bid.carrier, 'company', None)
        carrier_name = carrier_name.name if carrier_name else bid.carrier.email
        _log(load, request.user, f'Bid by {carrier_name} rejected.')

        return CustomResponse.success(
            message='Bid rejected.',
            data=BidSerializer(bid).data,
        )


# returns booking detail including contact info for both parties (contact-reveal gate)
class BookingDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, booking_id):
        try:
            booking = Booking.objects.select_related(
                'load', 'shipper__company', 'carrier__company'
            ).get(id=booking_id)
        except Booking.DoesNotExist:
            return CustomResponse.error('Booking not found.', status_code=status.HTTP_404_NOT_FOUND)

        if booking.shipper != request.user and booking.carrier != request.user:
            return CustomResponse.error(
                'You are not a party to this booking.',
                status_code=status.HTTP_403_FORBIDDEN,
            )

        return CustomResponse.success(
            message='Booking retrieved.',
            data=BookingSerializer(booking).data,
        )


# carrier browses open/bidding loads with filters, sorting, and pagination
class LoadBrowseView(APIView):
    permission_classes = [IsAuthenticated, IsVerifiedCarrier]

    def get(self, request):
        qs = Load.objects.filter(
            status__in=[Load.Status.OPEN, Load.Status.BIDDING],
            visibility=Load.Visibility.PUBLIC,
        ).select_related('poster__company')

        p = request.query_params

        if p.get('origin'):
            qs = qs.filter(origin__icontains=p['origin'])
        if p.get('destination'):
            qs = qs.filter(destination__icontains=p['destination'])
        if p.get('equipment_type') and p['equipment_type'] != 'Any equipment':
            qs = qs.filter(equipment_type=p['equipment_type'])
        if p.get('pickup_from'):
            qs = qs.filter(pickup_date__gte=p['pickup_from'])
        if p.get('pickup_to'):
            qs = qs.filter(pickup_date__lte=p['pickup_to'])
        if p.get('min_cubic_feet'):
            qs = qs.filter(cubic_feet__gte=p['min_cubic_feet'])
        if p.get('max_cubic_feet'):
            qs = qs.filter(cubic_feet__lte=p['max_cubic_feet'])

        sort = p.get('sort', 'newest')
        if sort == 'pickup_asc':
            qs = qs.order_by('pickup_date')
        elif sort == 'cuft_desc':
            qs = qs.order_by('-cubic_feet')
        else:
            qs = qs.order_by('-posted_at')

        page_size = 6
        try:
            page = max(1, int(p.get('page', 1)))
        except (ValueError, TypeError):
            page = 1
        start = (page - 1) * page_size
        end = start + page_size
        total = qs.count()

        return CustomResponse.success(
            message='Loads retrieved.',
            data={
                'count': total,
                'page': page,
                'page_size': page_size,
                'total_pages': max(1, (total + page_size - 1) // page_size),
                'results': LoadCarrierListSerializer(qs[start:end], many=True).data,
            },
        )


# returns the carrier's own bid on a specific load — 404 if no bid exists
class MyBidOnLoadView(APIView):
    permission_classes = [IsAuthenticated, IsVerifiedCarrier]

    def get(self, request, load_id):
        try:
            load = Load.objects.get(id=load_id)
        except Load.DoesNotExist:
            return CustomResponse.error('Load not found.', status_code=status.HTTP_404_NOT_FOUND)

        try:
            bid = load.bids.get(carrier=request.user)
        except Bid.DoesNotExist:
            return CustomResponse.error('No bid found.', status_code=status.HTTP_404_NOT_FOUND)

        return CustomResponse.success(
            message='Bid retrieved.',
            data=BidSerializer(bid).data,
        )


# carrier places a new bid on an open or bidding load
class PlaceBidView(APIView):
    permission_classes = [IsAuthenticated, IsVerifiedCarrier]

    @transaction.atomic
    def post(self, request, load_id):
        try:
            load = Load.objects.select_for_update().get(id=load_id)
        except Load.DoesNotExist:
            return CustomResponse.error('Load not found.', status_code=status.HTTP_404_NOT_FOUND)

        if load.status not in (Load.Status.OPEN, Load.Status.BIDDING):
            return CustomResponse.error('This load is not accepting bids.', status_code=status.HTTP_400_BAD_REQUEST)

        if load.poster == request.user:
            return CustomResponse.error('You cannot bid on your own load.', status_code=status.HTTP_400_BAD_REQUEST)

        existing = load.bids.filter(
            carrier=request.user,
            status__in=[Bid.Status.PENDING, Bid.Status.COUNTERED],
        ).first()
        if existing:
            return CustomResponse.error(
                'You already have an active bid on this load.',
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        serializer = PlaceBidSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        bid = Bid.objects.create(
            load=load,
            carrier=request.user,
            amount=serializer.validated_data['amount'],
            note=serializer.validated_data.get('note', ''),
        )

        # transition load from open to bidding on first bid
        if load.status == Load.Status.OPEN:
            load.status = Load.Status.BIDDING
            load.save(update_fields=['status'])

        carrier_name = getattr(request.user, 'company', None)
        carrier_name = carrier_name.name if carrier_name else request.user.email
        _log(load, request.user, f'{carrier_name} placed a bid of ${bid.amount}.')

        notification_service.notify(
            recipient=load.poster,
            notification_type='bid_placed',
            actor=request.user,
            target_kind='load',
            target_id=str(load.id),
            meta={
                'bid_id': str(bid.id),
                'amount': str(bid.amount),
                'carrier_name': carrier_name,
                'load_id': str(load.id)
            }
        )

        return CustomResponse.success(
            message='Bid placed.',
            data=BidSerializer(bid).data,
            status_code=status.HTTP_201_CREATED,
        )


# carrier withdraws their active bid and reverts the load to open if no bids remain
class WithdrawBidView(APIView):
    permission_classes = [IsAuthenticated, IsVerifiedCarrier]

    @transaction.atomic
    def post(self, request, load_id):
        try:
            load = Load.objects.select_for_update().get(id=load_id)
        except Load.DoesNotExist:
            return CustomResponse.error('Load not found.', status_code=status.HTTP_404_NOT_FOUND)

        try:
            bid = load.bids.get(
                carrier=request.user,
                status__in=[Bid.Status.PENDING, Bid.Status.COUNTERED],
            )
        except Bid.DoesNotExist:
            return CustomResponse.error('No active bid to withdraw.', status_code=status.HTTP_404_NOT_FOUND)

        bid.status = Bid.Status.WITHDRAWN
        bid.save(update_fields=['status'])

        # revert load to open if no active bids remain
        active_remaining = load.bids.filter(
            status__in=[Bid.Status.PENDING, Bid.Status.COUNTERED]
        ).count()
        if active_remaining == 0 and load.status == Load.Status.BIDDING:
            load.status = Load.Status.OPEN
            load.save(update_fields=['status'])

        carrier_name = getattr(request.user, 'company', None)
        carrier_name = carrier_name.name if carrier_name else request.user.email
        _log(load, request.user, f'{carrier_name} withdrew their bid.')

        return CustomResponse.success(
            message='Bid withdrawn.',
            data=BidSerializer(bid).data,
        )


# carrier accepts a shipper's counter offer, triggering booking creation
class AcceptCounterView(APIView):
    permission_classes = [IsAuthenticated, IsVerifiedCarrier]

    @transaction.atomic
    def post(self, request, load_id):
        try:
            load = Load.objects.select_for_update().get(id=load_id)
        except Load.DoesNotExist:
            return CustomResponse.error('Load not found.', status_code=status.HTTP_404_NOT_FOUND)

        try:
            bid = load.bids.get(carrier=request.user, status=Bid.Status.COUNTERED)
        except Bid.DoesNotExist:
            return CustomResponse.error('No countered bid found.', status_code=status.HTTP_404_NOT_FOUND)

        bid.amount = bid.counter_amount
        bid.status = Bid.Status.ACCEPTED
        bid.save(update_fields=['amount', 'status'])

        load.bids.exclude(id=bid.id).update(status=Bid.Status.REJECTED)
        load.status = Load.Status.BOOKED
        load.save(update_fields=['status'])

        booking = Booking.objects.create(
            load=load,
            bid=bid,
            shipper=load.poster,
            carrier=request.user,
            agreed_price=bid.amount,
        )

        carrier_name = getattr(request.user, 'company', None)
        carrier_name = carrier_name.name if carrier_name else request.user.email
        _log(load, request.user, f'{carrier_name} accepted counter offer of ${bid.amount}. Load booked.')

        notification_service.notify(
            recipient=load.poster,
            notification_type='counter_accepted',
            actor=request.user,
            target_kind='booking',
            target_id=str(booking.id),
            meta={
                'agreed_price': str(bid.amount),
                'carrier_name': carrier_name,
                'booking_id': str(booking.id)
            }
        )

        notification_service.mark_related_notifications_read(
            user=request.user,
            notification_type='bid_countered',
            meta_filters={'bid_id': str(bid.id)}
        )

        return CustomResponse.success(
            message='Counter accepted. Load is now booked.',
            data={'booking_id': str(booking.id)},
            status_code=status.HTTP_201_CREATED,
        )


# returns all carrier bids filtered by tab with per-tab counts for badge rendering
class MyBidsView(APIView):
    permission_classes = [IsAuthenticated, IsVerifiedCarrier]

    TAB_STATUSES = {
        'active': [Bid.Status.PENDING, Bid.Status.COUNTERED],
        'won': [Bid.Status.ACCEPTED],
        'lost': [Bid.Status.REJECTED],
        'withdrawn': [Bid.Status.WITHDRAWN],
    }

    def get(self, request):
        tab = request.query_params.get('tab', 'active')
        statuses = self.TAB_STATUSES.get(tab, self.TAB_STATUSES['active'])

        bids = Bid.objects.filter(
            carrier=request.user,
            status__in=statuses,
        ).select_related('load')

        counts = {
            tab_name: Bid.objects.filter(
                carrier=request.user,
                status__in=tab_statuses,
            ).count()
            for tab_name, tab_statuses in self.TAB_STATUSES.items()
        }

        return CustomResponse.success(
            message='Bids retrieved.',
            data={
                'counts': counts,
                'bids': MyBidItemSerializer(bids, many=True).data,
            },
        )


# carrier creates a new capacity posting advertising available truck space
class CapacityCreateView(APIView):
    permission_classes = [IsAuthenticated, IsVerifiedCarrier]

    def post(self, request):
        serializer = CapacityPostingWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        posting = serializer.save(carrier=request.user)
        return CustomResponse.success(
            message='Capacity posted.',
            data=CapacityPostingReadSerializer(posting).data,
            status_code=status.HTTP_201_CREATED,
        )


# returns the carrier's capacity postings grouped into active and past
class MyCapacityView(APIView):
    permission_classes = [IsAuthenticated, IsVerifiedCarrier]

    def get(self, request):
        today = timezone.now().date()
        base = CapacityPosting.objects.filter(carrier=request.user)

        active = base.filter(status=CapacityPosting.Status.ACTIVE, available_to__gte=today)
        past = base.filter(
            Q(status=CapacityPosting.Status.EXPIRED) |
            Q(status=CapacityPosting.Status.DEACTIVATED)
        )

        return CustomResponse.success(
            message='Capacity postings retrieved.',
            data={
                'active': CapacityPostingReadSerializer(active, many=True).data,
                'past': CapacityPostingReadSerializer(past, many=True).data,
            },
        )


# GET retrieves a single capacity posting for the edit form; PATCH updates it
class CapacityDetailView(APIView):
    permission_classes = [IsAuthenticated, IsVerifiedCarrier]

    def _get_posting(self, posting_id, user):
        try:
            return CapacityPosting.objects.get(id=posting_id, carrier=user)
        except CapacityPosting.DoesNotExist:
            return None

    def get(self, request, posting_id):
        posting = self._get_posting(posting_id, request.user)
        if not posting:
            return CustomResponse.error('Posting not found.', status_code=status.HTTP_404_NOT_FOUND)
        return CustomResponse.success(
            message='Posting retrieved.',
            data=CapacityPostingReadSerializer(posting).data,
        )

    def patch(self, request, posting_id):
        posting = self._get_posting(posting_id, request.user)
        if not posting:
            return CustomResponse.error('Posting not found.', status_code=status.HTTP_404_NOT_FOUND)

        if posting.status != CapacityPosting.Status.ACTIVE:
            return CustomResponse.error('Only active postings can be edited.', status_code=status.HTTP_400_BAD_REQUEST)

        serializer = CapacityPostingWriteSerializer(posting, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return CustomResponse.success(
            message='Posting updated.',
            data=CapacityPostingReadSerializer(posting).data,
        )


# marks a capacity posting as deactivated so it no longer appears in search
class CapacityDeactivateView(APIView):
    permission_classes = [IsAuthenticated, IsVerifiedCarrier]

    def post(self, request, posting_id):
        try:
            posting = CapacityPosting.objects.get(id=posting_id, carrier=request.user)
        except CapacityPosting.DoesNotExist:
            return CustomResponse.error('Posting not found.', status_code=status.HTTP_404_NOT_FOUND)

        posting.status = CapacityPosting.Status.DEACTIVATED
        posting.save(update_fields=['status'])
        return CustomResponse.success(
            message='Posting deactivated.',
            status_code=status.HTTP_204_NO_CONTENT,
        )


# returns all offers received on a carrier's capacity posting
class CapacityOffersView(APIView):
    permission_classes = [IsAuthenticated, IsVerifiedCarrier]

    def get(self, request, posting_id):
        try:
            posting = CapacityPosting.objects.get(id=posting_id, carrier=request.user)
        except CapacityPosting.DoesNotExist:
            return CustomResponse.error('Posting not found.', status_code=status.HTTP_404_NOT_FOUND)

        offers = posting.offers.select_related('offered_by__company').all()
        return CustomResponse.success(
            message='Offers retrieved.',
            data={
                'posting': CapacityPostingReadSerializer(posting).data,
                'offers': CapacityOfferSerializer(offers, many=True).data,
            },
        )
