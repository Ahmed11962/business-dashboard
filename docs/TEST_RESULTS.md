# Executed validation — 15 October 2026, Asia/Riyadh

The latest full run of `.venv/bin/pytest -q --disable-warnings --maxfail=1` completed with **53 passed, 0 failed, 0 errors, 0 skipped**, in 41.31 seconds. PostgreSQL and real Chromium were used, not SQLite or browser mocks. One harmless local-runtime warning reports that `XDG_RUNTIME_DIR` falls back to `/tmp/runtime-1000` for the bundled PostgreSQL launcher.

## What executed

- Exact reference calculations, 95% yield, charge bases, decimal rejection rules, VAT total-level rounding, both break-even views and cash-reserve repayment calculation.
- Immutable joint approvals, second-user identity, duplicate/stale/hash rejection, material changes, automatic document-replacement invalidation, concurrent signatures and at-most-once execution.
- Concurrent stock reservations without overselling; quarantine/reject rules; purchase/production/receipt/quality/bill/sale/delivery/invoice/collection; partial payments and returns/refunds.
- Customer deposits and allocations; supplier advances/refunds; mold asset acceptance and operating depreciation; principal repayments distinct from profit; distribution/compensation lock.
- Balanced ledger enforcement, direct unapproved database posting rejection, immutable journals and signatures, period locks/reversals, nested-transaction regression and control-account/management-statement reconciliation.
- Cross-tenant document/export denial, read-only write rejection, CSRF, MFA replay rejection, membership revocation, non-owner PostgreSQL RLS and successful nested posting with a provisioned non-owner runtime role.
- Internal contract approval versus unverified uploaded external evidence, changed-contract snapshot rejection, draft PDFs and complete private archive manifests.
- Actual `pg_dump`/`pg_restore` into an empty database, restoring postings, document bytes, approvals, audit and user/password/access configuration; refusal to restore into a nonempty database.
- Two independent Chromium sessions: password/TOTP login, recent TOTP reauthentication, nine decisions with eighteen signatures through real CSRF-protected forms, purchase through bank matching, desktop/mobile screenshots and no mobile horizontal overflow.

## Additional checks

- `manage.py check`: passed.
- `manage.py makemigrations --check --dry-run`: no missing migrations.
- `manage.py verify_integrity`: passed for the current seeded environment.
- `manage.py check --deploy` with production settings and a temporary secret: passed after adding clickjacking middleware. This is a configuration check, not a hosted deployment security certification.
- Repeated `scripts/install.sh`: lockfile install, retained PostgreSQL restart, migrations, idempotent seeding, static collection and checks passed.
- Gunicorn started locally; landing, health and login returned expected HTTP 200 content.
- Screenshots were inspected at desktop and 390px mobile widths. All screenshot transactions are explicitly synthetic.

## Fix found by real browser validation

The first browser run exposed a genuine PostgreSQL immutability bug under nested Django transactions: comparing row `xmin` to the top-level transaction ID incorrectly rejected initial journal lines created inside a savepoint. Migration `0004_nested_transaction_posting` stores the top-level transaction marker explicitly. A dedicated regression test and the repeated full browser workflow passed afterward. Earlier failing attempts were not counted as acceptance passes.

## Not established by these tests

No invitation emails were sent. No production users, verified balances, invoices or transactions were created. Hosted ingress/TLS, provider webhooks, statutory e-invoicing, malware scanning, managed backup scheduling/PITR, legal/tax/accounting review, load testing and complete brief scope are not established. See REQUIREMENTS.md and GO_LIVE.md. Live execution remains disabled in application and database code.

## Simplified dashboard validation

The added tests cover SAR scenario math and break-even, cash versus recognized expense, unpaid and partial balances, refunds, duplicate references, audited edits, multiple PDF/image attachments, browser preview/download, Excel/PDF/CSV exports, opening balances, reader restrictions, two independent votes with recent reauthentication, tenant isolation and repeatable synthetic seeding. Additive migrations 0005–0011 were applied to the retained cloud database; `verify_integrity` passed afterward without rewriting historical postings. The Mac upgrade path includes a full pre-migration PostgreSQL backup.
