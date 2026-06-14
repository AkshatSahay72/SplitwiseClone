# AI Assistance Usage: Splitwise Clone

This document details how the AI coding assistant, **Antigravity**, was utilized during the development of the Splitwise Clone.

---

## 1. Collaborative Pair Programming Model
The Splitwise Clone was built through pairing between the developer and Antigravity. 
* The developer provided high-level system requirements, database access, credentials, and review feedback.
* Antigravity performed codebase analysis, designed relational schemas, wrote python controller blueprints, built premium Jinja2 views, and implemented the automated test suite.

---

## 2. Tool Integrations & Execution
Antigravity used several specialized integration tools:
1. **File Search & Viewers**: Ripgrep and file-reading tools were used to audit the structure, locate routes, inspect layout CSS, and verify SQLAlchemy types.
2. **Terminal Runner**: Used to execute unit tests (`tests/test_algorithms.py`) locally, verify code syntax correctness, and ensure clean server starts.
3. **Database Inspection**: Inspected live tables on Supabase to ensure columns were correctly modified and initialized.

---

## 3. Scope Management
* Proactively negotiated out-of-scope compromises (such as omitting complex invite workflows in favor of a clean dropdown mapping selector for the CSV importer).
* Implemented strict rounding logic and tolerance parameters for split verification.
