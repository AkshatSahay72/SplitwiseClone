# Project Scope: Splitwise Clone

This document details the boundaries, functional requirements, and out-of-scope details for the Splitwise Clone project.

---

## 1. Scope Boundaries

The Splitwise Clone is a web-based expense tracking application designed specifically for college students to manage food and travel splits. It handles secure accounts, dynamic balances, multiple currencies, smart CSV imports, and detailed ledger auditing.

---

## 2. Implemented Features

### User Accounts & Session Management
* Secure signup with validation (full name, email, password confirmation).
* Hashed password storage using bcrypt.
* Persistent cookie sessions via Flask-Login.

### Group Management
* Creators can add members from a dropdown of registered users.
* Group creators can remove members (which updates their active interval instead of deleting records).
* Supports re-joining groups (creating multiple historical membership spans).

### Expenses & Splitting
* Divides expenses equally, by percentages, by shares, or by exact amounts.
* Dynamic calculation handles rounding remainders by assigning them to the last participant in the split list.
* Validates percentage splits to sum to 100% (with a minor tolerance of $99.99\% - 100.01\%$).

### Temporal Calculations
* Group member list aggregates multiple active/inactive spans.
* Expenses only split among members whose membership interval overlaps with the expense date.
* Prevent non-active members from being payer or participant.

### Multi-Currency & Conversions
* Track transactions in USD or INR.
* Converts non-base currency transactions (USD) to the group's base currency (INR) using exchange rates stored in the database.
* Balance computations, ledgers, and simplified debt transactions run in INR.

### Smart CSV Importer
* Direct upload of CSV exports.
* Parsed dates, currencies, and split configurations are checked for anomalies.
* Dry-run review screen details warnings for duplicates, split percentage sum errors, and unresolved member names.
* User-friendly interface maps unrecognized CSV names to registered users or auto-creates stub accounts.
* All mapped CSV transactions commit inside a safe SQL transaction block.

### Auditable Ledgers
* Member audit ledgers display every expense split or settlement chronologically.
* Logs original transaction currency, exchange rate, net balance impact, and running net total.

### Debt Simplification
* Dynamically reduces debt matrices on page load to minimize total transfer counts.

---

## 3. Out of Scope Features

The following features are explicitly out of scope:
1. **Receipt Image Processing**: No receipt OCR parsing or attachment uploads are supported.
2. **Notifications**: Email notifications and push alerts are omitted.
3. **General Multi-Currency Conversion APIs**: Exchange rates are fixed/manual in the database (USD to INR default seed is 83.00). No real-time external exchange API integration is included.
4. **General Groups/Friends Boundaries**: Group-less 1-to-1 expenses outside group contexts are not supported.
5. **Mobile Applications**: The application is strictly optimized for web browsers.
