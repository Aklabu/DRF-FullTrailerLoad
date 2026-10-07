import requests
from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView

from utils.response import CustomResponse

from .models import SupportTicket
from .notifications import send_ticket_confirmation_email, send_urgent_alert_email
from .serializers import ContactSerializer, TrackingResultSerializer

# external tracking API — base URL kept here so it's easy to override via settings
_TRACKING_API_URL = 'https://movingwyze.com/api/tracking/search/'
# job_id is capped at 15 chars per spec
_JOB_ID_MAX_LEN = 15


# public endpoint — creates a SupportTicket and sends confirmation / urgent-alert emails
class ContactView(APIView):
    permission_classes = [AllowAny]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        serializer = ContactSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ticket = serializer.save()

        # always send submitter a confirmation
        send_ticket_confirmation_email(ticket)

        # urgent tickets get an immediate alert to the support team inbox
        if ticket.urgency == SupportTicket.Urgency.URGENT:
            send_urgent_alert_email(ticket)

        return CustomResponse.success(
            message='Our freight operations team will respond within 2 business hours. Check your email for a ticket confirmation.',
            status_code=status.HTTP_201_CREATED,
        )


# public proxy — fetches shipment status from the external tracking API and strips private fields
class TrackingSearchView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        job_id = request.query_params.get('job_id', '').strip()

        if not job_id:
            return CustomResponse.error(
                'job_id parameter is required.',
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        if len(job_id) > _JOB_ID_MAX_LEN:
            return CustomResponse.error(
                f'job_id must not exceed {_JOB_ID_MAX_LEN} characters.',
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        try:
            response = requests.get(
                _TRACKING_API_URL,
                params={'job_id': job_id},
                timeout=10,
            )
        except requests.exceptions.ConnectionError:
            return CustomResponse.error(
                'Tracking service is unavailable. Please try again later.',
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except requests.exceptions.Timeout:
            return CustomResponse.error(
                'Tracking service timed out. Please try again later.',
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            )
        except requests.exceptions.RequestException:
            return CustomResponse.error(
                'An error occurred while contacting the tracking service.',
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        if response.status_code == 400:
            # pass the upstream message through directly
            try:
                upstream_message = response.json().get('message', 'No task found for the given job ID.')
            except ValueError:
                upstream_message = 'No task found for the given job ID.'
            return CustomResponse.error(upstream_message, status_code=status.HTTP_400_BAD_REQUEST)

        if not response.ok:
            return CustomResponse.error(
                'An error occurred. Please try again.',
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        try:
            payload = response.json()
        except ValueError:
            return CustomResponse.error(
                'An error occurred. Please try again.',
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # upstream returns { status, message, data: { task, loadsheet } }
        upstream_data = payload.get('data', {})
        if not upstream_data.get('task'):
            return CustomResponse.error(
                'No task found for the given job ID.',
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        # serialize strips all private fields before returning to the client
        serializer = TrackingResultSerializer(upstream_data)
        return CustomResponse.success(
            message='Shipment found.',
            data=serializer.data,
        )
