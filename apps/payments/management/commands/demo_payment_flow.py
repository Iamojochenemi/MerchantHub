"""
Management command to demo the full MerchantHub payment pipeline.

Runs the complete 6-step demo flow against the Nomba sandbox:

1. Create a product + inventory
2. Create a sale
3. Click "Pay with Nomba" -> generate checkout link
4. Show Payment = PENDING in the database
5. Verify transaction -> Payment -> SUCCESS, Sale -> PAID
6. Show the updated dashboard state

Usage::

    python manage.py demo_payment_flow
    python manage.py demo_payment_flow --amount 15000.00
    python manage.py demo_payment_flow --skip-sandbox  (test auth + DB only)
"""

from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.accounts.models import User
from apps.customers.models import Customer
from apps.inventory.models import Inventory
from apps.payments.integrations.nomba import (
    NombaAuthService,
    NombaCheckoutService,
    NombaPaymentService,
)
from apps.payments.models import Payment
from apps.products.models import Product
from apps.sales.models import Sale
from apps.sales.services import SalesService
from apps.workspaces.models import Workspace, WorkspaceMembership


def _sep(title: str) -> None:
    """Print a section separator."""
    print()
    print("=" * 72)
    print(f"  {title}")
    print("=" * 72)


def _step(n: int, title: str) -> None:
    """Print a step heading."""
    print()
    print(f"  >>  STEP {n}: {title}")
    print("-" * 60)


def _ok(msg: str) -> None:
    """Print a success message."""
    print(f"     [OK] {msg}")


def _info(msg: str) -> None:
    """Print an info message."""
    print(f"     [..] {msg}")


def _warn(msg: str) -> None:
    """Print a warning."""
    print(f"     [!!] {msg}")


class Command(BaseCommand):
    """Demonstrate the full MerchantHub payment pipeline."""

    help = "Demonstrate the full MerchantHub payment pipeline end-to-end"

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--amount",
            type=str,
            default="15000.00",
            help="Sale amount (default: 15000.00)",
        )
        parser.add_argument(
            "--email",
            type=str,
            default="demo@merchanthub.com",
            help="Merchant email (default: demo@merchanthub.com)",
        )
        parser.add_argument(
            "--password",
            type=str,
            default="demopass123",
            help="Merchant password (default: demopass123)",
        )
        parser.add_argument(
            "--skip-sandbox",
            action="store_true",
            help="Skip Nomba sandbox calls (test DB flow only)",
        )

    def handle(self, *args, **options) -> None:
        """Run the full demo flow."""
        amount_str: str = options["amount"]
        email: str = options["email"]
        password: str = options["password"]
        skip_sandbox: bool = options["skip_sandbox"]

        amount = Decimal(amount_str)

        print()
        print("+========================================================+")
        print("|  MERCHANTHUB - Full Payment Pipeline Demo             |")
        print("+========================================================+")
        print(f"     Amount: {amount} NGN")
        print(f"     Sandbox: {'SKIPPED' if skip_sandbox else 'ENABLED'}")
        print(f"     Nomba URL: {settings.NOMBA_BASE_URL}")

        try:
            self._run_pipeline(amount, email, password, skip_sandbox)
        except Exception as e:
            print()
            print(f"     [FAIL] Demo failed: {e}")
            raise

        print()
        print("+========================================================+")
        print("|  DEMO COMPLETE - Pipeline Verified!                   |")
        print("+========================================================+")
        print()

    # ------------------------------------------------------------------
    # Pipeline
    # ------------------------------------------------------------------

    def _run_pipeline(
        self,
        amount: Decimal,
        email: str,
        password: str,
        skip_sandbox: bool,
    ) -> None:
        _sep("SETUP")
        _step(1, "Create workspace and merchant account")

        # Create user if not exists
        user, user_created = User.objects.get_or_create(
            email=email,
            defaults={
                "first_name": "Demo",
                "last_name": "Merchant",
            },
        )
        if user_created:
            user.set_password(password)
            user.save()

        # Create workspace
        workspace, _ = Workspace.objects.get_or_create(
            owner=user,
            name="Demo Store",
            defaults={"slug": "demo-store"},
        )
        WorkspaceMembership.objects.get_or_create(
            user=user,
            workspace=workspace,
            defaults={"role": WorkspaceMembership.Role.OWNER},
        )

        _ok(f"Merchant: {user.email}")
        _ok(f"Workspace: {workspace.name} (ID: {workspace.pk})")

        _step(2, "Create product and inventory")

        product, _ = Product.objects.get_or_create(
            workspace=workspace,
            sku="DEMO-001",
            defaults={
                "name": "Demo Product",
                "cost_price": "5000.00",
                "selling_price": str(amount),
            },
        )
        inventory, _ = Inventory.objects.get_or_create(
            product=product,
            defaults={"quantity": 100},
        )

        # Also create a customer for reference
        customer, _ = Customer.objects.get_or_create(
            workspace=workspace,
            phone_number="+2348000000000",
            defaults={
                "first_name": "John",
                "last_name": "Demo",
                "email": "customer@example.com",
            },
        )

        _ok(f"Product: {product.name} -- NGN {product.selling_price}")
        _ok(f"Inventory: {inventory.quantity} units")
        _ok(f"Customer: {customer.first_name} {customer.last_name}")

        # ------------------------------------------------------------------
        _sep("SALE CREATION")

        _step(3, "Create a sale")

        sale = SalesService.create_sale(
            workspace=workspace,
            created_by=user,
            items=[
                {"product": product, "quantity": 2},
            ],
        )

        _ok(f"Sale created: ID={sale.pk}")
        _ok(f"Subtotal: NGN {sale.subtotal}")
        _ok(f"Total: NGN {sale.total}")
        _ok(f"Payment status: {sale.payment_status}")

        # ------------------------------------------------------------------
        _sep("PAYMENT INITIATION")

        _step(4, "Click 'Pay with Nomba' -- generate checkout link")

        if skip_sandbox:
            _warn("Sandbox skipped -- using mock checkout data")
            mock_ref = "demo-skip-ref-" + str(sale.pk)[:8]
            checkout_link = f"https://pay.nomba.com/sandbox/{mock_ref}"
            order_ref = mock_ref
        else:
            _info("Authenticating with Nomba sandbox...")
            auth = NombaAuthService()
            token = auth.get_access_token()
            _ok(f"Nomba token obtained: {token.access_token[:20]}...")

            _info("Creating checkout order...")
            checkout = NombaCheckoutService(
                access_token=token.access_token,
                account_id=settings.NOMBA_ACCOUNT_ID,
            )
            order_result = checkout.create_order(
                amount=str(sale.total),
                currency="NGN",
                callback_url="https://merchanthub.example.com/callback",
                customer_email="customer@example.com",
                metadata={
                    "demo": "merchanthub-pipeline",
                    "sale_id": str(sale.pk),
                },
            )
            checkout_link = order_result.checkout_link
            order_ref = order_result.order_reference

        _ok(f"Checkout link: {checkout_link}")
        _ok(f"Order reference: {order_ref}")

        # Show the checkout link as a clickable URL (important for demo)
        print()
        print("     *** SHARE THIS LINK WITH THE CUSTOMER ***")
        print(f"     {checkout_link}")
        print()

        # ------------------------------------------------------------------
        _step(5, "Record PENDING Payment in database")

        if skip_sandbox:
            # In skip mode, create the Payment directly without Nomba calls
            _warn("Sandbox skipped -- creating PENDING Payment directly")
            payment = Payment.objects.create(
                workspace=workspace,
                sale=sale,
                amount=sale.total,
                currency="NGN",
                payment_method=Payment.PaymentMethod.TRANSFER,
                status=Payment.Status.PENDING,
                provider_reference=order_ref,
                notes=f"Demo checkout: {checkout_link}",
            )
        else:
            # Reuse the token from step 4
            init_result = NombaPaymentService.initiate_checkout(
                sale=sale,
                callback_url="https://merchanthub.example.com/callback",
                customer_email="customer@example.com",
                metadata={"demo": "merchanthub-pipeline"},
                access_token=token.access_token,
            )
            payment = Payment.objects.get(pk=init_result.payment_id)
        _ok(f"Payment ID: {payment.pk}")
        _ok(f"Payment status: {payment.status}")
        _ok(f"Provider reference: {payment.provider_reference}")
        _ok(f"Notes: {payment.notes}")

        # ------------------------------------------------------------------
        _sep("PAYMENT VERIFICATION")

        _step(6, "Verify transaction -- flip Payment to SUCCESS, Sale to PAID")

        if skip_sandbox:
            _warn("Sandbox skipped -- simulating SUCCESS verification")
            # Manually update payment to SUCCESS and sale to PAID
            from django.db import transaction

            with transaction.atomic():
                payment.status = Payment.Status.SUCCESS
                payment.save(update_fields=["status", "updated_at"])
                sale.payment_status = Sale.PaymentStatus.PAID
                sale.save(update_fields=["payment_status", "updated_at"])

            _ok("Payment manually marked as SUCCESS")
            _ok("Sale manually marked as PAID")
        else:
            _info("Verifying payment with Nomba sandbox...")

            # Refresh payment from DB
            payment.refresh_from_db()

            verify_result = NombaPaymentService.verify_and_update_payment(
                payment=payment,
                access_token=token.access_token,
            )

            _ok(f"Old payment status: {verify_result.old_status}")
            _ok(f"New payment status: {verify_result.new_status}")
            _ok(f"Sale payment status: {verify_result.sale_payment_status}")
            _ok(f"Nomba returned: {verify_result.nomba_status}")

        # ------------------------------------------------------------------
        _sep("DASHBOARD STATE")

        # Refresh from DB
        payment.refresh_from_db()
        sale.refresh_from_db()

        _info("FINAL STATE -- What the dashboard shows:")

        print()
        print("     +-------------------------------------------+")
        print(f"     | SALE ID:       {sale.pk}    |")
        print(f"     | TOTAL:         NGN {sale.total}                 |")
        print(f"     | STATUS:        {sale.payment_status}           |")
        print("     +-------------------------------------------+")
        print(f"     | PAYMENT ID:    {payment.pk}  |")
        print(f"     | AMOUNT:        NGN {payment.amount}                 |")
        print(f"     | STATUS:        {payment.status}                    |")
        print(f"     | PROVIDER REF:  {payment.provider_reference}  |")
        print("     +-------------------------------------------+")
        print()

        # Final assertions
        assert sale.payment_status == Sale.PaymentStatus.PAID, (
            f"Sale should be PAID, got {sale.payment_status}"
        )
        assert payment.status == Payment.Status.SUCCESS, (
            f"Payment should be SUCCESS, got {payment.status}"
        )

        _ok("All assertions passed -- pipeline is correct!")
