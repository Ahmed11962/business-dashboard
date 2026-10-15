# Plastics Desk

A private, two-operator plastics manufacturing and finance dashboard built with Django and PostgreSQL. The six main sections are Dashboard, Molds, Production, Products & Inventory, Sales & Invoices, and Finances. Decisions, calculators, documents, and reports remain available from the top bar. Sayem and Sami keep separate invitations, passwords, and authenticator codes. No bank, payment, transfer, outbound invoicing, or tax service is connected.

This redesign extends the existing application with additive migrations. Historical posted journals, approvals, files, permissions, and audit records remain in place. The Test workspace contains clearly synthetic data; live records stay separate. Payments are stored once in the existing `FinanceTransaction` register and linked to molds, production batches, invoices, or capital. Stock changes use an append-only event ledger and locked product balances. Invoice issue, goods dispatch, collection, return, credit, and refund are separate events.

## Test it on a Mac

Follow [the Mac testing and safe update guide](docs/MAC_TESTING.md). Existing Mac users should back up the local database before switching to the `manufacturing-workflow` branch. Keep `.runtime/`: it contains the PostgreSQL database, uploaded documents, local secrets, invitations, and backups. `./scripts/install.sh` applies migrations and adds the synthetic basket walkthrough only to Test if it is not already present.

For a fresh clone with Homebrew's `uv` installed, use:

```sh
./scripts/install.sh
./scripts/prepare_local_test.sh YOUR_EMAIL
./scripts/start.sh
```

In another Terminal window, run `./scripts/open_local_invitation.sh` to enroll. Open `http://127.0.0.1:8000/login/` on later days.

## Working with the figures

[Manufacturing and accounting rules](docs/MANUFACTURING_WORKFLOW.md) explain when cash, sales revenue, inventory, cost of goods sold, profit, and obligations change. The internal sales PDF is not a verified ZATCA tax invoice. Opening balances, authoritative accounting books, legal funding terms, stock valuation exceptions, and live document scanning need review before launch.

## Developer checks

```sh
.venv/bin/python -m pytest -q
.venv/bin/python manage.py check
.venv/bin/python manage.py makemigrations --check --dry-run
.venv/bin/python manage.py verify_integrity
```

The test suite includes production arithmetic, the 5,000-basket purchasing-to-collection scenario, partial payments, inventory movements, returns, credits, capital, attachments, permissions, approvals, migrations, historical ledger integrity, and a real Chromium browser test. The earlier advanced workflow URLs remain available for historical records and controls.
