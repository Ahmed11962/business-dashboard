# Deployment, backup and recovery

## Development services

Use the existing `/workspace/business-dashboard` checkout. `uv sync --frozen` installs the lockfile without changing it. `scripts/dev_database.py` starts the retained local PostgreSQL files with a private Unix socket. Do not replace the database to resolve a startup issue. Start Django with `manage.py runserver 127.0.0.1:8000 --noreload`; use local HTTP requests for health checks. There is no supported onboarding web-preview URL.

Development data and secrets live under ignored `.runtime/` with restricted permissions. The seeded live workspace has no users or actual postings. Synthetic test users live only in disposable test databases unless an operator explicitly creates test invitations. Do not reuse test credentials or data in production.

## Deployment architecture

Python 3.12+, PostgreSQL 16+ (local embedded distribution tested separately), Django 5.2 LTS, Gunicorn and static files served by WhiteNoise. The frontend is server-rendered responsive HTML/CSS with normal CSRF-protected forms, avoiding a second client-side authorization layer. No npm build is required.

A deployment example is in `Dockerfile` and `compose.example.yml`. It is a starting point for a chosen host, **not a validated hosted deployment**. Do not expose the app or database publicly before completing GO_LIVE.md. The example intentionally leaves financial execution locked.

1. Select the host, region and data handling policy after the entity’s review. Provision managed PostgreSQL with encryption, automated backups and PITR if supported; use TLS `sslmode=verify-full` and its trusted CA.
2. Keep separate **owner/migration** and **non-owner runtime** database credentials. Runtime must not be superuser, table owner, or `BYPASSRLS`. Never use the local embedded database owner as the deployed app identity.
3. Set `APP_ENV=production`, a new `DJANGO_SECRET_KEY`, `DATABASE_URL`, and exact `ALLOWED_HOSTS` via secret/environment management. Do not place secret values in source, compose files, logs or frontend assets.
4. Run migrations and seed commands using the owner connection. Run the non-owner provisioning script with owner `DATABASE_URL` and secret `APP_DB_PASSWORD`; it grants the runtime role the required table privileges. Review grants with the selected host. Role ownership and RLS validation must be included in the hosted acceptance run.
5. Terminate TLS at a trusted ingress. The app redirects to HTTPS, uses Secure/HttpOnly/SameSite cookies, HSTS, CSP, CSRF and `no-store` on private views. If using a reverse proxy, explicitly configure its trusted forwarded-protocol handling in a reviewed deployment change; do not blindly trust client-supplied forwarding headers. The sample uses Gunicorn SSL directly to avoid assuming a proxy configuration.
6. Collect static files during the build. Use Gunicorn workers appropriate for measured traffic and database capacity; two are a conservative starting point. Health check `/health/` proves HTTP service, not financial readiness. Add database health, integrity, latency/error and backup-failure monitoring on the chosen host.
7. Configure log redaction. Do not log request bodies, cookies, auth headers, invitation-token paths or document contents. Disable general access logs until paths are safely redacted. Error reports must omit request payloads and secrets.
8. Configure a malware scanner and independent audit retention before releasing live documents. This version deliberately keeps live files quarantined and has no public file-serving route. Database storage makes transactional backup of files and metadata consistent; a later object-storage adapter requires its own consistency and authorization tests.
9. Run the complete acceptance suite against a separate production-like test database and restricted runtime identity. Security review, load testing, TLS/ingress validation and provider sandbox tests are outstanding deployment work, not established by local passing tests.

### Database row security and immutable records

`core/migrations/0002_integrity.py` enables tenant policies on business tables. Every authenticated workspace request sets a transaction-local `app.user_id`; policies consult active membership. PostgreSQL owners bypass RLS, so ownership separation is essential. These policies are defense in depth against missing scope predicates, not protection against a fully compromised application server with authority to set its own session context.

Database triggers reject edits/deletes to journals, lines, signatures, decision versions, executions, stock movements, evidence and audit rows. Deferred constraints reject incomplete/unbalanced journals at commit. Additional guards require two distinct current operator signatures, an authorized decision, open accounting period and a test division. A top-level transaction marker permits initial line insertion through nested Django savepoints and prevents adding lines in later transactions. Privileged infrastructure owners can alter database objects; independent immutable backup/audit retention is needed for stronger evidence.

## Consistent backups

Documents are stored as private database bytes, so one PostgreSQL snapshot covers transactions, documents, signatures, audit, invitation metadata, memberships, password hashes, MFA configuration and sessions. This is a sensitive archive: encrypt it with the selected backup service/KMS, restrict access and never store it in Git. The helper produces a private file and SHA-256 sidecar. A checksum detects accidental modification but is not a substitute for authenticated encryption or independent retention.

Install PostgreSQL client tools matching or newer than the server major version. For local tests, bundled clients are at `.venv/lib/python3.12/site-packages/pgserver/pginstall/bin`.

```sh
# DATABASE_URL is injected securely; never print it.
.venv/bin/python scripts/backup.py backup /secure-backups/business.dump --bin /path/to/postgresql/bin
```

The helper refuses to overwrite a backup. `pg_dump --format=custom` uses a consistent database snapshot. A managed PITR schedule and retention are not automatically configured by this script. Owners must approve recovery-point and recovery-time objectives, backup frequency, retention and legal holds. Configure automatic jobs and monitoring accordingly; do not infer a universal legal retention period.

## Clean restore

1. Stop writes and isolate the recovery environment. Provision a new **empty** database using an owner account; do not overwrite the live database.
2. Restore with the matching archive and checksum sidecar:

```sh
# DATABASE_URL now points to the empty recovery database.
.venv/bin/python scripts/backup.py restore /secure-backups/business.dump --bin /path/to/postgresql/bin
.venv/bin/python manage.py verify_integrity
```

3. The helper validates SHA-256, refuses a nonempty target, and restores in one transaction with `--exit-on-error`. Restore failures must not be presented as a valid recovery.
4. Recreate the non-owner runtime role and grants; ownership/ACLs are deliberately excluded from the archive. Validate restricted-role tenant isolation, journal/subledger ties, document hashes, signature/version hashes, memberships, MFA and at least one full read-only walkthrough.
5. Authentication configuration is restored, but revoke old sessions before reopening service to avoid reviving stale logins. Recover or rotate application secrets and signing/encryption keys through the approved secret-manager procedure; they are not embedded in the archive. Check revoked invitations and account changes against independent incident records.
6. Only switch traffic after a reviewed recovery drill. Keep the original database and backups under the retention/legal-hold policy.

The automated restore test performs a real dump/restore into a clean database, verifies transactions, private bytes, both signatures, audit count and user access, and checks refusal to restore onto nonempty data. It does not prove a cloud provider’s backup SLA, PITR, disaster region availability or KMS recovery.

## Portable business exports

Reports provide CSV and JSON. The private division archive includes all scoped records, document bytes, versions, approvals, postings, audit and access metadata with a manifest. It omits passwords/MFA secrets and is not a replacement for the full disaster recovery backup. Do not import it into a live ledger without reconciliation and external-ID deduplication. General-ledger references are unique per division.

## Lost access and incident response

- Disable the affected membership and revoke sessions using a controlled owner maintenance process; log the incident and preserve independent evidence. Do not impersonate an operator or synthesize a signature.
- The two-operator approval rule has no hidden recovery override. An existing operator cannot be replaced by `invite_operator`. Resolve the legal entity’s agreed recovery/mediation procedure with the relevant parties; record the evidence, require a witnessed authorized database migration, invalidate all pending approvals and obtain new signatures. This procedure is not yet a self-service UI and is a launch prerequisite.
- For suspected compromise, isolate the app, revoke sessions, rotate secrets via the secret manager, preserve database/audit/backups under hold and reconcile external bank/supplier activity. Never rewrite accounting history to conceal an event.

## Operating routine

Daily: record actual evidence and exceptions, review approvals, receipts, shipments and due items. Weekly: import and reconcile bank evidence, review aging, check stock and production, update all thirteen forecast weeks. Monthly: reconcile control accounts, jointly approve adjustments/reversals, review funding and tax with the accountant, jointly close the period, and export a review pack. Unresolved reconciliation and missing evidence remain visible; closing a period is not an assurance that external books are complete.
