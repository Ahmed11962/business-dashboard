# Required before live business use

Live execution is **locked in code and in PostgreSQL**. There is no settings checkbox, administrator override or secret that silently unlocks it. Removing the lock requires a reviewed implementation change after the following requirements and the remaining scope in REQUIREMENTS.md are resolved. Development and synthetic end-to-end testing can continue now.

## Information from the owners

| Needed | Why it is needed / where it will be used |
|---|---|
| Actual entity name, legal structure, CR and permitted activity | Entity records, contracts and authority; confirm that the proposed operation is permitted. |
| Sayem and Sami’s full legal names and documented permitted roles/signing authority | Invited identity and governance. Do not infer ownership, work authorization or personal guarantees. |
| Agreed governance, 50/50 economics, ordinary losses, misconduct, exit, deadlock and incapacity terms | Legally reviewed participation and approval/recovery procedures. No unilateral tie-break is implemented. |
| Entity VAT status, taxpayer identity, numbering and actual Phase 2 notification/obligations | Select and validate statutory invoicing integration, rounding and entity-wide numbering. The division is not a separate taxpayer. |
| Accountant decision on authoritative books and reviewed account/cost policies | You confirmed no existing system. Decide whether these books will be authoritative after validation or whether reconciled entries must be exported into another system. Avoid duplicate posting. |
| Verified opening bank/cash, receivables, payables and stock, with as-of dates and statements | Establish opening balances. Unknown balances currently display “Not configured.” Shared bank funds must be allocated and reconciled to the division. |
| Mold quote, supplier identity, receipt for the reported SAR 10,000, payment date and actual payer | Verify the historical draft, funding classification and VAT treatment; avoid duplicating an entry in the father’s entity books. |
| Mold balance milestones, design version, legal ownership, acceptance, warranty and custody/retrieval terms | Contract and asset acceptance, useful life, residual value and approved depreciation method. |
| Product name/photo/specification, tolerances, reference sample and carton conversion | Quality inspections and saleable units. No carton size or tolerance is assumed. |
| Written factory quote and minimum batch | Confirm input-vs-output kg basis; resin/color/waste/regrind/packing/VAT inclusions; who owns materials and scrap; reject remedies. |
| Tested wholesale price, VAT basis, buyers, delivery and credit terms | Approved sales terms, margins and customer credit policies. Candidate SAR 2–2.50 prices are not verified orders. |
| Funding counterparty, recipient, classification, actual disbursements, future limit and agreed repayment conditions | Funding statement and repayment proposal; obtain counterparty consent. Principal repayment is not operating expense. |
| Compensation, reserve, next production cycle and legal distribution rules | Implement reviewed mappings and cash/profit eligibility. Distributions and compensation posting are disabled. |
| Stock locations, freight, packing, storage, sales costs and salaries | Complete landed cost and cash forecast. Missing costs are not verified zero. |
| Separate invitation emails | Issue individual invitations only when agreed. No passwords or secret keys in chat. |

## Production engineering and professional validation

- Complete the required operating scope marked partial or blocked in REQUIREMENTS.md for the actual chosen workflow. The current implementation is strongest for factory-supplied material and management accounting in a test workspace.
- Have an accountant validate recognition, VAT input/recovery, advances, mold asset/depreciation, rejected goods, control accounts, opening balances and period-close controls against representative evidence.
- Select Saudi-appropriate hosting and review data location/cross-border handling, privacy, minimization, retention, legal holds and incident response with qualified advisers. No legal compliance badge is asserted.
- Supply deployment account access through secure environment settings. Use separate database owner/migration and non-owner runtime credentials, TLS with proper certificate validation, encrypted volumes/backups and a secret manager.
- Integrate and test a private malware scanner before releasing quarantined live files. This release stores private bytes transactionally in PostgreSQL; there is no public object URL. Optional private object storage needs a separately validated adapter.
- Select an e-signature provider only if needed; validate authority, signature requirements, authenticated webhooks, idempotency and completion evidence. Current upload evidence is explicitly not independently verified. No automatic contract completion occurs.
- Select the accounting/e-invoicing integration, validate current official requirements and test with its sandbox. Do not issue live invoices from the current management invoice record.
- Run tests using the exact deployed non-owner role and connection pool, secure ingress, chosen backup service and production-like data volumes. The local owner connection is a development convenience, not a production permission configuration.
- Configure monitoring and redacted logging, alerts, a retention schedule and recovery objectives; perform a witnessed restore and access-revocation/recovery drill. The local restore test is evidence of the backup method, not a managed hosting backup SLA or PITR service.
- Document the dual-review initial invitation and lost-access procedure. Initial invitations are audited; replacements and role-policy changes are intentionally not self-service until that procedure is agreed and implemented.

## What the application will not do automatically

No transfer at the bank, tax filing, customer/vendor message, signature on someone’s behalf, automatic payout, or guarantee that external physical actions were authorized. If dual bank authorization is required, establish it at the bank. An outside payment can be recorded immediately as an exception without fabricating prior consent.
