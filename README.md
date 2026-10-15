# Business Finance

A private, two-operator business finance and decision dashboard. The main navigation has six sections: Dashboard, Transactions, Decision Calculator, Decisions & Approvals, Documents, and Reports. It uses SAR by default. Sayem and Sami have separate invitations, passwords and authenticator codes. No payment, bank transfer, outbound invoice or tax service is connected.

The simple management register records cash paid/received, amounts owed, and estimated income/expenses separately. Historical posted journals, approvals, documents and audit records from the earlier workflow are preserved and shown separately in Reports or historical decision links. They are not automatically merged into the new register because copying an old event could count it twice. Opening cash/bank balances must be explicitly entered and dated before a current balance is shown. An accountant must confirm the authoritative books before live use.

## On a Mac

Follow [first-time setup and safe update instructions](docs/MAC_TESTING.md). For a fresh clone with Homebrew's `uv` installed:

```sh
./scripts/install.sh
./scripts/prepare_local_test.sh YOUR_EMAIL
./scripts/start.sh
```

In another Terminal window run `./scripts/open_local_invitation.sh` to enroll. The first command installs locked Python dependencies, starts a private local PostgreSQL server, applies additive migrations, and loads synthetic sample data only into the Test workspace. Repeatable setup leaves existing entries alone. The database, uploaded files, secrets and backups are stored under ignored `.runtime/`; keep that folder when updating.

## What the new sections do

- **Dashboard:** cash received/paid, net movement, dated account balances when entered, open receivables/payables, estimated income/expenses/profit, pending decisions, and monthly activity.
- **Transactions:** quick entry, partial payments, unpaid amounts, refunds, optional payer/payee, multiple evidence files, search, date/category filters, audit-backed edits, and CSV/Excel export. One reference cannot be reused in a workspace.
- **Decision Calculator:** saved, side-by-side SAR scenarios for investment, units, unit cost, price, additional costs, gross margin, break-even, projected profit and ROI. Estimates do not post actual money.
- **Decisions & Approvals:** proposals, risks, benefits, documents, linked scenarios and transactions, comments and individual votes. Each proposal specifies one or two independent approvals. Votes require recent password and authenticator verification. Users cannot vote twice or for each other.
- **Documents:** private PDF/image/text files, linked evidence, search, browser preview and download. Live downloads are blocked until malware scanning is configured; the Test workspace permits testing.
- **Reports:** spending categories, monthly/yearly comparisons, money in/out, outstanding items, estimated results, separate historical posted results, and Excel/PDF export.

Existing advanced workflow URLs remain available to preserve historical records and controls, but are not part of the six-section navigation. Their old funding classifications are historical data, not assumptions in new entries. The live workspace still blocks financial execution; the Test workspace is clearly marked synthetic.

## Developer checks

```sh
.venv/bin/pytest -q
.venv/bin/python manage.py check
.venv/bin/python manage.py makemigrations --check --dry-run
.venv/bin/python manage.py verify_integrity
```

The PostgreSQL test suite covers decimal math, partial payments/refunds, file uploads/downloads, permissions, two-person approvals, migrations, historical ledger reconciliation, and browser interactions. See [test results](docs/TEST_RESULTS.md), [data preservation notes](docs/SIMPLIFICATION.md), and [launch inputs](docs/GO_LIVE.md).
