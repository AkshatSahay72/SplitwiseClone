# AI Context: Splitwise Clone

This document serves as the absolute source of truth for the Splitwise Clone project. The application must be fully buildable and reproducible from the specifications detailed below.

---

## 1. Project Overview & Scope
* **Goal**: Build a functional web-based Splitwise clone to showcase database relationships, routing, and algorithmic execution.
* **Target Audience**: College students tracking food and travel expenses.
* **Core Features**:
  * User registration and authentication.
  * Group creation and membership management.
  * Expense creation with equal and unequal splitting (percentage and share-based).
  * Group debt simplification (simplified balances) enabled globally.
  * Settlement logging (recording payments between group members).
  * Commenting on expenses.
* **Explicitly Out of Scope**:
  * Email and push notifications.
  * Receipt image uploads.
  * Currency conversion (all amounts are in a single local currency, e.g., INR / Rs. represented as `Decimal`).
  * Mobile application (web-only).
  * Multi-currency support.
  * Activity logs/audit trails.

---

## 2. Tech Stack & Architecture
* **Architecture**: Monolithic web application serving backend logic and frontend templates from the same codebase.
* **Backend**: Python 3 with Flask.
* **Database**: PostgreSQL (hosted on Supabase for production, local/PostgreSQL for development).
* **ORM**: SQLAlchemy.
* **Authentication**: Session-based auth via `Flask-Login` and `Flask-Bcrypt` for password hashing.
* **Frontend**: HTML & server-rendered Jinja2 templates.
* **Styling**: Bootstrap 5 (Vanilla CSS overrides as needed).
* **API Style**: REST API structure internally, mapped to controllers/blueprints (e.g., `/auth`, `/groups`, `/expenses`, `/settlements`, `/comments`).
* **Deployment**: Hosted on Render.

---

## 3. Data Model (PostgreSQL Schema)
All tables must contain `id` (Primary Key), `created_at` (Timestamp with timezone), and `updated_at` (Timestamp with timezone) fields.

### Tables & Relationships

#### 1. `users`
* `id`: Serial/Integer PK
* `full_name`: String (not null)
* `email`: String (unique, index, not null)
* `password`: String (hashed using bcrypt, not null)
* `created_at`: DateTime
* `updated_at`: DateTime

#### 2. `groups`
* `id`: Serial/Integer PK
* `name`: String (not null)
* `description`: String (nullable)
* `creator_id`: Integer FK -> `users.id` (on delete restrict, not null)
* `created_at`: DateTime
* `updated_at`: DateTime

#### 3. `group_members`
* `id`: Serial/Integer PK
* `group_id`: Integer FK -> `groups.id` (on delete cascade)
* `user_id`: Integer FK -> `users.id` (on delete cascade)
* `created_at`: DateTime
* `updated_at`: DateTime
* *Constraint*: Unique index on `(group_id, user_id)`

#### 4. `expenses`
* `id`: Serial/Integer PK
* `group_id`: Integer FK -> `groups.id` (on delete cascade)
* `paid_by_id`: Integer FK -> `users.id` (payer, not null)
* `created_by_id`: Integer FK -> `users.id` (creator, not null)
* `description`: String (not null)
* `total_amount`: Numeric(10, 2) (using Decimal precision, not null)
* `split_type`: String (enum/text: `'equal'`, `'percentage'`, `'share'`)
* `created_at`: DateTime
* `updated_at`: DateTime

#### 5. `expense_splits`
Represents how much each user owes for a specific expense.
* `id`: Serial/Integer PK
* `expense_id`: Integer FK -> `expenses.id` (on delete cascade)
* `user_id`: Integer FK -> `users.id` (on delete cascade)
* `amount`: Numeric(10, 2) (the actual calculated share, not null)
* `percentage`: Numeric(5, 2) (null unless split_type is percentage)
* `share`: Integer (null unless split_type is share)
* `created_at`: DateTime
* `updated_at`: DateTime

#### 6. `settlements`
Represents payments made to settle balances.
* `id`: Serial/Integer PK
* `group_id`: Integer FK -> `groups.id` (on delete cascade)
* `payer_id`: Integer FK -> `users.id` (the person paying, not null)
* `receiver_id`: Integer FK -> `users.id` (the person receiving, not null)
* `amount`: Numeric(10, 2) (amount settled, not null)
* `created_at`: DateTime
* `updated_at`: DateTime

#### 7. `comments`
* `id`: Serial/Integer PK
* `expense_id`: Integer FK -> `expenses.id` (on delete cascade)
* `user_id`: Integer FK -> `users.id` (on delete cascade)
* `content`: Text (not null)
* `created_at`: DateTime
* `updated_at`: DateTime

---

## 4. Workflows & Core Logic

### 1. Expense Splitting Calculations
* **Equal Split**: The total amount is divided equally among all selected participants. Any remaining cents/paise from rounding (e.g., splitting Rs. 100.00 among 3 users = 33.33, 33.33, 33.34) is added to the last participant in the split list to ensure the sum of splits matches `total_amount` exactly.
* **Percentage Split**: Each participant is assigned a percentage. The system must validate that the sum of percentages is between 99.99% and 100.01%. The amount for each user is `(percentage / 100) * total_amount`, rounded to 2 decimal places. Any rounding remainder is added to the last participant in the split list.
* **Share-based Split**: Each participant is assigned a number of shares (e.g., A: 2 shares, B: 1 share). The total shares are summed. Each user's amount is `(total_amount * user_shares) / total_shares`, rounded to 2 decimal places. Any rounding remainder is added to the last participant in the split list.

### 2. Debt Simplification (Simplify Debts) Algorithm
* Calculated dynamically per group based on net balances.
* **Net Balance**: For any user in a group, their net balance is calculated as:
  $$\text{Net Balance} = \text{Total Paid as Payer} + \text{Total Received in Settlements} - \text{Total Owed in Expense Splits} - \text{Total Sent in Settlements}$$
* **Simplification Logic**:
  1. Calculate the net balance of all members in the group.
  2. Separate members into debtors (net balance < 0) and creditors (net balance > 0).
  3. Sort debtors ascending (most negative first) and creditors descending (most positive first).
  4. Greedily match the largest debtor with the largest creditor:
     * Let $D$ be the debtor who owes $X$, and $C$ be the creditor who is owed $Y$.
     * The settlement amount is $M = \min(X, Y)$.
     * Register that $D$ needs to pay $C$ the amount $M$.
     * Update their balances: $X \leftarrow X - M$ and $Y \leftarrow Y - M$.
     * Re-sort or repeat until all balances are near zero.
* This simplified list of transactions must be displayed to users in the group page as "Who owes whom".

### 3. Settlement Workflow
* To settle, a user clicks "Settle Up" inside a group.
* They choose the Payer, the Receiver, and the Amount.
* Saving the settlement inserts a record into the `settlements` table for the group. This immediately offsets the calculated net balances.

### 4. Group Membership Workflow
* When a user creates a group, they are automatically added as a member.
* To add new members, the creator can choose from a dropdown list of all registered users (for simple MVP/demo workflows). Only registered users can be added.
* Any group member can be removed by the group creator. The creator cannot remove themselves unless ownership (`creator_id`) is transferred first.

### 5. Expense Permissions & Deletion
* Any member of a group can create an expense.
* Editing an expense is out of scope.
* Only the user who created the expense (`created_by_id`) can delete it. 
* When an expense is deleted, its splits are deleted, and group balances recalculate.

### 6. Comments Workflow
* Any group member can post comments on an expense.
* Comment editing and deleting is out of scope (post-only feed).

---

## 5. UI Views & User Flows

1. **Authentication (Login / Signup)**
   * Login: Email and Password inputs.
   * Registration: Full Name, Email, Password, Password confirmation.

2. **Dashboard**
   * Displays overall balance summary: "You are owed total $X$" and "You owe total $Y$".
   * Lists the groups the user is a member of, showing the net balance in each group.
   * Lists a feed of recent expenses across all groups.
   * "Create Group" button.

3. **Group Details**
   * Shows group name and members list.
   * Displays the Simplified Debt Summary ("A owes B Rs. 100").
   * Lists all expenses added in this group.
   * "Add Expense" button and "Settle Up" button.

4. **Add Expense Form**
   * Input description, total amount, and choose payer (defaults to current user).
   * Select split type (Equal, Percentage, or Share).
   * Checkboxes/inputs for group members to specify how they split (equal split check list, percentage inputs, or share inputs).
   * Validation of inputs before saving.

5. **Expense Details & Comments**
   * Displays the expense name, total amount, who paid it, and a breakdown of who owes what (splits).
   * Shows a comments feed where group members can read and post comments.

6. **Settlement Screen**
   * Form to log a payment: Select Payer, Select Receiver, Enter Amount, Select Date (defaults to now).

---

## 6. Risks, Tradeoffs, & Implementations
* **Precision**: All financial columns are defined as PostgreSQL `Numeric(10,2)` to prevent floating-point errors. Application calculations must use Python's `decimal.Decimal`.
* **Scale**: The algorithm is optimized for small to medium groups (typical of friends, travel, or college suites). High scale optimization is out of scope.
* **Security**: Standard cookie-based sessions, password hashing via bcrypt. No rate limiting or multi-factor auth is implemented for the MVP.
