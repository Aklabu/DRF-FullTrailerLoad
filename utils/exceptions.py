from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import exception_handler


def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)

    if response is not None:
        error_data = response.data

        if isinstance(error_data, dict):
            message = error_data.get('detail', 'An error occurred')
            errors = {k: v for k, v in error_data.items() if k != 'detail'}
            if not errors:
                errors = None
        else:
            message = 'An error occurred'
            errors = error_data if error_data else None

        response.data = {
            'success': False,
            'statusCode': response.status_code,
            'message': str(message),
            'timestamp': timezone.now().isoformat(),
            'data': None,
            'errors': errors,
        }

    return response
