from django.contrib import admin
from unfold.admin import ModelAdmin as UnfoldModelAdmin

from .models import CompanyRating, Review


# admin view for all submitted reviews with filtering by rating
@admin.register(Review)
class ReviewAdmin(UnfoldModelAdmin):
    list_display = ('id', 'reviewer_name', 'reviewee_name', 'overall_rating', 'booking_ref', 'created_at')
    list_filter = ('overall_rating',)
    search_fields = ('reviewer__name', 'reviewee__name', 'booking__booking_ref')
    readonly_fields = ('id', 'created_at')

    def reviewer_name(self, obj):
        return obj.reviewer.name
    reviewer_name.short_description = 'Reviewer'

    def reviewee_name(self, obj):
        return obj.reviewee.name
    reviewee_name.short_description = 'Reviewee'

    def booking_ref(self, obj):
        return obj.booking.booking_ref
    booking_ref.short_description = 'Booking'


# admin view for the denormalized rating cache — read-only, updated by signal
@admin.register(CompanyRating)
class CompanyRatingAdmin(UnfoldModelAdmin):
    list_display = ('company_name', 'avg_rating', 'review_count', 'last_updated')
    search_fields = ('company__name',)
    readonly_fields = ('company', 'avg_rating', 'review_count', 'last_updated')

    def company_name(self, obj):
        return obj.company.name
    company_name.short_description = 'Company'

    def has_add_permission(self, request):
        return False
