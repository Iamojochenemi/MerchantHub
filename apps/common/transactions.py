"""
Transaction utilities for MerchantHub.

Provides helpers and documentation for the three critical
transaction boundaries in the system:

1. **Sale creation** — atomic inventory deduction + sale recording
2. **Payment recording** — atomic payment + sale status update
3. **Inventory adjustment** — atomic movement + stock update

Usage patterns
--------------
All critical operations should follow this pattern:

.. code:: python

    from django.db import transaction

    def create_sale(...):
        with transaction.atomic():
            products = Product.objects.select_for_update().filter(
                id__in=product_ids
            )
            # ... validate stock, create sale, deduct inventory ...


Concurrency protection
----------------------
- **Sale creation**: ``select_for_update()`` on Product rows prevents
  overselling under concurrent requests.
- **Payment recording**: ``select_for_update()`` on the Sale row
  prevents concurrent payments from exceeding the sale total.
- **Stock deduction**: ``F()`` expressions ensure atomic updates
  without race conditions:

  .. code:: python

      Product.objects.filter(id=pk).update(
          current_stock=F('current_stock') - quantity
      )
"""

from django.db import transaction  # noqa: F401  Re-export for convenience

# Sentinel value used to indicate an atomic block should be used.
# Usage::
#     with transaction.atomic():
#         ...
ATOMIC = transaction.atomic


def lock_rows(model, ids, order_by=None):
    """Return a queryset with rows locked via ``select_for_update()``.

    Always lock rows in a consistent order to prevent deadlocks.

    Parameters
    ----------
    model : Model class
        The Django model to query.
    ids : list of UUID
        Primary keys of the rows to lock.
    order_by : str, optional
        Field to order by (recommended to prevent deadlocks).
        Defaults to ``'id'``.

    Returns
    -------
    QuerySet
        Locked queryset.
    """
    qs = model.objects.filter(pk__in=ids)
    if order_by:
        qs = qs.order_by(order_by)
    else:
        qs = qs.order_by("id")
    return qs.select_for_update()
