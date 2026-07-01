# MerchantHub — Product Requirements Document

**Version:** 1.0  
**Status:** Draft  
**Last Updated:** July 1, 2026

---

## Vision Statement

MerchantHub enables small and medium-sized businesses to operate their entire retail or service operation from a single, unified online dashboard. We replace the patchwork of spreadsheets, paper ledgers, standalone POS systems, and disconnected tools with one integrated platform that manages inventory, sales, customers, expenses, and payments — accessible from anywhere, on any device.

---

## Problem Statement

Small merchants and service providers face a fragmented tool landscape. They typically manage inventory in a spreadsheet, track sales on a receipt book or basic POS, handle customers through messaging apps, and reconcile finances manually at month-end. This leads to:

- **Data silos** — information lives in disconnected systems with no single source of truth.
- **Operational overhead** — manual data entry across multiple tools wastes hours each week.
- **Cash flow blind spots** — without integrated expense and payment tracking, profitability is opaque.
- **Scaling friction** — adding locations or staff requires duplicating processes, not extending the system.
- **Customer attrition** — no centralized customer history means missed opportunities for loyalty, follow-ups, and personalized service.

Existing solutions are either too simplistic (spreadsheets, single-purpose apps) or too complex and expensive (ERP systems designed for enterprises with dedicated IT staff). There is a gap for a modern, affordable, multi-tenant platform tailored to the needs of growing merchants.

---

## Goals

1. **Deliver a functional MVP** within a hackathon timeline that demonstrates end-to-end commerce workflows: inventory management, sales recording, customer tracking, expense logging, and payment reconciliation.
2. **Establish a multi-tenant architecture** from day one so that the platform can support multiple businesses on a single deployment with strong data isolation.
3. **Provide real-time financial visibility** by integrating expenses, sales, and payments into a coherent dashboard with profit calculations.
4. **Build for extensibility** — the module structure, API-first design, and base model abstractions should accommodate future modules (e-commerce storefront, invoicing, advanced reporting, POS integration) without rewrites.
5. **Achieve production-readiness** with automated testing, API documentation via OpenAPI/Spectacular, and deployment configurations suitable for cloud hosting.

---

## Non-Goals

- **Not a general-purpose ERP** — we do not target manufacturing, supply chain logistics, HR, or procurement workflows.
- **Not a payment gateway** — we integrate with third-party payment processors (via the payments module) rather than building our own.
- **Not a POS hardware driver** — the MVP does not interact with barcode scanners, receipt printers, or payment terminals; these are future integrations.
- **No native mobile apps** — the MVP is a responsive web application; native mobile apps are post-MVP.
- **No e-commerce storefront** — MerchantHub is a back-office operations platform; a customer-facing storefront is future scope.
- **No AI/ML features** — predictive analytics, demand forecasting, and automated categorization are post-MVP enhancements.

---

## Target Users

| Segment | Description |
|---|---|
| **Micro-merchants** | Sole proprietors and freelancers (retail stalls, food vendors, service providers) managing < 500 SKUs and < 50 daily transactions. |
| **Small business owners** | Teams of 2–20 employees operating 1–3 locations, managing 500–5,000 SKUs and 50–500 daily transactions. |
| **Growth-stage merchants** | Multi-location businesses with 5–50 employees, needing basic role-based access, consolidated reports, and multi-location inventory visibility. |

---

## User Personas

### Persona 1: Maria — The Boutique Owner

**Demographics:** Age 34, owns a women's fashion boutique in a mid-sized city, employs 2 part-time staff.  
**Technical proficiency:** Comfortable with web apps, uses Instagram for marketing, tracks inventory in Google Sheets.  
**Pain points:**  
- Spends 3–4 hours per week reconciling sales from the card terminal against her spreadsheet.  
- Often overstocks popular sizes and understocks slow movers because manual tracking is error-prone.  
- Has no easy way to see which customers are her most loyal or when they last visited.  
**Needs:** Simple inventory management, sales recording, customer profiles, and a clear profit dashboard.

### Persona 2: James — The Mobile Food Vendor

**Demographics:** Age 28, operates 2 food trucks, employs 4 shift workers.  
**Technical proficiency:** Tech-savvy, uses Square for payments, tracks expenses in separate apps.  
**Pain points:**  
- Juggles 2 separate Square accounts and manually aggregates data to understand per-truck profitability.  
- Employees sometimes forget to log cash sales, leading to discrepancies at end of day.  
- No centralized view of ingredient costs vs. revenue.  
**Needs:** Multi-location (workspace) support, cash/card payment tracking, expense logging tied to locations.

### Persona 3: Priya — The Scaling Salon Chain

**Demographics:** Age 42, owns 3 hair salons (45 employees total), manages via paper schedules and Excel.  
**Technical proficiency:** Low — uses email and basic web browsing, relies on her assistant for digital tasks.  
**Pain points:**  
- Cannot compare performance across locations without manual report assembly.  
- Staff scheduling and commission tracking are entirely manual.  
- Wants to introduce gift cards and loyalty programs but has no system to support them.  
**Needs:** Role-based access (owner, manager, staff), multi-workspace dashboard, customer history per location, integrated payment tracking.

---

## User Journeys

### Journey 1: Onboarding & First Sale

1. Maria signs up, creates her workspace (named "Maria's Boutique").
2. She adds her first 10 products — names, prices, and stock quantities.
3. A walk-in customer purchases a dress. Maria records the sale in the dashboard: selects the product, enters quantity, chooses payment type (card).
4. The system deducts inventory, logs the sale, and updates the dashboard revenue metrics in real time.
5. Maria optionally records the customer's name and phone number, creating a customer profile.
6. She sees her updated profit (revenue minus COGS) on the dashboard.

### Journey 2: Daily Operations & Expense Tracking

1. James starts his shift, logs into the dashboard for Truck A.
2. He records a supplier delivery of ingredients as an expense, categorizing it under "Cost of Goods Sold."
3. Throughout the day, cash and card sales are logged. Card payments are batch-matched against the total.
4. At closing, James reconciles: the dashboard shows expected cash on hand vs. actual, highlighting any discrepancies.
5. He switches to Truck B's workspace and reviews its daily summary side-by-side.

### Journey 3: Customer Management

1. Priya looks up a regular customer who called to book an appointment.
2. She finds the customer profile, which shows visit history, total spend, and last visit date.
3. She notes the customer's preferred service and adds a note about a recent product allergy.
4. Later, she uses the customer list to identify clients who haven't visited in 3+ months for a re-engagement campaign (exported via CSV).

---

## MVP Scope

### Core Modules

| Module | Key Features |
|---|---|
| **Workspaces** | Create/manage businesses, user invitation and role assignment (owner, manager, staff), workspace switching |
| **Accounts & Auth** | Registration, login/logout, password reset, JWT-based API authentication, profile management |
| **Inventory** | Product CRUD, stock quantities, cost price tracking, low-stock alerts (manual thresholds), category tagging |
| **Sales** | Record sales (cash, card, transfer), automatic inventory deduction, sale history with filters, basic receipts |
| **Customers** | Customer CRUD, purchase history linked to sales, total spend and visit count metrics, search/filter |
| **Payments** | Record payments received (link to sales), payment method tracking, outstanding balance tracking |
| **Expenses** | Expense CRUD, category classification (COGS, operating, utilities, etc.), link to workspaces |
| **Dashboard** | Summary KPIs (today's revenue, total sales count, low-stock items, recent activity feed), period-over-period comparison |

### Cross-Cutting Concerns

- Multi-tenant data isolation via workspace-scoped queries
- RESTful API with OpenAPI documentation via drf-spectacular
- Django admin for super-admin oversight
- SQLite for development (configurable to PostgreSQL for production)

### Excluded from MVP

- Invoice generation and emailing
- Barcode/label printing
- Employee time tracking
- E-commerce storefront
- Mobile apps
- AI-driven insights
- Tax reporting
- Multi-currency support
- Gift cards and loyalty programs

---

## Future Scope

- **E-commerce Storefront** — public product catalog, online ordering, inventory sync
- **Advanced Reporting** — configurable reports, export to PDF/Excel, scheduled email reports
- **Invoicing & Billing** — generate invoices, send via email, track payment status
- **POS Integration** — REST API for third-party POS terminals and barcode scanners
- **Inventory Transfers** — move stock between multiple workspace locations
- **Supplier Management** — purchase orders, supplier profiles, reorder point automation
- **Employee Management** — time tracking, commission calculation, role templates
- **Gift Cards & Loyalty** — issue, redeem, track balances
- **Tax Engine** — automatic tax calculation per product/location
- **Multi-Currency** — currency conversion, per-workspace currency settings
- **Mobile App** — companion apps for iOS/Android (inventory scanning, quick sale entry)
- **AI Features** — demand forecasting, anomaly detection in expenses/sales, auto-categorization
- **Integrations** — Stripe/PayPal/M-Pesa payment gateways, Shopify/ Square sync, accounting software (QuickBooks, Xero)

---

## Functional Requirements

### FR-01: Workspace Management
- Users can create, rename, and delete workspaces.
- Workspace owners can invite users by email with a role (owner, manager, staff).
- Users can switch between workspaces they belong to.
- All data is scoped to a workspace — users only see data within their current workspace context.

### FR-02: User Authentication
- Users can register with email and password.
- Authentication via JWT tokens (access + refresh) using `djangorestframework-simplejwt`.
- Password reset via email link (token-based, time-limited).
- Profile editing (name, phone number, avatar).

### FR-03: Product Inventory
- Create, read, update, delete products within a workspace.
- Each product has: name, description, SKU (optional), category, unit price, cost price, current stock quantity, low-stock threshold.
- Stock quantity decreases automatically when a sale is recorded.
- Low-stock warning indicator on the dashboard and product list.

### FR-04: Sales Recording
- Record a sale: select products, enter quantities, compute total automatically.
- Support multiple payment methods per sale (split payments).
- Cash, card, and bank transfer as payment method options.
- Automatic inventory deduction on sale creation.
- Sale history with date range filtering, search by product/customer.

### FR-05: Customer Profiles
- Create customer records with name, phone, email, and notes.
- Link sales to customer profiles automatically.
- Display per-customer metrics: total visits, total spend, average transaction value, last visit date.
- Search customers by name or phone number.

### FR-06: Payment Tracking
- Record payments received (reference to sale, amount, method, date).
- Track outstanding balances (sales recorded but not fully paid).
- Payment history per customer.

### FR-07: Expense Management
- Record expenses with amount, category, date, description, and optional receipt attachment.
- Predefined categories: Cost of Goods Sold, Rent, Utilities, Salaries, Marketing, Maintenance, Other.
- View expenses by category and date range.

### FR-08: Dashboard
- Live KPI tiles: today's revenue, total sales, total expenses, net profit (revenue — expenses — COGS).
- Low-stock products list (products below threshold).
- Recent activity feed (latest sales, expenses, payments).
- Period-over-period comparison (today vs. yesterday, this week vs. last week).

---

## Non-Functional Requirements

### NFR-01: Performance
- API response times < 200ms for p95 under typical load (100 concurrent users, < 10K records per workspace).
- Dashboard load time < 2 seconds for workspaces with up to 50K records.
- Database queries scoped by workspace_id at the ORM level to avoid cross-tenant leaks and maintain query performance.

### NFR-02: Security
- All API endpoints behind JWT authentication (except registration and login).
- Workspace-scoped data access enforced at the view layer and ORM layer.
- Passwords hashed with Django's default PBKDF2 algorithm.
- CSRF protection for session-based admin; API uses token-based auth.
- Input validation and sanitization on all endpoints.

### NFR-03: Reliability
- Graceful error responses with consistent JSON structure (`{error: string, code: string}`).
- Database transactions for operations spanning multiple models (e.g., creating a sale + deducting inventory).
- Automated test coverage > 80% for critical business logic (sales, inventory deduction, payment reconciliation).

### NFR-04: Scalability
- Stateless API servers — horizontal scaling via load balancer.
- Database can be swapped from SQLite to PostgreSQL with minimal changes.
- Workspace isolation ensures no tenant can impact another tenant's performance or data.

### NFR-05: Maintainability
- Modular Django apps with clear ownership boundaries (inventory, sales, payments, expenses, customers, accounts, workspaces, dashboard).
- Base model abstractions (`BaseModel`, `TimeStampedModel`, `UUIDModel`) to eliminate boilerplate.
- OpenAPI schema generated automatically via drf-spectacular for API consumers.
- Code style enforced via consistent patterns across all modules.

### NFR-06: Usability
- Responsive web design (mobile-first) — functional on phones and tablets.
- Consistent UI components and navigation patterns.
- Clear error messages and inline form validation.

---

## Business Modes

MerchantHub will offer two business modes to accommodate both free-tier users and growth-stage businesses:

### Starter Mode (Free / Entry-Level)

| Feature | Details |
|---|---|
| Workspaces | 1 workspace |
| Users per workspace | Up to 2 (owner + 1 staff) |
| Products (SKUs) | Up to 100 |
| Transactions | Up to 500 sales + expenses per month |
| Customers | Up to 200 |
| Reports | Basic dashboard KPIs only |
| Data export | CSV export of all modules |
| Support | Community support (docs + email) |
| Hosting | Shared infrastructure |

### Growth Mode (Paid / Subscription)

| Feature | Details |
|---|---|
| Workspaces | Up to 5 workspaces |
| Users per workspace | Up to 20 (role-based: owner, manager, staff) |
| Products (SKUs) | Up to 10,000 |
| Transactions | Unlimited |
| Customers | Unlimited |
| Reports | Full dashboard with period comparisons, advanced filters |
| Data export | CSV + PDF + scheduled email reports |
| Support | Priority email + chat support |
| Integrations | API access for third-party integrations |
| Hosting | Dedicated database option |

> **Note:** Monetization is post-MVP. The MVP implements the full feature set under Starter Mode without hard limits, and the Growth mode feature set is built as a superset. Tier enforcement is implemented at a later stage via a subscription management module.

---

## Assumptions

1. **Internet connectivity** — users have consistent internet access (web app, not offline-first in MVP).
2. **Desktop-primary usage** — the primary workflow is on desktop/laptop; mobile responsiveness is important but secondary in MVP.
3. **Single currency per workspace** — each workspace operates in one currency throughout MVP.
4. **Manual data entry** — all data entry is manual in MVP; no bulk import/export beyond basic CSV (future scope).
5. **Third-party payment processing** — the payments module tracks payments but does not process them; merchants use their existing payment terminals/gateways.
6. **Simple tax model** — MVP assumes tax-inclusive pricing; dedicated tax engine is future scope.
7. **Small-to-medium data volumes** — MVP is optimized for workspaces with < 10,000 products and < 50,000 transactions.
8. **English language only** — MVP UI and documentation are English-only; internationalization is future scope.

---

## Constraints

1. **Timeline** — MVP must be demonstrable within a hackathon timeframe.
2. **Team size** — development is by a small team (1–3 developers).
3. **Technology stack** — Python/Django/DRF backend, HTML/JavaScript frontend (or DRF Browsable API + lightweight frontend). No budget for paid infrastructure or services in MVP.
4. **Deployment** — MVP must be deployable on free-tier cloud hosting (e.g., Render, Railway, Fly.io) with SQLite or free-tier PostgreSQL.
5. **No native mobile** — MVP is limited to responsive web; no native app development capability in the current timeline.
6. **Authentication** — initial MVP uses JWT; full OAuth/SSO integration is future scope.

---

## Success Metrics

| Metric | Target (MVP) | Target (Post-MVP) |
|---|---|---|
| **User onboarding completion** | > 80% of registered users create a workspace and add at least 1 product | > 90% |
| **Daily active users (DAU) / registered users** | > 30% DAU/registered ratio | > 50% |
| **Transactions recorded per active workspace** | > 100 sales + expenses per week | > 500 per week |
| **Time-to-value** | < 5 minutes from signup to first sale recorded | < 2 minutes |
| **Dashboard load time** | < 2 seconds | < 1 second |
| **API uptime** | > 99.5% (hackathon deployment) | > 99.9% |
| **Test coverage** | > 80% for core business logic modules (sales, inventory, payments, expenses) | > 90% |
| **Bug escape rate** | < 5% of merged PRs introduce regressions | < 2% |
| **Hackathon submission quality** | Fully functional MVP, comprehensive README, demo video, live deployment | N/A (portfolio phase) |

---

*This document is a living artifact and will be updated as requirements evolve through development.*
