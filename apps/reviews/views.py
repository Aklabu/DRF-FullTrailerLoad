from django.db.models import Count, Q
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from utils.response import CustomResponse
from apps.accounts.models import Company
from apps.marketplace.models import Booking, Load

from .models import (
    CARRIER_SUB_RATING_KEYS,
    SHIPPER_BROKER_SUB_RATING_KEYS,
    CompanyRating,
    Review,
)
from .serializers import (
    CompanyProfileSerializer,
    ReviewCreatedSerializer,
    ReviewReadSerializer,
    ReviewStatusSerializer,
    ReviewWriteSerializer,
)


def _get_review_context(job_id, user):
    # resolves load, booking and companies from a job_id for the current user
    try:
        load = Load.objects.get(job_id=job_id)
    except Load.DoesNotExist:
        return None, 'load_not_found'

    try:
        booking = Booking.objects.select_related(
            'load', 'shipper__company', 'carrier__company'
        ).get(load=load)
    except Booking.DoesNotExist:
        return None, 'booking_not_found'

    company = getattr(user, 'company', None)
    if not company:
        return None, 'no_company'

    shipper_company = getattr(booking.shipper, 'company', None)
    carrier_company = getattr(booking.carrier, 'company', None)

    is_shipper = company == shipper_company
    is_carrier = company == carrier_company

    if not is_shipper and not is_carrier:
        return None, 'not_participant'

    reviewee = carrier_company if is_shipper else shipper_company
    return {
        'load': load,
        'booking': booking,
        'reviewer': company,
        'reviewee': reviewee,
        'reviewer_role': company.role,
    }, None


# returns eligibility status so the frontend can decide which screen to render
class ReviewStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, job_id):
        ctx, error = _get_review_context(job_id, request.user)

        if error == 'load_not_found':
            return CustomResponse.error('Load not found.', status_code=status.HTTP_404_NOT_FOUND)
        if error == 'booking_not_found':
            return CustomResponse.error('Booking not found.', status_code=status.HTTP_404_NOT_FOUND)
        if error in ('no_company', 'not_participant'):
            return CustomResponse.error('You are not a participant on this job.', status_code=status.HTTP_403_FORBIDDEN)

        booking = ctx['booking']
        reviewer = ctx['reviewer']
        reviewee = ctx['reviewee']

        eligible = booking.status == Booking.Status.COMPLETED
        already_reviewed = Review.objects.filter(booking=booking, reviewer=reviewer).exists()

        data = {
            'eligible': eligible,
            'already_reviewed': already_reviewed,
            'job_id': ctx['load'].job_id,
            'origin': ctx['load'].origin,
            'destination': ctx['load'].destination,
            'completed_at': booking.completed_at,
            'counterparty': {
                'id': str(reviewee.id),
                'company_name': reviewee.name,
                'role': reviewee.role,
            },
            'reviewer_role': ctx['reviewer_role'],
        }
        return CustomResponse.success(
            message='Review status retrieved.',
            data=ReviewStatusSerializer(data).data,
        )


# validates eligibility and saves the review with sub_rating key enforcement
class SubmitReviewView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, job_id):
        ctx, error = _get_review_context(job_id, request.user)

        if error == 'load_not_found':
            return CustomResponse.error('Load not found.', status_code=status.HTTP_404_NOT_FOUND)
        if error == 'booking_not_found':
            return CustomResponse.error('Booking not found.', status_code=status.HTTP_404_NOT_FOUND)
        if error in ('no_company', 'not_participant'):
            return CustomResponse.error('You are not a participant on this job.', status_code=status.HTTP_403_FORBIDDEN)

        booking = ctx['booking']
        reviewer = ctx['reviewer']
        reviewee = ctx['reviewee']

        if booking.status != Booking.Status.COMPLETED:
            return CustomResponse.error(
                'Reviews can only be submitted after both parties confirm job completion.',
                status_code=status.HTTP_403_FORBIDDEN,
                errors={'code': 'not_eligible'},
            )

        if Review.objects.filter(booking=booking, reviewer=reviewer).exists():
            return CustomResponse.error(
                'You have already reviewed this job.',
                status_code=status.HTTP_400_BAD_REQUEST,
                errors={'code': 'already_reviewed'},
            )

        serializer = ReviewWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        # enforce sub_rating keys match the reviewee's role
        sub_ratings = data.get('sub_ratings', {})
        if sub_ratings:
            allowed = (
                CARRIER_SUB_RATING_KEYS
                if reviewee.role == Company.Role.CARRIER
                else SHIPPER_BROKER_SUB_RATING_KEYS
            )
            invalid_keys = set(sub_ratings.keys()) - allowed
            if invalid_keys:
                return CustomResponse.error(
                    f'Invalid sub_rating keys for role {reviewee.role}: {", ".join(invalid_keys)}',
                    status_code=status.HTTP_400_BAD_REQUEST,
                    errors={'code': 'invalid_sub_ratings'},
                )

        review = Review.objects.create(
            booking=booking,
            reviewer=reviewer,
            reviewee=reviewee,
            overall_rating=data['overall_rating'],
            sub_ratings=sub_ratings,
            review_text=data.get('review_text', ''),
        )

        return CustomResponse.success(
            message='Review submitted.',
            data=ReviewCreatedSerializer(review).data,
            status_code=status.HTTP_201_CREATED,
        )


# returns public company profile with denormalized avg_rating and job_count
class CompanyProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, company_id):
        try:
            company = Company.objects.select_related('rating').get(id=company_id)
        except Company.DoesNotExist:
            return CustomResponse.error('Company not found.', status_code=status.HTTP_404_NOT_FOUND)

        return CustomResponse.success(
            message='Profile retrieved.',
            data=CompanyProfileSerializer(company).data,
        )


# returns paginated reviews for a company with summary distribution and sort/filter
class CompanyReviewsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, company_id):
        try:
            company = Company.objects.select_related('rating').get(id=company_id)
        except Company.DoesNotExist:
            return CustomResponse.error('Company not found.', status_code=status.HTTP_404_NOT_FOUND)

        qs = Review.objects.filter(reviewee=company).select_related(
            'reviewer', 'booking__load'
        )

        # star filter
        star = request.query_params.get('star')
        if star:
            try:
                qs = qs.filter(overall_rating=int(star))
            except ValueError:
                pass

        # sort
        sort = request.query_params.get('sort', 'newest')
        if sort == 'highest':
            qs = qs.order_by('-overall_rating', '-created_at')
        elif sort == 'lowest':
            qs = qs.order_by('overall_rating', '-created_at')
        else:
            qs = qs.order_by('-created_at')

        # pagination
        page_size = 10
        try:
            page = max(1, int(request.query_params.get('page', 1)))
        except (ValueError, TypeError):
            page = 1
        start = (page - 1) * page_size
        end = start + page_size
        total = qs.count()
        page_qs = qs[start:end]

        # rating distribution across all reviews regardless of filter
        all_reviews = Review.objects.filter(reviewee=company)
        distribution = {str(i): 0 for i in range(1, 6)}
        for row in all_reviews.values('overall_rating').annotate(count=Count('id')):
            distribution[str(row['overall_rating'])] = row['count']

        rating = getattr(company, 'rating', None)
        summary = {
            'avg_rating': float(rating.avg_rating) if rating else None,
            'review_count': rating.review_count if rating else 0,
            'distribution': distribution,
        }

        return CustomResponse.success(
            message='Reviews retrieved.',
            data={
                'summary': summary,
                'reviews': ReviewReadSerializer(page_qs, many=True).data,
                'count': total,
                'next': f'?page={page + 1}' if end < total else None,
                'previous': f'?page={page - 1}' if page > 1 else None,
            },
        )
