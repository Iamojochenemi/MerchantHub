# MerchantHub — Domain Model

**Version:** 1.0  
**Status:** Draft  
**Last Updated:** July 1, 2026  
**Phase:** 1 (Foundation & Domain Modeling)

---

## Purpose

This document defines every business entity in the MerchantHub domain, including its purpose, responsibilities, ownership, lifecycle, relationships, invariants, business rules, and whether it is an aggregate root or a dependent entity. This model is the authoritative source of truth for all subsequent database design, API development, and business logic implementation.

---

## Aggregate Roots vs. Dependent Entities

An **Aggregate Root** is the entry point for a cluster of domain objects. External actors (APIs, services) may only hold references to aggregate roots. Dependent entities within an aggregate are accessed and mutated only through their root.

| Type | Definition | Examples |
|---|---|---|
| **Aggregate Root** | Standalone entity with its own identity and lifecycle | Workspace, User, Product, Customer, Sale, Expense |
| **Dependent Entity** | Exists only within the context of a parent aggregate root | SaleItem, Payment, BusinessProfile (exists in Workspace aggregate), WorkspaceMembership, InventoryMovement |

---

## Entity Map

| # | Entity | Type | Module | Aggregate Root? |
|---|---|---|---|---|
| 1 | User | Core | accounts | Yes |
| 2 | Workspace | Core | workspaces | Yes |
| 3 | BusinessProfile | Core | workspaces | No (depends on Workspace) |
| 4 | Staff | Core | workspaces | No (depends on User + Workspace) |
| 5 | Role | Enum-like | workspaces | Yes |
| 6 | Permission | Enum-like | workspaces | No (depends on Role) |
| 7 | Category | Core | inventory | Yes |
| 8 | Product | Core | inventory | Yes |
| 9 | InventoryMovement | Transaction | inventory | No (depends on Product) |
| 10 | Customer | Core | customers | Yes |
| 11 | Sale | Core | sales | Yes |
| 12 | SaleItem | Transaction | sales | No (depends on Sale) |
| 13 | Payment | Core | payments | No (depends on Sale; MVP only — may become aggregate root in future) |
| 14 | Expense | Core | expenses | Yes |
| 15 | Notification | Cross-cutting | common | Yes |
| 16 | AuditLog | Cross-cutting | common | Yes |

---

## Entity Definitions

---

### 1. User

| Field | Value |
|---|---|
| **Purpose** | Represents a human being who can authenticate and interact with the MerchantHub system across one or more workspaces. |
| **Responsibilities** | Authentication, profile management, workspace membership, identity across tenants. |
| **Owner** | `accounts` app. |
| **Aggregate Root** | Yes. Users exist independently of any workspace. |
| **Workspace-scoped?** | No. Users are global entities. However, their *actions* and *visibility* are scoped to the workspace they are currently acting within. |

**Relationships:**
- Has many `WorkspaceMembership` entries (many-to-many with `Workspace` through an intermediary).
- Has one default/primary workspace (the one created at registration).
- Optionally references a `Staff` profile (if they are assigned as staff in a workspace context).

**Important Business Rules:**
- A User must have a unique email address.
- A User can exist without belonging to any workspace (e.g., deactivated accounts).
- A User's password is hashed and never stored in plain text.
- `is_merchant` flag indicates the user registered as a business owner rather than as a super-admin.

**Invariants:**
- `email` must be unique across all users.
- `username` must be unique across all users.
- A User must have at least one verified contact method (email).

**Lifecycle:**
```
Created (registration) → Active (email verified) → Suspended (optional) → Archived (deactivated)
```

---

### 2. Workspace

| Field | Value |
|---|---|
| **Purpose** | A tenant boundary representing one business entity (e.g., "Maria's Boutique" or "Truck A"). All domain data (products, sales, customers, expenses, payments) is scoped within a workspace. |
| **Responsibilities** | Data isolation, multi-tenancy boundary, subscription tier enforcement, business profile container. |
| **Owner** | `workspaces` app. |
| **Aggregate Root** | Yes. Workspaces are the top-level organizational unit. |
| **Workspace-scoped?** | N/A — Workspace is the scoping mechanism itself. |

**Relationships:**
- Has many `WorkspaceMembership` entries.
- Has one `BusinessProfile`.
- Owns all domain entities (Products, Sales, Customers, Expenses, Payments).

**Important Business Rules:**
- A Workspace name must be unique within the platform (or at least within the owner's scope — TBD).
- Deleting a workspace deletes all scoped data within it.
- A workspace has exactly one owner (the User who created it).
- A workspace can be transferred to another User (future scope).

**Invariants:**
- `name` must be unique across all workspaces (or combined with some slug/domain — team decision).
- A workspace must always have at least one owner (`WorkspaceMembership` with `role=owner`).

**Lifecycle:**
```
Created (on user registration) → Active → Suspended (payment failure) → Deleted (permanent)
```

---

### 3. BusinessProfile

| Field | Value |
|---|---|
| **Purpose** | Stores business-specific metadata for a workspace — legal name, tax ID, address, currency preference, timezone, logo. |
| **Responsibilities** | Tax reporting configuration, business identity, localization settings. |
| **Owner** | `workspaces` app. |
| **Aggregate Root** | No. Dependent entity within the Workspace aggregate. BusinessProfile has no independent lifecycle — all creation, updates, and deletion occur through the owning Workspace. |
| **Workspace-scoped?** | Yes. One BusinessProfile per Workspace. |

**Relationships:**
- Belongs to exactly one `Workspace` (1:1).

**Important Business Rules:**
- Creating a workspace automatically creates an empty BusinessProfile.
- BusinessProfile fields are optional during workspace creation (can be filled later).
- `currency` defaults to the workspace's local currency (MVP: USD).
- BusinessProfile is entirely managed through the Workspace aggregate. It cannot be created, updated, or deleted independently of its Workspace.

**Invariants:**
- A workspace may have zero or one BusinessProfile.
- BusinessProfile cannot exist outside a Workspace.

**Lifecycle:**
```
Created (automatically with workspace) → Updated (through workspace management) → Deleted (with workspace; no independent deletion)
```

---

### 4. Staff

| Field | Value |
|---|---|
| **Purpose** | Represents a User in the context of a specific workspace with a specific role. Associates a human (User) with a workspace position. |
| **Responsibilities** | Role assignment, workspace-specific profile, access control. |
| **Owner** | `workspaces` app. |
| **Aggregate Root** | No. Dependent entity — exists only as a relationship between User and Workspace. |

> **Note:** In MVP, `Staff` is equivalent to `WorkspaceMembership`. It may evolve into a richer profile (shift assignments, commission rates, schedule) post-MVP. The domain model treats Staff and WorkspaceMembership as the same concept during Phase 1.

**Relationships:**
- References exactly one `User`.
- References exactly one `Workspace`.
- Has exactly one `Role`.

**Important Business Rules:**
- A User can have multiple Staff profiles across different workspaces.
- A Staff profile cannot exist without both a User and a Workspace.
- Removing a User from a workspace deletes the Staff profile.

**Invariants:**
- A User cannot have more than one Staff profile in the same workspace.
- A workspace must have at least one Staff member with `role=owner`.

**Lifecycle:**
```
Created (invitation accepted) → Active → Suspended → Removed (membership revoked)
```

---

### 5. Role

| Field | Value |
|---|---|
| **Purpose** | Defines a named set of permissions within a workspace. Provides coarse-grained access control. |
| **Responsibilities** | Authorization boundaries, feature gating. |
| **Owner** | `workspaces` app. |
| **Aggregate Root** | Yes (as a reference/lookup entity). |
| **Workspace-scoped?** | Roles are system-defined (seeded), not created per workspace in MVP. Future scope may allow custom roles. |

**Predefined Roles (MVP):**
| Role | Level | Capabilities |
|---|---|---|
| `owner` | 100 | Full access. Can manage staff, delete workspace, view all data, configure settings. |
| `manager` | 50 | Can view and edit all business data (products, sales, customers, expenses), view staff list, run reports. Cannot invite/remove staff or delete workspace. |
| `staff` | 10 | Can record sales, view products and customers, log expenses. Cannot view profit metrics, staff list, or modify settings. |

**Important Business Rules:**
- Roles have a rank/level for hierarchical comparison (a user with a higher-level role can perform all actions of lower-level roles).
- MVP uses exactly three roles. Custom roles are future scope.

**Lifecycle:**
```
Seeded (at deployment) → Immutable (MVP)
```

---

### 6. Permission

| Field | Value |
|---|---|
| **Purpose** | A fine-grained action that a Role may perform (e.g., `product.create`, `sale.read`, `staff.invite`). |
| **Responsibilities** | Fine-grained authorization. |
| **Owner** | `workspaces` app. |
| **Aggregate Root** | No. Dependent on Role. |

**Important Business Rules:**
- In MVP, permissions are implicitly derived from the Role enum (owner/manager/staff) rather than stored in a database table. Explicit Permission entities are prepared here for future extensibility.
- Each Role maps to a predefined set of permissions.

**Lifecycle:**
```
Seeded → Immutable (MVP) → Customizable (future)
```

---

### 7. Category

| Field | Value |
|---|---|
| **Purpose** | Tags products into logical groupings for organization, reporting, and filtering (e.g., "Clothing," "Ingredients," "Services"). |
| **Responsibilities** | Product grouping, sales categorization, expense categorization (via expense categories). |
| **Owner** | `inventory` app. |
| **Aggregate Root** | Yes. |
| **Workspace-scoped?** | Yes. Categories belong to exactly one workspace. |

**Relationships:**
- Has many `Product` entries.
- Can optionally be hierarchical (parent category → subcategory) — future scope.

**Important Business Rules:**
- A Category name must be unique within a workspace.
- Deleting a category does not delete its products; products become uncategorized (category set to null or a default "Uncategorized" category).

**Invariants:**
- `name` + `workspace` must be unique.

**Lifecycle:**
```
Created → Updated → Deleted (products unlinked)
```

---

### 8. Product

| Field | Value |
|---|---|
| **Purpose** | Represents an item or service that a merchant sells. The central entity in the inventory domain. |
| **Responsibilities** | Price tracking, stock tracking, sales line items, cost accounting. |
| **Owner** | `inventory` app. |
| **Aggregate Root** | Yes. Products are standalone entities within a workspace. |
| **Workspace-scoped?** | Yes. Products belong to exactly one workspace. |

**Relationships:**
- Belongs to exactly one `Workspace`.
- Belongs to zero or one `Category`.
- Has many `SaleItem` references (but SaleItem is in the Sale aggregate — Product is referenced, not owning).
- Has many `InventoryMovement` entries.

**Important Business Rules:**
- Stock quantity is a computed value: the sum of all inbound InventoryMovements minus the sum of all outbound InventoryMovements. For MVP efficiency, a materialized `current_stock` field is maintained on the Product and updated atomically with each movement.
- A Product cannot be deleted if it has associated SaleItems (to preserve historical sales integrity). Instead, it should be archived/marked inactive.
- SKU is optional; if provided, it must be unique within a workspace.
- `cost_price` is used for profit calculation (revenue — cost of goods sold).
- `unit_price` is the selling price.

**Invariants:**
- `unit_price` must be ≥ 0.
- `cost_price` must be ≥ 0 (if provided).
- `current_stock` must be ≥ 0 (enforced at the application layer during sale creation).
- `sku` + `workspace` must be unique if SKU is provided.
- A Product must belong to exactly one Workspace — it can never exist outside one.

**Lifecycle:**
```
Created → Active → Low Stock (alert) → Archived/Discontinued (historical records preserved)
```

---

### 9. InventoryMovement

| Field | Value |
|---|---|
| **Purpose** | Records every change to a product's stock quantity — initial stock setup, sale deduction, manual adjustment, return/restock. |
| **Responsibilities** | Stock audit trail, inventory reconciliation, movement history. |
| **Owner** | `inventory` app. |
| **Aggregate Root** | No. Dependent on Product. |
| **Workspace-scoped?** | Yes (scoped through the owning Product's workspace). |

**Movement Types:**
| Type | Effect | Trigger |
|---|---|---|
| `initial` | + | Product creation or stock take |
| `sale` | − | Sale creation (automatic) |
| `return` | + | Sale refund or return |
| `adjustment` | ± | Manual stock correction |
| `transfer_out` | − | Transfer to another location (future) |
| `transfer_in` | + | Transfer from another location (future) |

**Relationships:**
- References exactly one `Product`.
- Optionally references a `Sale` (when movement type is `sale` or `return`).

**Important Business Rules:**
- Every InventoryMovement is immutable — once recorded, it cannot be edited or deleted. Corrections are done via new adjustment movements.
- The Product's `current_stock` is the sum of all movement quantities for that product.
- Movement quantity is always positive; the direction is encoded in the `movement_type` field.

**Invariants:**
- `quantity` must be > 0.
- A movement must always reference a Product. It cannot exist independently.
- `movement_type` must be one of the predefined types.

**Lifecycle:**
```
Created → Immutable (permanent record)
```

---

### 10. Customer

| Field | Value |
|---|---|
| **Purpose** | Represents a person who purchases from the merchant. Used for sales attribution, loyalty tracking, and re-engagement. |
| **Responsibilities** | Purchase history aggregation, customer relationship management. |
| **Owner** | `customers` app. |
| **Aggregate Root** | Yes. Customers exist independently within a workspace. |
| **Workspace-scoped?** | Yes. Customers belong to exactly one workspace. |

**Relationships:**
- Belongs to exactly one `Workspace`.
- Has many `Sale` entries (a customer can make multiple purchases).
- Computed fields: total visits (count of sales), total spend (sum of sale totals), average transaction value (total spend / total visits), last visit date (max sale date).

**Important Business Rules:**
- A Customer record can be created without an associated sale (pre-emptive profile creation).
- Phone number or email is required (at least one for identification).
- Customers are not shared across workspaces (even if the same person shops at two different merchant locations, they are separate records).

**Invariants:**
- At least one of `phone` or `email` must be provided.

**Lifecycle:**
```
Created → Active (with sales) → Inactive (no sales in 6+ months) → Merged (future: deduplication)
```

---

### 11. Sale

| Field | Value |
|---|---|
| **Purpose** | Records a transaction between the merchant and a customer. The central financial event in the system. |
| **Responsibilities** | Revenue recording, inventory deduction trigger, payment tracking, customer purchase history. |
| **Owner** | `sales` app. |
| **Aggregate Root** | Yes. The Sale aggregate contains SaleItems and Payments. |
| **Workspace-scoped?** | Yes. Every Sale belongs to exactly one workspace. |

**Sale Statuses:**
| Status | Description |
|---|---|
| `pending` | Sale created but payment not yet completed |
| `completed` | Sale finalized with full payment |
| `partially_paid` | Sale with partial payment received |
| `refunded` | Sale fully refunded |
| `cancelled` | Sale voided before fulfillment |

**Relationships:**
- Belongs to exactly one `Workspace`.
- Optionally references one `Customer`.
- Has many `SaleItem` entries (1:N).
- Has many `Payment` entries (1:N) — Payments are dependent entities within the Sale aggregate in MVP. Future versions may promote Payment to an independent aggregate root when standalone payments, deposits, or gift cards are introduced.
- References a `User` (the staff member who recorded the sale).

**Important Business Rules:**
- Creating a Sale must deduct inventory within an atomic transaction. If any line item exceeds available stock, the entire sale is rejected.
- Sale total is computed as the sum of all SaleItem line totals (quantity × unit_price).
- Sale status is derived from the sum of Payment amounts vs. the sale total.
- A Sale cannot be deleted once completed; corrections are done via refunds (new Sales of negative quantity or separate refund records).

**Invariants:**
- A Sale must belong to exactly one Workspace — it can never exist outside one.
- A Sale must have at least one SaleItem.
- `total_amount` must equal the sum of all SaleItem line totals.
- Inventory deduction must be atomic with Sale creation.

**Lifecycle:**
```
Created (pending) → Completed (paid) → Partially Paid → Refunded → Cancelled
```

---

### 12. SaleItem

| Field | Value |
|---|---|
| **Purpose** | Represents a single line within a sale — one product and the quantity purchased. |
| **Responsibilities** | Line-level detail for sales reporting, inventory deduction. |
| **Owner** | `sales` app. |
| **Aggregate Root** | No. Dependent on Sale. |
| **Workspace-scoped?** | Yes (scoped through the owning Sale's workspace). |

**Relationships:**
- Belongs to exactly one `Sale`.
- References exactly one `Product`.

**Important Business Rules:**
- A SaleItem cannot exist without a parent Sale.
- `unit_price` is captured at sale time (snapshot of the product's current price) — changes to the Product's price after the sale do not affect historical SaleItems.
- `line_total` is computed as `quantity × unit_price`.

**Invariants:**
- `quantity` must be > 0.
- `unit_price` must be ≥ 0.
- A SaleItem must reference a Product — it cannot reference a free-text description or a non-existent product.
- A SaleItem cannot exist without a Sale.

**Lifecycle:**
```
Created (with Sale) → Immutable (SaleItem is read-only after Sale is finalized)
```

---

### 13. Payment

| Field | Value |
|---|---|
| **Purpose** | Records a payment received from a customer against a sale. Tracks how much was paid, when, and through which method. |
| **Responsibilities** | Payment reconciliation, outstanding balance tracking, payment method analytics. |
| **Owner** | `payments` app. |
| **Aggregate Root** | No. Dependent entity within the Sale aggregate in MVP. Payments are created only in the context of Sales and cannot exist without a parent Sale. May become its own aggregate root in a future version when standalone payments, deposits, credits, or gift cards are introduced. |
| **Workspace-scoped?** | Yes. Payments belong to exactly one workspace. |

**Payment Methods (MVP):**
- `cash`
- `card`
- `bank_transfer`

**Relationships:**
- Belongs to exactly one `Workspace`.
- References exactly one `Sale` (MVP — future scope may allow standalone payments without a Sale).
- Optionally references a `Customer`.

**Important Business Rules:**
- A Payment cannot exceed the remaining balance of the Sale (overpayment should be prevented or treated as credit — MVP decision: prevent overpayment).
- Multiple payments can be applied to a single Sale (split payments: e.g., $20 cash + $30 card).
- A Payment amount must be > 0.

**Invariants:**
- `amount` must be > 0.
- Sum of payments against a Sale must not exceed the Sale's `total_amount`.
- A Payment must reference a Sale (in MVP).
- A Payment cannot exist without a Sale.

**Lifecycle:**
```
Created (within a Sale) → Completed (applied to sale) → Refunded (future)
```

---

### 14. Expense

| Field | Value |
|---|---|
| **Purpose** | Records a business expense — any outflow of money for operating the business. |
| **Responsibilities** | Cost tracking, profit calculation, expense categorization. |
| **Owner** | `expenses` app. |
| **Aggregate Root** | Yes. Expenses stand alone within a workspace. |
| **Workspace-scoped?** | Yes. Expenses belong to exactly one workspace. |

**Expense Categories (MVP):**
- `cost_of_goods_sold` — direct product/ingredient costs
- `rent` — rent or lease payments
- `utilities` — electricity, water, internet
- `salaries` — employee wages
- `marketing` — advertising, promotions
- `maintenance` — repairs, upkeep
- `other` — anything not fitting above

**Relationships:**
- Belongs to exactly one `Workspace`.
- Optionally references a `Category` (for expense-specific categorization, separate from product categories).

**Important Business Rules:**
- An Expense amount must be > 0.
- Expense description is required for audit purposes.
- Optional receipt attachment (stored as a file reference — future scope in MVP).

**Invariants:**
- `amount` must be > 0.
- An Expense must belong to exactly one Workspace — it can never exist outside one.

**Lifecycle:**
```
Created → Active → Updated (correction, with audit trail) → Archived (older than fiscal period)
```

---

### 15. Notification

| Field | Value |
|---|---|
| **Purpose** | Represents a system-generated message to a user or staff member about an event (low-stock alert, payment received, staff invitation). |
| **Responsibilities** | User communication, event-driven alerts, in-app notification center. |
| **Owner** | `common` app (cross-cutting). |
| **Aggregate Root** | Yes. Notifications exist independently. |
| **Workspace-scoped?** | Yes (contextually — a notification belongs to a workspace context or is global to the user). |

**Notification Types (MVP):**
- `low_stock_alert` — product stock below threshold
- `sale_completed` — a sale was recorded
- `staff_invite` — invitation to join a workspace
- `payment_received` — a payment was applied

**Relationships:**
- Belongs to exactly one `User` (the recipient).
- Optionally belongs to a `Workspace` (context).
- Optionally references a source entity (Product, Sale, etc.) via a generic foreign key or type-specific fields.

**Important Business Rules:**
- Notifications can be marked as read (soft state transition).
- Notifications are created by system events, not by users.
- Read notifications can be auto-deleted after 30 days (configurable).

**Invariants:**
- A Notification must have a recipient (User) — it cannot be orphaned.
- A Notification must have a type and a message.

**Lifecycle:**
```
Created (by system event) → Unread → Read → Deleted (auto-cleanup)
```

---

### 16. AuditLog

| Field | Value |
|---|---|
| **Purpose** | An immutable record of every significant state change in the system. Provides a compliance-grade trail of who did what and when. |
| **Responsibilities** | Security audit, change tracking, compliance, debugging. |
| **Owner** | `common` app (cross-cutting). |
| **Aggregate Root** | Yes. AuditLogs are independent, append-only records. |
| **Workspace-scoped?** | Yes (contextually — scoped by the workspace in which the action occurred). |

**Audited Actions (MVP):**
| Action Category | Examples |
|---|---|
| `entity.create` | Product created, Sale created, Customer created |
| `entity.update` | Product price changed, Customer info updated |
| `entity.delete` | Product archived, Customer deleted |
| `auth.login` | User logged in |
| `auth.logout` | User logged out |
| `workspace.membership` | Staff invited, role changed, member removed |
| `sale.status_change` | Sale marked as refunded |

**Relationships:**
- References the acting `User`.
- Optionally references the affected `Workspace`.
- Stores the target entity type and ID as a generic reference.
- Stores a JSON snapshot of the change (before/after values).

**Important Business Rules:**
- AuditLogs are append-only — they can never be edited or deleted.
- AuditLog creation must not fail or block the primary operation (fire-and-forget or async).
- Sensitive data (passwords, tokens) must never be logged.

**Invariants:**
- Every AuditLog must have an actor (User), an action type, and a timestamp.
- AuditLogs are immutable once created — no updates, no deletes.

**Lifecycle:**
```
Created (on system event) → Immutable (permanent record)
```

---

## Workspace Scoping Summary

| Entity | Always in a Workspace? | Can Exist Outside? | Rationale |
|---|---|---|---|
| User | No | Yes | Users are global platform entities |
| Workspace | N/A | N/A | Workspace is the scoping mechanism |
| BusinessProfile | Yes | No | Describes a workspace |
| Staff (WorkspaceMembership) | Yes | No | Represents a User-in-Workspace relationship |
| Role | No | Yes (seeded globally) | System-defined, not tenant-specific |
| Permission | No | Yes (seeded globally) | System-defined, not tenant-specific |
| Category | Yes | No | User-defined product groupings per workspace |
| Product | **Yes** | **No** | A product cannot exist outside a workspace |
| InventoryMovement | Yes | No | Scoped through Product → Workspace |
| Customer | **Yes** | **No** | A customer record is specific to a merchant |
| Sale | **Yes** | **No** | A sale cannot exist outside a workspace |
| SaleItem | Yes | No | Scoped through Sale → Workspace |
| Payment | **Yes** | **No** | A payment cannot exist outside a workspace |
| Expense | **Yes** | **No** | An expense cannot exist outside a workspace |
| Notification | No | Yes (user-level) | Can be user-global or workspace-scoped |
| AuditLog | Yes (contextual) | No | Logs are scoped by workspace context |

---

## Entity Invariants (Compiled)

### Structural Invariants
1. **Products belong to exactly one Workspace.** — A Product can never exist outside a Workspace context.
2. **Every Sale belongs to exactly one Workspace.** — A Sale can never exist outside a Workspace context.
3. **SaleItems cannot exist without a Sale.** — They are dependent entities within the Sale aggregate.
4. **Payments cannot exist without a Sale (MVP).** — In the current scope, every Payment is linked to a Sale. Future scope may introduce standalone payments.
5. **InventoryMovements must always reference a Product.** — Stock changes are always attributed to a specific product.
6. **Users may belong to multiple Workspaces (future), but MVP assumes a single owned Workspace.** — The registration flow creates one default workspace.

### Business Invariants
7. **Stock cannot go negative.** — A sale with insufficient stock must be rejected entirely (atomic rollback).
8. **Sale total must equal the sum of line items.** — No arbitrary total overrides.
9. **Payment sum cannot exceed sale total.** — Overpayment is prevented (or treated as credit — MVP chooses prevention).
10. **A workspace must always have at least one owner.** — The last owner cannot remove themselves or be demoted.
11. **At least one contact method (phone or email) is required for Customer creation.**

### Data Integrity Invariants
12. **Email is unique across all Users.**
13. **SKU is unique within a Workspace** (if provided).
14. **Category name is unique within a Workspace.**
15. **AuditLogs and InventoryMovements are immutable** — once written, they are never modified or deleted.

---

## Module Ownership Map

| Module | Owned Entities |
|---|---|
| `accounts` | User |
| `workspaces` | Workspace, BusinessProfile, Staff (WorkspaceMembership), Role, Permission |
| `inventory` | Category, Product, InventoryMovement |
| `customers` | Customer |
| `sales` | Sale, SaleItem |
| `payments` | Payment |
| `expenses` | Expense |
| `common` | Notification, AuditLog |
| `dashboard` | None (reads from all modules, no owned entities) |

---

*This document is a living artifact. Entities, invariants, and rules may be refined as development progresses.*
