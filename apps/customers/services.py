"""
Service-layer functions for the ``customers`` app.

Keeps business logic out of views and serializers, making the
workflow testable without HTTP.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from apps.customers.models import Customer
    from apps.workspaces.models import Workspace


class CustomerService:
    """Handles customer lifecycle operations.

    All customer mutations go through this service to ensure
    consistent behaviour (workspace scoping, audit hooks for
    future use).
    """

    @staticmethod
    def create_customer(
        *, workspace: Workspace, **validated_data: Any
    ) -> Customer:
        """Create a new customer scoped to *workspace*.

        Parameters
        ----------
        workspace:
            The workspace the customer belongs to.
        **validated_data:
            Pre-validated field values (``first_name``,
            ``last_name``, ``phone_number``, ``email``,
            ``address``, ``notes``).

        Returns
        -------
        Customer
            The newly created ``Customer`` instance.
        """
        from apps.customers.models import Customer

        customer = Customer.objects.create(
            workspace=workspace,
            **validated_data,
        )
        return customer

    @staticmethod
    def update_customer(
        *, instance: Customer, **validated_data: Any
    ) -> Customer:
        """Update an existing customer in-place.

        Parameters
        ----------
        instance:
            The customer to update.
        **validated_data:
            Pre-validated field values to apply.

        Returns
        -------
        Customer
            The updated ``Customer`` instance (same object).
        """
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance

    @staticmethod
    def delete_customer(*, instance: Customer) -> None:
        """Hard-delete a customer from the database.

        Customers are hard-deleted because there is no sales
        relationship to preserve yet. When the sales module is
        extended to link customers, this should switch to a
        soft-delete or archival pattern.

        Parameters
        ----------
        instance:
            The customer to delete.
        """
        instance.delete()
