# Information needed before live business use

The application is ready for private testing with synthetic records. It records internal management activity only; it cannot send payments, bank transfers, statutory invoices, or tax filings. Test and live workspaces remain separate.

| Information or decision needed | Why it matters |
| --- | --- |
| Sami's invitation email and both operators' verified authority | Sami must enroll with his own account and authenticator; nobody can vote for him. His invitation stays pending until his email is provided. |
| Accountant's confirmation of the new authoritative accounting system, opening balances, and date of transition | The management register and historical posted records are not automatically the legal books. Named cash/bank balances require verified openings and assignment of future payments. |
| VAT registration status, tax treatment, and Saudi invoice compliance plan | Internal sales PDFs are explicitly not verified ZATCA tax invoices. Tax amounts are manually entered for planning only. |
| Legal ownership and physical possession evidence for each mold | Full payment alone does not prove ownership. The app tracks ownership confirmation separately. |
| Written classification and terms for each funder contribution | Contributions are not assumed repayable. Legal repayment obligations and their priority must be confirmed before recording repayments or relying on distribution plans. |
| Sayem and Sami's formal 50/50 agreement, retention rules, taxes, reserve policy, and approval thresholds | The 50/50 planner is illustrative, does not authorize a payment, and can overstate available funds if liabilities or reserves are missing. |
| Policy for rejected goods, damaged goods, supplier credits, and final production-cost allocation | Only accepted units enter inventory. Rejected/damaged production costs need an agreed loss or supplier-credit treatment before final profit can be authoritative. |
| Hosting, malware scanner, backups, recovery owner, and restore drill | New live files remain quarantined and cannot be previewed or downloaded until scanning is configured. A retained backup and recovery process must be tested. |

No payer, contributor, mold owner, loan, or opening balance is inferred. Older records with different assumptions stay preserved as historical evidence and should be reviewed with the accountant rather than silently changed. Live financial execution remains disabled; testing should continue in Test until the items above are confirmed.

For a hosted deployment that already uses a non-owner PostgreSQL runtime role, the database owner should run `python scripts/grant_runtime_updates.py` after migrations with the owner `DATABASE_URL` and the configured `APP_DB_ROLE`. This idempotently grants access to the new tables while preserving the existing authority restrictions; verify row security in that environment before launch.
