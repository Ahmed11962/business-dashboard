# Plastics business workspace

A working, invitation-only Django/PostgreSQL application for the plastics division. It separates unverified business facts, planning scenarios, decisions and posted accounting. **This is a tested development release, not a launch-ready accounting or tax system. Live financial execution is deliberately blocked in both the service and database layers.**

The owners reported no existing accounting system. An accountant must confirm the authoritative books before live use. Reports remain division management records. No user identities, opening balances, bank funds, receipts or actual sales are invented.

## Run locally

For a first-time Mac setup, follow [the Mac testing guide](docs/MAC_TESTING.md). In an existing checkout with `uv` installed, run `./scripts/install.sh` once and `./scripts/start.sh` each time you want to use the app. The install script obtains Python 3.12, installs locked dependencies, starts the bundled local PostgreSQL server, applies migrations and loads the synthetic Test workspace. Chromium is optional and only needed for browser automation tests.

The local PostgreSQL server uses a private Unix socket and `.runtime/postgres`; connection details and a random development Django key are kept in ignored, permission-restricted files. `scripts/dev_database.py` restarts the database after a machine restart without deleting data. It is not a production database installer. A fresh Mac checkout has its own database and invitation, separate from the cloud workspace.

`seed_workspace` is repeatable. It creates unverified placeholders, two pending operator invitations without emails, eight lawyer-review contract drafts and **zero posted transactions or active users**. `--demo` creates a separate, visibly labeled test division. Do not enter real personal or business data into the test workspace.

## Invite the operators

No default passwords, public signup or automatic messages exist. First agree who occupies each operator slot. Obtain the real invitation email privately through your normal invitation workflow.

```sh
.venv/bin/python manage.py invite_operator DIVISION_UUID sayem EMAIL \
  --governance-reference 'reference to agreed initial authority' \
  --output .runtime/sayem-invitation.txt
```

Repeat for `sami` with a distinct email and output file. Deliver the one-use path through an authorized secure channel. Do not commit it, paste it in public logs or send passwords. Invitations expire after 48 hours. Enrollment sets an individual password and prompts for authenticator setup. Replacing an existing operator is deliberately unavailable through the bootstrap command; see the recovery runbook.

Both operators must enroll before decisions can be created. Signing and recording execution require password plus fresh, one-use TOTP verification, valid for five minutes. The same authenticator code cannot be reused for login and reauthentication; use the next code. Technical administrators have no financial authority.

## Reviewable implementation stages

1. **Foundation:** migrations; tenant-scoped access; invitations and TOTP; decimal double-entry ledger; immutable versions, signatures and evidence; unanimous approvals; funding drafts; dashboard. PostgreSQL policies and triggers supplement server checks.
2. **Operating workflow:** purchase approval → production release → receipts → quality release → weighted-average stock → reserved sales order → delivery/revenue/COGS → management invoice → partial collection → statement matching. Includes bills, payments, returns, credit/refund handling, principal repayment, period locks and linked reversals.
3. **Documents and operations:** eight lawyer-review templates, draft PDF export, private versioned evidence, tenant archive/CSV/JSON exports, full database backup and tested clean restore, deployment/recovery guidance. External signing, statutory invoicing and production operational validation remain blocked, not simulated.
4. **Deferred enhancements:** full Arabic translations, automated reminders, richer forecasts and optional external integrations. The layout uses logical CSS properties and UTF-8 for future RTL support; Arabic UI and Arabic PDF rendering are not delivered.

See [stage demonstrations](docs/STAGES.md), [requirement matrix](docs/REQUIREMENTS.md), [launch inputs and blockers](docs/GO_LIVE.md), and [operations](docs/OPERATIONS.md). The matrix is authoritative about incomplete scope; these stage summaries do not mean every feature in the brief is complete.

## Validation

```sh
.venv/bin/pytest -q
.venv/bin/python manage.py check
.venv/bin/python manage.py verify_integrity
```

Tests use an isolated PostgreSQL test database. Financial tests exercise exact decimal reference values, VAT, funding, stock/COGS, collections, returns, period locks and reversals. Approval tests exercise API bypass, duplicate signatures, stale versions, material/document changes, concurrent signatures, repeated execution and overselling. Security tests exercise tenant isolation, read-only roles, CSRF, MFA and non-owner database row security. Browser tests use two independent Chromium sessions, real login/TOTP, and form-based joint decisions. A restoration test runs `pg_dump` and `pg_restore` into a new empty database and checks postings, private files, signatures, audit and user access.

If Chromium is absent, the browser test explicitly skips; a skipped browser test does not establish end-to-end readiness. The browser test waits at most one TOTP period for a fresh code. Screenshots in `docs/screenshots` are labeled synthetic test workspaces.

## Financial conventions

All financial inputs use decimal strings. Calculations use `Decimal`, never binary floats. Posting rounds SAR lines to 2 decimals, half-up; unit-cost calculations retain precision. The reference VAT scenario uses total-level net rounding and residual VAT. **These are management calculations, not a validated statutory invoice rounding engine.**

The SAR 20,000 mold quote, reported SAR 10,000 direct payment, remaining SAR 10,000 commitment and 100,000-unit batch are unverified facts/plans. The reported direct payment has no date, proof or legal classification yet. Only an evidence-backed, jointly approved posting in the test workspace credits a funding account and debits supplier advance; it does not inflate bank cash.

Profit, cash movement, outstanding principal and proposed distributions are distinct. 50/50 is proposed economics, not registered ownership. No payout activation, bank transfer, tax filing or external signing endpoint exists.
