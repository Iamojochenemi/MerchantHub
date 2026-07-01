# MerchantHub — Engineering Roadmap

**Version:** 1.0  
**Status:** Draft  
**Last Updated:** July 1, 2026  

---

## Overview

This document outlines the engineering phases for MerchantHub, from initial product discovery through hackathon submission and beyond into post-hackathon portfolio enhancement. The roadmap is organized into phases, each with clear deliverables, success criteria, and estimated effort.

```
Phase 0: Product Discovery       ████████░░░░░░░░░░░░   (current)
Phase 1: Foundation & Auth       ████████░░░░░░░░░░░░
Phase 2: Core Business Modules   ████████████████░░░░
Phase 3: Dashboard & Integration ████████████████████░░
Phase 4: Hackathon Polish        ██████████████████████
Phase 5: Portfolio Enhancement   ████████████████████████████████...
```

---

## Phase 0: Product Discovery

**Status:** ✅ In Progress  
**Duration:** 1–2 days  
**Owner:** Lead Architect

### Objectives
- Define the product vision, scope, and constraints.
- Establish the technical architecture and module boundaries.
- Produce living documentation that guides all subsequent phases.

### Deliverables
| Artifact | Description |
|---|---|
| **PRD.md** | Product Requirements Document covering vision, personas, journeys, requirements, metrics |
| **roadmap.md** | This document — phased engineering roadmap |
| **Architecture Decision Records (ADRs)** | Informal notes on key decisions (optional in earliest stage) |

### Key Decisions Made
- **Multi-tenant via workspace scoping** — every model carries a `workspace` FK, and all queries are filtered by the active workspace.
- **Django REST Framework** for API layer with drf-spectacular for OpenAPI schema generation.
- **Custom User model** (`accounts.User`) extending `AbstractUser` for extensibility.
- **UUID primary keys** via `BaseModel` (composing `UUIDModel` + `TimeStampedModel`).
- **Modular app structure** under `apps/` with clear domain boundaries.

### Success Criteria
- [x] PRD reviewed and accepted by stakeholders
- [x] Roadmap defined
- [x] Module boundaries identified
- [x] Base models established

---

## Phase 1: Foundation & Authentication

**Status:** 🔲 Not Started  
**Duration:** 2–3 days  
**Dependencies:** Phase 0 complete

### Objectives
- Implement the multi-tenant workspace foundation.
- Build authentication and user management.
- Establish the shared infrastructure (permissions, serializers, utilities).

### Tasks

| # | Task | Module | Effort |
|---|---|---|---|
| 1.1 | Implement `Workspace` model with invite code generation | workspaces | Medium |
| 1.2 | Implement `WorkspaceMembership` model (user + role + workspace) | workspaces | Medium |
| 1.3 | Build workspace CRUD API endpoints | workspaces | Medium |
| 1.4 | Build workspace invitation (create invite, accept invite) | workspaces | Medium |
| 1.5 | Add `workspace` FK to `BaseModel` for automatic scoping | common | Small |
| 1.6 | Complete `User` model (profile fields, workspace relation) | accounts | Small |
| 1.7 | Implement registration endpoint (creates user + default workspace) | accounts | Medium |
| 1.8 | Implement login endpoint with JWT (access + refresh tokens) | accounts | Medium |
| 1.9 | Implement password reset flow | accounts | Medium |
| 1.10 | Build workspace-aware permission classes (`IsWorkspaceMember`, `IsWorkspaceOwner`) | common | Medium |
| 1.11 | Add workspace context middleware (extract workspace_id from request header) | common | Medium |
| 1.12 | Implement user profile read/update endpoint | accounts | Small |
| 1.13 | Write tests for all auth and workspace flows | accounts, workspaces | Medium |

### Tech Details
- **JWT library:** `djangorestframework-simplejwt`
- **Permission model:** Custom DRF permission classes that verify `WorkspaceMembership`
- **Workspace resolution:** `X-Workspace-ID` header extracted by middleware, attached to `request.workspace`
- **Base model integration:** All models inherit `BaseModel` which includes `workspace = ForeignKey(Workspace)` by default

### Success Criteria
- [ ] User can register, create a workspace, and log in
- [ ] User can invite another user to their workspace
- [ ] Invited user can accept invitation and switch workspaces
- [ ] All API endpoints reject unauthenticated requests
- [ ] Workspace-scoped queries return only data belonging to the current workspace
- [ ] Test coverage > 80% for auth and workspace modules

---

## Phase 2: Core Business Modules

**Status:** 🔲 Not Started  
**Duration:** 4–5 days  
**Dependencies:** Phase 1 complete

### Objectives
- Implement the four core business domains: Inventory, Sales, Payments, and Expenses.
- Each module follows the same pattern: Model → Serializer → ViewSet → URL registration → Tests.
- Sales and Inventory are tightly coupled (inventory deduction on sale).

### Tasks

#### Inventory Module
| # | Task | Effort |
|---|---|---|
| 2.1 | Implement `Category` model (name, description, workspace) | Small |
| 2.2 | Implement `Product` model (name, SKU, price, cost_price, stock, threshold, category, workspace) | Medium |
| 2.3 | Build product CRUD API endpoints with filtering, search, pagination | Medium |
| 2.4 | Implement low-stock query endpoint (products where stock ≤ threshold) | Small |
| 2.5 | Write inventory module tests | Medium |

#### Customers Module
| # | Task | Effort |
|---|---|---|
| 2.6 | Implement `Customer` model (name, phone, email, notes, workspace) | Small |
| 2.7 | Build customer CRUD API endpoints with search | Small |
| 2.8 | Add computed fields: total visits, total spend, last visit date | Medium |
| 2.9 | Write customers module tests | Small |

#### Sales Module
| # | Task | Effort |
|---|---|---|
| 2.10 | Implement `Sale` model (customer, products via line items, total, payment status, workspace) | Medium |
| 2.11 | Implement `SaleItem` model (product, quantity, unit_price, line_total) | Medium |
| 2.12 | Build sale creation endpoint (creates sale, deducts inventory in a transaction) | Large |
| 2.13 | Build sale history endpoint with date filtering, product/customer search | Medium |
| 2.14 | Implement sale status tracking (pending, completed, refunded) | Small |
| 2.15 | Write sales module tests (critical: inventory deduction correctness) | Medium |

#### Payments Module
| # | Task | Effort |
|---|---|---|
| 2.16 | Implement `Payment` model (sale, amount, method, date, reference, workspace) | Small |
| 2.17 | Build payment CRUD endpoints | Small |
| 2.18 | Implement outstanding balance computation (sales total — payments total) | Medium |
| 2.19 | Write payments module tests | Small |

#### Expenses Module
| # | Task | Effort |
|---|---|---|
| 2.20 | Implement `Expense` model (amount, category, date, description, receipt, workspace) | Small |
| 2.21 | Build expense CRUD endpoints with category filtering | Small |
| 2.22 | Write expenses module tests | Small |

### Data Integrity Rules
- **Sales + Inventory:** Creating a sale with line items must deduct stock within an atomic transaction. If stock is insufficient for any item, the entire sale is rejected with a clear error message detailing which products are short.
- **Sales + Customers:** If a customer is attached to a sale, the customer's computed metrics (total visits, total spend) update automatically.
- **Payments + Sales:** Payments are linked to sales. A sale's payment status (paid, partial, unpaid) is derived from the sum of linked payments vs. the sale total.

### Success Criteria
- [ ] Full CRUD for products, customers, sales, payments, and expenses
- [ ] Creating a sale deducts inventory atomically
- [ ] Insufficient stock returns a descriptive error and rolls back the transaction
- [ ] Customer metrics update automatically with new sales
- [ ] Payment status derives correctly from linked payments
- [ ] All endpoints are workspace-scoped and authenticated
- [ ] Test coverage > 80% for each module

---

## Phase 3: Dashboard & Integration

**Status:** 🔲 Not Started  
**Duration:** 2–3 days  
**Dependencies:** Phase 2 complete

### Objectives
- Build the unified dashboard API that aggregates data across all modules.
- Wire up URL routing for all modules at the project level.
- Add drf-spectacular schema generation and configure the browsable API.

### Tasks

| # | Task | Effort |
|---|---|---|
| 3.1 | Implement dashboard KPI endpoint | Large |
| 3.2 | Implement recent activity feed (union of latest sales, expenses, payments) | Medium |
| 3.3 | Implement low-stock indicator endpoint | Small |
| 3.4 | Implement period-over-period comparison logic | Medium |
| 3.5 | Register all app URLs in project-level `urls.py` | Small |
| 3.6 | Configure drf-spectacular for OpenAPI schema generation | Small |
| 3.7 | Add schema/API docs endpoints (`/api/schema/`, `/api/docs/`) | Small |
| 3.8 | Build a lightweight HTML dashboard (template-based views or a simple frontend SPA) | Large |
| 3.9 | Add CORS headers configuration for future frontend separation | Small |
| 3.10 | End-to-end integration testing across all modules | Medium |

### Dashboard KPI Endpoint Design

```json
GET /api/dashboard/summary/?period=today
{
  "revenue": { "today": 1250.00, "yesterday": 980.00, "change_pct": 27.55 },
  "sales_count": { "today": 42, "yesterday": 35, "change_pct": 20.00 },
  "expenses": { "today": 320.00, "yesterday": 280.00, "change_pct": 14.29 },
  "net_profit": { "today": 930.00, "yesterday": 700.00, "change_pct": 32.86 },
  "low_stock_count": 5,
  "recent_activity": [
    { "type": "sale", "id": "...", "description": "Sale #1023 — $45.00", "timestamp": "..." },
    { "type": "expense", "id": "...", "description": "Supplier delivery — $120.00", "timestamp": "..." },
    ...
  ]
}
```

### Success Criteria
- [ ] Dashboard KPI endpoint returns accurate aggregate data across all modules
- [ ] Recent activity feed shows cross-module events in chronological order
- [ ] OpenAPI schema is generated and accessible via `/api/schema/`
- [ ] All module URLs are wired and accessible
- [ ] Lightweight frontend displays dashboard data (if built)
- [ ] Period-over-period comparisons are mathematically correct

---

## Phase 4: Hackathon Polish

**Status:** 🔲 Not Started  
**Duration:** 2–3 days  
**Dependencies:** Phase 3 complete

### Objectives
- Prepare the project for hackathon submission.
- Focus on quality, documentation, demo readiness, and deployment.

### Tasks

| # | Task | Effort |
|---|---|---|
| 4.1 | Comprehensive README with project overview, setup instructions, and architecture diagram | Medium |
| 4.2 | Add `CONTRIBUTING.md` with development guidelines | Small |
| 4.3 | Create and test a production-ready Dockerfile + docker-compose.yml | Medium |
| 4.4 | Add/configure PostgreSQL support via environment variables | Small |
| 4.5 | Configure environment variable management (django-environ or python-decouple) | Small |
| 4.6 | Add `seed_data` management command (demo data for hackathon judges) | Medium |
| 4.7 | Create `POSTMAN_COLLECTION.md` or export ready-to-import collection | Medium |
| 4.8 | Run full test suite and achieve > 80% coverage | Medium |
| 4.9 | Performance test with realistic data volumes | Small |
| 4.10 | Security audit (ensure no workspace data leakage, auth bypasses, or hardcoded secrets) | Medium |
| 4.11 | Create demo video or demo script (walkthrough of all user journeys) | Medium |
| 4.12 | Deploy to free-tier cloud hosting (Render/Railway/Fly.io) | Medium |
| 4.13 | Final code review — clean up TODOs, remove debug code, ensure consistent code style | Medium |
| 4.14 | Write a brief architecture overview doc for judges | Small |

### Deployment Architecture (Hackathon)

```
                   ┌─────────────┐
                   │  Cloudflare  │
                   │   DNS/CDN    │
                   └──────┬──────┘
                          │
                   ┌──────▼──────┐
                   │   Gunicorn   │
                   │  (4 workers) │
                   └──────┬──────┘
                          │
              ┌───────────┴───────────┐
              │                       │
      ┌───────▼───────┐     ┌────────▼────────┐
      │   PostgreSQL   │     │  Redis (future) │
      │   (Railway)    │     │  (caching/queue)│
      └───────────────┘     └─────────────────┘
```

### Success Criteria
- [ ] Project is deployed and accessible via a public URL
- [ ] Demo data can be loaded with a single management command
- [ ] README passes the "new developer can set up in 5 minutes" test
- [ ] Test suite passes with > 80% code coverage
- [ ] No known security vulnerabilities
- [ ] Demo video/script covers all user journeys

---

## Phase 5: Portfolio Enhancement (Post-Hackathon)

**Status:** 🔲 Not Started  
**Duration:** Ongoing  
**Dependencies:** Phase 4 complete

### Objectives
- Transform the hackathon project into a polished portfolio piece.
- Add depth and breadth to demonstrate engineering maturity.

### Enhancement Areas

#### 5.1 — Testing & Quality

| Task | Effort | Impact |
|---|---|---|
| Add integration tests covering full user journeys | Medium | High |
| Add property-based tests for inventory deduction logic | Medium | High |
| Set up CI/CD pipeline (GitHub Actions: lint → test → build → deploy) | Medium | High |
| Add performance benchmarks with `django-silk` or similar | Small | Medium |
| Implement pre-commit hooks (ruff, black, isort) | Small | Medium |

#### 5.2 — Frontend

| Task | Effort | Impact |
|---|---|---|
| Build a React/Vue SPA frontend with the DRF API | Large | Very High |
| Add real-time updates via WebSocket (Django Channels) for dashboard | Large | High |
| Implement mobile-responsive design with Tailwind CSS | Medium | High |
| Add dark mode | Small | Medium |

#### 5.3 — API & Developer Experience

| Task | Effort | Impact |
|---|---|---|
| Add rate limiting (django-ratelimit or DRF throttling) | Small | Medium |
| Add API versioning (URL-based or header-based) | Small | Medium |
| Implement HATEOAS links in API responses | Medium | Medium |
| Add webhook support for external integrations | Large | High |

#### 5.4 — Infrastructure

| Task | Effort | Impact |
|---|---|---|
| Containerize with Docker and publish image to Docker Hub | Medium | High |
| Add docker-compose.prod.yml with PostgreSQL, Redis, Nginx | Medium | High |
| Set up Terraform/Pulumi for cloud infrastructure | Large | Very High |
| Implement Blue/Green deployment strategy | Large | Medium |

#### 5.5 — Feature Expansion

| Task | Effort | Impact |
|---|---|---|
| E-commerce storefront module (product listing, cart, checkout) | Very Large | Very High |
| Invoice generation and email delivery | Large | High |
| Supplier management + purchase orders | Large | High |
| Employee time tracking + commission calculation | Medium | High |
| Gift cards and loyalty programs | Medium | Medium |
| Multi-currency support | Medium | Medium |
| Tax engine with configurable rules | Large | High |

#### 5.6 — Monitoring & Observability

| Task | Effort | Impact |
|---|---|---|
| Add structured logging (structlog or django-std logging to stdout) | Small | High |
| Integrate Sentry for error tracking | Small | High |
| Add health check endpoint (`/health/`) | Small | Medium |
| Set up Prometheus metrics + Grafana dashboard | Medium | High |

### Portfolio Narrative

For hackathon judges and future employers, MerchantHub demonstrates:

- **Clean architecture** — modular Django apps with separation of concerns
- **Multi-tenancy** — real-world SaaS pattern implemented correctly
- **Data integrity** — atomic transactions across domain boundaries
- **API design** — RESTful, documented, testable
- **Security-first mindset** — workspace isolation, JWT auth, input validation
- **Testing discipline** — comprehensive test coverage, not just unit tests
- **DevOps readiness** — Docker, CI/CD, cloud deployment

---

## Timeline Summary

| Phase | Days | Cumulative | Milestone |
|---|---|---|---|
| **Phase 0:** Product Discovery | 1–2 | 1–2 | PRD + roadmap finalized |
| **Phase 1:** Foundation & Auth | 2–3 | 3–5 | Multi-tenant auth working |
| **Phase 2:** Core Business Modules | 4–5 | 7–10 | All CRUD endpoints complete |
| **Phase 3:** Dashboard & Integration | 2–3 | 9–13 | Dashboard API + URL wiring |
| **Phase 4:** Hackathon Polish | 2–3 | 11–16 | Deployed and submitted |
| **Phase 5:** Portfolio Enhancement | Ongoing | — | Continuous improvement |

**Total hackathon timeline:** ~11–16 days (depending on team size and daily availability).

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Scope creep during implementation | Medium | High | Strict adherence to MVP scope defined in PRD |
| Insufficient test coverage under time pressure | Medium | Medium | Write tests alongside code (TDD where practical); enforce coverage threshold in CI |
| SQLite performance issues with demo data | Low | Medium | Test with realistic data volume early; document PostgreSQL migration path |
| Authentication/workspace bugs causing data leaks | Low | Very High | Dedicated security test suite; code review with security checklist |
| Deployment environment differences | Medium | Medium | Docker from day one; test deployment early in Phase 3 |
| Team availability fluctuation | Medium | Medium | Modular architecture allows parallel work; document all interfaces |

---

*This roadmap is a living document. Tasks may be reordered, split, or merged as development progresses and new information emerges.*
