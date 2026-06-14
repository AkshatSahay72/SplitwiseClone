# Build Plan: Splitwise Clone - Implementation Summary

This document summarizes the product research, final architecture, collaborative engineering choices, compromises, and roadmap of the implemented Splitwise Clone.

---

## 1. Product Research & Assumptions

### Features Studied
* **Group Splitting**: Examined how Splitwise partitions expenses within groups, allowing group members to track multi-party debts.
* **Unequal Split Types**: Researched percentage-based splits, share-based splits, and exact/unequal splits.
* **Simplified Debts**: Evaluated Splitwise's "Simplify Debts" feature which computes net balances and greediest matches to minimize total peer-to-peer transaction counts.
* **Temporal memberships**: Studied how users joining and leaving groups affect past/future expenses, requiring membership interval tracking.
* **Multi-Currency**: Track transactions in INR (base) and USD, fetching conversions from db-seeded exchange rates.
* **CSV Import**: Modeled bulk transaction uploads from standard CSV exports, identifying messy data issues (duplicate rows, unresolved name mappings, settlements mislabeled as expenses).

### Core Workflows Identified
1. **User Sign Up & Sessions**: Login gating to secure group membership and expense details.
2. **Group Management**: Group creation, membership assignment, and member removals.
3. **Expense Capture**: Adding expenses with descriptions, values, currency, exchange rate, and split ratios.
4. **CSV Import**: Analysis dry-run identifying duplicates or bad math, and mapping screen for unresolved names.
5. **Ledger Auditing**: Chronological list of transactions contributing to a user's balance.

### Product Assumptions Made
* **Group-Centric Boundaries**: Every expense, comment, and settlement belongs strictly to a group.
* **Temporal Splitting Rules**: Expenses only split among members whose active membership interval overlaps with the expense date.
* **Conversions to Base Currency**: All net balances and simplified debt matrices are computed using base currency (INR) converted values.

---

## 2. Implemented Architecture

### Tech Stack
* **Web Framework**: Flask 3.0.3 (Monolithic layout)
* **Authentication**: Flask-Login + Flask-Bcrypt (Hashed cookie sessions)
* **Database & ORM**: PostgreSQL (Supabase) + Flask-SQLAlchemy 3.1.1
* **Frontend UI**: Bootstrap 5 + Google Font Outfit + Custom HSL Stylesheet
* **Package Manager**: Pip

### Database Schema (8 Tables)
* `users`: Profile roster with encrypted credentials.
* `groups`: Group records.
* `group_members`: junction table with `joined_at` and `left_at` intervals.
* `expenses`: total converted amount (INR), original amount, currency, exchange rate, and date.
* `expense_splits`: Calculated shares, percentages, or share numbers per member per expense.
* `settlements`: logs payer/receiver payment, original currency, exchange rate, and date.
* `comments`: Discussion threads linked to individual expenses.
* `exchange_rates`: database table storing currency conversions.

### API & Blueprint Design (23 Endpoints)
* Root: Redirects to `/dashboard`.
* Authentication (`/auth`): `/register` (GET/POST), `/login` (GET/POST), `/logout` (GET).
* Dashboard & Groups: `/dashboard` (GET), `/groups/create` (GET/POST), `/groups/<id>` (GET), `/groups/<id>/add-member` (POST), `/groups/<id>/remove-member/<uid>` (POST), `/groups/<id>/members/<uid>/ledger` (GET).
* CSV Importer: `/groups/<id>/import` (GET), `/groups/<id>/import/analyze` (POST), `/groups/<id>/import/confirm` (POST).
* Expenses: `/groups/<id>/expenses/add` (GET/POST), `/expenses/<id>` (GET), `/expenses/<id>/delete` (POST).
* Settlements: `/groups/<id>/settle` (GET/POST).
* Comments: `/expenses/<id>/comments` (POST).

---

## 3. Engineering Tradeoffs & Compromises

* **Dynamic Schema Migration**: Implemented programmatic auto-migrations in `app.py` utilizing SQLAlchemy inspect to automatically append columns (`joined_at`, `left_at`, `currency`, etc.) if absent.
* **CSV Dry-Run Sessions**: Saved parsed CSV states into Flask session cookies, keeping db staging tables out of the design.
* **Base Currency Simplicity**: All simplified debts run in INR. If a USD settlement occurs, the database converts the rate first, avoiding multi-currency matrix complexity.
