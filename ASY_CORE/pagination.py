from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


class StandardResultsSetPagination(PageNumberPagination):
    """
    Custom pagination class that standardizes response format across the project.
    Returns responses in the format:
    {
        "count": total records number,
        "next": next page URL or null,
        "previous": previous page URL or null,
        "results": [list of items]
    }
    """
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100

    def get_paginated_response(self, data):
        return Response({
            'count': self.page.paginator.count,
            'next': self.get_next_link(),
            'previous': self.get_previous_link(),
            'results': data
        })
