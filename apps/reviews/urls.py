from django.urls import path

from .views import (
    CompanyProfileView,
    CompanyReviewsView,
    ReviewStatusView,
    SubmitReviewView,
)

urlpatterns = [
    # review eligibility check and submission — scoped under marketplace/jobs/
    path('marketplace/jobs/<str:job_id>/review-status/', ReviewStatusView.as_view(), name='review-status'),
    path('marketplace/jobs/<str:job_id>/review/', SubmitReviewView.as_view(), name='review-submit'),

    # public company profile and review list
    path('profiles/<uuid:company_id>/', CompanyProfileView.as_view(), name='company-profile'),
    path('profiles/<uuid:company_id>/reviews/', CompanyReviewsView.as_view(), name='company-reviews'),
]
