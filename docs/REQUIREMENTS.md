# Requirement coverage and remaining scope

Source: [user-supplied brief](BRIEF.md). The brief defines product requirements; it does not supply verified legal facts, production credentials or business evidence. The user additionally confirmed that **no accounting system currently exists and an accountant must confirm the authoritative system**.

Statuses: **Implemented** means executable code with relevant local tests; **Partial** identifies specific unfinished engineering; **Blocked** needs business/professional/provider input as well as subsequent implementation or validation; **Deferred** is optional later scope. Nothing marked Partial/Blocked is represented as ready for real transactions. All live financial execution is intentionally locked.

## Initial facts, boundaries and user experience

| Requirement | Status / implementation or gap |
|---|---|
| Separate legal entity and division | Implemented: entity FK on division; all business records are scoped through the division; canonical approvals include both IDs. |
| CR, VAT, authority, accounting-source onboarding | Implemented placeholders and visible launch flags. Blocked on actual identities and professional review. No live activation switch. |
| Known product, quote, payment and commitment | Implemented exact unverified facts in `seed.py`. No invented receipt, date, supplier or opening balance. |
| 100,000-unit batch and candidate prices | Implemented forecast/scenario records only. No stock or revenue seeded. |
| Pending invitations without invented addresses | Implemented; no users or built-in passwords seeded. |
| Test/live separation, unknown balances | Implemented distinct divisions, labels and live lock. Opening cash remains Not configured. |
| Responsive English interface, all navigation sections | Implemented, inspected desktop/mobile with Chromium. Forms for workflow decisions use explicit references and some technical JSON inputs; richer task-specific forms remain Partial. |
| Arabic/RTL structure | Logical CSS and Unicode implemented. Full translated UI, RTL browser acceptance and Arabic PDF fonts/shaping Deferred. |
| Drill-down totals, dates, source labels, empty states | Implemented links to records/ledger and as-of/source notices. More granular account filters and statement-date completeness Partial. |
| Search | Implemented tenant-scoped title/document-metadata search. OCR/body search and richer indexed full-text filters Deferred. |
| Multiple products/factories/locations/customers | Implemented scoped records and SKU/location/lot dimensions. Rich master-data screens and validated external IDs Partial. |

## Financial arithmetic and accounting

| Requirement | Status / implementation or gap |
|---|---|
| Reference SAR 36,900 / 0.369 / 56,900 / 46,900 | Implemented exact Decimal calculations and tests. |
| Yield and explicit input/output/piece/hour bases | Implemented calculator with separate resin and extra-cost inputs. Detailed runner/regrind mass balance Partial, dependent on factory specification. |
| VAT-inclusive reference and two break-even definitions | Implemented total-level illustrative rounding and ceil-based views. Statutory invoice rounding Blocked on entity/accountant/provider validation. |
| High-precision money, balanced journals | Implemented Decimal services, halala posting, PostgreSQL constraints and deferred balance triggers. |
| Authoritative books, external source deduplication | Unique journal reference per division implemented. General export implemented. Named accounting connector/import mapping Blocked on accountant/system selection. |
| Father's direct payment and classification | Implemented evidence-backed test posting to supplier advance/funding, without bank inflation. Real classification/evidence Blocked. |
| Commitment separate from payable | Implemented no automatic bill from quote/commitment. Approved receipts/bills are separate events. Remaining commitment matching/roll-forward Partial. |
| Mold advance → asset → depreciation | Implemented advance, refund, acceptance and explicit operating depreciation actions. Configurable useful-life schedule, units-of-production depreciation and inventory capitalization Partial/Blocked on policy. |
| Sales/delivery/invoice/payment separate | Implemented revenue+COGS at approved delivery, management invoice without duplicate posting, partial collections. Actual recognition policies Blocked on accountant review. |
| Deposits not revenue | Implemented customer deposit liability and approved allocation to receivable. |
| Posted immutability, reversals, period close/reopen | Implemented database immutability and jointly approved period changes. Subledger events use returns/refunds rather than unsafe generic reversals. |
| Accounts for cash, assets, tax, funding, inventory, expenses | Implemented chart and journal validation. Raw-material/WIP operational subledgers, input VAT recovery workflows and automated allocation Partial. |
| Principal versus profit and compensation/distribution | Principal repayment implemented and tested, separate accounts defined. Compensation/distribution posting Blocked/disabled pending legally reviewed arrangement. |
| Bank CSV, deduplication, matching and unreconciled rows | Implemented stable external IDs, conflict detection, exact amount/tenant matching and statement dates. Shared-account allocation must be supplied; no automatic whole-bank balance. |
| Numbered cash receipt evidence | Unique posting references and private evidence required. Dedicated receipt-number sequence/PDF Partial. |

## Joint decisions and security

| Requirement | Status / implementation or gap |
|---|---|
| All supported business actions require both named operators | Implemented with no amount thresholds or standing exceptions; generic resolutions record other decisions but do not execute unsupported actions. |
| No same-user second consent or technical-admin override | Implemented server checks, unique constraints, distinct slots and database posting guard. |
| Immutable version/payload/document hash and signature history | Implemented canonical SHA-256 payload, contract snapshot, document hashes, consent, UTC timestamp and auth-event ID. |
| Material edits invalidate approvals | Implemented new unsigned decision versions. Replacing referenced evidence automatically revises pending decisions; historical signatures remain. Contract field changes block stale execution. |
| Concurrent signatures/execution/idempotency | Implemented division row lock, atomic effects, unique execution keys and PostgreSQL constraints; real concurrent tests. |
| Exact payment amount and beneficiary | Implemented approved payload; supplier payment beneficiary must match the signed bill. Beneficiary master-data management and controlled change workflow Partial. |
| Workflow states | Draft/submitted/one-signature/authorized/executed/closed/rejected/withdrawn implemented. Superseded versions preserved. Expiry enforcement exists in services but expiry editing/scheduling UI is Partial. |
| Factual exceptions without prior authorization | Implemented unverified records and audit. Jointly approved posting remains separate; no fabricated retroactive authorization. |
| Deadlock, reminders, mediation | Rejection blocks execution. Mediation/recovery agreement Blocked on owners; automated reminders Deferred. |
| Invitations and MFA, sensitive reauth | Implemented local invited authentication, strong password validation, TOTP replay protection, session rotation/revocation and 5-minute signing auth. Managed identity-provider adapter Deferred. |
| Read-only/reviewer roles | Models, server enforcement and tests implemented. Optional-role invitation UI Partial; no father/accountant account automatically created. |
| Governance changes and lost access | No hidden override. Initial bootstrap is audited; replacement/approval-policy workflows Blocked on agreed process and subsequent implementation. |
| Tenant isolation, exports, private downloads | Implemented request scoping and non-owner PostgreSQL RLS. Tests include cross-tenant access and restricted-role posting. Full hosted connection-pool validation remains Blocked on deployment. |
| TLS/cookies/CSRF/CSP/rate limiting/parameterized queries | Implemented settings and protections; production ingress/certificate testing Blocked on host. No public signup. |
| Audit | Append-only application events with hash chain and database edit protection. Infrastructure owners retain privileged access; independent immutable retention Blocked on provider/policy. |

## Operating workflows

| Requirement | Status / implementation or gap |
|---|---|
| Purchasing through invoice/payment | Implemented approved order → quantity-controlled production release → receipt → quality → bill → partial payment. Rich requisitions and supplier credit-note matching Partial. |
| Production rate/quantity/material-ownership terms | Implemented approval fields and forecast bases. Detailed actual consumption, scrap recovery, owned raw material at factory and regrind subledger Partial. Current tested path is factory-supplied material. |
| Quality acceptance/rejection and evidence | Implemented quarantine, accepted/rejected quantities, inspection description and private documents. Structured contractual tolerance checks, rework and measurement UI Partial. |
| Mold register and custody | Initial record and extensible factual metadata implemented. Maintenance scheduler, complete handover history and asset retrieval workflow Partial. |
| Weighted-average stock, lot trace, reservations | Implemented by SKU/location across available company-owned lots; negative and concurrent overselling blocked. |
| Extended inventory states, carton conversion, external ownership | Expected planning, quarantined, available, reserved, delivered, returned and scrapped flows implemented. Transfers/in-transit, carton conversion, FIFO and third-party custody workflows Partial. Do not infer owned materials. |
| Customers, price/terms approval, receivables | Customer facts and per-order unanimous price/VAT/credit terms implemented. New credit for overdue customers blocked. Leads, sample pipeline, reusable approved price lists/minimum margins/global credit-limit UI Partial. |
| Delivery, management invoice, receipt allocation | Implemented; duplicate invoice posting rejected. Statutory tax invoices disabled. |
| Returns, customer credit/refund, supplier advance refund | Implemented and tested. Return stock quarantined. Supplier defective-product claims and multi-invoice netting Partial. |
| Funding ledger and repayment availability proposal | Implemented principal movement, classification, reserve-based calculator and counterparty-consent field. Scheduling and automated eligibility proof Partial. No transfer or automatic commitment. |

## Documents, reporting and operations

| Requirement | Status / implementation or gap |
|---|---|
| Eight legal/acceptance templates | Implemented field/clause checklists and PDF draft workflow. They are not complete legal prose or ready-to-sign agreements; legal review Blocked. |
| Contract versus internal approval | Implemented separate status, immutable approval snapshot and unverified external evidence. Internal approval never means external execution. |
| Private uploads and versions | Implemented 10 MB limit, MIME/magic checks, immutable bytes/hash and replacement links. Stored transactionally in PostgreSQL. |
| Scan/quarantine | Quarantine implemented; live individual/archive downloads blocked while quarantined. Scanner/object-storage integration Blocked on provider selection and validation. |
| External certified signatures and webhooks | Blocked; no provider chosen or credentials. No enabled webhook/pretend completion endpoint. Adapter interface documented in integration module. Uploaded drawings/signatures never acquire verified status. |
| P&L, trial balance, ledger, management position, cash movement | Implemented from posted ledger; control-account tie checks. Statutory/entity consolidated statements not claimed. |
| Inventory valuation, delivered batch gross margin, aging | Implemented from stock/open items/deliveries, with returns accounted for. Full manufacturing variance profitability Partial. |
| Funding, commitments, tax controls, approval exceptions | Implemented management views. Final remaining commitment amount, input VAT recovery, entity tax reserve and profit eligibility Blocked/Partial. |
| Thirteen-week cash forecast | Implemented dated manual inflows/outflows and unknown opening balance. Forecasts never post. Automated commitment/due-date integration and scenarios Deferred. |
| CSV/JSON/PDF/complete archive | Trial balance CSV, structured reports, contract PDFs and complete tenant archive implemented. Complete monthly PDF review-pack formatting Partial. |
| Backup/restore, user access and documents | Full PostgreSQL dump/restore helper implemented and clean restore tested. Encryption, schedules, retention, legal holds and managed PITR Blocked on hosting/policy. |
| Monitoring/error reporting/incident recovery | Health endpoint, security headers and runbook implemented. Hosted telemetry/alerts/error redaction service and recovery drill Blocked on hosting. |
| AI assistance, messages, bank transfers, tax filing | No AI posting/signing, external messages, transfers or filings. Optional future integrations Deferred and must independently enforce authorization. |

## Acceptance tests from the brief

| # | Evidence / result boundary |
|---|---|
| 1–3 | `test_finance.py`: exact weight/factory values, 95% yield, total-level VAT. Statutory invoice rounding remains blocked. |
| 4–5 | Funding/duplicate-source and seed tests: direct payment avoids bank, no invented bill/stock. |
| 6–8 | Approval and API tests: one signer, duplicate/stale/edit/hash, concurrent signing/execution. Signing-provider webhook execution is not enabled, so provider retry acceptance remains blocked. |
| 9 | Service and two-session browser test: delivery/invoice/partial receipt affect each ledger once. |
| 10 | Return/refund/reject/quarantine/oversell tests, including concurrent reservations. Complex supplier claims remain Partial. |
| 11 | Balanced/unbalanced DB tests, immutable history, close-period/reversal and report ties; nested-savepoint regression. |
| 12 | Principal-not-profit test; compensation/distribution deliberately disabled rather than mapped without legal terms. |
| 13 | Cross-tenant/read-only/export/CSRF tests, non-owner RLS visibility and restricted-role posting. |
| 14 | Unconfigured signing route cannot mark a contract complete; uploaded evidence status stays unverified. Real-provider webhook acceptance Blocked. |
| 15 | Real pg_dump/pg_restore into clean DB checks journals/documents/signatures/audit/user access and rejects nonempty target. |
| 16 | Real Chromium test: two independent password/TOTP logins and nine jointly approved actions through purchase → reconciliation. |
| 17 | Seed/dashboard/forecast tests: no forecast in ledger, cash unknown until openings verified. |
| 18 | Internal contract approval and uploaded evidence tests: neither creates externally executed/provider-verified state. |

See TEST_RESULTS.md for the latest executed counts. Passing these tests demonstrates the implemented development workflow; it does not satisfy blocked statutory/provider/production acceptance items.
