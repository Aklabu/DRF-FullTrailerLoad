from django.contrib import admin
from unfold.admin import ModelAdmin as UnfoldModelAdmin

from .models import AuditLog, Bid, Booking, CapacityOffer, CapacityPosting, Load


# read-only inline showing all bids on a load in the admin change page
class BidInline(admin.TabularInline):
    model = Bid
    extra = 0
    readonly_fields = ('id', 'carrier', 'amount', 'counter_amount', 'status', 'note', 'placed_at')
    fields = ('carrier', 'amount', 'counter_amount', 'status', 'note', 'placed_at')
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


# read-only inline showing the audit trail on a load change page
class AuditLogInline(admin.TabularInline):
    model = AuditLog
    extra = 0
    readonly_fields = ('actor', 'action', 'timestamp')
    fields = ('actor', 'action', 'timestamp')
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


# admin view for loads with bid and audit log inlines
@admin.register(Load)
class LoadAdmin(UnfoldModelAdmin):
    list_display = ('job_id', 'poster_email', 'status', 'origin', 'destination', 'pickup_date', 'posted_at')
    list_filter = ('status', 'equipment_type', 'pricing_mode', 'visibility')
    search_fields = ('job_id', 'origin', 'destination', 'poster__email')
    readonly_fields = ('id', 'job_id', 'posted_at', 'updated_at')
    inlines = [BidInline, AuditLogInline]

    fieldsets = (
        ('Identity', {'fields': ('id', 'job_id', 'poster', 'status', 'visibility')}),
        ('Route', {'fields': ('origin', 'destination', 'pickup_date', 'delivery_date')}),
        ('Specs', {'fields': ('cubic_feet', 'weight', 'equipment_type', 'special_requirements')}),
        ('Pricing', {'fields': ('pricing_mode', 'fixed_price')}),
        ('Timestamps', {'fields': ('posted_at', 'updated_at'), 'classes': ('collapse',)}),
    )

    def poster_email(self, obj):
        return obj.poster.email
    poster_email.short_description = 'Poster'
    poster_email.admin_order_field = 'poster__email'


# admin view for individual bids across all loads
@admin.register(Bid)
class BidAdmin(UnfoldModelAdmin):
    list_display = ('id', 'load_job_id', 'carrier_email', 'amount', 'counter_amount', 'status', 'placed_at')
    list_filter = ('status',)
    search_fields = ('load__job_id', 'carrier__email')
    readonly_fields = ('id', 'placed_at', 'updated_at')

    def load_job_id(self, obj):
        return obj.load.job_id
    load_job_id.short_description = 'Load'

    def carrier_email(self, obj):
        return obj.carrier.email
    carrier_email.short_description = 'Carrier'


# admin view for confirmed bookings — read-only booking_ref
@admin.register(Booking)
class BookingAdmin(UnfoldModelAdmin):
    list_display = ('booking_ref', 'load_job_id', 'shipper_email', 'carrier_email', 'agreed_price', 'confirmed_at')
    search_fields = ('booking_ref', 'load__job_id', 'shipper__email', 'carrier__email')
    readonly_fields = ('id', 'booking_ref', 'confirmed_at')

    def load_job_id(self, obj):
        return obj.load.job_id
    load_job_id.short_description = 'Load'

    def shipper_email(self, obj):
        return obj.shipper.email
    shipper_email.short_description = 'Shipper'

    def carrier_email(self, obj):
        return obj.carrier.email
    carrier_email.short_description = 'Carrier'


# read-only inline showing all offers on a capacity posting
class CapacityOfferInline(admin.TabularInline):
    model = CapacityOffer
    extra = 0
    readonly_fields = ('offered_by', 'message', 'offered_at')
    fields = ('offered_by', 'message', 'offered_at')
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


# admin view for capacity postings with offers inline
@admin.register(CapacityPosting)
class CapacityPostingAdmin(UnfoldModelAdmin):
    list_display = ('id', 'carrier_email', 'origin', 'destination', 'available_from', 'available_to', 'status', 'posted_at')
    list_filter = ('status', 'equipment_type')
    search_fields = ('origin', 'destination', 'carrier__email')
    readonly_fields = ('id', 'posted_at', 'updated_at')
    inlines = [CapacityOfferInline]

    def carrier_email(self, obj):
        return obj.carrier.email
    carrier_email.short_description = 'Carrier'
