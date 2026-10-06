from django.utils import timezone
from rest_framework.response import Response


class CustomResponse:

    @staticmethod
    def success(message, data=None, status_code=200):
        return Response(
            {
                'success': True,
                'statusCode': status_code,
                'message': message,
                'timestamp': timezone.now().isoformat(),
                'data': data,
                'errors': None,
            },
            status=status_code,
        )

    @staticmethod
    def error(message, status_code=400, data=None, errors=None):
        return Response(
            {
                'success': False,
                'statusCode': status_code,
                'message': message,
                'timestamp': timezone.now().isoformat(),
                'data': data,
                'errors': errors,
            },
            status=status_code,
        )
