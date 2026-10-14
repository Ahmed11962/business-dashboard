# Codex build brief for the plastics business dashboard

## Instruction to Codex

Build a working, secure, multi-user business management web application from this specification. This is a real business application, not a visual mockup. Implement in reviewable stages, run the acceptance tests, and provide setup, backup, restore and deployment instructions. Inspect any existing repository and its instructions first. Reuse an appropriate existing stack; for a new project, a conventional TypeScript web frontend, server API, PostgreSQL database, managed authentication and private object storage is a reasonable implementation choice. Verify current official documentation for dependencies and integrations at implementation time.

Do not invent legal identities, credentials, signed agreements, bank balances, tax status, production receipts or sales. Keep forecasts, demo fixtures, reported historical events and verified posted transactions visibly separate. Complete everything possible with configuration placeholders, then identify precise remaining deployment or compliance dependencies. Do not claim a production-ready system while critical tests or integrations remain incomplete.

## Business context and known information

The operators are Sayem (confirm full legal name) and Sami (full legal name unknown). They intend an equal 50/50 economic arrangement and joint decision approval. Operations will be under the father's existing Saudi legal entity and commercial registration. Father provides funding to be repaid gradually when the business can afford it. Legal ownership, employment arrangements, authority to bind the entity and loss liability are NOT confirmed.

The business owns or intends to own molds and outsources plastic production to a factory. It does not currently operate its own factory. The first product is provisionally named Plastic flower holder, SKU FLW-001; exact product name, specifications and photograph are pending.

Known values:
- Currency SAR; user timezone Asia/Riyadh.
- Mold quoted total SAR 20,000; VAT inclusion unknown.
- Father reportedly paid SAR 10,000 directly toward the mold.
- Remaining mold commitment SAR 10,000; due date unknown.
- Mold lead time approximately one month; contractual starting date and acceptance conditions unknown.
- Planned first batch 100,000 pieces, not yet produced or ordered on confirmed terms.
- Piece weight 82 g, equal to 0.082 kg.
- Indicative factory rate SAR 4.50/kg, not agreed; inclusion of resin, color, waste, packaging and VAT unknown.
- Candidate sales prices SAR 2.00 and SAR 2.50 per piece; VAT inclusion unknown.
- Current cash, stock, receivables, salaries, other costs and sales are unknown, not verified zero.
- No accountant is currently employed.

The application must be useful with this limited starting information and support multiple products, molds, factories, warehouses and customers later.

## Verified arithmetic and scenario rules

Reference calculation, assuming 100,000 saleable pieces, no chargeable waste, factory rate including resin and conversion, prices and costs excluding VAT, all units sold, and no other expenses:
- Output weight = 100,000 × 0.082 = 8,200 kg.
- Factory estimate = 8,200 × 4.50 = SAR 36,900.
- Factory estimate per piece = SAR 0.369.
- Mold plus factory cash outlay = SAR 56,900.
- Remaining baseline outlay after reported SAR 10,000 payment = SAR 46,900.
- Revenue at SAR 2.00 = SAR 200,000; at SAR 2.50 = SAR 250,000.
- Revenue less factory estimate = SAR 163,100 or SAR 213,100.
- Revenue less factory estimate and full mold outlay = SAR 143,100 or SAR 193,100.
- First-batch cost including full mold allocation = SAR 0.569/piece.

The last two figures are incomplete planning scenarios, NOT accounting net profit or available distributions. Do not automatically divide them between the partners.

If factory fee excludes resin, estimate cost as gross input kg × resin rate plus the conversion fee on its contracted weight basis plus additives, setup, packing, transport and other costs. Keep rate bases explicit: input kg, good output kg, machine hours or pieces. Do not charge conversion on the wrong weight basis.

If yield is 95% and 100,000 good pieces are required, a simple same-weight mass-balance scenario is 8,200 / 0.95 = 8,631.578947 kg input. At SAR 4.50 per input kg that costs SAR 38,842.105263. This is an illustrative scenario only; runners, regrind and different defect weights may require a more detailed mass balance. Track scrap ownership and recovery credits.

At 15% VAT, a VAT-inclusive SAR 2.00 price has net revenue per unit 2 / 1.15; total net revenue for 100,000 pieces is SAR 173,913.04. A VAT-inclusive SAR 2.50 price gives SAR 217,391.30 net revenue. Use high precision and documented line/invoice rounding. VAT treatment must be confirmed for the actual legal entity.

Use two explicitly different break-even views:
1. Contribution recovery of a SAR 20,000 mold at SAR 2.00 selling price and SAR 0.369 variable cost: ceil(20,000 / 1.631) = 12,263 units. At SAR 2.50: ceil(20,000 / 2.131) = 9,386 units.
2. Recovery of all SAR 56,900 already paid for the mold and full batch, from collected sales with no additional variable cash costs: 28,450 units at SAR 2.00 or 22,760 at SAR 2.50.
These answer different questions. Display assumptions; default to full landed cost and net-of-VAT selling price once known.

## Scope and user experience

Build a responsive desktop and mobile web app, with English initially and an Arabic/RTL-ready structure. Use plain labels and short explanations for non-accountants. Avoid decorative charts with no action attached.

Navigation:
Dashboard; Sales and Customers; Purchasing and Suppliers; Production and Quality; Inventory; Cash and Banking; Accounting; Funding and Distributions; Decisions and Approvals; Contracts and Documents; Reports; Settings.

Every dashboard amount must drill into underlying records. Show as-of dates, source status, missing evidence, forecast versus actual and unreconciled balances. Provide a global search and clear empty states. Never substitute demo data in live views.

Dashboard:
- Recorded cash and bank balances, reconciliation status and latest statement date.
- Customer receivables and overdue aging.
- Supplier payables and due-date aging.
- Open purchase commitments separately from recognized payables.
- Funding actually received or paid on the division's behalf, repayments and remaining balance.
- Inventory quantity and cost by location, reserved stock and available-to-promise.
- Revenue excluding VAT, gross profit, operating result and cash flow as distinct measures.
- VAT control balances and tax reserve with appropriate entity-level limitations.
- Production status, rejects, mold completion and delivery milestones.
- Decisions awaiting each partner, unsigned external contracts and expiring documents.
- Thirteen-week cash forecast and low-cash warnings.
- Proposed distributable cash and profit eligibility with a visible calculation, never automatic payout.

## Legal entity and accounting boundary

Model the existing legal entity and the plastics division separately. All records must identify legal_entity_id and division_id where applicable. The division is not automatically a separate company or separate taxpayer.

Choose the authoritative accounting system during setup. If the father's entity already has an accounting system, integrate with it or export reconciled division entries into it with unique external IDs. Do not maintain two independent sources of truth. Display division reports as management reports until consolidated into entity books.

VAT status, taxpayer identity, invoice numbering coordination and Phase 2 obligations must be established at the entity level. Do not assume a new division has its own VAT registration threshold. Recoverable VAT is not an inventory expense; nonrecoverable VAT may form part of cost subject to accounting policy.

Father's funding might be a documented loan to the legal entity, proprietor funding or a transfer from the parent entity to its division. The legal relationship determines the ledger account. Keep the planning label Father funding, with classification pending review. Never treat it as revenue.

If father personally paid the mold supplier directly, the provisional accounting example is debit supplier advance SAR 10,000 and credit the appropriate funding/current account SAR 10,000. There is no debit and credit through division bank unless money actually passed through it. If the existing company paid, use the correct existing bank or inter-division account instead and avoid posting twice. Use the actual invoice and VAT evidence before finalizing.

The unpaid SAR 10,000 is initially a contractual commitment. Recognize accounts payable only when the invoice/performance and accounting recognition criteria warrant it; do not invent a supplier bill.

A mold normally requires an asset/advance workflow rather than expensing its full cost in the first batch. Transfer advances into the mold asset upon appropriate receipt/acceptance and apply the approved depreciation policy when ready for use. Useful life, residual value, units-of-production versus time-based depreciation and allocations must be configurable and reviewed. Prevent double counting depreciation in inventory and operating costs.

## Login, access and separation of duties

- Individual invited accounts for Sayem and Sami; equal operator access.
- No public signup. No shared account or built-in passwords.
- Optional father read-only view and optional accountant/reviewer role, inactive until invited.
- Separate technical administration from financial approval authority.
- MFA support; reauthentication for signing, payout approval, role changes and bank beneficiary changes.
- Server-enforced permissions and database authorization, including all file downloads.
- A user can draft a decision and sign as one partner, but cannot provide the second partner's consent.
- An administrator cannot silently impersonate a partner or bypass joint approval.
- Invitations, replacements of an approver and changes to approval rules require the current agreed governance procedure; loss of access must have a documented, audited recovery route rather than a hidden override.

## Mandatory joint approval

The user's chosen default is unanimous approval by the two distinct named operators for every business decision. Do not introduce an amount threshold or standing-budget exception without their explicit later decision.

Decision types include purchases, production releases, price lists and discounts, credit terms, customer orders, payments, refunds, write-offs, stock adjustments, funding changes, repayment schedules, distributions, contracts, supplier bank changes and approval-policy changes.

Workflow:
Draft -> Submitted -> One signature -> Both signatures -> Authorized -> Executed -> Verified/Closed.
Also support rejected, withdrawn, expired and superseded states.

Each submitted decision contains a fixed version, purpose, amount/currency and VAT basis, supplier/customer, beneficiary when relevant, stock/cash impact, related documents, risks, effective date and execution conditions. Each signature binds to the exact canonical payload and document hashes. Any material edit invalidates all previous approvals and creates a new version. Previous versions remain accessible.

Enforce approval checks on server endpoints, not just disabled buttons. Use database transactions, unique constraints and idempotency keys to prevent duplicate execution and race conditions. Approved payment decisions must be tied to the exact beneficiary and amount.

Permit immediate factual logging of receipts, physical counts or externally executed transactions so the accounts do not omit reality. Such recording is not authorization for the decision. Flag unapproved actions as exceptions, preserve evidence and require both partners to review any resulting adjustment/posting. Do not fabricate retroactive prior authorization.

An app approval does not move money or prevent an outside bank transfer. Start with manual execution and bank proof. If dual authorization is needed at the bank, use the bank's own mandate and permissions. External payment integrations are optional later and must independently honor the approval controls.

A disagreement blocks the proposed action. Add reminders and a documented mediation/escalation process. Do not give either partner or father an automatic unilateral tie-break unless all relevant parties later agree to an appropriate rule.

## Accounting engine and cash controls

Use double-entry bookkeeping with balanced journals. Support:
- Bank, petty cash, supplier advances, raw material, work in progress, finished goods and mold assets.
- Receivables, supplier payables, customer deposits, tax accounts, funding/current accounts.
- Revenue, returns, discounts, cost of goods sold, production variances, scrap, expenses and depreciation.
- Equity/distribution accounts or approved compensation accounts according to the legally reviewed structure.

Use decimal arithmetic and sufficient precision for a SAR 0.369 unit cost; never binary floats for money or premature rounding to SAR 0.37. Quantities, kg and grams must carry explicit units.

Post only through transaction-safe services. Posted journals are immutable; correct with linked reversal and replacement entries. No silent deletes. Lock closed periods and require dual approval to reopen them.

Sales, invoices, deliveries, stock movements and cash receipts are different events. Recognize revenue and COGS at the appropriate delivery/control-transfer event; deposits are not automatically revenue. Partial collections reduce receivables and increase cash without creating sales again. Avoid duplicate COGS on invoice and delivery.

Purchases move through requisition/approval, order, delivery, quality acceptance, supplier bill and payment. Match orders, accepted quantities and invoices; route discrepancies for approval. Support partial deliveries, partial billing and refunds.

Bank statement CSV import must deduplicate transactions, support matching and expose unreconciled items. Cash receipts need numbered evidence. Prefer company banking and segregated tracking; if the company account is shared, show a reconciled division cash allocation and do not present the entire account balance as this venture's cash.

No automated bank transfers, tax filings or signing on behalf of users. Do not send customer/vendor messages without an explicitly authorized sending workflow.

## Production, molds and inventory

Mold register: supplier, specifications/drawings, asset owner, serial/reference, cavities if known, factory location, photos, quoted and paid amounts, trial/acceptance status, warranty, maintenance log, useful life and retrieval conditions.

Production orders: SKU, mold, factory, target GOOD quantity, planned input kg, rate and charge basis, material ownership, resin grade, colors, approved regrind policy, lead time, deposits and expected landed cost.

Record raw material issues, actual consumption, finished goods, rejects, scrap/regrind and unexplained variance. If the factory supplies all material, do not create fictional owned raw-material inventory. Support company-owned material held at the factory.

Quality: approved reference sample, dimensions, weight tolerances, color, finish, functional checks, batch inspection, accepted/rejected quantity, rework, photos and release signoff. Tolerances are entered from the contract, not invented.

Stock statuses: expected, received pending inspection, quarantined, available, reserved, in transit, dispatched, returned, damaged and scrapped. Track units and cartons with configurable conversion; never assume a carton quantity.

Use perpetual weighted-average cost for interchangeable goods unless a reviewed policy selects FIFO. Keep lot traceability either way. Allocate eligible freight, packing and normal production costs under a documented policy; segregate abnormal waste. Block negative available stock and overselling through concurrent requests.

Keep customer-owned and supplier-owned goods separate. Returns require inspection and linked credit/refund decisions.

## Customers, selling and collections

Customer profiles include legal name, contact, billing/delivery details and tax details where needed. Track leads, sample requests, quotations, price tiers, minimum orders, orders, delivery proof, invoices, payments, returns and balances.

Sales forecast probabilities and unsigned orders must not become booked revenue. Credit limits and payment terms require both signatures. Alert on overdue customers and blocked new credit. Support customer deposits and allocation of receipts to invoices.

Compare realized price with net landed cost and approved minimum margin. Separate VAT-inclusive price display from net revenue. No unapproved discount or credit override.

## Funding, repayment and 50/50 economics

Record each actual funding event with who paid, whom they paid, purpose, date, evidence and legal classification. Keep promised future funding separate. Start with the reported SAR 10,000 direct payment as an unverified historical draft pending evidence, date and classification. Do not seed SAR 20,000 or SAR 56,900 as money already lent.

Track principal added, repayments, adjustments and outstanding principal. Loan principal repayments reduce a liability and cash, not operating profit. Do not deduct mold cost a second time just because the funding used to buy it is being repaid.

Create a configurable repayment proposal, not an automatic commitment. Calculate available cash after tax provisions, committed payments, operating needs, the next approved production cycle and a minimum reserve. Both partners and the funding counterparty must agree the repayment terms.

Separate:
1. Economic profit/loss allocation.
2. Approved partner compensation, if any.
3. Cash available for repayment.
4. Legally permissible distributions or performance payments.
5. Payments actually made.

50/50 is a proposed economic split, not proof of registered ownership. Keep payout activation disabled until the permitted legal arrangement is documented. Do not infer either operator personally guarantees 50% of father's unpaid funding. Define ordinary loss, misconduct, capital calls and insolvency treatment in the signed agreement.

## Contracts, signatures and document storage

Support document templates, PDF generation, uploads, versioning, parties, obligations, milestones, expiry dates, transaction links and full-text metadata search. Private storage only; short-lived authorized downloads. Validate file types and size, scan/quarantine uploads where supported, sanitize previews and protect against malicious files.

Separate internal joint decision approval from external contract execution. Two operator signatures do not substitute for a supplier's signature, father's consent to his funding terms or the legal entity's authorized signatory.

Internal approval evidence should include user identity, role, exact version/hash, consent text, timestamp in UTC with Riyadh display and authentication event. Capture only necessary device/network evidence under the privacy policy.

For external e-signatures, design an adapter to a provider suitable for Saudi requirements. Preserve original signed files, completion evidence, certificate/validation information when applicable, provider reference and authenticated webhook events. Verify webhook signatures and idempotency. Never label an image of a signature as a certified digital signature.

Until a provider and legal requirements are verified, support approved PDF export and signed-document upload, displaying Uploaded signature evidence — not independently verified. Internal approvals remain available. Never invent a compliance badge or provider integration.

Templates to implement as lawyer-review drafts:
1. Entity/operator/funder governance and economic participation agreement.
2. Funding and repayment agreement.
3. Mold design, manufacture and ownership agreement.
4. Contract manufacturing, quality and mold custody agreement.
5. Customer supply and credit agreement.
6. Joint decision resolution.
7. Repayment or distribution resolution.
8. Mold handover, trial acceptance and batch acceptance forms.

Required fields and clause checklists:

Governance: actual entity and CR, authority, permitted roles, profit definition, 50/50 split if permitted, salaries if agreed, ordinary loss versus personal liability, funding classification, asset ownership, dual signatures, conflicts of interest, disclosure, deadlock, exit, valuation, incapacity, disputes and applicable law.

Funding: lender/funder and recipient, verified disbursements including direct supplier payments, maximum future commitment if any, agreed interest/return terms without assuming them, repayment trigger and schedule, liquidity reserve, treatment of shortfalls and business closure, guarantees only if expressly agreed, amendments and signatures.

Mold: legal owner, exact drawing/sample version, material/specification, SAR 20,000 price and VAT basis, SAR 10,000 reported payment subject to proof, remaining installment milestone, delivery date, trial sample acceptance, corrections, defects, warranty, delays, transport, custody, no unauthorized third-party use and retrieval rights.

Manufacturing: exact rate and chargeable kg basis, resin/additives/packing inclusions, material ownership, specification and tolerances, sample approval, chargeable waste and regrind, rejected-product remedies, delivery, staged releases, invoice/payment terms, authorized overruns, confidentiality, mold maintenance, custody and return.

Customer supply: SKU/specification, accepted sample, quantity, unit and carton prices, VAT, delivery, inspection, returns, credit limit, payment deadline and remedies reviewed locally.

Do not generate a ready-to-sign external agreement with missing identity or legal-authority fields. Show missing fields and retain draft status. A short joint decision record can document routine internal decisions without pretending to replace the underlying supplier/customer agreement.

## Security, storage and operations

- Server-side authorization on every read/write/export; authorization and tenant isolation tests.
- Private documents and attachments; no publicly guessable object URLs.
- Secrets only in environment/secret management, never in frontend bundles or source control.
- TLS, secure cookies, CSRF protections where applicable, input validation and parameterized queries.
- Rate limits for authentication and signing; revocable sessions and controlled account recovery.
- Append-only application audit events recording actor, time, reason, versions and correlation IDs. Ordinary app administrators cannot edit logs. Describe privileged infrastructure access honestly; use independent retention or tamper-evident storage for stronger evidence.
- Encryption at rest where supported, automated backups, point-in-time recovery where available and tested restoration of database plus documents.
- Define backup frequency and retention based on the legal entity's reviewed obligations; apply legal holds. Do not invent a universal legal retention period.
- Minimal personal data, access restrictions, retention/deletion policy and review of Saudi hosting/cross-border data requirements before choosing production providers.
- Monitoring, error reporting without sensitive payload leakage, uptime alerts and documented incident recovery.
- Export CSV, PDF and a complete structured archive including attachments and audit records; keep the business portable.

## Reports and operating routine

Reports: division P&L, balance sheet/management position, cash flow, trial balance, general ledger, inventory valuation, batch profitability, customer and supplier aging, bank reconciliation, funding statement, commitments, tax summaries, approval exceptions and thirteen-week cash forecast. Every total must reconcile to the appropriate ledger/subledger.

Daily: record evidence, review receipts and shipments, check cash and due items.
Weekly: reconcile bank and cash, inspect overdue invoices, count selected inventory, review production and update cash forecast.
Monthly: complete reconciliation, review stock adjustments and returns, approve journals, review funding, close the period and export a review pack.

AI assistance, if added later, can explain figures, flag anomalies and draft documents. Deterministic accounting services calculate and post transactions. AI cannot invent invoices, change balances, sign, approve or move money.

## Initial data and setup

Production workspace starts with clearly marked unverified facts and editable scenario records. Do not install actual live users without invitations.

Create:
- Placeholder legal entity and plastics division; onboarding flags for CR, VAT, authority and accounting source.
- Two pending operator invitations without fabricated email addresses.
- Product FLW-001, 82 g, planned selling prices.
- One proposed mold record at SAR 20,000.
- Reported direct payment draft SAR 10,000 with unknown date and receipt.
- SAR 10,000 remaining mold commitment.
- Planned batch of 100,000 pieces and indicative SAR 4.50/kg quote.
- Missing-cost flags for resin, waste, packing, freight, storage, sales costs, salaries and VAT.
- Zero verified transactions until verified posting/import; unknown opening balances must display Not configured, not a misleading zero.
- Demo/test workspace separately labeled and isolated from production.

## Delivery stages

Stage 1: repository setup, data model/migrations, authentication, role enforcement, ledger services, approval engine, private files, funding drafts and basic dashboard. Demonstrate two distinct users signing the same immutable decision.

Stage 2: purchasing, production, quality, stock, customers, orders, delivery, bills, payments, bank reconciliation and reliable reports. Complete the end-to-end sample batch in a test workspace.

Stage 3: contract templates, PDF workflow, external signature adapter, invoice/accounting integration, backup/restore and hardened deployment. Clearly identify integrations awaiting credentials. Do not issue live tax invoices from an unvalidated placeholder.

Stage 4: optional automated alerts, forecasting enhancements, Arabic UI and further products. Do not let these delay the reliable financial workflow.

For each stage provide working code, migrations, focused tests and a short demonstration. Keep a checklist mapping every requirement to implemented, blocked or deferred with reasons. No fake working buttons.

## Acceptance tests required before real transactions

1. 100,000 × 82 g = 8,200 kg and × SAR 4.50 = SAR 36,900 exactly at the specified precision.
2. At 95% yield on input-kg charging, the reference scenario produces SAR 38,842.11 rounded.
3. SAR 200,000 inclusive of 15% VAT produces SAR 173,913.04 net and SAR 26,086.96 VAT under the declared total-level test rounding; implement statutory invoice rounding separately.
4. A supplier payment made personally by father increases the appropriate funding account and supplier advance without inflating bank cash; importing an existing entity posting does not duplicate it.
5. The remaining mold commitment is not automatically posted as a bill; future batch quantities do not become stock.
6. One partner cannot execute a controlled decision; the same user cannot sign twice; API bypass and stale versions are rejected.
7. Changing amount, beneficiary, terms or document bytes resets approvals; old signature evidence stays attached to the old version.
8. Concurrent approvals/execution and repeated webhook requests execute the underlying action at most once.
9. A customer invoice/delivery and a partial payment update revenue, COGS, stock, receivables and cash once each at their proper events.
10. Returns, credit notes, rejects and supplier refunds reconcile; unavailable or quarantined stock cannot be sold.
11. Every posted journal balances; reports tie to journals and subledgers; reversals preserve history; closed periods reject unauthorized backdating.
12. Principal repayment reduces cash and funding balance, not profit; compensation and distribution follow distinct account mappings.
13. Another user/tenant and read-only roles cannot fetch unauthorized documents or mutate finance data, including direct object URLs and exports.
14. Loss of a signing-provider webhook does not mark unsigned contracts complete; a drawing of a signature never acquires a verified-provider status.
15. A clean restore recovers transactions, documents, approval evidence and user access configuration consistently.
16. Two operators can independently log in and complete a realistic purchase -> production -> quality -> stock -> sale -> collection -> reconciliation scenario.
17. Forecast outputs never appear as actual money or profit, and incomplete opening balances remain visibly incomplete.
18. Joint internal approval does not make an external contract Executed until its actual required signatories have signed.

## Business launch plan for the owners

Week 1: obtain the mold receipt and written quote, confirm legal structure/authority and the entity's tax setup, agree funding and partnership terms, obtain a factory quotation spelling out inclusions and kg basis, and interview potential flower-shop/wholesale buyers.

Week 2: validate the actual product with buyers, record required quantities and net wholesale prices, secure written orders or deposits under agreed terms, measure carton dimensions and obtain freight/storage quotes.

Week 3: approve trial samples and quality criteria, negotiate staged production and defect remedies, finish core dashboard testing and banking controls, and prepare customer terms.

Week 4: accept the mold only against agreed tests, release the first approved production tranche, record incoming quality and stock, begin confirmed deliveries and reconcile collections.

The one-month mold estimate is not a promise that production, testing and all sales will be complete in one month. Base the calendar on actual supplier milestones.

A 5,000–10,000-piece pilot is an illustrative option to negotiate if machine setup and minimum batch economics allow it, not a confirmed factory offer. With the indicative all-in rate, 10,000 pieces require 820 kg and SAR 3,690 before other costs. Do not commit all 100,000 pieces solely because theoretical margins look large.

## Information required from the owners

1. A product photo/name and its exact specification.
2. Factory quote: whether SAR 4.50/kg includes resin, color, waste, packaging and VAT; weight basis and minimum batch.
3. Whether SAR 2.00–2.50 is a tested wholesale price and includes VAT; any confirmed buyers.
4. Actual legal entity name, structure, CR activity and VAT registration/invoicing status.
5. Operator legal names, residency/work/investment authorization and signing authority; obtain professional review rather than assume ownership.
6. Mold quote, payment receipt, actual payment date, supplier identity and acceptance/balance-payment terms.
7. Funding source, maximum agreed funding, repayment trigger, salary arrangement and exact meaning of shared losses.
8. Bank/accounting arrangements, stock location, packing, delivery costs and customer credit policy.
9. Login invitation emails and desired hosting/integration accounts only when setup needs them; never request passwords in chat.

## Source notes for legal and tax setup

Research checked 15 October 2026 Riyadh time. These sources support the need for review; they do not determine the owners' specific legal position. Recheck current applicable rules and the entity's actual notifications at launch.

- ZATCA, Guideline for Tax Invoicing and Records under VAT Provisions, May 2026: https://zatca.gov.sa/en/HelpCenter/guidelines/Documents/Guideline-for-Tax-Invoicing-and-Records-under-VAT-Provisions.pdf
- ZATCA, Detailed Guidelines for E-Invoicing, version 2: https://www.zatca.gov.sa/en/e-invoicing/introduction/guidelines/documents/e-invoicing_detailed__guideline.pdf
- Ministry of Commerce, explanation of unauthorized own-account activity through another person's registration (historical explanatory notice; not a source for current penalties): https://mc.gov.sa/en/mediacenter/News/Pages/12-01-15-01.aspx
- HRSD, Employment of Non-Saudis: https://www.hrsd.gov.sa/en/توظيف-غير-السعوديين
- Digital Government Authority, Electronic Transactions Law and implementing regulations: https://dga.gov.sa/en/electronic-transactions and https://dga.gov.sa/en/implementing-regulations-of-electronic-transactions-law
  DGA search listings were available; full pages could not be fetched in this research. Verify exact current signature requirements with the chosen provider and local counsel.

The custom application cannot by itself establish legal ownership, authorize employment, make an invalid agreement valid, replace required tax compliance or guarantee accurate accounts when source transactions are missing.
