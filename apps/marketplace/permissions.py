from rest_framework.permissions import BasePermission

from apps.accounts.models import Company


def _company(user):
    return getattr(user, 'company', None)


# blocks anyone who is not a verified shipper or broker
class IsVerifiedShipperOrBroker(BasePermission):
    message = 'Only verified shippers or brokers can perform this action.'

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        company = _company(request.user)
        if not company:
            return False
        return (
            company.role in (Company.Role.SHIPPER, Company.Role.BROKER)
            and company.verification_status == Company.VerificationStatus.VERIFIED
        )


# blocks anyone who is not a verified carrier
class IsVerifiedCarrier(BasePermission):
    message = 'Only verified carriers can perform this action.'

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        company = _company(request.user)
        if not company:
            return False
        return (
            company.role == Company.Role.CARRIER
            and company.verification_status == Company.VerificationStatus.VERIFIED
        )


# object-level guard — only the load poster can access
class IsLoadOwner(BasePermission):
    message = 'You do not own this load.'

    def has_object_permission(self, request, view, obj):
        return obj.poster == request.user


# object-level guard — only the shipper or carrier on a booking can access
class IsBookingParty(BasePermission):
    message = 'You are not a party to this booking.'

    def has_object_permission(self, request, view, obj):
        return obj.shipper == request.user or obj.carrier == request.user


# object-level guard — only the carrier who created the capacity posting can access
class IsCapacityOwner(BasePermission):
    message = 'You do not own this capacity posting.'

    def has_object_permission(self, request, view, obj):
        return obj.carrier == request.user
