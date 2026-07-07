# MerchantHub

> **A financial operating system for merchants, powered by Nomba's commerce infrastructure.**

MerchantHub is a production-oriented, multi-tenant backend platform that helps small and medium-sized businesses manage inventory, customers, sales, payments, and business operations from a single source of truth.

Built with Django and Django REST Framework, MerchantHub combines secure authentication, workspace-based multi-tenancy, service-oriented architecture, and Nomba payment integration to provide the backend foundation for modern merchant operations.

---

# Why MerchantHub?

Many merchants receive payments every day but still struggle to answer important questions like:

* How much profit did I make today?
* Why doesn't my cash balance match my sales?
* Which customers still owe me money?
* Which products are running low?
* Is my business actually growing?

Most small businesses still rely on notebooks, spreadsheets, manual bookkeeping, and disconnected tools.

MerchantHub aims to eliminate that uncertainty by providing one centralized platform where business operations and financial data work together.

---

# Vision

MerchantHub is designed to become a complete financial operating system for merchants.

Rather than simply recording transactions, the platform transforms business activities into meaningful financial insights that help business owners make informed decisions with confidence.

---

# Features

## Authentication & Security

* JWT Authentication
* User Registration
* Secure Login
* Current User Endpoint
* Protected API Endpoints
* Serializer-based validation

---

## Multi-Tenant Workspace Management

Every registered merchant automatically receives:

* Personal Workspace
* Business Profile
* Owner Workspace Membership
* Workspace Isolation
* Tenant-aware data access

Each merchant's business data remains completely isolated from every other merchant.

---

## Business Operations

### Products

* Create products
* Update products
* Delete products
* Product listing
* SKU support

### Inventory

* Inventory tracking
* Stock quantity updates
* Stock movement history
* Inventory endpoints

### Customers

* Customer management
* Customer CRUD operations

### Sales

* Sale creation
* Multiple sale items
* Sale tracking
* Payment status updates

### Payments

* Payment recording
* Payment verification
* Multiple payment methods
* Payment status management

---

# Nomba Integration

MerchantHub includes a dedicated integration layer for Nomba's payment infrastructure.

Current capabilities include:

* OAuth authentication
* Checkout orchestration
* Payment verification
* Webhook processing
* HMAC signature verification
* Idempotent webhook handling
* Payment reconciliation architecture
* Service-layer payment synchronization

The payment integration is designed so that all payment state transitions flow through a single source of truth, ensuring consistency across the platform.

---

# Dashboard & Business Intelligence

MerchantHub includes dashboard endpoints that aggregate merchant business data for reporting and future financial analytics.

This foundation will power:

* Revenue tracking
* Profit calculations
* Cash flow monitoring
* Business performance metrics
* Growth analytics
* Merchant insights

---

# Architecture

MerchantHub follows a layered architecture that separates responsibilities.

```text
API Views
    │
    ▼
Serializers
    │
    ▼
Service Layer
    │
    ▼
Models
```

Business logic is intentionally isolated inside services rather than views, making the application easier to test, maintain, and extend.

---

# Technology Stack

* Python
* Django
* Django REST Framework
* PostgreSQL
* SimpleJWT
* drf-spectacular (OpenAPI / Swagger)
* Nomba API Integration

---

# API Documentation

Interactive Swagger documentation:

```text
/api/docs/
```

OpenAPI schema:

```text
/api/schema/
```

---

# Available API Modules

* Authentication
* Products
* Inventory
* Customers
* Sales
* Payments
* Dashboard
* Stock Movements

---

# Project Structure

```text
apps/
├── accounts/
├── common/
├── customers/
├── dashboard/
├── inventory/
├── payments/
│   └── integrations/
│       └── nomba/
├── products/
├── sales/
├── stock_movements/
└── workspaces/
```

---

# Running Locally

## Clone the repository

```bash
git clone https://github.com/Iamojochenemi/MerchantHub.git
```

## Navigate into the project

```bash
cd MerchantHub
```

## Create a virtual environment

```bash
python -m venv venv
```

### Windows

```bash
venv\Scripts\activate
```

### Linux/macOS

```bash
source venv/bin/activate
```

## Install dependencies

```bash
pip install -r requirements.txt
```

## Configure environment variables

Create a `.env` file and configure:

* Django Secret Key
* Database credentials
* JWT settings
* Nomba credentials
* Webhook secret

## Apply migrations

```bash
python manage.py migrate
```

## Start the development server

```bash
python manage.py runserver
```

---

# Running Tests

Run the complete automated test suite:

```bash
python manage.py test
```

MerchantHub currently includes **376 automated tests**, covering services, APIs, models, permissions, middleware, validators, integrations, and business logic.

---

# Code Quality

The project includes:

* Layered service architecture
* Serializer validation
* Custom exceptions
* Custom permissions
* Middleware
* OpenAPI documentation
* Comprehensive automated testing
* Multi-tenant isolation
* Payment orchestration
* Webhook processing

---

# Roadmap

## Phase 1 ✅ Foundation

* Authentication
* Multi-tenancy
* Business Profiles
* Workspace Memberships
* Swagger Documentation
* Automated Testing

## Phase 2 ✅ Merchant Operations

* Products
* Inventory
* Customers
* Sales
* Payments
* Stock Movements

## Phase 3 🚧 Financial Intelligence

* Profit Analysis
* Expense Tracking
* Cash Flow
* Revenue Analytics
* Financial Reports

## Phase 4 🚧 Nomba Commerce

* Checkout Improvements
* Settlement Tracking
* Payment Synchronization
* Automated Reconciliation

## Phase 5 🚧 Business Intelligence

* Merchant Dashboard
* AI-powered Insights
* Forecasting
* Business Recommendations

---

# Hackathon

MerchantHub was built as part of the **DevCareer × Nomba Hackathon 2026**.

The project demonstrates how Nomba's payment infrastructure can serve as the foundation for a complete merchant operating system rather than a standalone payment gateway.

---

# Contributing

Contributions, ideas, bug reports, and feature suggestions are welcome.

Feel free to open an issue or submit a pull request.

---

# License

This project was created for the **DevCareer × Nomba Hackathon 2026** and is intended for educational and demonstration purposes.
