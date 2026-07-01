# MerchantHub — Database Design Decisions

**Version:** 1.0  
**Status:** Draft  
**Last Updated:** July 1, 2026  
**Phase:** 1 (Foundation & Database Design)

---

## Table of Contents

1. [UUID vs. Integer Primary Keys](#1-uuid-vs-integer-primary-keys)
2. [Decimal Precision for Money](#2-decimal-precision-for-money)
3. [Timestamp Strategy](#3-timestamp-strategy)
4. [Timezone Handling](#4-timezone-handling)
5. [Currency Handling](#5-currency-handling)
6. [Soft Delete Implementation](#6-soft-delete-implementation)
7. [Indexing Strategy](#7-indexing-strategy)
8. [Full-Text Search](#8-full-text-search)
9. [JSONB Usage](#9-jsonb-usage)
10. [Denormalization Decisions](#10-denormalization-decisions)
11. [Concurrency Control](#11-concurrency-control)
12. [Data Retention & Archiving](#12-data-retention--archiving)
13. [Future Compatibility](#13-future-compatibility)
14. [Potential Performance Bottlenecks](#14-potential-performance-bottlenecks)
15. [Scaling Recommendations](#15-scaling-recommendations)
16. [Trade-offs Made](#16-trade-offs-made)

---

## 1. UUID vs. Integer Primary Keys

### Decision: UUID v4 for All Primary Keys

| Aspect | UUID v4 | Auto-increment Integer |
|---|---|---|
| **Uniqueness** | Globally unique without coordination | Unique only within table/database |
| **Security** | Not predictable; no information leakage | Predictable; exposes record count and sequence |
| **Merging** | Safe to merge databases (no collisions) | Collisions likely when merging |
| **Distributed/Offline** | Can generate offline; no central sequence needed | Requires sequence coordination |
| **Index performance** | Slower B-Tree insertion due to randomness | Fast, monotonic insertion |
| **Storage size** | 16 bytes | 4 bytes (int) or 8 bytes (bigint) |
| **Readability** | Hard to read/type manually | Easy to read, reference in URLs |
| **ORM support** | Django native `UUIDField` | Native, trivial |

### Rationale

For MerchantHub, UUID v4 is the stronger choice despite the performance and storage trade-offs:

1. **Security:** Sequential integer IDs in a multi-tenant SaaS application leak information — a competitor could infer the number of users, customers, or transaction volume by observing ID sequences. UUIDs do not reveal this.
2. **Multi-tenancy & merging:** If a tenant ever needs to migrate from a shared database to a dedicated database (or vice versa), UUIDs guarantee no collision. Integer sequences would require expensive re-keying.
3. **Offline generation:** Mobile apps (future scope) can generate UUIDs offline without a round-trip to the server.
4. **Distributed readiness:** Horizontal sharding becomes dramatically easier when IDs are globally unique.

### Mitigations for UUID Performance Costs

- **Indexing:** Use `gen_random_uuid()` (PostgreSQL) rather than application-level UUID generation to minimize network round-trips and leverage server-side randomness.
- **Clustered indexing:** Do **not** use UUID as the clustered index in databases that support clustering (e.g., MySQL InnoDB). In PostgreSQL, there is no implicit clustering by PK, so this is not a concern — every index on the UUID column is a B-Tree on random values, which has insertion overhead. Mitigated by keeping the working set in memory (adequate `shared_buffers`) and using SSDs.
- **Storage:** The additional 12 bytes per row compared to integer PKs is negligible for the expected data volumes (< 10K products, < 50K transactions per workspace).
- **Alternate sequential sort key:** If UUID-based range queries become a bottleneck, consider adding a monotonically increasing `sequence_number` column per workspace (e.g., invoice numbers: `INV-00001`) for human-readable reference.

### Decision Summary

| Entity | PK Strategy | Justification |
|---|---|---|
| All entities | UUID v4 | Security, distributed readiness, merge safety |

---

## 2. Decimal Precision for Money

### Decision: `DECIMAL(14, 2)` for amounts, `DECIMAL(12, 2)` for unit prices

| Field | Type | Rationale |
|---|---|---|
| `unit_price`, `cost_price` | `DECIMAL(12, 2)` | Max value: 99,999,999,999.99. Sufficient for any single product price. |
| `line_total` | `DECIMAL(14, 2)` | Max value: 9,999,999,999,999.99. Allows for quantities up to 100,000 × unit_price. |
| `total_amount`, `paid_amount` | `DECIMAL(14, 2)` | Max value: 9,999,999,999,999.99. Ample for workspace-level totals. |
| `current_stock` | `DECIMAL(12, 3)` | Max value: 99,999,999,999.999. 3 decimal places supports fractional inventory (e.g., 1.5 kg of ingredients). |
| `discount_amount` | `DECIMAL(12, 2)` | Max value: 99,999,999,999.99. |

### Why Not Float?

- **Floating-point errors** (IEEE 754) cause inexact representation of decimal fractions like 0.10 or 19.99. Over time, these errors accumulate and lead to penny-level discrepancies that are unacceptable for financial data.
- **DECIMAL** provides exact arithmetic at the cost of slightly larger storage and slower computation. For financial applications, this is the correct trade-off.

### Why 2 Decimal Places?

- MVP assumes single-currency, tax-inclusive pricing. Two decimal places are standard for most fiat currencies (USD, EUR, GBP, etc.).
- **Future compatibility:** 4 decimal places would be needed for currencies like Kuwaiti Dinar (3 decimal places) or cryptocurrencies. This is a migration path: `ALTER COLUMN ... TYPE DECIMAL(14, 4)` is a simple DDL change in PostgreSQL.

### Quantity Precision

| Entity | Precision | Rationale |
|---|---|---|
| `inventory_product.current_stock` | `DECIMAL(12, 3)` | Supports fractional inventory (e.g., 1.500 kg of rice). |
| `sales_saleitem.quantity` | `DECIMAL(12, 3)` | Supports fractional sales (e.g., 0.500 kg of produce). |
| `inventory_inventorymovement.quantity` | `DECIMAL(12, 3)` | Must match product and sale item precision. |

---

## 3. Timestamp Strategy

### Decision: `TIMESTAMPTZ` (TIMESTAMP WITH TIME ZONE) for all temporal fields

| Field | Type | Behavior |
|---|---|---|
| `created_at` | `TIMESTAMPTZ` | Set once on creation, never updated. |
| `updated_at` | `TIMESTAMPTZ` | Updated automatically on every row modification. |
| `deleted_at` | `TIMESTAMPTZ` (nullable) | Non-NULL = record is soft-deleted. |
| `paid_at` | `TIMESTAMPTZ` | When the payment was received (may differ from `created_at`). |
| `expense_date` | `DATE` (no time) | Only the date matters for expenses, not the time. |
| `last_visit_date` | `DATE` (no time) | Only the date matters for customer visit tracking. |
| `read_at` | `TIMESTAMPTZ` (nullable) | When a notification was read. |

### Why TIMESTAMPTZ Over TIMESTAMP Without Time Zone

- `TIMESTAMPTZ` stores the value as UTC internally but converts to the client's timezone on retrieval. This is critical for a SaaS application where merchants operate in different timezones (Maria in New York, James in Los Angeles).
- Queries like "sales from the last 24 hours" must work consistently regardless of the workspace's configured timezone.

### Default Values

- All `created_at` columns: `DEFAULT NOW()`
- All `updated_at` columns: Automatically updated via Django's `auto_now=True` or a database-level trigger.
- All `deleted_at` columns: `DEFAULT NULL`

### Updated_at Management

In MVP, `updated_at` is managed by Django's `auto_now=True` on the model field. For production-grade applications, a database trigger or PostgreSQL's `moddatetime` extension is more reliable (it fires regardless of how the row is modified). Django's `auto_now` is sufficient for MVP.

---

## 4. Timezone Handling

### Decision: UTC for storage, timezone-aware workspace display

| Layer | Timezone | Rationale |
|---|---|---|
| **Database storage** | UTC | Universal standard; no ambiguity. All `TIMESTAMPTZ` values stored as UTC. |
| **API responses** | UTC (ISO 8601) | Standard for machine-to-machine communication. |
| **UI display** | Workspace-configured timezone | Stored in `workspaces_businessprofile.timezone`. Converted at the presentation layer. |

### Implementation

- Django's `USE_TZ = True` is set in `settings.py`. All `DateTimeField` values are timezone-aware.
- The workspace's timezone is stored in `BusinessProfile.timezone` (IANA format: `'America/New_York'`, `'America/Los_Angeles'`, `'UTC'`, etc.).
- At the API layer, timestamps are returned in ISO 8601 with timezone offset: `2026-07-01T14:30:00+00:00`.
- Dashboard aggregations (e.g., "today's sales") must convert UTC timestamps to the workspace's timezone before bucketing. This is a performance consideration — for large datasets, consider storing a `date` column in the workspace's timezone as a denormalized field.

---

## 5. Currency Handling

### Decision: Single currency per workspace (MVP), ISO 4217 code stored in BusinessProfile

| Property | Decision |
|---|---|
| **MVP scope** | Single currency per workspace |
| **Storage** | `VARCHAR(3)` ISO 4217 code (e.g., `'USD'`, `'EUR'`, `'GBP'`) |
| **Default** | `'USD'` |
| **Location** | `workspaces_businessprofile.currency` |
| **Formatting** | Determined at the presentation layer based on the currency code |
| **Exchange rates** | Not in scope for MVP |

### Future Multi-Currency Path

1. Add `currency` to `Sale` and `Expense` (allowing per-transaction overrides).
2. Add a `currency_conversion_rates` table with source, target, rate, and effective_date.
3. Add `base_currency` to `BusinessProfile` for consolidated reporting.
4. All monetary columns already use `DECIMAL` type, which supports any currency with appropriate decimal scaling.

---

## 6. Soft Delete Implementation

### Decision: `deleted_at TIMESTAMPTZ NULL` pattern

| Aspect | Decision |
|---|---|
| **Marker** | `deleted_at` timestamp (NULL = active, non-NULL = deleted) |
| **Boolean alternative** | Rejected — provides no information about *when* the deletion occurred |
| **Query filtering** | All queries implicitly include `WHERE deleted_at IS NULL` |
| **Indexing** | Index `deleted_at` on tables with high volume to avoid scanning deleted records |
| **Unique constraints** | Partial unique indexes that exclude soft-deleted records |

### Partial Unique Index Pattern (PostgreSQL)

For constraints like SKU uniqueness that should not apply to soft-deleted records:

```sql
CREATE UNIQUE INDEX uq_products_sku_workspace_active
ON inventory_product (workspace_id, sku)
WHERE sku IS NOT NULL AND deleted_at IS NULL;
```

This allows a new product to reuse the SKU of a deleted product without constraint violation.

### Entity-Specific Soft Delete Rules

| Entity | Strategy | Notes |
|---|---|---|
| `User` | `is_active = false` | Django convention. Cannot use `deleted_at` due to `AbstractUser`. |
| `Workspace` | `deleted_at` timestamp | 30-day grace period before permanent purge. |
| `Product` | `deleted_at` timestamp | Also has `is_active` for disabling without full deletion. |
| `Customer` | `deleted_at` timestamp | Sales history preserved; customer profile hidden. |
| `Sale` | `deleted_at` timestamp | Sales are never truly deleted — status changes to `cancelled`. |
| `SaleItem` | CASCADE with Sale | No independent soft delete. |
| `Payment` | `deleted_at` timestamp | Financial records preserved. |
| `Expense` | `deleted_at` timestamp | Financial records preserved. |
| `Category` | `deleted_at` timestamp | Products become uncategorized. |
| `Staff` (Membership) | Hard delete | No historical value in preserving old memberships. |
| `Notification` | Hard delete | Auto-deleted after 30 days. |
| `InventoryMovement` | No delete (immutable) | Append-only audit trail. |
| `AuditLog` | No delete (immutable) | Append-only compliance record. |

### Data Purging

Soft-deleted records that reached the end of their retention period should be hard-deleted via a scheduled job (cron or Celery Beat):

```sql
DELETE FROM workspace WHERE deleted_at IS NOT NULL AND deleted_at < NOW() - INTERVAL '30 days';
```

---

## 7. Indexing Strategy

### Principles

1. **Every foreign key gets an index.** This is non-negotiable for join performance.
2. **Frequently filtered columns get indexes.** `workspace_id` is the most common filter across all workspace-scoped tables.
3. **Composite indexes for common query patterns.** The dashboard queries `(workspace_id, created_at)` range queries frequently.
4. **Covering indexes where possible.** Include all columns needed for a common query to avoid table heap lookups.
5. **Avoid over-indexing.** Every index slows down writes. For MVP volumes (< 10K products, < 50K transactions per workspace), the query planner can use sequential scans efficiently for small tables.

### Recommended Indexes Per Table

(See `docs/database-schema.md` — Indexes sections for each table.)

### Index Maintenance

- **PostgreSQL:** `ANALYZE` runs automatically with autovacuum. Index bloat is not a concern at MVP volumes.
- **Monitoring:** Use `pg_stat_user_indexes` to identify unused indexes after launch.

---

## 8. Full-Text Search

### Decision: Use database `ILIKE`/`LIKE` for MVP; migrate to full-text search (PostgreSQL `tsvector`) if performance demands it.

### Rationale
- At MVP volumes (hundreds to low thousands of records per workspace), `ILIKE` queries with B-Tree indexes on the leading edge perform adequately.
- Use `pg_trgm` extension for fuzzy matching if needed: `CREATE INDEX idx_products_name_trgm ON inventory_product USING gin (name gin_trgm_ops);`

### Future Path
- Add `tsvector` column for Product name/description and Customer name/notes.
- Use PostgreSQL `ts_rank()` for relevance-ranked results.
- For cross-workspace search or full-text across modules, consider Elasticsearch or Meilisearch post-MVP.

---

## 9. JSONB Usage

### Decision: Use JSONB only where schema is inherently dynamic

| Table | Column | Purpose |
|---|---|---|
| `common_auditlog` | `changes` | Stores before/after snapshots. Schema varies by entity type. |
| `common_auditlog` | `metadata` | Flexible metadata like IP, user agent, correlation ID. |

### What JSONB Is NOT Used For

- **Product attributes** — EAV or JSONB for variable product attributes (size, color, material) is explicitly deferred to post-MVP. MVP products have fixed fields only.
- **Customer preferences** — Not yet needed. Future scope.
- **Configuration** — Use dedicated columns or a settings table.

---

## 10. Denormalization Decisions

### Denormalized Fields

| Field | Source | Rationale | Update Strategy |
|---|---|---|---|
| `product.current_stock` | Computed from InventoryMovements | Avoids O(n) scan of movements on every product read. | Updated atomically on every movement insertion. |
| `customer.total_visits` | COUNT of Sales | Avoids COUNT query on every customer read. | Updated on sale creation when customer is referenced. |
| `customer.total_spend` | SUM of Sale totals | Avoids SUM query on every customer read. | Updated on sale creation. |
| `customer.last_visit_date` | MAX of Sale dates | Avoids MAX query. | Updated on sale creation. |
| `sale.paid_amount` | SUM of Payments | Avoids SUM query on every sale read; needed for status computation. | Updated on payment creation. |

### Risks & Mitigations

| Risk | Mitigation |
|---|---|
| **Stale denormalized data** | All updates happen within the same transaction as the source operation. Consistency is guaranteed by atomicity. |
| **Write amplification** | Acceptable at MVP volumes. If performance becomes an issue, move to a background job for customer metric computation. |
| **Multiple code paths** | All mutations go through service-layer functions, not direct ORM writes. This centralizes denormalized updates. |

### What Is NOT Denormalized

- **Dashboard KPIs** (today's revenue, expenses) — computed fresh on each dashboard load. For MVP volumes, this is fast enough. Future: materialized views or Redis counters.

---

## 11. Concurrency Control

### Decision: Optimistic locking with `select_for_update()` for critical paths

| Operation | Strategy | Details |
|---|---|---|
| Sale creation | Pessimistic lock | `Product.objects.select_for_update().filter(id__in=product_ids)` before stock check/deduction |
| Payment recording | Pessimistic lock | Lock the Sale row to prevent concurrent payments exceeding total |
| Customer metric update | No lock (acceptable race) | Lost update on `total_visits` is tolerable for MVP; rare concurrent writes to same customer |
| Product update | Optimistic | Use `updated_at` version check or `F()` expressions to avoid race conditions on stock |

### PostgreSQL Isolation Level

- Default: `READ COMMITTED` (Django default). Sufficient for most operations.
- For sale creation: use `select_for_update()` which uses `SELECT ... FOR UPDATE` to lock product rows, preventing concurrent stock deductions.

### Race Condition: Stock Deduction

Two concurrent sale requests for the same product:

1. Request A reads `current_stock = 5`.
2. Request B reads `current_stock = 5`.
3. Request A deducts 3 → writes `current_stock = 2`.
4. Request B deducts 4 → writes `current_stock = 1` (should fail because 4 > 2).

**Without locking:** Both succeed, stock becomes inconsistent.

**With SELECT FOR UPDATE:**
1. Request A acquires row lock on Product.
2. Request B waits for the lock.
3. Request A deducts 3 → writes `current_stock = 2`, releases lock.
4. Request B acquires lock, reads `current_stock = 2`, attempts to deduct 4 → CHECK constraint `current_stock >= 0` fails → ROLLBACK.

---

## 12. Data Retention & Archiving

| Entity | Retention | Archiving Policy |
|---|---|---|
| Active records | Indefinite | Never archived while active. |
| Soft-deleted Workspace | 30 days | Hard-deleted after 30 days via scheduled job. |
| Soft-deleted records (other entities) | 90 days | Hard-deleted after 90 days via scheduled job. |
| AuditLogs | 12 months | Move to cold storage (Parquet/S3) after 12 months. |
| Notifications | 30 days after read | Hard-deleted after 30 days (`expires_at`). |
| InventoryMovements | Indefinite | Append-only; never deleted. |

### Archiving Implementation

- For MVP, no archiving is implemented. All data lives in the primary database indefinitely.
- Post-MVP, archiving uses a scheduled job that:
  1. Exports records to CSV/Parquet files.
  2. Uploads files to object storage (S3, GCS).
  3. Deletes archived records from the primary database.
  4. Updates indexes.

---

## 13. Future Compatibility

### Multi-Workspace (Multi-Location) Support

The schema is already compatible:
- `workspace_id` FK on all tenant-scoped tables enables multiple workspaces per user.
- `workspaces_workspacemembership` supports user membership across workspaces.
- No schema changes are needed to support a user owning or working in 5 workspaces.

### Multi-Branch / Inventory Transfers

Future schema changes:
- Add `from_location_id` and `to_location_id` to `InventoryMovement` for transfer tracking.
- Add a `Location` model (with FK to Workspace) representing a physical store, warehouse, or truck.
- Add `location_id` to `Product` (default stock location) and `Sale` (point-of-sale location).

### Supplier Management

Future schema additions:
- `Supplier` model (workspace-scoped, with contact info).
- `PurchaseOrder` (header + line items, linked to Products).
- `PurchaseOrderReceipt` (inbound movement linked to PO).

### E-Commerce Storefront

- The existing `Product`, `Category`, and `Customer` schemas are compatible with a public API.
- Add `is_visible_online` flag to Product.
- Add `online_inventory` (separate allocation) or shared stock pool.

### Tax Engine

- Add `tax_rate` to Product (per-product override) and `tax_rate_id` to Sale (per-sale override).
- Add `TaxRate` model with jurisdiction, percentage, and applicability rules.

### Gift Cards & Loyalty

- Add `GiftCard` model (workspace-scoped, balance tracking).
- Add `LoyaltyProgram` and `LoyaltyPoints` models.

---

## 14. Potential Performance Bottlenecks

| # | Bottleneck | Risk Level | Mitigation |
|---|---|---|---|
| 1 | **Dashboard aggregation queries** — computing today's revenue, expenses, profit across multiple tables without indexes. | Medium | Composite indexes on `(workspace_id, created_at)` for Sale, Expense, and Payment tables. |
| 2 | **Customer metric denormalization** — writing to `total_visits`, `total_spend`, `last_visit_date` on every sale. | Low | All writes are within the same transaction as the sale. At MVP volumes (< 50K sales), the overhead is negligible. |
| 3 | **UUID index fragmentation** — random insertion into B-Tree indexes causing page splits. | Medium | Mitigated by PostgreSQL's MVCC and autovacuum. Keep `shared_buffers` at 25% of RAM. |
| 4 | **Soft-delete record accumulation** — scanning through soft-deleted records on every query. | Low (MVP) → Medium (growth) | Add `WHERE deleted_at IS NULL` to all queries. Index `deleted_at`. Schedule purge jobs. |
| 5 | **Full-table scans on small tables** — lookup tables like Role, Permission are tiny. | None | Not a bottleneck at any scale. |
| 6 | **Stock deduction under high concurrency** — row-level locking on Product during peak sales. | Low (MVP) | For MVP volumes (< 100 concurrent users), contention is unlikely. Monitor and shard by workspace if needed. |
| 7 | **JSONB query performance** — querying inside AuditLog JSONB without GIN indexes. | Low | Audit logs are queried infrequently. Add GIN indexes if analytics on audit data becomes common. |

---

## 15. Scaling Recommendations

### MVP (Phase 1–4)

| Resource | Recommendation |
|---|---|
| **Database** | PostgreSQL 16+ on free-tier (Railway, Render, Fly.io) |
| **Connection pool** | `psycopg2` connection pooling or `pgbouncer` |
| **Memory** | 1 GB RAM (PostgreSQL `shared_buffers` = 256 MB) |
| **Storage** | 10 GB SSD |
| **Backups** | Automated daily backups (platform-provided) |

### Growth Stage (Phase 5)

| Concern | Recommendation |
|---|---|
| **Read replicas** | Add 1–2 read replicas for dashboard queries and reporting. |
| **Connection pooling** | Deploy `pgbouncer` in transaction pooling mode. |
| **Caching** | Add Redis for dashboard KPI caching (TTL: 30 seconds). |
| **Materialized views** | Create materialized views for dashboard aggregates; refresh every 5 minutes. |
| **Horizontal scaling** | Separate tenants into dedicated database instances (by workspace_id hash). |
| **Query optimization** | Use `EXPLAIN ANALYZE` on slow queries; add missing indexes. |

### Long-Term

| Concern | Recommendation |
|---|---|
| **Sharding** | Hash-based sharding on `workspace_id`. Application-routed queries. |
| **Citus (PostgreSQL sharding)** | Use pg_distributed for automatic sharding across nodes. |
| **Read replicas** | 3+ replicas for analytics and reporting workloads. |
| **Archival** | Automated archival of records older than 12 months to cold storage. |

---

## 16. Trade-offs Made

| # | Trade-off | Chose | Over | Rationale |
|---|---|---|---|---|
| 1 | **Primary key type** | UUID v4 | Auto-increment integer | Security (non-predictable), distributed readiness, merge safety. Sacrificed index insertion performance and storage. |
| 2 | **Soft delete execution** | `deleted_at` timestamp | Boolean `is_deleted` flag | Timestamps provide audit trail and enable scheduled purging. Sacrificed simplicity. |
| 3 | **Stock tracking** | Materialized `current_stock` + append-only movements | Computed-on-read from movements only | O(1) reads with O(n) write amplification (1 extra write per movement). Sacrificed write simplicity for read performance. |
| 4 | **Customer metrics** | Denormalized on Customer row | Computed-on-read (COUNT/SUM) | Avoids expensive aggregation on every customer list view. Sacrificed write simplicity and risked staleness (mitigated by transactional updates). |
| 5 | **Payment → Sale coupling** | Payment must reference a Sale | Standalone payments allowed | MVP simplicity. Future: add `sale_id` nullable to support standalone payments (deposits, gift card purchases). |
| 6 | **Multi-tenancy model** | Shared DB, shared schema, row-level isolation | Separate databases or schemas | Operational simplicity; no per-tenant provisioning. Sacrificed absolute data isolation and noise isolation (one tenant can impact others' query performance). |
| 7 | **Decimal precision** | 2 decimal places for money | 4 decimal places | Simpler, standard for 95% of use cases. Future: ALTER COLUMN if needed. |
| 8 | **Category hierarchy** | Flat (no parent_id) | Adjacency list or nested sets | MVP simplicity. Future: add `parent_id` (self-referential FK). |
| 9 | **SaleItem unit_price** | Snapshot at sale time | Reference to Product.unit_price | Historical accuracy — price changes don't affect past sales. Sacrificed simplicity (must store duplicate data). |
| 10 | **JSONB for audit logs** | JSONB for changes/metadata | Separate tables per action type | Schema flexibility without migration overhead. Sacrificed queryability and referential integrity. |
| 11 | **Database-level CHECK constraints** | Used for critical invariants (positive amounts, non-negative stock) | Application-only validation | Defense-in-depth. Some constraints (sale total = sum of items) are not feasible in SQL and remain in the application layer. |
| 12 | **Concurrency isolation** | Optimistic + selective pessimistic locking (`select_for_update`) | Full serializable isolation | Simpler, better performance. Sacrificed absolute concurrency safety for specific critical paths only. |

---

*This document captures the rationale behind every significant database design decision. It should be consulted before changing schemas, adding indexes, or modifying data access patterns.*
