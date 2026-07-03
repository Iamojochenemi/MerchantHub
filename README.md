# MerchantHub

> **A financial operating system for merchants, built on Nomba's commerce infrastructure.**

MerchantHub is a multi-tenant backend platform designed to help small and medium-sized businesses confidently manage their operations and finances.

Rather than simply recording business activities, MerchantHub transforms transactions into meaningful financial insights that merchants can trust. By leveraging Nomba's commerce infrastructure, the platform aims to automate financial calculations, reconcile business activities, and provide accurate business intelligence from a single source of truth.

---

## Why MerchantHub?

Many merchants successfully receive payments every day but still struggle to answer important business questions:

- How much profit did I actually make today?
- Why doesn't my cash match today's sales?
- Which customers still owe me money?
- How much inventory do I really have?
- Is my business actually growing?

Most small businesses still rely on notebooks, spreadsheets, calculators, and manual bookkeeping, making mistakes inevitable.

MerchantHub exists to eliminate that uncertainty.

---

# Vision

Our vision is to become the financial operating system for merchants.

MerchantHub helps business owners spend less time calculating numbers and more time making informed business decisions.

Every transaction should increase confidence—not confusion.

---

# Current MVP

The current version establishes the secure backend foundation for the platform.

## Authentication

- Secure user registration
- JWT authentication
- Login endpoint
- Current authenticated user endpoint

## Workspace Management

Every registered merchant automatically receives:

- Personal business workspace
- Business profile
- Owner workspace membership
- Tenant isolation

## Developer Experience

- OpenAPI documentation
- Swagger UI
- Service-layer architecture
- Comprehensive automated tests
- Serializer-based validation

---

# Planned Features

## Business Operations

- Product management
- Inventory management
- Customer management
- Supplier management
- Sales management
- Purchase management

## Financial Intelligence

MerchantHub's primary focus.

- Revenue tracking
- Profit calculation
- Expense tracking
- Cash flow monitoring
- Outstanding debt tracking
- Settlement reconciliation
- Financial reports
- Business health dashboard

## Nomba Integration

- Payment synchronization
- Transaction reconciliation
- Settlement tracking
- Commerce analytics

## Business Insights

- Business performance metrics
- Growth analytics
- Restocking recommendations
- AI-powered financial assistant
- Predictive business insights

---

# Technology Stack

- Python
- Django
- Django REST Framework
- PostgreSQL
- SimpleJWT
- drf-spectacular (Swagger/OpenAPI)

---

# Architecture

MerchantHub follows a layered architecture that separates responsibilities.

```
Views
   │
   ▼
Serializers
   │
   ▼
Services
   │
   ▼
Models
```

This approach keeps business logic independent from the API layer, making the project easier to test, maintain, and extend.

---

# API Documentation

Interactive API documentation is available through Swagger.

```
/api/docs/
```

OpenAPI schema:

```
/api/schema/
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

### Linux / macOS

```bash
source venv/bin/activate
```

## Install dependencies

```bash
pip install -r requirements.txt
```

## Apply migrations

```bash
python manage.py migrate
```

## Run the development server

```bash
python manage.py runserver
```

---

# Running Tests

Run the service tests

```bash
python manage.py test apps.accounts.tests.test_registration_service
```

Run the API tests

```bash
python manage.py test apps.accounts.tests.test_views
```

---

# Project Status

🚧 Active Development

Current milestone:

- Authentication
- Multi-tenant workspace provisioning
- Business profile creation
- JWT authentication
- API documentation
- Automated testing

Next milestone:

- Inventory
- Sales
- Financial Intelligence
- Nomba integration

---

# Roadmap

## Phase 1 ✅ Foundation

- Authentication
- Multi-tenant workspaces
- Business profiles
- Workspace memberships
- API documentation
- Testing

## Phase 2 🚧 Business Operations

- Products
- Inventory
- Sales
- Customers
- Suppliers

## Phase 3 📊 Financial Intelligence

- Profit calculations
- Revenue tracking
- Expense management
- Cash flow
- Business dashboard

## Phase 4 💳 Nomba Commerce Integration

- Payment synchronization
- Settlement reconciliation
- Automated bookkeeping

## Phase 5 🤖 Smart Business Intelligence

- AI insights
- Forecasting
- Business recommendations

---

# Contributing

Contributions, suggestions, and feedback are welcome.

Please open an issue before submitting major changes.

---

# License

This project is currently developed as part of the **DevCareer × Nomba Hackathon 2026** and is intended for educational and demonstration purposes.