# MerchantHub — Entity Relationships & Data Architecture

**Version:** 1.0  
**Status:** Draft  
**Last Updated:** July 1, 2026  
**Phase:** 1 (Foundation & Domain Modeling)

---

## Purpose

This document defines the relationships between all business entities in the MerchantHub domain. It covers parent/child hierarchies, ownership boundaries, aggregate boundaries, deletion strategies, soft vs. hard delete recommendations, the multi-tenant isolation strategy, and audit requirements. This document serves as the bridge between the domain model and database schema design.

---

## 1. Entity Relationship Overview

The following describes all entity-to-entity relationships in the MerchantHub domain at the logical (not physical) level.

```
User ──1:N──> Staff (WorkspaceMembership) ──N:1── Workspace
                                                          │
                                            ┌─────────────┼─────────────┐
                                            │             │             │
                                      BusinessProfile   Category   Customer
                                                          │             │
                                                    1:N Product        │
                                                         │  ↑          │
                                                   1:N SaleItem ──N:1 Sale ──N:1┐
                                                         │                     │
                                                   1:N InventoryMovement   1:N Payment
                                                                                │
                                               Expense ────────────────────────┘
```

---

## 2. Relationship Matrix

| Entity A | Relationship | Entity B | Cardinality | Description |
|---|---|---|---|---|
| User | owns | Workspace | 1:N | A User can own multiple workspaces (MVP: 1) |
| User | works in | Workspace | M:N | Through Staff (WorkspaceMembership) |
| User | has | Staff | 1:N | A User can have multiple staff profiles |
| Workspace | has | Staff | 1:N | A workspace has many members |
| Workspace | has | BusinessProfile | 1:1 | Each workspace has one business profile |
| Workspace | owns | Product | 1:N | A workspace contains many products |
| Workspace | owns | Customer | 1:N | A workspace has many customers |
| Workspace | owns | Sale | 1:N | A workspace records many sales |
| Workspace | owns | Expense | 1:N | A workspace logs many expenses |
| Workspace | owns | Payment | 1:N | A workspace receives many payments |
| Workspace | owns | Category | 1:N | A workspace defines many categories |
| Staff | has | Role | N:1 | Each staff member has exactly one role |
| Role | grants | Permission | N:M | A role bundles many permissions |
| Category | groups | Product | 1:N | A category can contain many products |
| Product | appears in | SaleItem | 1:N | A product appears in many sale line items |
| Product | has | InventoryMovement | 1:N | A product has a history of stock movements |
| Sale | contains | SaleItem | 1:N | A sale comprises many line items |
| Sale | references | Customer | N:1 | A sale optionally references a customer |
| Sale | has | Payment | 1:N | A sale can have multiple payments |
| Sale | recorded by | Staff | N:1 | A sale is recorded by a staff member |
| SaleItem | references | Product | N:1 | Each line item references one product |

---

## 3. Parent/Child Relationships

A parent/child relationship means the child entity cannot exist without the parent entity. These are strong ownership relationships.

| Parent | Child | Cascade Behavior | Rationale |
|---|---|---|---|
| Workspace | BusinessProfile | Cascade | 1:1 — the profile is meaningless without the workspace |
| Workspace | Staff | Cascade | Membership is inherently tied to the workspace |
| Product | InventoryMovement | Cascade | A movement record is meaningless without the product it tracks |
| Sale | SaleItem | Cascade | Line items are meaningless outside the context of their sale |
| Sale | Payment | Cascade (or PROTECT) | Payments reference sales; orphaned payments are financial errors |

**Non-cascading parent/child relationships** (children survive parent deletion — handled via SET_NULL or archiving):

| Parent | Child | On-Delete Strategy | Rationale |
|---|---|---|---|
| Category | Product | SET_NULL | Products survive category deletion (become uncategorized) |
| Customer | Sale | PROTECT or SET_NULL | Sales survive customer deletion (set customer to null to preserve financial records) |
| Product | SaleItem | PROTECT | Historical sale records must be preserved even if a product is archived |

---

## 4. Ownership Boundaries

Ownership boundaries define which module is responsible for an entity's lifecycle. Cross-boundary references must be resolved via IDs (foreign keys at the database level), but no module should directly modify another module's entities.

| Module | Owns (Primary Responsibility) | References (External) |
|---|---|---|
| `accounts` | User | None |
| `workspaces` | Workspace, BusinessProfile, Staff, Role, Permission | User (FK) |
| `inventory` | Category, Product, InventoryMovement | Workspace (FK), Sale (optional FK on InventoryMovement) |
| `customers` | Customer | Workspace (FK) |
| `sales` | Sale, SaleItem | Workspace (FK), Customer (FK, optional), Product (FK, SaleItem), User/Staff (FK) |
| `payments` | Payment | Workspace (FK), Sale (FK) |
| `expenses` | Expense | Workspace (FK) |
| `common` | Notification, AuditLog | Workspace (FK, optional), User (FK), generic entity reference |

**Key boundary rules:**
- The `inventory` module must never directly create or modify SaleItems.
- The `sales` module must never directly modify Product stock — it must create InventoryMovements (which inventory module owns) or call an inventory service/function.
- The `payments` module must not modify Sale data — only read Sale totals to validate payment amounts.

---

## 5. Aggregate Boundaries

Aggregates define transactional consistency boundaries. Operations within an aggregate are atomic; operations across aggregates use eventual consistency or distributed transactions (avoided in MVP).

| Aggregate Root | Children | Consistency Boundary |
|---|---|---|
| **Workspace** | BusinessProfile, Staff | Workspace metadata changes are atomic |
| **Product** | InventoryMovement | Stock level and movements are consistent within one product |
| **Sale** | SaleItem | Sale creation (line items + inventory deduction + payment) is atomic |
| **Sale** | Payment (logical) | Payment validation against sale total is checked at the application layer |
| **Customer** | (none in MVP) | Customer is a simple aggregate |
| **Expense** | (none in MVP) | Expense is a simple aggregate |
| **User** | (none in MVP) | User is a simple aggregate |

**Cross-aggregate transactions (MVP):**
The most critical cross-aggregate operation is **Sale creation**, which spans:
- Sale aggregate (Sale + SaleItems)
- Product aggregate (InventoryMovement creation + stock deduction)

These must execute within a single database transaction. If InventoryMovement creation fails, the entire Sale is rolled back.

---

## 6. Deletion Strategy

| Strategy | When to Use | Entities |
|---|---|---|
| **Hard Delete** | Ephemeral or easily regenerated data; no historical value | Notification (after read/expiry) |
| **Soft Delete** (archive/deactivate/is_active flag) | Data with historical significance that should not be permanently lost; regulatory compliance | Product, Customer, Sale, Expense, Staff, Category, Payment |
| **CASCADE** | Child entity that cannot exist without its parent | SaleItem → Sale, InventoryMovement → Product, BusinessProfile → Workspace, Staff → Workspace |
| **PROTECT** (prevent deletion) | Referenced data that must be preserved for historical integrity | Product (if has SaleItems), Customer (if has Sales) |
| **SET_NULL** | Relationship that should be optionally preserved | Product.category_id → Category (on category deletion), Sale.customer_id → Customer (on customer deletion) |

### Recommendations by Entity

| Entity | Strategy | Detail |
|---|---|---|
| User | Soft delete (is_active flag) | Preserve workspace ownership history; allow account reactivation |
| Workspace | Soft delete, then hard delete after grace period | 30-day grace period before permanent deletion; notify owner |
| BusinessProfile | CASCADE with Workspace | Deleted when workspace is deleted |
| Staff | Hard delete | Membership is revocable; no historical value in preserving inactive memberships |
| Category | Soft delete | Prevent accidental loss; products remain but lose category |
| Product | Soft delete (is_active flag) | Preserve historical sale references; inactive products hidden from new sales |
| InventoryMovement | Immutable (no delete) | Audit trail must never be destroyed |
| Customer | Soft delete | Preserve sales history; GDPR right to erasure handled separately |
| Sale | Soft delete / status-based | Sales are never hard-deleted; status changes to cancelled/refunded |
| SaleItem | CASCADE with Sale | Deleted only when the parent Sale is hard-deleted (which should never happen) |
| Payment | Soft delete | Financial records must be preserved |
| Expense | Soft delete | Financial records must be preserved |
| Notification | Hard delete | After read or after TTL; no historical value |
| AuditLog | Immutable (no delete) | Append-only; retention policy via archiving, not deletion |

---

## 7. Soft Delete vs. Hard Delete Recommendations

### Soft Delete Implementation

A `deleted_at` timestamp column is preferred over a boolean `is_deleted` flag because it records *when* the deletion occurred, which aids audit and allows time-based cleanup.

**Additional considerations:**
- All queries must filter `WHERE deleted_at IS NULL` to exclude soft-deleted records by default.
- An index on `deleted_at` prevents performance degradation from scanning deleted records.
- Soft-deleted records should be inaccessible via the API but visible to super-admins via Django admin.
- Unique constraint violations with soft deletion: if a soft-deleted Product has SKU "ABC-123," a new product should be allowed to reuse that SKU (unique constraint should include only active records, or use a composite unique constraint on `(workspace_id, sku, deleted_at)` with a partial index).

### When to Hard Delete

| Condition | Entities |
|---|---|
| Data is ephemeral and has zero historical value | Notifications after read+TTL |
| User exercises GDPR right to erasure | User (and anonymize their sales) |
| Data was created in error within a short window | Not applicable directly — use status changes instead |

### General Rule

**Prefer soft delete for all business entities.** Hard delete is reserved for ephemeral or cross-cutting entities (notifications, logs that exceed retention policy).

---

## 8. Multi-Tenant Isolation Strategy

### 8.1 Approach: Discriminated Workspace Column (Shared Database, Shared Schema)

All tenant-scoped entities carry a `workspace_id` foreign key. Every query includes a `WHERE workspace_id = <current_workspace>` filter.

| Property | Decision |
|---|---|
| **Strategy** | Shared database, shared schema, row-level isolation via `workspace_id` |
| **Why not separate databases?** | MVP simplicity; no per-tenant provisioning overhead; cost-effective for small tenants |
| **Why not separate schemas?** | Django ORM does not natively support per-request schema switching without middleware complexity |
| **Future migration path** | Switch to a separate-schema or separate-database model if compliance or scale demands it |

### 8.2 Implementation Patterns

**Pattern A — Base Model Integration (Recommended for MVP)**

All workspace-scoped entities inherit from a `WorkspaceScopedModel` (a subclass of `BaseModel`):

```
BaseModel (UUID, created_at, updated_at)
  └── WorkspaceScopedModel (workspace FK)
        ├── Product
        ├── Customer
        ├── Sale
        ├── Expense
        ├── Payment
        └── Category
```

This eliminates the need to add the `workspace` FK manually to every model.

**Entities that intentionally do NOT inherit from `WorkspaceScopedModel`:**
- `User` — global identity
- `Role` — system-defined
- `Permission` — system-defined
- `AuditLog` — uses workspace FK but is not a domain entity (cross-cutting)
- `Notification` — may be workspace-scoped or user-scoped

**Pattern B — Query Filtering**

Enforce workspace scoping at the ORM level via a custom manager or queryset:

```python
class WorkspaceScopedQuerySet(models.QuerySet):
    def for_workspace(self, workspace):
        return self.filter(workspace=workspace)
```

**Pattern C — Middleware-Based Default Scope (Phase 2)**

Middleware extracts `X-Workspace-ID` from the request header and attaches it to `request.workspace`. A DRF view mixin or permission class automatically applies the workspace filter to all queries:

```python
class WorkspaceScopedViewMixin:
    def get_queryset(self):
        return super().get_queryset().filter(workspace=self.request.workspace)
```

### 8.3 Cross-Tenant Data Access

- **Explicitly forbidden** in the standard API. No endpoint allows cross-workspace queries.
- **Super-admin access** exists via Django admin for support and debugging purposes.
- **Future scope:** cross-workspace analytics for users with multiple workspaces (aggregated, not granular).

### 8.4 Tenant Identification Chain

```
Request → JWT Token → User → WorkspaceMembership → Workspace
                                       ↑
                              X-Workspace-ID header
```

- The user authenticates via JWT.
- The `X-Workspace-ID` header specifies which workspace they are acting within.
- The system verifies the user has an active `WorkspaceMembership` for that workspace.
- All subsequent queries are scoped to that workspace.

---

## 9. Audit Requirements

### 9.1 What to Audit

| Action | Audit Level | Fields Captured |
|---|---|---|
| User login/logout | Actor + timestamp | user_id, ip_address, user_agent |
| Entity creation | Actor + timestamp + target | user_id, entity_type, entity_id, created_data (JSON) |
| Entity modification | Actor + timestamp + target + diff | user_id, entity_type, entity_id, before (JSON), after (JSON) |
| Entity soft delete | Actor + timestamp + target | user_id, entity_type, entity_id |
| Staff invitation | Actor + timestamp + target | inviting_user_id, invited_user_id, workspace_id, role |
| Role change | Actor + timestamp + target | changed_by_user_id, target_user_id, old_role, new_role |
| Sale status change | Actor + timestamp + target | user_id, sale_id, old_status, new_status |
| Inventory adjustment | Actor + timestamp + target | user_id, product_id, old_stock, new_stock, reason |
| Settings change | Actor + timestamp + target | user_id, setting_key, old_value, new_value |

### 9.2 Audit Log Format

Each audit log entry should capture:

```json
{
  "id": "uuid",
  "workspace_id": "uuid (nullable — for system-wide actions)",
  "actor_id": "uuid (user who performed the action)",
  "action": "entity.create | entity.update | entity.delete | auth.login | ...",
  "target_type": "product | sale | customer | ...",
  "target_id": "uuid",
  "changes": {
    "before": { "field": "old_value" },
    "after": { "field": "new_value" }
  },
  "metadata": {
    "ip_address": "string",
    "user_agent": "string",
    "correlation_id": "uuid (for tracing request chains)"
  },
  "timestamp": "ISO 8601"
}
```

### 9.3 Implementation Considerations

- **Write path:** Use Django signals (`post_save`, `pre_delete`) or model mixins to auto-create audit log entries. Signals are simpler for MVP; a middleware-based approach is more robust but more complex.
- **Performance:** Audit log writes should be asynchronous (fire-and-forget). For MVP, synchronous writes to the same database are acceptable given low transaction volumes.
- **Retention:** Audit logs are retained indefinitely for MVP. A data retention policy (e.g., 12 months + archive) is future scope.
- **Storage:** Audit logs live in the same database in MVP. A separate audit database or log aggregation service (e.g., ELK stack) is future scope.

---

## 10. Entity Dependency Graph (Topological Order)

This ordering defines the sequence in which entities must be created (and seeded) to satisfy all foreign key constraints:

```
Level 0 (no dependencies):
    Role → seeded at deployment
    Permission → seeded at deployment
    User → registration (no FK to other entities)

Level 1 (depends on Level 0):
    Workspace → depends on User (owner)
    Staff (WorkspaceMembership) → depends on User + Workspace + Role

Level 2 (depends on Level 1):
    BusinessProfile → depends on Workspace
    Category → depends on Workspace
    Customer → depends on Workspace

Level 3 (depends on Level 2):
    Product → depends on Workspace, optional Category
    Expense → depends on Workspace

Level 4 (depends on Level 3):
    InventoryMovement → depends on Product
    Sale → depends on Workspace, optional Customer, User/Staff
    SaleItem → depends on Sale + Product

Level 5 (depends on Level 4):
    Payment → depends on Sale

Cross-cutting (can be created at any time):
    Notification → depends on User, optional Workspace
    AuditLog → depends on User, optional Workspace
```

---

## 11. Summary of Key Design Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Multi-tenancy model | Shared DB, shared schema, row-level isolation | Simplest for MVP; cost-effective |
| Workspace scoping | `WorkspaceScopedModel` base class | Eliminates boilerplate; enforces consistency |
| Soft delete | Prefer `deleted_at` timestamp over boolean | Provides audit awareness; enables time-based cleanup |
| Hard delete | Only for ephemeral data (notifications) | Business data must never be permanently lost without explicit intent |
| Cascade delete | BusinessProfile, Staff, SaleItem, InventoryMovement | Dependent entities cannot exist without their parent |
| Sale/Payment integrity | Application-layer enforcement (not DB triggers) | More maintainable with Django ORM; sufficient for MVP |
| Audit log write | Synchronous (MVP) — async (future) | Acceptable at low volume; simpler implementation |
| Inventory tracking | Materialized `current_stock` on Product + append-only movements | `current_stock` provides O(1) reads; movements provide audit trail |
| Cross-aggregate transaction | Sale creation = atomic DB transaction | Guarantees inventory + sale consistency |

---

*This document is a living artifact. Relationships, strategies, and decisions should be revisited as the architecture evolves.*
