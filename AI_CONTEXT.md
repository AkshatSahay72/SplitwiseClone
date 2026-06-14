# AI Context: Splitwise Clone

This document serves as the absolute source of truth for the Splitwise Clone project. The application is fully built and reproducible from the specifications detailed below.

---

## 1. Project Overview & Scope
* **Goal**: Build a functional web-based Splitwise clone to showcase database relationships, routing, and algorithmic execution.
* **Target Audience**: College students tracking food and travel expenses.
* **Core Features**:
  * User registration and authentication.
  * Group creation and membership management with temporal intervals (`joined_at`, `left_at`).
  * Expense creation with equal and unequal splitting (percentage, share, exact splits).
  * Multi-currency support (INR base currency and USD tracking with exchange rates).
  * Smart CSV importer with dry-run reports, anomaly/duplicate detection, and unresolved member name mapping.
  * Auditable member ledgers showing running balances.
  * Group debt simplification (simplified balances) enabled globally.
  * Settlement logging (recording payments between group members).
  * Commenting on expenses.
* **Explicitly Out of Scope**:
  * Email and push notifications.
  * Receipt image uploads.
  * Mobile application (web-only).
  * General multi-currency with automatic real-time rate API updates (uses seed/manual database rates).

---

## 2. Tech Stack & Architecture
* **Architecture**: Monolithic web application serving backend logic and frontend templates from the same codebase.
* **Backend**: Python 3.13 + Flask 3.0.3.
* **Database**: PostgreSQL (hosted on Supabase, dynamic column auto-migrations implemented in `app.py`).
* **ORM**: SQLAlchemy.
* **Authentication**: Session-based auth via `Flask-Login` and `Flask-Bcrypt` for secure password hashing.
* **Frontend**: HTML5 & server-rendered Jinja2 templates.
* **Styling**: Bootstrap 5 (Vanilla CSS premium green-palette styles in `static/css/styles.css`).
* **API Style**: REST-mapped blueprints (`auth_bp`, `groups_bp`, `expenses_bp`, `settlements_bp`, `comments_bp`, `importer_bp`).
* **Deployment**: Render.

---

## 3. Data Model (PostgreSQL Schema)
All tables contain auto-updating timestamps.

### Tables & Relationships

#### 1. `users`
* `id`: Integer PK
* `full_name`: String (not null)
* `email`: String (unique, index, not null)
* `password`: String (hashed, not null)
* `created_at` / `updated_at`: DateTime

#### 2. `groups`
* `id`: Integer PK
* `name`: String (not null)
* `description`: String (nullable)
* `creator_id`: Integer FK -> `users.id` (on delete restrict, not null)
* `created_at` / `updated_at`: DateTime

#### 3. `group_members`
Tracks historical memberships (allows users leaving and rejoining).
* `id`: Integer PK
* `group_id`: Integer FK -> `groups.id` (on delete cascade)
* `user_id`: Integer FK -> `users.id` (on delete cascade)
* `joined_at`: Date (default current date)
* `left_at`: Date (nullable)
* `created_at` / `updated_at`: DateTime
* *Note*: No unique constraint on `(group_id, user_id)` to allow multiple historical membership rows.

#### 4. `expenses`
* `id`: Integer PK
* `group_id`: Integer FK -> `groups.id` (on delete cascade)
* `paid_by_id`: Integer FK -> `users.id` (payer, not null)
* `created_by_id`: Integer FK -> `users.id` (creator, not null)
* `description`: String (not null)
* `total_amount`: Numeric(10, 2) (converted amount in base currency INR, not null)
* `original_amount`: Numeric(10, 2) (amount entered in original currency, not null)
* `currency`: String(3) (default 'INR', not null)
* `exchange_rate`: Numeric(10, 6) (default 1.0, not null)
* `date`: Date (default current date, not null)
* `split_type`: String (enum: `'equal'`, `'percentage'`, `'share'`, `'exact'`)
* `created_at` / `updated_at`: DateTime

#### 5. `expense_splits`
* `id`: Integer PK
* `expense_id`: Integer FK -> `expenses.id` (on delete cascade)
* `user_id`: Integer FK -> `users.id` (on delete cascade)
* `amount`: Numeric(10, 2) (actual split share in INR, not null)
* `percentage`: Numeric(5, 2) (nullable)
* `share`: Integer (nullable)
* `created_at` / `updated_at`: DateTime

#### 6. `settlements`
* `id`: Integer PK
* `group_id`: Integer FK -> `groups.id` (on delete cascade)
* `payer_id`: Integer FK -> `users.id` (payer, not null)
* `receiver_id`: Integer FK -> `users.id` (receiver, not null)
* `amount`: Numeric(10, 2) (amount in INR, not null)
* `original_amount`: Numeric(10, 2) (amount in original currency, not null)
* `currency`: String(3) (default 'INR', not null)
* `exchange_rate`: Numeric(10, 6) (default 1.0, not null)
* `date`: Date (default current date, not null)
* `created_at` / `updated_at`: DateTime

#### 7. `comments`
* `id`: Integer PK
* `expense_id`: Integer FK -> `expenses.id` (on delete cascade)
* `user_id`: Integer FK -> `users.id` (on delete cascade)
* `content`: Text (not null)
* `created_at` / `updated_at`: DateTime

#### 8. `exchange_rates`
* `id`: Integer PK
* `from_currency`: String(3) (not null)
* `to_currency`: String(3) (not null)
* `rate`: Numeric(10, 6) (not null)
* `date`: Date (nullable, None indicates default fallback)

---

## 4. Workflows & Core Logic

### 1. Temporal Group Membership
* A user can join and leave groups multiple times. Each membership span is represented by a `[joined_at, left_at]` date interval row in `group_members`.
* When an expense is created, it is only split among members whose membership interval overlaps with the expense `date`.
* Payer and split participants must be active on the transaction date.

### 2. Multi-Currency conversions
* Core balance calculations are kept in base currency (INR).
* Non-base currency amounts (e.g., USD) are converted using:
  $$\text{Converted Amount (INR)} = \text{Original Amount} \times \text{Exchange Rate}$$
* Standard seed rates are loaded in `app.py` (e.g. USD -> INR = 83.00). Users can manually override the exchange rate when adding transactions.

### 3. CSV Importer
* Uploads `Expenses Export.csv` directly.
* Parses transaction date, description, paid_by, amount, currency, splits, and split details.
* **Anomaly checks**:
  * Unresolved name mapping (links CSV names to existing database users or creates stub user logins).
  * Duplicate detections (flagged if identical description, date, and amount exist in database or duplicate rows inside CSV).
  * Settlement detections (if 1-to-1 split with description keywords like "paid back", flags as settlement).
  * Math/split ratio checks (percentages sum to 100% check, shares check).
* Review screen lets the user configure mappings, ignore bad rows, and check warnings. Everything commits inside a single database transaction.

### 4. Auditable Ledger
* Computes running balance for any group member chronologically.
* Tracks: date, type (Expense Paid, Expense Shared/Owed, Settlement Sent, Settlement Received), description, original currency, exchange rate, net impact, and running net total.

---

## 5. UI Views & User Flows
1. **Authentication (Login / Signup)**
2. **Dashboard**: Overall balance and group list showing net balances.
3. **Group Details**: Displays feed, Simplified Debt Summary ("A owes B Rs. 100"), member list with active interval badges and ledger buttons.
4. **Add Expense / Settle Forms**: Inputs for description, amount, date, currency (INR/USD), exchange rate, and split options.
5. **Expense Details & Comments Feed**
6. **CSV Import Upload**: File field with column format hints.
7. **CSV Import Review Report**: Name mapping selectors, anomaly warning badges, selectable checkboxes to select records.
8. **Audit Ledger View**: Chronological table showing exchange rates, impacts, and a running balance column.
