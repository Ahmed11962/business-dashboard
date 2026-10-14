# Implementation references

Reviewed for this implementation on 15 October 2026 (Riyadh):

- Django 5.2 official transaction documentation, including nested `atomic`, savepoints and handling errors outside the failed transaction: https://raw.githubusercontent.com/django/django/stable/5.2.x/docs/topics/db/transactions.txt
- Django 5.2 official authentication documentation, individual users, sessions and login forms with CSRF: https://raw.githubusercontent.com/django/django/stable/5.2.x/docs/topics/auth/default.txt
- PostgreSQL official concurrency/locking source documentation: https://raw.githubusercontent.com/postgres/postgres/REL_17_STABLE/doc/src/sgml/mvcc.sgml

The official documentation website hosts rejected this environment’s requests with proxy HTTP 403; the corresponding official upstream GitHub documentation was fetched successfully. Dependency versions and artifact hashes are frozen in `uv.lock`; TLS/checksum validation was not disabled. Runtime behavior was verified against the installed versions and real PostgreSQL.

Legal/tax links in BRIEF.md were supplied by the user’s document. They have not been revalidated as part of this build and are not treated as a legal determination. Current entity-specific statutory rules, signature requirements and provider documentation must be checked at launch; no external signing, tax or banking integration is represented as complete.
