from django.urls import path

from .views import (
    AcceptCounterView,
    BidAcceptView,
    BidCounterView,
    BidRejectView,
    BookingCompleteView,
    BookingDetailView,
    CapacityCreateView,
    CapacityDeactivateView,
    CapacityDetailView,
    CapacityOffersView,
    LoadBrowseView,
    LoadCreateView,
    LoadDetailView,
    MyBidOnLoadView,
    MyBidsView,
    MyCapacityView,
    MyLoadListView,
    PlaceBidView,
    WithdrawBidView,
)

urlpatterns = [
    # load posting and browsing
    path('loads/', LoadCreateView.as_view(), name='marketplace-load-create'),
    path('loads/browse/', LoadBrowseView.as_view(), name='marketplace-load-browse'),
    path('loads/<uuid:load_id>/', LoadDetailView.as_view(), name='marketplace-load-detail'),
    path('my-loads/', MyLoadListView.as_view(), name='marketplace-my-loads'),

    # carrier bid actions — must come before <uuid:bid_id> patterns so "mine" isn't swallowed by the UUID converter
    path('loads/<uuid:load_id>/bids/', PlaceBidView.as_view(), name='marketplace-bid-place'),
    path('loads/<uuid:load_id>/bids/mine/', MyBidOnLoadView.as_view(), name='marketplace-bid-mine'),
    path('loads/<uuid:load_id>/bids/mine/withdraw/', WithdrawBidView.as_view(), name='marketplace-bid-withdraw'),
    path('loads/<uuid:load_id>/bids/mine/accept-counter/', AcceptCounterView.as_view(), name='marketplace-bid-accept-counter'),

    # shipper/broker bid actions
    path('loads/<uuid:load_id>/bids/<uuid:bid_id>/accept/', BidAcceptView.as_view(), name='marketplace-bid-accept'),
    path('loads/<uuid:load_id>/bids/<uuid:bid_id>/counter/', BidCounterView.as_view(), name='marketplace-bid-counter'),
    path('loads/<uuid:load_id>/bids/<uuid:bid_id>/reject/', BidRejectView.as_view(), name='marketplace-bid-reject'),

    # bookings
    path('bookings/<uuid:booking_id>/', BookingDetailView.as_view(), name='marketplace-booking-detail'),
    path('bookings/<uuid:booking_id>/complete/', BookingCompleteView.as_view(), name='marketplace-booking-complete'),

    # carrier-specific
    path('carrier/my-bids/', MyBidsView.as_view(), name='marketplace-my-bids'),
    path('carrier/my-capacity/', MyCapacityView.as_view(), name='marketplace-my-capacity'),

    # capacity postings
    path('capacity/', CapacityCreateView.as_view(), name='marketplace-capacity-create'),
    path('capacity/<uuid:posting_id>/', CapacityDetailView.as_view(), name='marketplace-capacity-detail'),
    path('capacity/<uuid:posting_id>/deactivate/', CapacityDeactivateView.as_view(), name='marketplace-capacity-deactivate'),
    path('capacity/<uuid:posting_id>/offers/', CapacityOffersView.as_view(), name='marketplace-capacity-offers'),
]
