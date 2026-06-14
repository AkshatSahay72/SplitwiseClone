# Design Decisions & Compromises: Splitwise Clone

This document outlines the major architectural, algorithmic, and database decisions made during the development of the Splitwise Clone.

---

## 1. Monolithic Web Architecture
We selected a monolithic **Flask + Jinja2** design. 
* **Pros**: Rapid prototyping, minimal boilerplate, direct integration of backend logic with templates, and unified SQL transaction management.
* **Cons**: Less separation of concerns than a SPA (Single Page App) + API backend, but optimal for a 3-day MVP timeline.

---

## 2. Supabase PostgreSQL & Raw SQL Migrations
The application runs on **PostgreSQL hosted on Supabase**.
* **Direct Connection Sanitization**: psycopg2 connection strings with PgBouncer query parameters (like `?pgbouncer=true`) can cause connection issues on certain client configurations. We implemented automatic query variable stripping in `app.py`.
* **Programmatic Auto-Migrations**: Since tables are already hosted on the live database, standard SQLAlchemy `db.create_all()` would not add new columns. We added inspection routines in `app.py` that run raw SQL `ALTER TABLE` queries to add columns dynamically on startup.

---

## 3. Financial Precision & Calculations
To prevent floating-point calculation errors:
* All financial values in the database use `Numeric(10,2)`.
* In Python, all calculations are performed using the `decimal.Decimal` class.
* Split rounding remainders are added to the last participant in the list.

---

## 4. On-the-Fly Debt Simplification
We implement a greedy debt-simplification algorithm that runs dynamically whenever a group detail page is loaded.
* **Pros**: Guarantees up-to-date debt calculations without complex balance-state synchronization code or risk of stale cached values.
* **Cons**: Scale limitation if a group has thousands of transactions, but highly efficient for college-student and travel-group scales (under 50 members).

---

## 5. Temporal Membership Design
Rather than deleting members or soft-deleting expenses:
* Memberships in `group_members` use date intervals `[joined_at, left_at]`.
* Expenses split only among members whose active membership span overlaps with the expense date.
* When adding a member who previously left, a new database row is inserted, capturing multiple active intervals.

---

## 6. CSV Importer Transaction Boundaries
To handle messy CSV uploads:
* CSV files are parsed and validation alerts are generated in a dry-run phase stored in session memory.
* If confirmed, all mappings, user creations, active membership updates, expenses, and splits are written inside a single database transaction block. If any error occurs, SQLAlchemy rolls back the entire import to keep the database consistent.
