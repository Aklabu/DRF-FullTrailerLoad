from django.urls import path

from .views import ContactView, TrackingSearchView

urlpatterns = [
    path('support/contact/', ContactView.as_view(), name='support-contact'),
    path('tracking/search/', TrackingSearchView.as_view(), name='tracking-search'),
]
