"""
Default pagination configuration for MerchantHub.

Uses DRF's ``PageNumberPagination`` with sensible defaults.
"""

from rest_framework.pagination import PageNumberPagination


class DefaultPagination(PageNumberPagination):
    """Standard pagination class for all list endpoints.

    - Default page size: 25
    - Maximum page size: 100
    - Clients can override the page size via the ``page_size``
      query parameter (capped at ``max_page_size``).
    """

    page_size = 25
    page_size_query_param = "page_size"
    max_page_size = 100
