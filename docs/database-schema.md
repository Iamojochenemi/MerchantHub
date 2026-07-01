# MerchantHub — Database Schema

**Version:** 1.0  
**Status:** Draft  
**Last Updated:** July 1, 2026  
**Phase:** 1 (Foundation & Database Design)

---

## Table of Contents

1. [Naming Conventions](#1-naming-conventions)
2. [Base Tables](#2-base-tables)
3. [Entity Schemas](#3-entity-schemas)
4. [Business Rules as Constraints](#4-business-rules-as-constraints)
5. [Transaction Boundaries](#5-transaction-boundaries)
6. [Database Creation Order](#6-database-creation-order)

---

## 1. Naming Conventions

### Table Names
- **Django convention (app_label + model_name, snake_case, plural):** `accounts_user`, `workspaces_workspace`, `workspaces_workspacemembership`, `inventory_product`, `sales_sale`, `sales_saleitem`, `payments_payment`, `expenses_expense`
- **Join tables:** `workspaces_role_permissions`
- **Cross-cutting:** `common_notification`, `common_auditlog`

### Column Names
- **Snake case:** `unit_price`, `current_stock`, `deleted_at`
- **Foreign keys:** `workspace_id`, `product_id`, `sale_id`
- **Boolean flags:** `is_active`, `is_merchant`, `is_read`
- **Timestamps:** `created_at`, `updated_at`, `deleted_at`
- **Enum-like statuses:** `status` (with CHECK constraints or application-level enum)
- **Primary keys:** `id` (UUID in all cases)

### Index Names
- Format: `idx_{table}_{column(s)}_{purpose}`
- Examples: `idx_products_workspace_id`, `idx_products_sku_workspace`, `idx_sales_workspace_date`

### Foreign Key Names
- Format: `fk_{child_table}_{parent_table}`
- Examples: `fk_sale_items_sale`, `fk_inventory_movements_product`

### Unique Constraint Names
- Format: `uq_{table}_{columns}`
- Examples: `uq_products_sku_workspace`, `uq_categories_name_workspace`

---

## 2. Base Tables

The following abstract base structures are inherited by concrete tables. They are not materialized as standalone tables.

### BaseModel (Abstract)

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | UUID (v4) | NOT NULL | `gen_random_uuid()` | Primary key. Universal across all entities. |
| `created_at` | TIMESTAMPTZ | NOT NULL | `NOW()` | Set on creation, never updated. |
| `updated_at` | TIMESTAMPTZ | NOT NULL | `NOW()` | Updated on every row modification. |

### SoftDeleteModel (Abstract)

Extends BaseModel:

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `deleted_at` | TIMESTAMPTZ | NULL | `NULL` | Non-NULL indicates a soft-deleted record. |

### WorkspaceScopedModel (Abstract)

Extends SoftDeleteModel (or BaseModel for non-soft-deletable entities):

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `workspace_id` | UUID | NOT NULL | — | Foreign key to `workspaces.id`. |

---

## 3. Entity Schemas

---

### 3.1 accounts_user

**Table:** `accounts_user`  
**Extends:** Django's `AbstractUser` (has its own auto-increment PK by default, but we use UUID override)  
**Soft-deletable:** Yes  
**Module:** accounts

#### Fields

| Column | Type | Nullable | Default | Constraints | Notes |
|---|---|---|---|---|---|
| `id` | UUID (v4) | NOT NULL | `gen_random_uuid()` | PK | Override Django's default integer PK. |
| `password` | VARCHAR(128) | NOT NULL | — | | Hashed password (Django PBKDF2). |
| `last_login` | TIMESTAMPTZ | YES | NULL | | |
| `is_superuser` | BOOLEAN | NOT NULL | `false` | | Django admin superuser flag. |
| `username` | VARCHAR(150) | NOT NULL | — | UNIQUE | Django default. |
| `first_name` | VARCHAR(150) | NOT NULL | `''` | | |
| `last_name` | VARCHAR(150) | NOT NULL | `''` | | |
| `email` | VARCHAR(254) | NOT NULL | — | UNIQUE | Business email (must be unique). |
| `phone_number` | VARCHAR(20) | YES | NULL | | E.164 format recommended. |
| `is_staff` | BOOLEAN | NOT NULL | `false` | | Django admin access flag. |
| `is_active` | BOOLEAN | NOT NULL | `true` | | Soft-delete flag. |
| `is_merchant` | BOOLEAN | NOT NULL | `true` | | Registered as merchant vs super-admin. |
| `date_joined` | TIMESTAMPTZ | NOT NULL | `NOW()` | | |

**Note:** Django's `AbstractUser` also includes `groups` and `user_permissions` M2M tables. These are inherited and used for Django admin only, not for workspace-level authorization.

#### Indexes

| Index | Columns | Purpose |
|---|---|---|
| `idx_accounts_user_email` | `email` | Lookup by email (login). |
| `idx_accounts_user_username` | `username` | Lookup by username. |

---

### 3.2 workspaces_workspace

**Table:** `workspaces_workspace`  
**Extends:** BaseModel + SoftDeleteModel  
**Soft-deletable:** Yes (30-day grace period)  
**Module:** workspaces

#### Fields

| Column | Type | Nullable | Default | Constraints | Notes |
|---|---|---|---|---|---|
| `id` | UUID (v4) | NOT NULL | `gen_random_uuid()` | PK | |
| `name` | VARCHAR(255) | NOT NULL | — | UNIQUE | Business name — must be unique across platform for now. |
| `slug` | VARCHAR(100) | NOT NULL | — | UNIQUE | URL-friendly identifier. |
| `owner_id` | UUID | NOT NULL | — | FK → `accounts_user.id` | The user who created the workspace. |
| `is_active` | BOOLEAN | NOT NULL | `true` | | |
| `created_at` | TIMESTAMPTZ | NOT NULL | `NOW()` | | |
| `updated_at` | TIMESTAMPTZ | NOT NULL | `NOW()` | | |
| `deleted_at` | TIMESTAMPTZ | YES | NULL | | |

#### Indexes

| Index | Columns | Purpose |
|---|---|---|
| `idx_workspaces_owner` | `owner_id` | Find workspaces owned by a user. |
| `idx_workspaces_slug` | `slug` | URL-based lookup. |

---

### 3.3 workspaces_workspacemembership

**Table:** `workspaces_workspacemembership`  
**Extends:** BaseModel  
**Soft-deletable:** No (hard delete on revocation)  
**Module:** workspaces

#### Fields

| Column | Type | Nullable | Default | Constraints | Notes |
|---|---|---|---|---|---|
| `id` | UUID (v4) | NOT NULL | `gen_random_uuid()` | PK | |
| `workspace_id` | UUID | NOT NULL | — | FK → `workspaces_workspace.id` (CASCADE) | |
| `user_id` | UUID | NOT NULL | — | FK → `accounts_user.id` (CASCADE) | |
| `role` | VARCHAR(20) | NOT NULL | `'staff'` | CHECK (role IN ('owner', 'manager', 'staff')) | Enum-like constraint. |
| `created_at` | TIMESTAMPTZ | NOT NULL | `NOW()` | | |
| `updated_at` | TIMESTAMPTZ | NOT NULL | `NOW()` | | |

#### Unique Constraints

| Constraint | Columns | Notes |
|---|---|---|
| `uq_membership_workspace_user` | `(workspace_id, user_id)` | One membership per user per workspace. |

#### Indexes

| Index | Columns | Purpose |
|---|---|---|
| `idx_membership_user` | `user_id` | Find all workspaces a user belongs to. |
| `idx_membership_workspace` | `workspace_id` | Find all members of a workspace. |

---

### 3.4 workspaces_businessprofile

**Table:** `workspaces_businessprofile`  
**Extends:** BaseModel  
**Soft-deletable:** No (CASCADE with workspace)  
**Module:** workspaces

#### Fields

| Column | Type | Nullable | Default | Constraints | Notes |
|---|---|---|---|---|---|
| `id` | UUID (v4) | NOT NULL | `gen_random_uuid()` | PK | |
| `workspace_id` | UUID | NOT NULL | — | FK → `workspaces_workspace.id` (CASCADE, UNIQUE) | One-to-one with workspace. |
| `legal_name` | VARCHAR(255) | YES | NULL | | Registered business name (if different). |
| `tax_id` | VARCHAR(50) | YES | NULL | | VAT/EIN/Tax registration number. |
| `address_line1` | VARCHAR(255) | YES | NULL | | |
| `address_line2` | VARCHAR(255) | YES | NULL | | |
| `city` | VARCHAR(100) | YES | NULL | | |
| `state` | VARCHAR(100) | YES | NULL | | |
| `postal_code` | VARCHAR(20) | YES | NULL | | |
| `country` | VARCHAR(100) | YES | NULL | | |
| `currency` | VARCHAR(3) | NOT NULL | `'USD'` | CHECK (currency IN known ISO codes) | ISO 4217 — MVP default: USD. |
| `timezone` | VARCHAR(50) | NOT NULL | `'UTC'` | | IANA timezone database identifier. |
| `logo_url` | VARCHAR(500) | YES | NULL | | URL to uploaded logo (future). |
| `created_at` | TIMESTAMPTZ | NOT NULL | `NOW()` | | |
| `updated_at` | TIMESTAMPTZ | NOT NULL | `NOW()` | | |

#### Unique Constraints

| Constraint | Columns | Notes |
|---|---|---|
| `uq_businessprofile_workspace` | `workspace_id` | One profile per workspace. |

---

### 3.5 workspaces_role

**Table:** `workspaces_role`  
**Extends:** BaseModel  
**Soft-deletable:** No (seeded, system-defined)  
**Module:** workspaces

#### Fields

| Column | Type | Nullable | Default | Constraints | Notes |
|---|---|---|---|---|---|
| `id` | UUID (v4) | NOT NULL | `gen_random_uuid()` | PK | |
| `name` | VARCHAR(50) | NOT NULL | — | UNIQUE | `owner`, `manager`, `staff`. |
| `level` | INTEGER | NOT NULL | — | CHECK (level >= 0) | Hierarchical rank: 100=owner, 50=manager, 10=staff. |
| `description` | TEXT | YES | NULL | | |
| `created_at` | TIMESTAMPTZ | NOT NULL | `NOW()` | | |
| `updated_at` | TIMESTAMPTZ | NOT NULL | `NOW()` | | |

**Seeded data:**
| name | level | description |
|---|---|---|
| `owner` | 100 | Full workspace access, can manage billing and members. |
| `manager` | 50 | Can manage all business data, view reports. Cannot manage billing or members. |
| `staff` | 10 | Can record sales and view products/customers. Limited access. |

---

### 3.6 workspaces_permission

**Table:** `workspaces_permission`  
**Extends:** BaseModel  
**Soft-deletable:** No (seeded, system-defined)  
**Module:** workspaces

#### Fields

| Column | Type | Nullable | Default | Constraints | Notes |
|---|---|---|---|---|---|
| `id` | UUID (v4) | NOT NULL | `gen_random_uuid()` | PK | |
| `codename` | VARCHAR(100) | NOT NULL | — | UNIQUE | e.g., `product.create`, `sale.read`. |
| `description` | TEXT | YES | NULL | | |
| `created_at` | TIMESTAMPTZ | NOT NULL | `NOW()` | | |
| `updated_at` | TIMESTAMPTZ | NOT NULL | `NOW()` | | |

**Join table:** `workspaces_role_permissions`

| Column | Type | Nullable | Constraints | Notes |
|---|---|---|---|---|
| `role_id` | UUID | NOT NULL | FK → `workspaces_role.id` (CASCADE) | |
| `permission_id` | UUID | NOT NULL | FK → `workspaces_permission.id` (CASCADE) | |

**Primary key:** `(role_id, permission_id)`

---

### 3.7 inventory_category

**Table:** `inventory_category`  
**Extends:** BaseModel + WorkspaceScopedModel + SoftDeleteModel  
**Soft-deletable:** Yes  
**Module:** inventory

#### Fields

| Column | Type | Nullable | Default | Constraints | Notes |
|---|---|---|---|---|---|
| `id` | UUID (v4) | NOT NULL | `gen_random_uuid()` | PK | |
| `workspace_id` | UUID | NOT NULL | — | FK → `workspaces_workspace.id` (CASCADE) | |
| `name` | VARCHAR(100) | NOT NULL | — | | Display name, e.g., "Clothing". |
| `description` | TEXT | YES | NULL | | |
| `created_at` | TIMESTAMPTZ | NOT NULL | `NOW()` | | |
| `updated_at` | TIMESTAMPTZ | NOT NULL | `NOW()` | | |
| `deleted_at` | TIMESTAMPTZ | YES | NULL | | |

#### Unique Constraints

| Constraint | Columns | Notes |
|---|---|---|
| `uq_categories_name_workspace` | `(workspace_id, name)` | Category name must be unique within a workspace. |

#### Indexes

| Index | Columns | Purpose |
|---|---|---|
| `idx_categories_workspace` | `workspace_id` | List categories for a workspace. |

---

### 3.8 inventory_product

**Table:** `inventory_product`  
**Extends:** BaseModel + WorkspaceScopedModel + SoftDeleteModel  
**Soft-deletable:** Yes  
**Module:** inventory

#### Fields

| Column | Type | Nullable | Default | Constraints | Notes |
|---|---|---|---|---|---|
| `id` | UUID (v4) | NOT NULL | `gen_random_uuid()` | PK | |
| `workspace_id` | UUID | NOT NULL | — | FK → `workspaces_workspace.id` (CASCADE) | |
| `category_id` | UUID | YES | NULL | FK → `inventory_category.id` (SET NULL on delete) | Null = uncategorized. |
| `name` | VARCHAR(255) | NOT NULL | — | | Product name/title. |
| `sku` | VARCHAR(100) | YES | NULL | | Stock-keeping unit code. |
| `description` | TEXT | YES | NULL | | |
| `unit_price` | DECIMAL(12, 2) | NOT NULL | — | CHECK (unit_price >= 0) | Selling price. |
| `cost_price` | DECIMAL(12, 2) | YES | NULL | CHECK (cost_price >= 0) | Null = unknown cost. |
| `current_stock` | DECIMAL(12, 3) | NOT NULL | `0` | CHECK (current_stock >= 0) | Materialized stock count. |
| `low_stock_threshold` | DECIMAL(12, 3) | YES | NULL | CHECK (low_stock_threshold >= 0) | Null = no alert. |
| `is_active` | BOOLEAN | NOT NULL | `true` | | For soft-disable (hide from new sales). |
| `created_at` | TIMESTAMPTZ | NOT NULL | `NOW()` | | |
| `updated_at` | TIMESTAMPTZ | NOT NULL | `NOW()` | | |
| `deleted_at` | TIMESTAMPTZ | YES | NULL | | |

#### Unique Constraints

| Constraint | Columns | Notes |
|---|---|---|
| `uq_products_sku_workspace` | `(workspace_id, sku)` | SKU is unique within a workspace (only when SKU is provided). PostgreSQL partial index recommended: `CREATE UNIQUE INDEX ... WHERE sku IS NOT NULL AND deleted_at IS NULL` |

#### Indexes

| Index | Columns | Purpose |
|---|---|---|
| `idx_products_workspace` | `workspace_id` | List products for a workspace. |
| `idx_products_category` | `category_id` | Filter products by category. |
| `idx_products_sku_workspace` | `(workspace_id, sku)` | SKU lookup (partial, non-null SKU). |
| `idx_products_name_workspace` | `(workspace_id, name)` | Text search by product name. |
| `idx_products_low_stock` | `(workspace_id, current_stock, low_stock_threshold)` | Find products needing restock. Filter: `current_stock <= low_stock_threshold AND low_stock_threshold IS NOT NULL`. |

#### Check Constraints

| Name | Condition | Purpose |
|---|---|---|
| `chk_products_price_non_negative` | `unit_price >= 0` | Price cannot be negative. |
| `chk_products_cost_non_negative` | `cost_price >= 0` | Cost cannot be negative. |
| `chk_products_stock_non_negative` | `current_stock >= 0` | Stock cannot go negative. |

---

### 3.9 inventory_inventorymovement

**Table:** `inventory_inventorymovement`  
**Extends:** BaseModel  
**Soft-deletable:** No (immutable)  
**Module:** inventory

#### Fields

| Column | Type | Nullable | Default | Constraints | Notes |
|---|---|---|---|---|---|
| `id` | UUID (v4) | NOT NULL | `gen_random_uuid()` | PK | |
| `product_id` | UUID | NOT NULL | — | FK → `inventory_product.id` (PROTECT) | The product being moved. |
| `sale_id` | UUID | YES | NULL | FK → `sales_sale.id` (SET NULL) | Link to sale if type='sale' or 'return'. |
| `movement_type` | VARCHAR(20) | NOT NULL | — | CHECK (movement_type IN ('initial', 'sale', 'return', 'adjustment', 'transfer_out', 'transfer_in')) | |
| `quantity` | DECIMAL(12, 3) | NOT NULL | — | CHECK (quantity > 0) | Always positive. Direction encoded in type. |
| `running_balance` | DECIMAL(12, 3) | NOT NULL | — | | Snapshot of product's stock after this movement. Useful for audit. |
| `reason` | TEXT | YES | NULL | | Free-text reason for manual adjustments. |
| `created_at` | TIMESTAMPTZ | NOT NULL | `NOW()` | | |

#### Indexes

| Index | Columns | Purpose |
|---|---|---|
| `idx_movements_product` | `product_id` | Find all movements for a product. |
| `idx_movements_product_date` | `(product_id, created_at)` | Chronological movement history. |
| `idx_movements_sale` | `sale_id` | Find movements linked to a specific sale. |

#### Check Constraints

| Name | Condition | Purpose |
|---|---|---|
| `chk_movements_quantity_positive` | `quantity > 0` | Quantity must always be positive. |

---

### 3.10 customers_customer

**Table:** `customers_customer`  
**Extends:** BaseModel + WorkspaceScopedModel + SoftDeleteModel  
**Soft-deletable:** Yes  
**Module:** customers

#### Fields

| Column | Type | Nullable | Default | Constraints | Notes |
|---|---|---|---|---|---|
| `id` | UUID (v4) | NOT NULL | `gen_random_uuid()` | PK | |
| `workspace_id` | UUID | NOT NULL | — | FK → `workspaces_workspace.id` (CASCADE) | |
| `name` | VARCHAR(255) | NOT NULL | — | | Customer's full name or business name. |
| `email` | VARCHAR(254) | YES | NULL | | Personal email. |
| `phone` | VARCHAR(20) | YES | NULL | | Phone number in E.164 format recommended. |
| `notes` | TEXT | YES | NULL | | Free-text notes about the customer. |
| `total_visits` | INTEGER | NOT NULL | `0` | CHECK (total_visits >= 0) | Computed/denormalized from sales count. |
| `total_spend` | DECIMAL(14, 2) | NOT NULL | `0.00` | CHECK (total_spend >= 0) | Computed/denormalized from sale totals. |
| `last_visit_date` | DATE | YES | NULL | | Computed/denormalized from latest sale date. |
| `created_at` | TIMESTAMPTZ | NOT NULL | `NOW()` | | |
| `updated_at` | TIMESTAMPTZ | NOT NULL | `NOW()` | | |
| `deleted_at` | TIMESTAMPTZ | YES | NULL | | |

#### Check Constraints

| Name | Condition | Purpose |
|---|---|---|
| `chk_customers_contact_required` | `email IS NOT NULL OR phone IS NOT NULL` | At least one contact method is required. This is enforced at the application layer; the DB constraint is optional if application enforcement is deemed sufficient. |

#### Indexes

| Index | Columns | Purpose |
|---|---|---|
| `idx_customers_workspace` | `workspace_id` | List customers for a workspace. |
| `idx_customers_name_workspace` | `(workspace_id, name)` | Search by name. |
| `idx_customers_phone_workspace` | `(workspace_id, phone)` | Search by phone. |
| `idx_customers_email_workspace` | `(workspace_id, email)` | Search by email. |
| `idx_customers_last_visit` | `(workspace_id, last_visit_date)` | Find inactive customers for re-engagement. |

---

### 3.11 sales_sale

**Table:** `sales_sale`  
**Extends:** BaseModel + WorkspaceScopedModel + SoftDeleteModel  
**Soft-deletable:** Yes (status-based, never hard-deleted)  
**Module:** sales

#### Fields

| Column | Type | Nullable | Default | Constraints | Notes |
|---|---|---|---|---|---|
| `id` | UUID (v4) | NOT NULL | `gen_random_uuid()` | PK | |
| `workspace_id` | UUID | NOT NULL | — | FK → `workspaces_workspace.id` (CASCADE) | |
| `customer_id` | UUID | YES | NULL | FK → `customers_customer.id` (SET NULL) | Null for walk-in sales with no profile. |
| `recorded_by_id` | UUID | NOT NULL | — | FK → `accounts_user.id` (PROTECT) | Staff who recorded the sale. |
| `status` | VARCHAR(20) | NOT NULL | `'pending'` | CHECK (status IN ('pending', 'completed', 'partially_paid', 'refunded', 'cancelled')) | |
| `total_amount` | DECIMAL(14, 2) | NOT NULL | — | CHECK (total_amount >= 0) | Computed sum of all SaleItems. |
| `paid_amount` | DECIMAL(14, 2) | NOT NULL | `0.00` | CHECK (paid_amount >= 0) | Sum of linked payments. Denormalized for performance. |
| `discount_amount` | DECIMAL(12, 2) | NOT NULL | `0.00` | CHECK (discount_amount >= 0) | Optional discount applied at sale level. |
| `notes` | TEXT | YES | NULL | | |
| `created_at` | TIMESTAMPTZ | NOT NULL | `NOW()` | | |
| `updated_at` | TIMESTAMPTZ | NOT NULL | `NOW()` | | |
| `deleted_at` | TIMESTAMPTZ | YES | NULL | | |

#### Check Constraints

| Name | Condition | Purpose |
|---|---|---|
| `chk_sales_total_non_negative` | `total_amount >= 0` | Sale total cannot be negative. |
| `chk_sales_paid_non_negative` | `paid_amount >= 0` | Paid amount cannot be negative. |
| `chk_sales_paid_not_exceed_total` | `paid_amount <= total_amount` | Cannot pay more than the sale total. |

#### Indexes

| Index | Columns | Purpose |
|---|---|---|
| `idx_sales_workspace` | `workspace_id` | List sales for a workspace. |
| `idx_sales_workspace_date` | `(workspace_id, created_at)` | Chronological sale listing (dashboard). |
| `idx_sales_customer` | `customer_id` | Find all sales by a customer. |
| `idx_sales_status` | `(workspace_id, status)` | Filter by payment status. |
| `idx_sales_recorded_by` | `recorded_by_id` | Sales recorded by a specific staff member. |

---

### 3.12 sales_saleitem

**Table:** `sales_saleitem`  
**Extends:** BaseModel  
**Soft-deletable:** No (CASCADE with Sale)  
**Module:** sales

#### Fields

| Column | Type | Nullable | Default | Constraints | Notes |
|---|---|---|---|---|---|
| `id` | UUID (v4) | NOT NULL | `gen_random_uuid()` | PK | |
| `sale_id` | UUID | NOT NULL | — | FK → `sales_sale.id` (CASCADE) | Parent sale. |
| `product_id` | UUID | NOT NULL | — | FK → `inventory_product.id` (PROTECT) | The product sold. |
| `quantity` | DECIMAL(12, 3) | NOT NULL | — | CHECK (quantity > 0) | Quantity sold. |
| `unit_price` | DECIMAL(12, 2) | NOT NULL | — | CHECK (unit_price >= 0) | Snapshot of price at sale time. |
| `line_total` | DECIMAL(14, 2) | NOT NULL | — | CHECK (line_total >= 0) | Computed: `quantity * unit_price`. |

#### Check Constraints

| Name | Condition | Purpose |
|---|---|---|
| `chk_saleitems_quantity_positive` | `quantity > 0` | Quantity must be positive. |
| `chk_saleitems_unit_price_non_negative` | `unit_price >= 0` | Unit price cannot be negative. |
| `chk_saleitems_line_total` | `line_total = quantity * unit_price` | Line total must equal quantity × unit price. |

#### Indexes

| Index | Columns | Purpose |
|---|---|---|
| `idx_saleitems_sale` | `sale_id` | Find all items in a sale. |
| `idx_saleitems_product` | `product_id` | Find all sales containing a specific product. |

---

### 3.13 payments_payment

**Table:** `payments_payment`  
**Extends:** BaseModel + WorkspaceScopedModel + SoftDeleteModel  
**Soft-deletable:** Yes  
**Module:** payments

#### Fields

| Column | Type | Nullable | Default | Constraints | Notes |
|---|---|---|---|---|---|
| `id` | UUID (v4) | NOT NULL | `gen_random_uuid()` | PK | |
| `workspace_id` | UUID | NOT NULL | — | FK → `workspaces_workspace.id` (CASCADE) | |
| `sale_id` | UUID | NOT NULL | — | FK → `sales_sale.id` (PROTECT) | Payment must reference a sale in MVP. |
| `customer_id` | UUID | YES | NULL | FK → `customers_customer.id` (SET NULL) | Optional denormalized reference for customer lookup. |
| `amount` | DECIMAL(14, 2) | NOT NULL | — | CHECK (amount > 0) | Payment amount. |
| `method` | VARCHAR(20) | NOT NULL | — | CHECK (method IN ('cash', 'card', 'bank_transfer')) | Payment method. |
| `reference` | VARCHAR(100) | YES | NULL | | External reference (card receipt #, transaction ID). |
| `paid_at` | TIMESTAMPTZ | NOT NULL | `NOW()` | | When the payment was received. |
| `created_at` | TIMESTAMPTZ | NOT NULL | `NOW()` | | |
| `updated_at` | TIMESTAMPTZ | NOT NULL | `NOW()` | | |
| `deleted_at` | TIMESTAMPTZ | YES | NULL | | |

#### Unique Constraints

| Constraint | Columns | Notes |
|---|---|---|
| `uq_payments_reference_workspace` | `(workspace_id, reference)` | Payment reference must be unique within a workspace (prevents duplicate reconciliation). Only applies when `reference` is provided. |

#### Check Constraints

| Name | Condition | Purpose |
|---|---|---|
| `chk_payments_amount_positive` | `amount > 0` | Payment must have a positive amount. |

#### Indexes

| Index | Columns | Purpose |
|---|---|---|
| `idx_payments_sale` | `sale_id` | Find all payments for a sale. |
| `idx_payments_workspace` | `workspace_id` | List payments for a workspace. |
| `idx_payments_customer` | `customer_id` | Payment history by customer. |
| `idx_payments_paid_at` | `(workspace_id, paid_at)` | Payments by date range. |

---

### 3.14 expenses_expense

**Table:** `expenses_expense`  
**Extends:** BaseModel + WorkspaceScopedModel + SoftDeleteModel  
**Soft-deletable:** Yes  
**Module:** expenses

#### Fields

| Column | Type | Nullable | Default | Constraints | Notes |
|---|---|---|---|---|---|
| `id` | UUID (v4) | NOT NULL | `gen_random_uuid()` | PK | |
| `workspace_id` | UUID | NOT NULL | — | FK → `workspaces_workspace.id` (CASCADE) | |
| `category` | VARCHAR(30) | NOT NULL | — | CHECK (category IN ('cost_of_goods_sold', 'rent', 'utilities', 'salaries', 'marketing', 'maintenance', 'other')) | Predefined expense categories. |
| `amount` | DECIMAL(14, 2) | NOT NULL | — | CHECK (amount > 0) | Expense amount. |
| `description` | TEXT | NOT NULL | — | | Required description for audit. |
| `expense_date` | DATE | NOT NULL | `CURRENT_DATE` | | When the expense occurred. |
| `receipt_url` | VARCHAR(500) | YES | NULL | | Link to uploaded receipt file (future scope). |
| `created_at` | TIMESTAMPTZ | NOT NULL | `NOW()` | | |
| `updated_at` | TIMESTAMPTZ | NOT NULL | `NOW()` | | |
| `deleted_at` | TIMESTAMPTZ | YES | NULL | | |

#### Check Constraints

| Name | Condition | Purpose |
|---|---|---|
| `chk_expenses_amount_positive` | `amount > 0` | Expense must have a positive amount. |

#### Indexes

| Index | Columns | Purpose |
|---|---|---|
| `idx_expenses_workspace` | `workspace_id` | List expenses for a workspace. |
| `idx_expenses_workspace_date` | `(workspace_id, expense_date)` | Expenses by date range. |
| `idx_expenses_category` | `(workspace_id, category)` | Filter expenses by category. |

---

### 3.15 common_notification

**Table:** `common_notification`  
**Extends:** BaseModel  
**Soft-deletable:** No (hard delete after TTL)  
**Module:** common

#### Fields

| Column | Type | Nullable | Default | Constraints | Notes |
|---|---|---|---|---|---|
| `id` | UUID (v4) | NOT NULL | `gen_random_uuid()` | PK | |
| `user_id` | UUID | NOT NULL | — | FK → `accounts_user.id` (CASCADE) | Recipient. |
| `workspace_id` | UUID | YES | NULL | FK → `workspaces_workspace.id` (SET NULL) | Optional workspace context. |
| `notification_type` | VARCHAR(30) | NOT NULL | — | CHECK (notification_type IN ('low_stock_alert', 'sale_completed', 'staff_invite', 'payment_received')) | |
| `title` | VARCHAR(255) | NOT NULL | — | | Short notification title. |
| `message` | TEXT | NOT NULL | — | | Notification body. |
| `is_read` | BOOLEAN | NOT NULL | `false` | | |
| `read_at` | TIMESTAMPTZ | YES | NULL | | When the user read the notification. |
| `expires_at` | TIMESTAMPTZ | YES | NULL | | Auto-delete after this timestamp. |
| `created_at` | TIMESTAMPTZ | NOT NULL | `NOW()` | | |

#### Indexes

| Index | Columns | Purpose |
|---|---|---|
| `idx_notifications_user` | `user_id` | Fetch notifications for a user. |
| `idx_notifications_user_unread` | `(user_id, is_read)` | Count unread notifications. |
| `idx_notifications_expires` | `expires_at` | Find expired notifications for cleanup. |

---

### 3.16 common_auditlog

**Table:** `common_auditlog`  
**Extends:** BaseModel  
**Soft-deletable:** No (immutable)  
**Module:** common

#### Fields

| Column | Type | Nullable | Default | Constraints | Notes |
|---|---|---|---|---|---|
| `id` | UUID (v4) | NOT NULL | `gen_random_uuid()` | PK | |
| `workspace_id` | UUID | YES | NULL | FK → `workspaces_workspace.id` (SET NULL) | Null for system-wide actions (auth login/logout). |
| `actor_id` | UUID | NOT NULL | — | FK → `accounts_user.id` (PROTECT) | Who performed the action. |
| `action` | VARCHAR(50) | NOT NULL | — | | e.g., `entity.create.product`, `entity.update.customer`. |
| `target_type` | VARCHAR(50) | YES | NULL | | e.g., `product`, `sale`, `customer`. |
| `target_id` | UUID | YES | NULL | | The ID of the affected entity. |
| `changes` | JSONB | YES | NULL | | `{"before": {...}, "after": {...}}` |
| `metadata` | JSONB | YES | NULL | | `{"ip_address": "...", "user_agent": "...", "correlation_id": "..."}` |
| `created_at` | TIMESTAMPTZ | NOT NULL | `NOW()` | | |

#### Indexes

| Index | Columns | Purpose |
|---|---|---|
| `idx_auditlog_workspace` | `workspace_id` | Find all audit log entries for a workspace. |
| `idx_auditlog_actor` | `actor_id` | Find actions by a specific user. |
| `idx_auditlog_target` | `(target_type, target_id)` | Find all changes to a specific entity. |
| `idx_auditlog_action` | `action` | Filter by action type. |
| `idx_auditlog_created` | `created_at` | Chronological audit trail. |

---

## 4. Business Rules as Constraints

| Rule | Enforcement | Where |
|---|---|---|
| Product SKU unique within workspace | UNIQUE partial index: `(workspace_id, sku) WHERE sku IS NOT NULL AND deleted_at IS NULL` | DB constraint |
| Category name unique within workspace | UNIQUE: `(workspace_id, name)` | DB constraint |
| Stock cannot be negative | CHECK: `current_stock >= 0` | DB constraint; also enforced before sale creation in app layer |
| Sale total = sum of SaleItems | CHECK: not feasible in pure SQL (aggregate in CHECK); enforce in application layer | Application layer |
| SaleItem quantity > 0 | CHECK: `quantity > 0` | DB constraint |
| Product unit_price >= 0 | CHECK: `unit_price >= 0` | DB constraint |
| Product cost_price >= 0 | CHECK: `cost_price >= 0` | DB constraint |
| Payment amount > 0 | CHECK: `amount > 0` | DB constraint |
| Payment sum cannot exceed sale total | Application layer (read sale total and existing payments before accepting new payment) | Application layer |
| Customer requires at least one contact method | Application layer (optional DB CHECK) | Application layer |
| Email unique across users | UNIQUE on `accounts_user.email` | DB constraint |
| One membership per user per workspace | UNIQUE: `(workspace_id, user_id)` | DB constraint |
| Workspace must have at least one owner | Application layer (on membership removal/role change) | Application layer |
| InventoryMovements are immutable | No UPDATE/DELETE triggers; app never modifies or deletes them | Application convention |

---

## 5. Transaction Boundaries

### 5.1 Sale Creation

This is the most critical transaction in the system. It spans multiple aggregates:

```
BEGIN TRANSACTION;

1. INSERT INTO sales_sale (...) VALUES (...);
2. For each product in the sale:
   a. INSERT INTO sales_saleitem (sale_id, product_id, quantity, unit_price, line_total) VALUES (...);
   b. UPDATE inventory_product SET current_stock = current_stock - quantity WHERE id = ... AND current_stock >= quantity;
      → If current_stock < quantity, ROLLBACK;
   c. INSERT INTO inventory_inventorymovement (product_id, sale_id, movement_type='sale', quantity=..., running_balance=current_stock - quantity) VALUES (...);
3. If customer_id is provided:
   UPDATE customers_customer SET total_visits = total_visits + 1, total_spend = total_spend + ...,
     last_visit_date = CURRENT_DATE WHERE id = ...;
4. UPDATE sales_sale SET total_amount = computed_sum, paid_amount = ...;

COMMIT;
```

**Failure handling:** If any step fails, the entire transaction rolls back. Stock is never partially deducted.

### 5.2 Stock Adjustment (Manual)

```
BEGIN TRANSACTION;

1. INSERT INTO inventory_inventorymovement (product_id, movement_type='adjustment', quantity=..., reason=...) VALUES (...);
2. UPDATE inventory_product SET current_stock = current_stock ± quantity WHERE id = ...;
   → CHECK constraint ensures current_stock >= 0.

COMMIT;
```

### 5.3 Payment Recording

```
BEGIN TRANSACTION;

1. INSERT INTO payments_payment (sale_id, amount, method, ...) VALUES (...);
2. Application layer validates: SELECT SUM(amount) FROM payments_payment WHERE sale_id = ...; 
   → If new total > sale.total_amount, ROLLBACK;
3. UPDATE sales_sale SET paid_amount = paid_amount + amount WHERE id = ...;
4. If paid_amount >= total_amount, UPDATE sales_sale SET status = 'completed';
   Else if paid_amount > 0, UPDATE sales_sale SET status = 'partially_paid';

COMMIT;
```

### 5.4 Concurrency Considerations

- **Sale creation:** Use `SELECT ... FOR UPDATE` on the Product row before checking stock and deducting. This prevents two concurrent sale requests from both seeing sufficient stock when only one unit remains.
- **Payment recording:** Use `SELECT SUM(amount) FROM payments_payment WHERE sale_id = ... FOR UPDATE` or lock the Sale row to prevent concurrent payments from exceeding the total.
- **Isolation level:** Use `REPEATABLE READ` or `SERIALIZABLE` for sale creation and payment recording to prevent phantom reads. Django's default `READ COMMITTED` is insufficient for stock deduction under concurrent load — explicit locking (`select_for_update()`) is required.

---

## 6. Database Creation Order

The following order respects all foreign key dependencies:

| Order | Table | Depends On | Notes |
|---|---|---|---|
| 1 | `accounts_user` | (none) | Django's AUTH_USER_MODEL |
| 2 | `workspaces_role` | (none) | Seeded reference data |
| 3 | `workspaces_permission` | (none) | Seeded reference data |
| 4 | `workspaces_role_permissions` | role, permission | Join table |
| 5 | `workspaces_workspace` | user | Owner FK |
| 6 | `workspaces_workspacemembership` | workspace, user, role | |
| 7 | `workspaces_businessprofile` | workspace | 1:1 |
| 8 | `inventory_category` | workspace | |
| 9 | `inventory_product` | workspace, category (optional) | |
| 10 | `customers_customer` | workspace | |
| 11 | `sales_sale` | workspace, customer (optional), user | |
| 12 | `sales_saleitem` | sale, product | |
| 13 | `inventory_inventorymovement` | product, sale (optional) | |
| 14 | `payments_payment` | workspace, sale, customer (optional) | |
| 15 | `expenses_expense` | workspace | |
| 16 | `common_notification` | user, workspace (optional) | |
| 17 | `common_auditlog` | workspace (optional), user | |

### Migration Order

1. Initial migration: `accounts` (User model)
2. `workspaces` (Role, Permission, role_permissions join table)
3. `workspaces` (Workspace, WorkspaceMembership, BusinessProfile)
4. `inventory` (Category, Product)
5. `customers` (Customer)
6. `sales` (Sale, SaleItem)
7. `inventory` (InventoryMovement — requires Sale to exist)
8. `payments` (Payment)
9. `expenses` (Expense)
10. `common` (Notification, AuditLog)

---

*This document defines the physical database schema derived from the domain model. It is intended to guide Django model implementation without prescribing ORM-specific syntax.*
