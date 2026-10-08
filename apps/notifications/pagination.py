from rest_framework.pagination import PageNumberPagination


class NotificationPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = None
    max_page_size = 10
