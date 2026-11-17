from django.urls import path

from .views import ContactView, TrackingSearchView

urlpatterns = [
    path('contact/', ContactView.as_view(), name='contact'),
    path('tracking/search/', TrackingSearchView.as_view(), name='tracking-search'),
]
