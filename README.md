# Splitwise Clone

A functional, premium web-based Splitwise clone designed for college students to split food, travel, and accommodation expenses. The application includes user authentication, group management, equal/unequal expense splitting, dynamic debt-simplification calculations, settlement logging, and comment threads.

---

## 🚀 Final Implementation Summary

* **Number of Database Tables**: 7 tables (`users`, `groups`, `group_members`, `expenses`, `expense_splits`, `settlements`, `comments`)
* **Number of API Endpoints**: 19 routes
* **Number of Frontend Pages**: 8 server-rendered views
* **Authentication Method**: Session-based cookie authentication using `Flask-Login` and `Flask-Bcrypt` (passwords securely hashed)
* **Deployment Target**: Render
* **Database Provider**: Supabase PostgreSQL

---

## ✨ Features

1. **User Authentication**: Secure registration, login, and logout.
2. **Group Management**: Create groups, auto-join as a member, add existing registered users via a dropdown selector, and remove group members (creator-only).
3. **Expense splitting**:
   * **Equally**: Divides the total bill equally among selected group members.
   * **Percentages**: Assigns custom percentages to members (validated to sum to 100%).
   * **Shares**: Splits using ratio proportions (e.g. 2 shares vs 1 share).
   * *Rounding Math*: Rounding differences are automatically adjusted on the last participant's balance.
4. **Greedy Debt Simplification**: Computes the net balance for each user on the fly and simplifies the debt matrix to minimize total payments ("Who owes whom").
5. **Payment Settlements**: Log payments between members to offset outstanding debts.
6. **Comments Feed**: Post questions or notes on any group expense timeline.

---

## 🛠️ Technology Stack

* **Backend**: Python 3.13 + Flask 3.0.3
* **Database**: PostgreSQL (hosted on Supabase)
* **ORM**: SQLAlchemy (via Flask-SQLAlchemy 3.1.1)
* **Frontend**: HTML5 + Server-Rendered Jinja2 Templates
* **Styling**: Bootstrap 5 + HSL Mint/Forest Green CSS Custom variables

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
Install all packages from `requirements.txt` (which has been updated to support Python 3.13):

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

The project includes an automated unit/integration test suite using an in-memory SQLite setup to test splitting calculations and debt simplification logic:

```powershell
python -m unittest tests/test_algorithms.py
```

---

## 📂 Folder Structure

```
SplitwiseClone/
├── routes/               # Controller blueprints (auth, groups, expenses, settlements, comments)
├── static/css/styles.css # Premium styling rules
├── templates/            # Jinja2 layouts
├── tests/                # Automated test suite
├── app.py                # App factory bootstrap
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
* **Expenses**:
  * `GET /groups/<group_id>/expenses/add` & `POST /groups/<group_id>/expenses/add` - Add expense
  * `GET /expenses/<expense_id>` - Expense details & splits
  * `POST /expenses/<expense_id>/delete` - Delete expense
* **Settlements**:
  * `GET /groups/<group_id>/settle` & `POST /groups/<group_id>/settle` - Record payment
* **Comments**:
  * `POST /expenses/<expense_id>/comments` - Add expense comment

---

## ⚠️ Assumptions and Limitations

1. **Floating Precision**: All calculations use Python's `Decimal` type. When split fractions do not divide evenly (e.g. Rs. 100 split 3 ways), the rounding remainder is added to the last participant.
2. **On-the-fly Computations**: Net balances and transaction simplifications are computed dynamically on page load. This simplifies architecture and works well for group scales typical of roommates.
3. **Group Scope**: Direct payments/expenses between individuals outside of a group boundaries are not supported.

---

## 🤖 AI Collaboration

This application was developed in pair programming with **Antigravity**, an agentic AI coding assistant designed by Google DeepMind. Scope control, SQL connection sanitization, and rounding rules were jointly verified through automated Playwright and unittest workflows.
