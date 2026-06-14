# Splitwise Clone (V2)

A robust, premium web-based Splitwise clone designed for college students to split food, travel, and accommodation expenses. The application includes user authentication, group management with temporal memberships, equal/unequal expense splitting, multi-currency support, a smart CSV importer, dynamic debt simplification, settlement logging, comments, and auditable ledgers.

---

## 🚀 Implementation Summary

* **Number of Database Tables**: 8 tables (`users`, `groups`, `group_members`, `expenses`, `expense_splits`, `settlements`, `comments`, `exchange_rates`)
* **Number of API Endpoints**: 23 routes
* **Number of Frontend Pages**: 11 server-rendered views
* **Authentication Method**: Session-based cookie authentication using `Flask-Login` and `Flask-Bcrypt` (passwords securely hashed)
* **Deployment Target**: Render
* **Database Provider**: Supabase PostgreSQL

---

## ✨ Features

1. **User Authentication**: Secure registration, login, and logout.
2. **Group Management & Temporal Membership**:
   * Create groups, auto-join as a member.
   * Add members via dropdown selection.
   * Remove members (creator-only) by setting a `left_at` date interval instead of deleting records.
   * Re-join group support by treating membership as a historical set of `[joined_at, left_at]` date intervals.
   * Expenses only split among members active on the expense date.
3. **Advanced Expense Splitting**:
   * **Equally**: Divides the total bill equally among selected active group members.
   * **Percentages**: Assigns custom percentages to members (validated to sum to 100% with minor tolerance).
   * **Shares**: Splits using ratio proportions (e.g. 2 shares vs 1 share).
   * **Exact/Unequal**: Splits by custom exact amounts.
   * *Rounding Math*: Rounding differences are automatically adjusted on the last participant's balance.
4. **Multi-Currency Support**:
   * Track transactions in **INR** (base currency) and **USD**.
   * Fetches exchange rates dynamically from the `ExchangeRate` table.
   * All non-base transactions are converted to INR on the fly using stored rates for debt calculations and balances.
5. **Robust CSV Importer**:
   * Upload `Expenses Export.csv` directly.
   * Parses various date and currency formats (defaults missing fields to INR/current date).
   * Run dry-run analysis showing anomalies (suspected duplicates, mathematical percentage splits mismatch, settlements masquerading as expenses).
   * Review interface resolves unrecognized user names to registered users or auto-creates stub accounts, allowing bulk toggles of rows before committing inside a SQL transaction.
6. **Auditable Ledgers**:
   * Transparent audit sheets for every group member.
   * Traces all splits and payments chronologically with exchange rate references and a running net balance.
7. **Greedy Debt Simplification**: Computes net balances on the fly and simplifies the debt matrix to minimize total payments ("Who owes whom").
8. **Payment Settlements**: Log payments between members to offset outstanding debts.
9. **Comments Feed**: Post questions or notes on any group expense timeline.

---

## 🛠️ Technology Stack

* **Backend**: Python 3.13 + Flask 3.0.3
* **Database**: PostgreSQL (hosted on Supabase)
* **ORM**: SQLAlchemy (via Flask-SQLAlchemy 3.1.1)
* **Frontend**: HTML5 + Server-Rendered Jinja2 Templates
* **Styling**: Bootstrap 5 + HSL Mint/Forest Green CSS Custom variables
* **Package Manager**: Pip

---

## ⚙️ Environment Variables

Create a `.env` file in the root directory:

```env
DATABASE_URL="postgresql://postgres.hrheevcvuojkqpifgmfj:Come%20Of%20Slpitwise@aws-1-ap-northeast-2.pooler.supabase.com:6543/postgres?pgbouncer=true"
SECRET_KEY="some-very-secret-key-splitwise-clone-development"
FLASK_DEBUG=1
```

*Note: The application automatically handles sanitization, including stripping pgbouncer query variables when initializing `psycopg2` connections.*

---

## 💻 Installation & Local Setup

### 1. Prerequisites
Ensure you have Python 3.10+ installed.

### 2. Clone and Setup Environment
Navigate to the directory and set up a virtual environment:

```powershell
# Create a virtual environment
python -m venv venv

# Activate on Windows
.\venv\Scripts\activate
```

### 3. Install Dependencies
Install all packages from `requirements.txt`:

```powershell
pip install -r requirements.txt
```

### 4. Running the Application
Start the Flask development server:

```powershell
python app.py
```
Open your browser and navigate to: [http://127.0.0.1:5000](http://127.0.0.1:5000)

---

## 🧪 Testing

The project includes an automated unit/integration test suite using an in-memory SQLite setup to test splitting calculations, temporal boundaries, and currency exchange rates:

```powershell
python -m unittest tests/test_algorithms.py
```

---

## 📂 Folder Structure

```
SplitwiseClone/
├── routes/               # Controller blueprints (auth, groups, expenses, settlements, comments, importer)
├── static/css/styles.css # Premium styling rules
├── templates/            # Jinja2 layouts and components
├── tests/                # Automated test suite
├── app.py                # App factory bootstrap and database auto-migrations
├── models.py             # ORM models (SQLAlchemy)
├── AI_CONTEXT.md         # Source of truth specifications
├── BUILD_PLAN.md         # Design decisions and tradeoffs
├── requirements.txt      # Project packages list
└── .env                  # Environment secrets
```

---

## 🔌 API Overview

* **Root Redirect**: `GET /` -> Redirects to `/dashboard`
* **Authentication**:
  * `GET /auth/register` & `POST /auth/register` - SignUp flow
  * `GET /auth/login` & `POST /auth/login` - Session start
  * `GET /auth/logout` - Logout (requires login)
* **Groups**:
  * `GET /dashboard` - Dashboard view
  * `GET /groups/create` & `POST /groups/create` - Create group
  * `GET /groups/<group_id>` - Group feed and debt calculations
  * `POST /groups/<group_id>/add-member` - Join a member
  * `POST /groups/<group_id>/remove-member/<user_id>` - Remove a member
  * `GET /groups/<group_id>/members/<user_id>/ledger` - Auditable member ledger
* **CSV Importer**:
  * `GET /groups/<group_id>/import` - File upload form
  * `POST /groups/<group_id>/import/analyze` - Anomaly analysis report
  * `POST /groups/<group_id>/import/confirm` - Confirms and writes mapped records
* **Expenses**:
  * `GET /groups/<group_id>/expenses/add` & `POST /groups/<group_id>/expenses/add` - Add expense
  * `GET /expenses/<expense_id>` - Expense details & splits
  * `POST /expenses/<expense_id>/delete` - Delete expense
* **Settlements**:
  * `GET /groups/<group_id>/settle` & `POST /groups/<group_id>/settle` - Record payment
* **Comments**:
  * `POST /expenses/<expense_id>/comments` - Add expense comment
