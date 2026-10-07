import uuid
from django.db import models
from django.db.models import Avg


# sub-rating keys allowed per reviewee role
CARRIER_SUB_RATING_KEYS = {'communication', 'reliability', 'on_time', 'load_care'}
SHIPPER_BROKER_SUB_RATING_KEYS = {'communication', 'payment_speed', 'load_accuracy', 'professionalism'}


# human-readable labels for sub-rating keys shown in the review list
SUB_RATING_LABELS = {
    'communication': 'Communication',
    'reliability': 'Reliability',
    'on_time': 'On-time delivery',
    'load_care': 'Load care',
    'payment_speed': 'Payment speed',
    'load_accuracy': 'Load accuracy',
    'professionalism': 'Professionalism',
}


# a review left by one company for another after a completed booking
class Review(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    booking = models.ForeignKey(
        'marketplace.Booking',
        on_delete=models.CASCADE,
        related_name='reviews',
    )
    reviewer = models.ForeignKey(
        'accounts.Company',
        on_delete=models.CASCADE,
        related_name='reviews_given',
    )
    reviewee = models.ForeignKey(
        'accounts.Company',
        on_delete=models.CASCADE,
        related_name='reviews_received',
    )
    overall_rating = models.SmallIntegerField()
    # stored as raw dict e.g. {"communication": 5, "reliability": 4}
    sub_ratings = models.JSONField(default=dict, blank=True)
    review_text = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        # one review per reviewer per booking
        constraints = [
            models.UniqueConstraint(
                fields=['booking', 'reviewer'],
                name='unique_review_per_booking_reviewer',
            )
        ]

    def __str__(self):
        return f'Review by {self.reviewer} for {self.reviewee} on {self.booking}'


# denormalized rating cache — updated via post_save signal on Review
class CompanyRating(models.Model):
    company = models.OneToOneField(
        'accounts.Company',
        on_delete=models.CASCADE,
        related_name='rating',
    )
    avg_rating = models.DecimalField(max_digits=4, decimal_places=2, default=0)
    review_count = models.IntegerField(default=0)
    last_updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'Rating for {self.company} — {self.avg_rating} ({self.review_count} reviews)'


def recalculate_company_rating(company):
    # recomputes avg and count from all reviews received by the company
    from django.db.models import Avg
    qs = Review.objects.filter(reviewee=company)
    count = qs.count()
    avg = qs.aggregate(Avg('overall_rating'))['overall_rating__avg'] or 0
    CompanyRating.objects.update_or_create(
        company=company,
        defaults={
            'avg_rating': round(avg, 2),
            'review_count': count,
        },
    )
