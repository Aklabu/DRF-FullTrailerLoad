import uuid
from django.conf import settings
from django.db import models
from django.utils import timezone


# represents a freight load posted by a shipper or broker
class Load(models.Model):
    class Status(models.TextChoices):
        OPEN = 'open', 'Open'
        BIDDING = 'bidding', 'Bidding'
        BOOKED = 'booked', 'Booked'
        COMPLETED = 'completed', 'Completed'
        EXPIRED = 'expired', 'Expired'

    class EquipmentType(models.TextChoices):
        ANY = 'Any equipment', 'Any Equipment'
        BOX_TRUCK = 'Box Truck', 'Box Truck'
        MOVING_TRAILER = 'Moving Trailer', 'Moving Trailer'
        DRY_VAN = 'Dry Van (Side Door)', 'Dry Van (Side Door)'

    class PricingMode(models.TextChoices):
        OPEN_BIDDING = 'open_bidding', 'Open Bidding'
        BEST_OFFER = 'best_offer', 'Best Offer'
        FIXED = 'fixed', 'Fixed'

    class Visibility(models.TextChoices):
        PUBLIC = 'public', 'Public'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    job_id = models.CharField(max_length=20, unique=True, editable=False)
    poster = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='posted_loads',
    )
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.OPEN)
    origin = models.CharField(max_length=255)
    destination = models.CharField(max_length=255)
    pickup_date = models.DateField()
    delivery_date = models.DateField()
    cubic_feet = models.PositiveIntegerField()
    weight = models.PositiveIntegerField(null=True, blank=True)
    equipment_type = models.CharField(max_length=30, choices=EquipmentType.choices)
    pricing_mode = models.CharField(max_length=15, choices=PricingMode.choices)
    fixed_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    special_requirements = models.TextField(blank=True)
    visibility = models.CharField(max_length=10, choices=Visibility.choices, default=Visibility.PUBLIC)
    posted_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-posted_at']

    def save(self, *args, **kwargs):
        if not self.job_id:
            # UUID-derived suffix keeps job_id unique without a DB round-trip
            self.job_id = f'FTL-{timezone.now().year}-{str(uuid.uuid4().int)[:4].zfill(4)}'
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.job_id} — {self.origin} → {self.destination}'


# a carrier's price offer on a specific load
class Bid(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        COUNTERED = 'countered', 'Countered'
        ACCEPTED = 'accepted', 'Accepted'
        REJECTED = 'rejected', 'Rejected'
        WITHDRAWN = 'withdrawn', 'Withdrawn'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    load = models.ForeignKey(Load, on_delete=models.CASCADE, related_name='bids')
    carrier = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='placed_bids',
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    counter_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.PENDING)
    note = models.TextField(blank=True)
    placed_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-placed_at']
        constraints = [
            # prevent a carrier from holding two active bids on the same load
            models.UniqueConstraint(
                fields=['load', 'carrier'],
                condition=models.Q(status__in=['pending', 'countered']),
                name='unique_active_bid_per_carrier_load',
            )
        ]

    def __str__(self):
        return f'Bid {self.amount} on {self.load.job_id} by {self.carrier.email}'


# created when a bid is accepted — locks in the agreed price and both parties
class Booking(models.Model):
    class Status(models.TextChoices):
        BOOKED = 'booked', 'Booked'
        IN_TRANSIT = 'in_transit', 'In Transit'
        COMPLETED = 'completed', 'Completed'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    booking_ref = models.CharField(max_length=20, unique=True, editable=False)
    load = models.OneToOneField(Load, on_delete=models.CASCADE, related_name='booking')
    bid = models.OneToOneField(Bid, on_delete=models.CASCADE, related_name='booking')
    shipper = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='shipper_bookings',
    )
    carrier = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='carrier_bookings',
    )
    agreed_price = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.BOOKED)
    completed_by_shipper = models.BooleanField(default=False)
    completed_by_carrier = models.BooleanField(default=False)
    confirmed_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-confirmed_at']

    def save(self, *args, **kwargs):
        if not self.booking_ref:
            year = timezone.now().year
            count = Booking.objects.filter(confirmed_at__year=year).count() + 1
            self.booking_ref = f'BK-{year}-{count:05d}'
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.booking_ref} — {self.load.job_id}'


# immutable event log attached to a load for shipper/broker transparency
class AuditLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    load = models.ForeignKey(Load, on_delete=models.CASCADE, related_name='audit_log')
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='audit_entries',
    )
    action = models.CharField(max_length=500)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f'{self.timestamp} — {self.action}'


# a carrier advertising available truck space on a route and date range
class CapacityPosting(models.Model):
    class Status(models.TextChoices):
        ACTIVE = 'active', 'Active'
        EXPIRED = 'expired', 'Expired'
        DEACTIVATED = 'deactivated', 'Deactivated'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    carrier = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='capacity_postings',
    )
    origin = models.CharField(max_length=255)
    destination = models.CharField(max_length=255)
    available_from = models.DateField()
    available_to = models.DateField()
    cubic_feet = models.PositiveIntegerField()
    equipment_type = models.CharField(max_length=30, choices=Load.EquipmentType.choices)
    notes = models.TextField(blank=True)
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.ACTIVE)
    posted_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-posted_at']

    def __str__(self):
        return f'Capacity {self.origin} → {self.destination} ({self.carrier.email})'


# a shipper or broker expressing interest in a carrier's capacity posting
class CapacityOffer(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    posting = models.ForeignKey(CapacityPosting, on_delete=models.CASCADE, related_name='offers')
    offered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='capacity_offers_sent',
    )
    message = models.TextField(blank=True)
    offered_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-offered_at']

    def __str__(self):
        return f'Offer on {self.posting} by {self.offered_by.email}'
