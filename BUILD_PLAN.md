# Build Plan: Splitwise Clone - Implementation Summary

This document summaries the product research, final architecture, collaborative engineering choices, compromises, and roadmap of the implemented Splitwise Clone.

---

## 1. Product Research & Assumptions

### Features Studied
* **Group Splitting**: Examined how Splitwise partitions expenses within groups, allowing group members to track multi-party debts.
* **Unequal Split Types**: Researched percentage-based splits (often used for room rent shares) and share-based splits (common for meals/groceries shared in ratios).
* **Simplified Debts**: Evaluated Splitwise's "Simplify Debts" feature which computes net balances and greediest matches to minimize total peer-to-peer transaction counts.
* **Settlement Workflows**: Modeled recording payments directly between users to zero out balances.

### Core Workflows Identified
1. **User Sign Up & Sessions**: Login gating to secure group membership and expense details.
2. **Group Management**: Group creation and membership assignment.
3. **Expense Capture**: Adding expenses with descriptions, values, selecting a payer, and calculating shares dynamically.
4. **Settlement Logging**: Resolving outstanding debts.
5. **Discussion**: Commenting directly on individual expenses to resolve discrepancies.

### Product Assumptions Made
* **Single Currency**: All balances are in one currency (Rs.). No currency conversion is supported.
* **Group-Centric Boundaries**: Every expense, comment, and settlement belongs strictly to a group. No direct/friend-only expenses outside groups are supported.
* **No Soft Deletes**: Deleting an expense completely purges its records and splits from the database, instantly recalculating member balances.

---

## 2. Implemented Architecture

### Tech Stack
* **Web Framework**: Flask 3.0.3 (Monolithic layout)
* **Authentication**: Flask-Login + Flask-Bcrypt (Hashed cookie sessions)
* **Database & ORM**: PostgreSQL (Supabase) + Flask-SQLAlchemy 3.1.1
* **Frontend UI**: Bootstrap 5 + Google Font Outfit + Custom HSL Stylesheet

### Database Schema (7 Tables)
* `users`: Roster profiles with encrypted passwords.
* `groups`: Group records with description and creator reference.
* `group_members`: Junction table for group memberships.
* `expenses`: Logs transaction amounts, creators, and split types.
* `expense_splits`: Calculated shares, percentages, or share numbers per member per expense.
* `settlements`: Logs peer payments to settle balances.
* `comments`: Discussion threads linked to individual expenses.

### API & Blueprint Design (19 Endpoints)
* Root: Redirects to `/dashboard`.
* Authentication (`/auth`): `/register` (GET/POST), `/login` (GET/POST), `/logout` (GET).
* Dashboard & Groups: `/dashboard` (GET), `/groups/create` (GET/POST), `/groups/<id>` (GET), `/groups/<id>/add-member` (POST), `/groups/<id>/remove-member/<uid>` (POST).
* Expenses: `/groups/<id>/expenses/add` (GET/POST), `/expenses/<id>` (GET), `/expenses/<id>/delete` (POST).
* Settlements: `/groups/<id>/settle` (GET/POST).
* Comments: `/expenses/<id>/comments` (POST).

### Frontend Layout
* Uses server-rendered Jinja2 templates (extending `templates/base.html`).
* Layout structured into clean grids: left side timelines of expenses, right side rosters and simplified debt balances.
* Dynamic JS handlers on the expense creation screen toggle inputs for equal check lists, percentage sliders, or share entries.

### Deployment Layout
* Deployed as a single service on Render.
* Interconnects with a Supabase PostgreSQL instance via direct socket connections.

---

## 3. AI Collaboration Process

### Scope Controls
To fit a 3-day development timeline, the scope was strictly locked:
* **Excluded**: Receipt OCR upload, email notifications, activity logs, and mobile wrappers.
* **Simplifications**: Selected a simple member dropdown list of registered users on the group page, which avoids building complex search/auto-complete invite workflows.

### Evolving Context
1. **Roster Permissions**: Decided group creators should have exclusive rights to remove group members (creator cannot remove themselves).
2. **Expense Deletion**: Decided only the expense creator (`created_by_id`) can delete it, triggering splits removal and balance updates.
3. **Rounding Rules**: Agreed that rounding remainders (e.g. dividing 100 among 3) will be added to the last participant in the split list.
4. **Sanitizing Strings**: Resolved psycopg2 syntax errors by stripping database parameters (like `?pgbouncer=true`) on the backend.

---

## 4. Engineering Tradeoffs & Compromises

* **Compute on Demand**: The debt-simplification algorithm runs on-the-fly whenever a group detail page is loaded. This avoids cache synchronization overhead, making it highly reliable for group scales up to 50 members.
* **Minimal Validation Tolerance**: Enforced percentage check bounds of $[99.99\%, 100.01\%]$ in both frontend JS and backend logic, permitting floating-point precision adjustments while preventing data leaks.
* **Basic Session State**: Avoided token-based JWT management in favor of cookie-based sessions (Flask-Login), which is highly secure and faster to implement for monolithic architectures.

---

## 5. Future Enhancements

1. **Transaction Minimization Across Groups**: Extend the debt-simplification algorithm to compute net balances across *all* groups, showing a user their overall net debt/credit position globally.
2. **Auto-settle Integrations**: Add mock UPI/payment gateways links on the settlement page to speed up peer-to-peer transfers.
3. **Receipt Parsing**: Integrate simple optical character recognition (OCR) to auto-fill expense amounts and descriptions from photo attachments.
