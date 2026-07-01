# MerchantHub — Implementation Checklist

**Version:** 1.0  
**Status:** Draft  
**Phase:** 3 (Implementation)  
**Last Updated:** July 1, 2026

---

## Overall Progress

- [ ] **Architecture** — All documents finalized and consistent
- [ ] **Foundation** — Base models, settings, shared components
- [ ] **Accounts** — User model, registration, authentication, profile
- [ ] **Workspaces** — Multi-tenant foundation, membership, roles, business profile
- [ ] **Inventory** — Categories, products, stock tracking, inventory movements
- [ ] **Customers** — Customer profiles, computed metrics, search
- [ ] **Sales** — Sale creation with atomic inventory deduction, sale items, status management
- [ ] **Payments** — Payment recording, sale status transitions, outstanding balances
- [ ] **Expenses** — Expense CRUD, category classification, date-range queries
- [ ] **Notifications** — In-app notification system, low-stock alerts, event-driven creation
- [ ] **Audit Logs** — Immutable audit trail, signal-based logging, entity change tracking
- [ ] **Dashboard** — KPI aggregation, activity feed, period-over-period comparison
- [ ] **Testing** — Unit, integration, API, transaction, and permission tests
- [ ] **Documentation** — README, API docs, deployment guide
- [ ] **Deployment** — Production settings, environment config, Docker, cloud hosting

---

## Foundation

### Project Setup

- [ ] **Configure `config/settings.py`:**
  - [ ] Set `AUTH_USER_MODEL = 'accounts.User'`
  - [ ] Add `djangorestframework`, `djangorestframework-simplejwt`, `drf-spectacular`, `django-cors-headers`, `django-filter` to `INSTALLED_APPS`
  - [ ] Register all MerchantHub apps: `apps.accounts`, `apps.common`, `apps.workspaces`, `apps.inventory`, `apps.customers`, `apps.sales`, `apps.payments`, `apps.expenses`, `apps.dashboard`
  - [ ] Configure `REST_FRAMEWORK` settings:
    - [ ] `DEFAULT_AUTHENTICATION_CLASSES` — `JWTAuthentication`
    - [ ] `DEFAULT_PERMISSION_CLASSES` — `IsAuthenticated`
    - [ ] `DEFAULT_PAGINATION_CLASS` — `PageNumberPagination` (page_size=25, max_page_size=100)
    - [ ] `DEFAULT_FILTER_BACKENDS` — `django_filters`, `SearchFilter`, `OrderingFilter`
    - [ ] `EXCEPTION_HANDLER` — `apps.common.exceptions.custom_exception_handler`
  - [ ] Configure `SIMPLE_JWT` settings (access token lifetime, refresh token lifetime, signing key)
  - [ ] Configure `SPECTACULAR_SETTINGS` for OpenAPI schema generation
  - [ ] Configure `CORS_ALLOWED_ORIGINS` or `CORS_ALLOW_ALL_ORIGINS=True` (MVP)
  - [ ] Set `USE_TZ = True`, `TIME_ZONE = 'UTC'`
  - [ ] Configure database — SQLite for development, PostgreSQL via `DATABASE_URL` for production
  - [ ] Configure `django-environ` or `python-decouple` for environment variables
  - [ ] Configure logging to stdout (structured log format recommended)

- [ ] **Environment configuration:**
  - [ ] Create `.env.example` with all required variables
  - [ ] Create `.env` (gitignored) for local development
  - [ ] Define variables: `SECRET_KEY`, `DEBUG`, `DATABASE_URL`, `ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS`

- [ ] **URL routing (`config/urls.py`):**
  - [ ] Register `admin/` for Django admin
  - [ ] Register `api/schema/` for drf-spectacular schema
  - [ ] Register `api/docs/` for Swagger UI
  - [ ] Register `api/v1/` namespace with included app URLs
  - [ ] Add `health/` endpoint

### Shared Models (`apps/common/models/`)

- [ ] **`UUIDModel` (abstract):**
  - [ ] `id = UUIDField(primary_key=True, default=uuid.uuid4, editable=False)`

- [ ] **`TimeStampedModel` (abstract):**
  - [ ] `created_at = DateTimeField(auto_now_add=True)`
  - [ ] `updated_at = DateTimeField(auto_now=True)`

- [ ] **`BaseModel` (abstract):**
  - [ ] Inherits from `UUIDModel` + `TimeStampedModel`
  - [ ] `class Meta: abstract = True`

- [ ] **`SoftDeleteModel` (abstract):**
  - [ ] Inherits from `BaseModel`
  - [ ] `deleted_at = DateTimeField(null=True, blank=True)`
  - [ ] Custom manager that excludes soft-deleted records by default
  - [ ] `delete()` method sets `deleted_at` instead of hard-deleting
  - [ ] `hard_delete()` method for permanent deletion
  - [ ] `class Meta: abstract = True`

- [ ] **`WorkspaceScopedModel` (abstract):**
  - [ ] Inherits from `SoftDeleteModel`
  - [ ] `workspace = ForeignKey('workspaces.Workspace', on_delete=CASCADE)`
  - [ ] `class Meta: abstract = True`

### Shared Components (`apps/common/`)

- [ ] **Custom Managers (`apps/common/managers.py`):**
  - [ ] `ActiveQuerySet` — filters `deleted_at__isnull=True`
  - [ ] `WorkspaceScopedQuerySet(ActiveQuerySet)` — adds `for_workspace(workspace)` method
  - [ ] `WorkspaceScopedManager.from_queryset(WorkspaceScopedQuerySet)`

- [ ] **Validators (`apps/common/validators.py`):**
  - [ ] `validate_positive_decimal(value)` — raises `ValidationError` if value ≤ 0
  - [ ] `validate_non_negative_decimal(value)` — raises `ValidationError` if value < 0
  - [ ] `validate_iso_currency(value)` — validates 3-letter ISO 4217 code
  - [ ] `validate_phone(value)` — validates E.164 or basic phone format

- [ ] **Exception Classes (`apps/common/exceptions.py`):**
  - [ ] `WorkspaceRequiredError(APIException)` — status_code=400, code=`WORKSPACE_REQUIRED`
  - [ ] `InsufficientStockError(APIException)` — status_code=409, code=`INSUFFICIENT_STOCK`
  - [ ] `PaymentExceedsTotalError(APIException)` — status_code=409, code=`PAYMENT_EXCEEDS_TOTAL`
  - [ ] `OwnerCannotRemoveSelfError(APIException)` — status_code=400, code=`OWNER_CANNOT_REMOVE_SELF`
  - [ ] `DuplicateSkuError(APIException)` — status_code=409, code=`DUPLICATE_SKU`
  - [ ] `custom_exception_handler(exc, context)` — converts all exceptions to `{error, code, details}` format

- [ ] **Permission Framework (`apps/common/permissions.py`):**
  - [ ] `IsWorkspaceMember` — verifies user has active `WorkspaceMembership` for `request.workspace`
  - [ ] `IsWorkspaceOwner` — verifies membership role is `owner`
  - [ ] `IsManagerOrAbove` — verifies role level ≥ 50

- [ ] **Middleware (`apps/common/middleware.py`):**
  - [ ] `WorkspaceMiddleware`:
    - [ ] Reads `X-Workspace-ID` header from request
    - [ ] Resolves to `Workspace` object
    - [ ] Verifies user has active membership
    - [ ] Attaches `request.workspace`
    - [ ] Returns 400 if header missing, 403 if not a member

- [ ] **Pagination (`apps/common/pagination.py`):**
  - [ ] `DefaultPagination(PageNumberPagination)` with `page_size=25`, `max_page_size=100`

- [ ] **Base ViewSet (`apps/common/views.py`):**
  - [ ] `WorkspaceScopedViewSet` mixin or base class:
    - [ ] Overrides `get_queryset()` to filter by `request.workspace`
    - [ ] Overrides `perform_create()` to set workspace from request

---

## Accounts

### Models (`apps/accounts/models.py`)

- [ ] **`User(AbstractUser)`:**
  - [ ] Override PK: `id = UUIDField(primary_key=True, default=uuid.uuid4, editable=False)`
  - [ ] `email = EmailField(unique=True)`
  - [ ] `phone_number = CharField(max_length=20, null=True, blank=True)`
  - [ ] `is_merchant = BooleanField(default=True)`
  - [ ] `db_table = 'accounts_user'`
  - [ ] `REQUIRED_FIELDS = ['email']`
  - [ ] `USERNAME_FIELD = 'email'` (or keep username as login field — verify with PRD)
  - [ ] Override `save()` to auto-set username from email (if using email-based login)

### Services (`apps/accounts/services.py`)

- [ ] **`RegistrationService`:**
  - [ ] `register(email, password, first_name, last_name, phone=None)` → `(User, Workspace)`
    - [ ] Wrapped in `transaction.atomic()`
    - [ ] Creates User with validated email + hashed password
    - [ ] Delegates default workspace + owner membership + business profile creation to `WorkspaceService.create_default_workspace(user)`
    - [ ] Returns created User and Workspace
    - [ ] Raises `IntegrityError` if email already exists

### Serializers (`apps/accounts/serializers.py`)

- [ ] **`RegisterSerializer`** — fields: email, password, first_name, last_name, phone
  - [ ] Password write-only, validated for minimum length (8+ characters)
  - [ ] `create()` calls `RegistrationService.register()`

- [ ] **`LoginSerializer`** — fields: email, password
  - [ ] Validates credentials via Django auth
  - [ ] Returns access + refresh tokens

- [ ] **`UserProfileSerializer`** — fields: id, email, first_name, last_name, phone, is_merchant, date_joined
  - [ ] Email read-only after creation

- [ ] **`PasswordResetSerializer`** — fields: email
- [ ] **`PasswordResetConfirmSerializer`** — fields: token, password

### Views (`apps/accounts/views.py`)

- [ ] **`RegisterView(CreateAPIView)`** — `POST /api/v1/auth/register/`
  - [ ] Permission: `AllowAny`
  - [ ] Returns user data + tokens on success

- [ ] **`LoginView`** — `POST /api/v1/auth/login/`
  - [ ] Permission: `AllowAny`
  - [ ] Returns JWT access + refresh tokens

- [ ] **`TokenRefreshView`** — uses `simplejwt`'s `TokenRefreshView`
- [ ] **`ProfileViewSet`** — `GET/PUT /api/v1/users/me/`
  - [ ] Permission: `IsAuthenticated`
  - [ ] Read/update own profile only

- [ ] **`PasswordResetView`** — `POST /api/v1/auth/password/reset/`
- [ ] **`PasswordResetConfirmView`** — `POST /api/v1/auth/password/reset/confirm/`

### URLs (`apps/accounts/urls.py`)

- [ ] Register all account endpoints under `auth/` and `users/` paths
- [ ] Include in project-level `urls.py` under `api/v1/`

### Tests (`apps/accounts/tests/`)

- [ ] **`test_models.py`:**
  - [ ] User creation with unique email enforced
  - [ ] User string representation
  - [ ] UUID PK generated on creation

- [ ] **`test_services.py`:**
  - [ ] Registration creates User + Workspace + Membership + BusinessProfile atomically
  - [ ] Duplicate email rejected
  - [ ] Password is hashed, not stored in plain text

- [ ] **`test_api.py`:**
  - [ ] Register endpoint returns 201 with user data and tokens
  - [ ] Register with duplicate email returns 400
  - [ ] Login with valid credentials returns 200 with tokens
  - [ ] Login with invalid credentials returns 401
  - [ ] Token refresh returns new access token
  - [ ] Profile endpoint returns authenticated user's data
  - [ ] Profile update works for authenticated user

- [ ] **`test_permissions.py`:**
  - [ ] Registration/login endpoints accessible without auth
  - [ ] Profile endpoint requires auth

---

## Workspaces

### Models (`apps/workspaces/models.py`)

- [ ] **`Workspace(BaseModel, SoftDeleteModel)`:**
  - [ ] `name = CharField(max_length=255, unique=True)`
  - [ ] `slug = SlugField(max_length=100, unique=True)`
  - [ ] `owner = ForeignKey('accounts.User', on_delete=PROTECT)`
  - [ ] `is_active = BooleanField(default=True)`
  - [ ] Auto-generate `slug` from `name` on creation
  - [ ] `db_table = 'workspaces_workspace'`

- [ ] **`WorkspaceMembership(BaseModel)`:**
  - [ ] `workspace = ForeignKey(Workspace, on_delete=CASCADE)`
  - [ ] `user = ForeignKey('accounts.User', on_delete=CASCADE)`
  - [ ] `role = CharField(max_length=20, choices=['owner', 'manager', 'staff'])`
  - [ ] Unique constraint on `(workspace, user)`
  - [ ] `db_table = 'workspaces_workspacemembership'`

- [ ] **`BusinessProfile(BaseModel)`:**
  - [ ] `workspace = OneToOneField(Workspace, on_delete=CASCADE, primary_key=True)`
  - [ ] `legal_name = CharField(max_length=255, null=True, blank=True)`
  - [ ] `tax_id = CharField(max_length=50, null=True, blank=True)`
  - [ ] `address_line1`, `address_line2`, `city`, `state`, `postal_code`, `country` — all optional
  - [ ] `currency = CharField(max_length=3, default='USD')`
  - [ ] `timezone = CharField(max_length=50, default='UTC')`
  - [ ] `logo_url = URLField(max_length=500, null=True, blank=True)`
  - [ ] `db_table = 'workspaces_businessprofile'`

- [ ] **`Role(BaseModel)`:**
  - [ ] `name = CharField(max_length=50, unique=True)`
  - [ ] `level = IntegerField()` — 100=owner, 50=manager, 10=staff
  - [ ] `description = TextField(null=True, blank=True)`
  - [ ] `db_table = 'workspaces_role'`
  - [ ] Seeded via data migration: owner(100), manager(50), staff(10)

- [ ] **`Permission(BaseModel)`:**
  - [ ] `codename = CharField(max_length=100, unique=True)`
  - [ ] `description = TextField(null=True, blank=True)`
  - [ ] `db_table = 'workspaces_permission'`
  - [ ] Many-to-many with Role through `workspaces_role_permissions`

### Data Migrations (`apps/workspaces/migrations/`)

- [ ] **Seed roles migration:**
  - [ ] Create owner role (level=100)
  - [ ] Create manager role (level=50)
  - [ ] Create staff role (level=10)

- [ ] **Seed permissions migration (optional — MVP uses role-level enforcement)**
  - [ ] Create permissions like `product.create`, `sale.read`, `staff.invite`
  - [ ] Assign to appropriate roles

### Services (`apps/workspaces/services.py`)

- [ ] **`WorkspaceService`:**
  - [ ] `create_default_workspace(user)` → `Workspace`
    - [ ] Creates Workspace with name derived from user (e.g., `"{user.first_name}'s Business"`)
    - [ ] Creates WorkspaceMembership with role=owner
    - [ ] Creates BusinessProfile with defaults
    - [ ] Returns the Workspace
  - [ ] `rename_workspace(workspace, new_name)` — with slug regeneration
  - [ ] `delete_workspace(workspace)` — soft delete with 30-day grace period

- [ ] **`MembershipService`:**
  - [ ] `add_member(workspace, user, role)` — creates membership
  - [ ] `change_role(workspace, user, new_role)` — prevents last-owner demotion
  - [ ] `remove_member(workspace, user)` — prevents last-owner removal
  - [ ] `can_remove_self(workspace, user)` — returns False if user is last owner

- [ ] **`InvitationService`:**
  - [ ] `invite(workspace, invited_by, email, role)` — creates invitation record
  - [ ] `accept_invite(token, user)` — creates membership from invitation

### Serializers (`apps/workspaces/serializers.py`)

- [ ] **`WorkspaceSerializer`** — fields: id, name, slug, is_active, created_at
- [ ] **`WorkspaceDetailSerializer`** — WorkspaceSerializer + nested BusinessProfile
- [ ] **`WorkspaceMembershipSerializer`** — fields: id, user (nested), role, created_at
- [ ] **`BusinessProfileSerializer`** — all profile fields
- [ ] **`InviteSerializer`** — fields: email, role (write-only for creation)

### Views (`apps/workspaces/views.py`)

- [ ] **`WorkspaceViewSet`** — `GET/POST /api/v1/workspaces/`, `GET/PUT/DELETE /api/v1/workspaces/{id}/`
  - [ ] Permission: `IsWorkspaceOwner` for update/delete, `IsWorkspaceMember` for detail view

- [ ] **`WorkspaceMembershipViewSet`** — `GET/POST /api/v1/workspaces/{id}/members/`
  - [ ] Permission: `IsWorkspaceOwner` for write, `IsWorkspaceMember` for read

- [ ] **`BusinessProfileViewSet`** — `GET/PUT /api/v1/workspaces/{id}/profile/`
  - [ ] Permission: `IsWorkspaceOwner` for update, `IsWorkspaceMember` for read

### URLs (`apps/workspaces/urls.py`)

- [ ] Register all workspace endpoints under appropriate paths
- [ ] Include in project-level `urls.py` under `api/v1/`

### Tests (`apps/workspaces/tests/`)

- [ ] **`test_models.py`:**
  - [ ] Workspace creation generates slug
  - [ ] WorkspaceMembership unique constraint enforced
  - [ ] BusinessProfile auto-created with workspace

- [ ] **`test_services.py`:**
  - [ ] `create_default_workspace()` creates workspace + membership + profile
  - [ ] Last owner cannot be removed
  - [ ] Last owner cannot be demoted from owner role
  - [ ] Role change validates against business rules

- [ ] **`test_api.py`:**
  - [ ] Create workspace returns 201
  - [ ] List workspaces returns user's workspaces
  - [ ] Update workspace requires owner role
  - [ ] Non-member gets 403 on workspace endpoints
  - [ ] Membership management endpoints respect owner-only access

- [ ] **`test_permissions.py`:**
  - [ ] Owner can manage members
  - [ ] Manager cannot manage members
  - [ ] Staff cannot view members list

---

## Inventory

### Models (`apps/inventory/models.py`)

- [ ] **`Category(WorkspaceScopedModel, SoftDeleteModel)`:**
  - [ ] `name = CharField(max_length=100)`
  - [ ] `description = TextField(null=True, blank=True)`
  - [ ] Unique constraint on `(workspace, name)`
  - [ ] `db_table = 'inventory_category'`

- [ ] **`Product(WorkspaceScopedModel, SoftDeleteModel)`:**
  - [ ] `category = ForeignKey(Category, on_delete=SET_NULL, null=True)`
  - [ ] `name = CharField(max_length=255)`
  - [ ] `sku = CharField(max_length=100, null=True, blank=True)`
  - [ ] `description = TextField(null=True, blank=True)`
  - [ ] `unit_price = DecimalField(max_digits=12, decimal_places=2)` — validated ≥ 0
  - [ ] `cost_price = DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)` — validated ≥ 0
  - [ ] `current_stock = DecimalField(max_digits=12, decimal_places=3, default=0)` — validated ≥ 0
  - [ ] `low_stock_threshold = DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)` — validated ≥ 0
  - [ ] `is_active = BooleanField(default=True)`
  - [ ] Partial unique index on `(workspace, sku)` where `sku IS NOT NULL AND deleted_at IS NULL`
  - [ ] `db_table = 'inventory_product'`

- [ ] **`InventoryMovement(BaseModel)`:**
  - [ ] `product = ForeignKey(Product, on_delete=PROTECT)`
  - [ ] `sale = ForeignKey('sales.Sale', on_delete=SET_NULL, null=True)` — **lazy string FK**
  - [ ] `movement_type = CharField(max_length=20, choices=['initial', 'sale', 'return', 'adjustment', 'transfer_out', 'transfer_in'])`
  - [ ] `quantity = DecimalField(max_digits=12, decimal_places=3)` — validated > 0
  - [ ] `running_balance = DecimalField(max_digits=12, decimal_places=3)`
  - [ ] `reason = TextField(null=True, blank=True)`
  - [ ] No `updated_at` field — immutable after creation
  - [ ] `db_table = 'inventory_inventorymovement'`

### Services (`apps/inventory/services.py`)

- [ ] **`ProductService`:**
  - [ ] `create_product(workspace, data)` — validates SKU uniqueness
  - [ ] `update_product(product, data)` — validates SKU uniqueness on change
  - [ ] `archive_product(product)` — sets `is_active=False`
  - [ ] `get_low_stock_products(workspace)` — returns products where `current_stock ≤ low_stock_threshold`

- [ ] **`InventoryService`:**
  - [ ] `adjust_stock(product, quantity, reason, user)` — creates adjustment movement with `transaction.atomic()`
  - [ ] `get_current_stock(product)` — reads `product.current_stock` (denormalized)

- [ ] **`MovementService`:**
  - [ ] `create_initial_movement(product, quantity)` — called on product creation
  - [ ] `create_sale_movement(product, sale, quantity)` — called by SaleService
  - [ ] `create_return_movement(product, sale, quantity, reason)`
  - [ ] All movements use `F()` expressions to atomically update `current_stock`

### Serializers (`apps/inventory/serializers.py`)

- [ ] **`CategorySerializer`** — fields: id, name, description, product_count
- [ ] **`ProductSerializer`** — all fields including cost_price (staff-restricted)
- [ ] **`ProductListSerializer`** — lightweight: id, name, sku, unit_price, current_stock, is_active (excludes cost_price for staff)
- [ ] **`InventoryMovementSerializer`** — read-only: id, product_id, movement_type, quantity, running_balance, reason, created_at

### Views (`apps/inventory/views.py`)

- [ ] **`CategoryViewSet`** — `GET/POST /api/v1/categories/`, `GET/PUT/DELETE /api/v1/categories/{id}/`
  - [ ] Permission: `IsManagerOrAbove` for write, `IsWorkspaceMember` for read

- [ ] **`ProductViewSet`** — `GET/POST /api/v1/products/`, `GET/PUT/DELETE /api/v1/products/{id}/`
  - [ ] Permission: `IsManagerOrAbove` for write, `IsWorkspaceMember` for read
  - [ ] SearchFilter on `name`, `sku`
  - [ ] OrderingFilter on `unit_price`, `name`, `created_at`
  - [ ] Staff-restricted: exclude `cost_price` from serialized output

- [ ] **`LowStockProductView`** — `GET /api/v1/products/low-stock/`
  - [ ] Returns products where `current_stock ≤ low_stock_threshold`

- [ ] **`InventoryMovementViewSet`** — `GET /api/v1/products/{product_id}/movements/`
  - [ ] Read-only, filtered by product

- [ ] **`AdjustStockView`** — `POST /api/v1/products/{id}/adjust-stock/`
  - [ ] Accepts `quantity` (positive for addition, negative for deduction) and `reason`

### URLs (`apps/inventory/urls.py`)

- [ ] Register all inventory endpoints with proper nested routing

### Tests (`apps/inventory/tests/`)

- [ ] **`test_models.py`:**
  - [ ] Product SKU uniqueness within workspace
  - [ ] Category name uniqueness within workspace
  - [ ] Product current_stock cannot go negative (via CHECK)
  - [ ] InventoryMovement is immutable (no update/delete)

- [ ] **`test_services.py`:**
  - [ ] Stock adjustment updates current_stock correctly
  - [ ] Stock adjustment creates movement record with correct running_balance
  - [ ] Low-stock query returns correct products
  - [ ] Duplicate SKU raises error

- [ ] **`test_api.py`:**
  - [ ] Product CRUD returns correct status codes
  - [ ] Low-stock endpoint returns accurate list
  - [ ] Movement history is read-only
  - [ ] Stock adjustment endpoint updates stock correctly

- [ ] **`test_permissions.py`:**
  - [ ] Staff can read products but cannot create/update/delete
  - [ ] Staff cannot see cost_price in product response
  - [ ] Non-member gets 403

---

## Customers

### Models (`apps/customers/models.py`)

- [ ] **`Customer(WorkspaceScopedModel, SoftDeleteModel)`:**
  - [ ] `name = CharField(max_length=255)`
  - [ ] `email = EmailField(null=True, blank=True)`
  - [ ] `phone = CharField(max_length=20, null=True, blank=True)`
  - [ ] `notes = TextField(null=True, blank=True)`
  - [ ] `total_visits = IntegerField(default=0)`
  - [ ] `total_spend = DecimalField(max_digits=14, decimal_places=2, default=0.00)`
  - [ ] `last_visit_date = DateField(null=True, blank=True)`
  - [ ] Application-layer validation: at least one of `email` or `phone` required
  - [ ] `db_table = 'customers_customer'`

### Services (`apps/customers/services.py`)

- [ ] **`CustomerService`:**
  - [ ] `create_customer(workspace, data)` — validates at-least-one-contact
  - [ ] `update_customer(customer, data)` — validates at-least-one-contact
  - [ ] `update_computed_metrics(customer, sale_total)` — called by SaleService
  - [ ] `search_customers(workspace, query)` — search by name, phone, email

### Serializers (`apps/customers/serializers.py`)

- [ ] **`CustomerSerializer`** — all editable fields: name, email, phone, notes
- [ ] **`CustomerDetailSerializer`** — CustomerSerializer + computed metrics: total_visits, total_spend, last_visit_date, average_transaction_value

### Views (`apps/customers/views.py`)

- [ ] **`CustomerViewSet`** — `GET/POST /api/v1/customers/`, `GET/PUT/DELETE /api/v1/customers/{id}/`
  - [ ] Permission: `IsWorkspaceMember` for read, `IsManagerOrAbove` for delete
  - [ ] SearchFilter on `name`, `phone`, `email`
  - [ ] Staff-restricted: optionally hide `total_spend` from staff role

### URLs (`apps/customers/urls.py`)

- [ ] Register customer endpoints

### Tests (`apps/customers/tests/`)

- [ ] **`test_models.py`:**
  - [ ] Customer creation with email only
  - [ ] Customer creation with phone only
  - [ ] Customer creation without email or phone — validation error

- [ ] **`test_services.py`:**
  - [ ] Search returns correct results
  - [ ] Computed metrics update correctly

- [ ] **`test_api.py`:**
  - [ ] CRUD operations return correct status codes
  - [ ] Search endpoint returns filtered results

- [ ] **`test_permissions.py`:**
  - [ ] Staff can create customers but not delete
  - [ ] Manager and owner can delete

---

## Sales

### Models (`apps/sales/models.py`)

- [ ] **`Sale(WorkspaceScopedModel, SoftDeleteModel)`:**
  - [ ] `customer = ForeignKey('customers.Customer', on_delete=SET_NULL, null=True)`
  - [ ] `recorded_by = ForeignKey('accounts.User', on_delete=PROTECT)`
  - [ ] `status = CharField(max_length=20, choices=['pending', 'completed', 'partially_paid', 'refunded', 'cancelled'], default='pending')`
  - [ ] `total_amount = DecimalField(max_digits=14, decimal_places=2)` — validated ≥ 0
  - [ ] `paid_amount = DecimalField(max_digits=14, decimal_places=2, default=0.00)` — validated ≥ 0
  - [ ] `discount_amount = DecimalField(max_digits=12, decimal_places=2, default=0.00)` — validated ≥ 0
  - [ ] `notes = TextField(null=True, blank=True)`
  - [ ] `db_table = 'sales_sale'`

- [ ] **`SaleItem(BaseModel)`:**
  - [ ] `sale = ForeignKey(Sale, on_delete=CASCADE, related_name='items')`
  - [ ] `product = ForeignKey('inventory.Product', on_delete=PROTECT)` — **lazy string FK**
  - [ ] `quantity = DecimalField(max_digits=12, decimal_places=3)` — validated > 0
  - [ ] `unit_price = DecimalField(max_digits=12, decimal_places=2)` — snapshot at sale time
  - [ ] `line_total = DecimalField(max_digits=14, decimal_places=2)` — computed: `quantity × unit_price`
  - [ ] `db_table = 'sales_saleitem'`

### Services (`apps/sales/services.py`)

- [ ] **`SaleService`:**
  - [ ] `create_sale(*, workspace, recorded_by, customer, items)`:
    - [ ] Wrapped in `transaction.atomic()`
    - [ ] Validates at least one item provided
    - [ ] Locks all Product rows with `select_for_update()`
    - [ ] For each item: verifies `product.current_stock ≥ item.quantity`
    - [ ] Creates Sale record
    - [ ] Creates SaleItem records with computed `line_total`
    - [ ] Deducts stock: `Product.objects.filter(id=pk).update(current_stock=F('current_stock') - qty)`
    - [ ] Creates InventoryMovement records with `running_balance`
    - [ ] Updates Customer computed metrics (if customer provided)
    - [ ] Sets `Sale.status = 'pending'`
    - [ ] If any stock check fails, rolls back entire transaction and raises `InsufficientStockError`
  - [ ] `cancel_sale(sale)` — sets status to `cancelled` (only if pending)
  - [ ] `get_sale_with_details(sale)` — returns sale + items + payments

### Serializers (`apps/sales/serializers.py`)

- [ ] **`SaleSerializer`** — read: id, customer, recorded_by, status, total_amount, paid_amount, discount_amount, notes, created_at
- [ ] **`SaleCreateSerializer`** — fields: customer_id, items (nested array of {product_id, quantity}), discount_amount, notes
  - [ ] Validates at least one item
  - [ ] Validates each product_id exists in workspace
- [ ] **`SaleDetailSerializer`** — SaleSerializer + nested SaleItems + nested Payments
- [ ] **`SaleListSerializer`** — lightweight: id, customer_name, total_amount, status, created_at
- [ ] **`SaleItemSerializer`** — fields: id, product_id, product_name, quantity, unit_price, line_total

### Views (`apps/sales/views.py`)

- [ ] **`SaleViewSet`** — `GET/POST /api/v1/sales/`, `GET /api/v1/sales/{id}/`
  - [ ] Permission: `IsWorkspaceMember` for read; all roles for create
  - [ ] DateFromToRangeFilter on `created_at`
  - [ ] SearchFilter on product name, customer name (via related fields)

- [ ] **`CancelSaleView`** — `POST /api/v1/sales/{id}/cancel/`
  - [ ] Only pending sales can be cancelled

### URLs (`apps/sales/urls.py`)

- [ ] Register sale endpoints
- [ ] Register cancel action as custom route

### Tests (`apps/sales/tests/`)

- [ ] **`test_models.py`:**
  - [ ] Sale creation generates UUID
  - [ ] SaleItem line_total equals quantity × unit_price
  - [ ] Sale status defaults to 'pending'

- [ ] **`test_services.py`:**
  - [ ] Sale creation deducts stock correctly
  - [ ] Insufficient stock raises error and rolls back transaction
  - [ ] Customer metrics update after sale creation
  - [ ] Multiple line items all deducted atomically
  - [ ] `select_for_update()` prevents race condition (concurrent test)
  - [ ] Cancelling a pending sale works
  - [ ] Cancelling a completed sale is rejected

- [ ] **`test_api.py`:**
  - [ ] Create sale returns 201 with sale data
  - [ ] Sale detail includes items and payments
  - [ ] Sale list supports date filtering
  - [ ] Insufficient stock returns 409 with product details
  - [ ] Cancel sale returns 200

- [ ] **`test_permissions.py`:**
  - [ ] Staff can create sales
  - [ ] Staff can view sales
  - [ ] Non-member gets 403

---

## Payments

### Models (`apps/payments/models.py`)

- [ ] **`Payment(WorkspaceScopedModel, SoftDeleteModel)`:**
  - [ ] `sale = ForeignKey('sales.Sale', on_delete=PROTECT, related_name='payments')`
  - [ ] `customer = ForeignKey('customers.Customer', on_delete=SET_NULL, null=True)`
  - [ ] `amount = DecimalField(max_digits=14, decimal_places=2)` — validated > 0
  - [ ] `method = CharField(max_length=20, choices=['cash', 'card', 'bank_transfer'])`
  - [ ] `reference = CharField(max_length=100, null=True, blank=True)`
  - [ ] `paid_at = DateTimeField(default=timezone.now)`
  - [ ] Partial unique on `(workspace, reference)` where reference is provided
  - [ ] `db_table = 'payments_payment'`

### Services (`apps/payments/services.py`)

- [ ] **`PaymentService`:**
  - [ ] `record_payment(*, workspace, sale, amount, method, reference=None, recorded_by=None)`:
    - [ ] Wrapped in `transaction.atomic()`
    - [ ] Locks Sale row with `select_for_update()`
    - [ ] Validates `sale.paid_amount + amount ≤ sale.total_amount`
    - [ ] Creates Payment record
    - [ ] Updates `Sale.paid_amount = F('paid_amount') + amount`
    - [ ] Derives and updates `Sale.status`:
      - [ ] `paid_amount ≥ total_amount` → `completed`
      - [ ] `paid_amount > 0` → `partially_paid`
      - [ ] (remains `pending` if paid_amount == 0 — edge case)
    - [ ] Raises `PaymentExceedsTotalError` if validation fails
  - [ ] `get_outstanding_sales(workspace)` — sales where `paid_amount < total_amount`
  - [ ] `get_payments_for_sale(sale)` — returns all payments for a given sale

### Serializers (`apps/payments/serializers.py`)

- [ ] **`PaymentSerializer`** — read: id, sale_id, customer_id, amount, method, reference, paid_at, created_at
- [ ] **`PaymentCreateSerializer`** — write: sale_id, amount, method, reference

### Views (`apps/payments/views.py`)

- [ ] **`PaymentViewSet`** — `GET/POST /api/v1/payments/`, `GET /api/v1/payments/{id}/`
  - [ ] Permission: `IsWorkspaceMember` for read; all roles for create
  - [ ] DateFromToRangeFilter on `paid_at`
  - [ ] Filter by `sale_id` query parameter

- [ ] **`OutstandingBalanceView`** — `GET /api/v1/sales/outstanding/`
  - [ ] Returns sales with remaining balance

- [ ] **`SalePaymentsView`** — `GET /api/v1/sales/{sale_id}/payments/`
  - [ ] Lists all payments for a specific sale

### URLs (`apps/payments/urls.py`)

- [ ] Register payment endpoints
- [ ] Register outstanding and sale-payments as additional routes

### Tests (`apps/payments/tests/`)

- [ ] **`test_models.py`:**
  - [ ] Payment amount must be positive
  - [ ] Payment method limited to valid choices

- [ ] **`test_services.py`:**
  - [ ] Payment recording updates sale status to partially_paid
  - [ ] Full payment updates sale status to completed
  - [ ] Over-payment raises error
  - [ ] Split payments (multiple payments per sale) work correctly
  - [ ] Concurrent payments prevented from exceeding total via `select_for_update()`

- [ ] **`test_api.py`:**
  - [ ] Create payment returns 201
  - [ ] Outstanding balance endpoint returns correct sales
  - [ ] Sale payments list returns correct data

- [ ] **`test_permissions.py`:**
  - [ ] Staff can create payments
  - [ ] Non-member gets 403

---

## Expenses

### Models (`apps/expenses/models.py`)

- [ ] **`Expense(WorkspaceScopedModel, SoftDeleteModel)`:**
  - [ ] `category = CharField(max_length=30, choices=['cost_of_goods_sold', 'rent', 'utilities', 'salaries', 'marketing', 'maintenance', 'other'])`
  - [ ] `amount = DecimalField(max_digits=14, decimal_places=2)` — validated > 0
  - [ ] `description = TextField()` — required
  - [ ] `expense_date = DateField(default=date.today)`
  - [ ] `receipt_url = URLField(max_length=500, null=True, blank=True)`
  - [ ] `db_table = 'expenses_expense'`

### Services (`apps/expenses/services.py`)

- [ ] **`ExpenseService`:**
  - [ ] `create_expense(workspace, data)` — validates category and amount
  - [ ] `update_expense(expense, data)` — validates changes
  - [ ] `get_expenses_by_category(workspace, category, start_date, end_date)` — filtered query

### Serializers (`apps/expenses/serializers.py`)

- [ ] **`ExpenseSerializer`** — all fields: id, category, amount, description, expense_date, receipt_url, created_at
- [ ] **`ExpenseListSerializer`** — lightweight: id, category, amount, expense_date, description (truncated)

### Views (`apps/expenses/views.py`)

- [ ] **`ExpenseViewSet`** — `GET/POST /api/v1/expenses/`, `GET/PUT/DELETE /api/v1/expenses/{id}/`
  - [ ] Permission: `IsWorkspaceMember` for read; all roles for create; `IsManagerOrAbove` for delete
  - [ ] ChoiceFilter on `category`
  - [ ] DateFromToRangeFilter on `expense_date`

### URLs (`apps/expenses/urls.py`)

- [ ] Register expense endpoints

### Tests (`apps/expenses/tests/`)

- [ ] **`test_models.py`:**
  - [ ] Expense amount must be positive
  - [ ] Expense category limited to valid choices
  - [ ] Description is required

- [ ] **`test_services.py`:**
  - [ ] Create expense validates required fields
  - [ ] Category filtering returns correct results

- [ ] **`test_api.py`:**
  - [ ] CRUD operations return correct status codes
  - [ ] Category filter works correctly
  - [ ] Date range filter works correctly

- [ ] **`test_permissions.py`:**
  - [ ] All roles can create expenses
  - [ ] Staff cannot delete expenses
  - [ ] Manager and owner can delete expenses

---

## Notifications

### Models (`apps/common/models/notification.py`)

- [ ] **`Notification(BaseModel)`:**
  - [ ] `user = ForeignKey('accounts.User', on_delete=CASCADE)`
  - [ ] `workspace = ForeignKey('workspaces.Workspace', on_delete=SET_NULL, null=True)`
  - [ ] `notification_type = CharField(max_length=30, choices=['low_stock_alert', 'sale_completed', 'staff_invite', 'payment_received'])`
  - [ ] `title = CharField(max_length=255)`
  - [ ] `message = TextField()`
  - [ ] `is_read = BooleanField(default=False)`
  - [ ] `read_at = DateTimeField(null=True, blank=True)`
  - [ ] `expires_at = DateTimeField(null=True, blank=True)`
  - [ ] `db_table = 'common_notification'`

### Services (`apps/common/services/notification_service.py`)

- [ ] **`NotificationService`:**
  - [ ] `create_notification(user, workspace, type, title, message)` — creates notification
  - [ ] `mark_as_read(notification)` — sets `is_read=True`, `read_at=now`
  - [ ] `mark_all_as_read(user, workspace)` — bulk mark-read
  - [ ] `get_unread_count(user, workspace)` — count unread
  - [ ] `cleanup_expired()` — deletes notifications where `expires_at < now` (called by scheduled job)
  - [ ] `notify_low_stock(product)` — creates low_stock_alert for workspace owner
  - [ ] `notify_sale_completed(sale)` — creates sale_completed notification

### Signals (`apps/common/signals.py`)

- [ ] `post_save` signal on Product — check low_stock_threshold and create notification if triggered
- [ ] `post_save` signal on Sale — create sale_completed notification
- [ ] `post_save` signal on Payment — create payment_received notification

### Serializers (`apps/common/serializers/notification_serializer.py`)

- [ ] **`NotificationSerializer`** — fields: id, type, title, message, is_read, read_at, created_at

### Views (`apps/common/views/notification_views.py`)

- [ ] **`NotificationViewSet`** — `GET /api/v1/notifications/`, `PATCH /api/v1/notifications/{id}/read/`
  - [ ] Filtered to current user
  - [ ] Mark-as-read action
  - [ ] Mark-all-as-read action

### Tests (`apps/common/tests/test_notifications.py`)

- [ ] Notification creation works
- [ ] Mark-as-read updates notification state
- [ ] Unread count is accurate
- [ ] Notifications scoped to correct user

---

## Audit Logs

### Models (`apps/common/models/audit_log.py`)

- [ ] **`AuditLog(BaseModel)`:**
  - [ ] `workspace = ForeignKey('workspaces.Workspace', on_delete=SET_NULL, null=True)`
  - [ ] `actor = ForeignKey('accounts.User', on_delete=PROTECT)`
  - [ ] `action = CharField(max_length=50)` — e.g., `entity.create.product`
  - [ ] `target_type = CharField(max_length=50, null=True, blank=True)` — e.g., `product`, `sale`
  - [ ] `target_id = UUIDField(null=True, blank=True)`
  - [ ] `changes = JSONField(null=True, blank=True)` — `{"before": {...}, "after": {...}}`
  - [ ] `metadata = JSONField(null=True, blank=True)` — `{"ip_address": "...", "user_agent": "..."}`
  - [ ] No `updated_at` field — immutable
  - [ ] `db_table = 'common_auditlog'`

### Services (`apps/common/services/audit_service.py`)

- [ ] **`AuditLogService`:**
  - [ ] `log_action(*, workspace, actor, action, target_type=None, target_id=None, changes=None, metadata=None)`
    - [ ] Fire-and-forget — catches and logs exceptions without re-raising
    - [ ] Never blocks the calling operation
  - [ ] `get_logs_for_entity(target_type, target_id)` — returns change history for an entity
  - [ ] `get_workspace_logs(workspace, limit=50)` — recent workspace activity

### Signals (`apps/common/signals.py`)

- [ ] `post_save` signal on Product — log create/update
- [ ] `post_save` signal on Sale — log create
- [ ] `post_save` signal on Customer — log create/update
- [ ] `post_save` signal on Payment — log create
- [ ] `post_save` signal on Expense — log create/update
- [ ] `post_delete` signal on membership — log removal
- [ ] Signal handlers use `transaction.on_commit()` to defer audit writes

### Tests (`apps/common/tests/test_audit_logs.py`)

- [ ] Audit log created on entity creation
- [ ] Audit log captures before/after on entity update
- [ ] Audit log is immutable (no update/delete)
- [ ] Audit log creation failure does not block primary operation

---

## Dashboard

### Services (`apps/dashboard/services.py`)

- [ ] **`DashboardService`:**
  - [ ] `get_summary(workspace, period='today')`:
    - [ ] Computes `revenue` — sum of `Sale.total_amount` for sales in period
    - [ ] Computes `sales_count` — count of sales in period
    - [ ] Computes `expenses` — sum of `Expense.amount` for expenses in period
    - [ ] Computes `net_profit` — `revenue - expenses - cost_of_goods_sold`
    - [ ] Computes `low_stock_count` — count of products meeting low-stock criteria
    - [ ] Computes period-over-period change percentages (e.g., today vs yesterday)
    - [ ] Period parameter: `today`, `week`, `month`
  - [ ] `get_recent_activity(workspace, limit=10)`:
    - [ ] Union of recent Sales, Payments, Expenses
    - [ ] Sorted by timestamp descending
    - [ ] Returns uniform activity items with type, description, timestamp

### Serializers (`apps/dashboard/serializers.py`)

- [ ] **`DashboardSummarySerializer`** — output-only:
  - [ ] `revenue: {current, previous, change_pct}`
  - [ ] `sales_count: {current, previous, change_pct}`
  - [ ] `expenses: {current, previous, change_pct}`
  - [ ] `net_profit: {current, previous, change_pct}`
  - [ ] `low_stock_count: int`
  - [ ] `recent_activity: [ActivityItem]`

- [ ] **`ActivityItemSerializer`** — output-only:
  - [ ] `type: str` — `sale`, `payment`, `expense`
  - [ ] `id: uuid`
  - [ ] `description: str`
  - [ ] `amount: Decimal`
  - [ ] `timestamp: datetime`

### Views (`apps/dashboard/views.py`)

- [ ] **`DashboardSummaryView`** — `GET /api/v1/dashboard/summary/?period=today`
  - [ ] Permission: `IsWorkspaceMember`
  - [ ] Calls `DashboardService.get_summary()`

- [ ] **`DashboardActivityView`** — `GET /api/v1/dashboard/activity/`
  - [ ] Permission: `IsWorkspaceMember`
  - [ ] Calls `DashboardService.get_recent_activity()`

### URLs (`apps/dashboard/urls.py`)

- [ ] Register dashboard endpoints

### Tests (`apps/dashboard/tests/`)

- [ ] Summary returns correct KPI values for period
- [ ] Period comparison math is correct
- [ ] Activity feed returns recent events across modules
- [ ] Low-stock count matches product query
- [ ] Empty workspace returns zeroes (not errors)

---

## API Documentation

### drf-spectacular Setup

- [ ] **Configuration:**
  - [ ] `SPECTACULAR_SETTINGS` in `settings.py` with:
    - [ ] `TITLE = 'MerchantHub API'`
    - [ ] `DESCRIPTION = 'API for MerchantHub multi-tenant commerce platform'`
    - [ ] `VERSION = '1.0.0'`
    - [ ] `SERVE_INCLUDE_SCHEMA = False`
    - [ ] `COMPONENT_SPLIT_REQUEST = True`
    - [ ] `AUTHENTICATION_WHITELIST = ['rest_framework_simplejwt.authentication.JWTAuthentication']`

- [ ] **URL registration:**
  - [ ] `GET /api/schema/` — OpenAPI schema (SpectacularAPIView)
  - [ ] `GET /api/docs/` — Swagger UI (SpectacularSwaggerView)
  - [ ] `GET /api/redoc/` — Redoc UI (SpectacularRedocView)

- [ ] **Validation:**
  - [ ] Run `python manage.py spectacular --validate` and fix any warnings
  - [ ] Verify all endpoints appear in schema
  - [ ] Verify request/response schemas are correct

---

## Testing

### Test Configuration

- [ ] **`pytest.ini` or `pyproject.toml` pytest config:**
  - [ ] `DJANGO_SETTINGS_MODULE = config.settings`
  - [ ] `python_files = test_*.py`
  - [ ] `testpaths = apps/`
  - [ ] `django_find_project = false`

- [ ] **`conftest.py` (project-level):**
  - [ ] `pytest_django` configuration
  - [ ] Fixtures for:
    - [ ] `api_client` — DRF APIClient
    - [ ] `user` — create test user
    - [ ] `workspace` — create test workspace
    - [ ] `owner_membership` — membership with owner role
    - [ ] `staff_membership` — membership with staff role
    - [ ] `manager_membership` — membership with manager role
    - [ ] `auth_client` — authenticated APIClient for a specific role
    - [ ] `product` — create test product
    - [ ] `customer` — create test customer

### Test Types

- [ ] **Unit tests** (`test_models.py` per app):
  - [ ] 1–3 tests per model covering invariants, constraints, and custom methods

- [ ] **Service tests** (`test_services.py` per app):
  - [ ] 3–5 tests per service method including success and failure paths
  - [ ] Test transaction boundaries
  - [ ] Test business rule enforcement

- [ ] **API tests** (`test_api.py` per app):
  - [ ] 2–4 tests per endpoint covering:
    - [ ] Successful operation (200/201)
    - [ ] Authentication failure (401)
    - [ ] Permission denial (403)
    - [ ] Validation error (400)
    - [ ] Not found (404)

- [ ] **Transaction tests:**
  - [ ] Sale creation with concurrent stock deduction — `select_for_update()` correctness
  - [ ] Payment recording with concurrent payments — prevents over-payment
  - [ ] Rollback behavior — verify no partial state if transaction fails

- [ ] **Permission tests** (`test_permissions.py` per app):
  - [ ] 1 test per (endpoint, role) combination
  - [ ] Verify staff cannot view restricted fields (cost_price, net_profit)

### Coverage Targets

- [ ] Overall: > 80%
- [ ] Sales module: > 85%
- [ ] Inventory module: > 85%
- [ ] Payments module: > 80%
- [ ] Accounts module: > 80%
- [ ] Workspaces module: > 75%
- [ ] Expenses module: > 75%
- [ ] Customers module: > 75%

---

## Deployment

### Environment Variables

- [ ] Define all required variables:
  - [ ] `SECRET_KEY` — Django secret key
  - [ ] `DEBUG` — set to `False` in production
  - [ ] `DATABASE_URL` — PostgreSQL connection string
  - [ ] `ALLOWED_HOSTS` — comma-separated hostnames
  - [ ] `CORS_ALLOWED_ORIGINS` — comma-separated origins
  - [ ] `JWT_SIGNING_KEY` — (optional, defaults to SECRET_KEY)
  - [ ] `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` — for password reset

- [ ] Create `.env.example` with all variables documented
- [ ] Never commit `.env` to version control

### Production Settings (`config/settings.py`)

- [ ] `DEBUG = False` check
- [ ] `ALLOWED_HOSTS` read from environment
- [ ] Database configured for PostgreSQL via `DATABASE_URL`
- [ ] Static files configured with `STATIC_ROOT` and `STATIC_URL`
- [ ] `SECURE_SSL_REDIRECT = True` (if behind HTTPS)
- [ ] `SESSION_COOKIE_SECURE = True`
- [ ] `CSRF_COOKIE_SECURE = True`
- [ ] `SECURE_HSTS_SECONDS = 31536000` (optional, once HTTPS is verified)
- [ ] Logging configured to stdout for containerized deployment

### Static Files

- [ ] `python manage.py collectstatic` — verify it works
- [ ] Serve static files via whitenoise or CDN

### Docker

- [ ] **`Dockerfile`:**
  - [ ] Python 3.12+ base image
  - [ ] Install system dependencies (libpq-dev)
  - [ ] Install Python dependencies
  - [ ] Copy project files
  - [ ] Collect static files
  - [ ] Run Gunicorn with 4 workers

- [ ] **`docker-compose.yml`:**
  - [ ] `web` service — Django + Gunicorn
  - [ ] `db` service — PostgreSQL 16
  - [ ] Environment variables for both services
  - [ ] Volume for database persistence

- [ ] **`.dockerignore`:**
  - [ ] Exclude `venv/`, `.git/`, `node_modules/`, `.env`, `__pycache__/`, `*.pyc`

### Health Checks

- [ ] `GET /health/` endpoint:
  - [ ] Returns 200 with `{"status": "healthy", "database": "connected"}`
  - [ ] Verifies database connectivity with a simple query
  - [ ] Does not require authentication

### Deployment Platform

- [ ] Deploy to free-tier cloud hosting:
  - [ ] Render (Python + PostgreSQL)
  - [ ] Railway (Python + PostgreSQL)
  - [ ] Fly.io (Python + PostgreSQL)
- [ ] Verify all endpoints work on deployed instance
- [ ] Verify CORS headers are correct
- [ ] Test registration flow on production

---

## Definition of Done

MerchantHub MVP is considered **complete** for the DevCareer × Nomba Hackathon when **all** of the following criteria are met:

### Core Functionality

- [ ] A new user can register, and the system automatically creates a workspace with owner membership
- [ ] User can log in and receive JWT tokens (access + refresh)
- [ ] User can create products with SKU, price, and stock quantity
- [ ] User can create customers with name and contact information
- [ ] User can record a sale with multiple items — inventory is deducted atomically
- [ ] Insufficient stock returns a clear 409 error and does not create the sale
- [ ] User can record a payment against a sale — sale status updates correctly (partial/complete)
- [ ] Over-payment is rejected with a clear 409 error
- [ ] User can record expenses with category and description
- [ ] Dashboard displays: today's revenue, sales count, expenses, net profit, low-stock count, and recent activity
- [ ] All data is scoped to the user's current workspace — switching workspaces shows different data
- [ ] Staff users cannot see cost_price on products or net_profit on dashboard
- [ ] Workspace owners can invite/remove members and change roles
- [ ] The last owner of a workspace cannot be removed or demoted

### Architecture & Quality

- [ ] All 16 database tables from the schema exist and match the design
- [ ] All entities use UUID primary keys
- [ ] Soft delete is implemented with `deleted_at` timestamp (not boolean flag)
- [ ] Sale creation is wrapped in an atomic transaction with `select_for_update()` on Product rows
- [ ] Payment recording locks the Sale row to prevent over-payment
- [ ] Inventory movements are append-only and immutable
- [ ] Audit logs capture significant state changes
- [ ] All errors return consistent JSON format: `{error, code, details}`
- [ ] OpenAPI schema generates without warnings
- [ ] `accounts` delegates workspace creation to `workspaces.WorkspaceService.create_default_workspace()`
- [ ] Circular imports between `inventory` and `sales` are prevented via lazy string FK references
- [ ] `SaleService.create_sale()` does not handle payments — they are recorded separately via `PaymentService.record_payment()`

### Testing

- [ ] Test suite passes with zero failures
- [ ] Code coverage > 80% for core modules (sales, inventory, payments)
- [ ] All 7 required test areas have coverage:
  - [ ] Auth (registration, login, token refresh)
  - [ ] Workspace (CRUD, membership, last-owner protection)
  - [ ] Inventory (CRUD, SKU uniqueness, stock adjustment)
  - [ ] Sales (atomic creation, stock deduction, insufficient stock)
  - [ ] Payments (status updates, over-payment prevention, split payments)
  - [ ] Expenses (CRUD, category validation)
  - [ ] Permissions (staff/manager/owner enforcement, field restrictions)

### Documentation

- [ ] README with: project overview, setup instructions, architecture diagram, environment variables
- [ ] API documentation available via Swagger UI at `/api/docs/`
- [ ] Seed data management command (`python manage.py seed_demo_data`)
- [ ] Postman collection or curl examples for each API endpoint
- [ ] Demo script covering all three user journeys (from PRD)

### Deployment

- [ ] Application is deployed to a public URL
- [ ] Health check endpoint returns 200
- [ ] Registration flow works on production
- [ ] No hardcoded secrets in version control
- [ ] `.env.example` documents all required environment variables
- [ ] `DEBUG=False` in production configuration

### Security

- [ ] All API endpoints (except register/login) require JWT authentication
- [ ] Workspace isolation verified — User A cannot access User B's data
- [ ] Staff users cannot access owner-only endpoints
- [ ] Input validation on all create/update endpoints
- [ ] Passwords are hashed (Django PBKDF2 default)
- [ ] No SQL injection vectors (Django ORM used throughout)
- [ ] No sensitive data in audit logs (passwords, tokens)

### Hackathon Readiness

- [ ] Demo data can be loaded with a single command
- [ ] Zero failing tests
- [ ] No TODOs or debug code remaining in source files
- [ ] Consistent code style across all modules
- [ ] Demo walkthrough covers:
  - [ ] User registration → workspace creation
  - [ ] Product creation → customer creation
  - [ ] Sale recording → inventory deduction
  - [ ] Payment recording → status update
  - [ ] Expense logging
  - [ ] Dashboard KPIs
  - [ ] Permission enforcement (staff vs owner viewer)

---

*This checklist is derived from the MerchantHub architecture documents (PRD, Domain Model, Database Schema, Database Decisions, Relationships, Backend Implementation Blueprint). It should be updated as implementation progresses and new tasks are discovered.*
