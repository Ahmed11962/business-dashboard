"""Lawyer-review checklists, not ready-to-sign contracts or certified signatures."""
import io
from xml.sax.saxutils import escape
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer
from reportlab.lib.styles import getSampleStyleSheet
TEMPLATES={
'governance':('Entity, operator and funder governance',['entity_name','cr','authorized_signatory','operator_legal_names','permitted_roles','profit_definition','economic_split','salaries','ordinary_loss','personal_liability','funding_classification','asset_ownership','joint_approval','conflicts_disclosure','deadlock_mediation','exit_valuation','incapacity','disputes_applicable_law']),
'funding':('Funding and repayment',['funder_identity','recipient_entity','verified_disbursements','direct_payments_evidence','maximum_future_commitment','return_terms','repayment_trigger','schedule','liquidity_reserve','shortfalls_closure','express_guarantees','amendments','required_signatories']),
'mold':('Mold design, manufacture and ownership',['entity_name','supplier_identity','legal_owner','drawing_version','specifications','price','vat_basis','payment_receipt','balance_milestone','delivery_date','sample_acceptance','corrections_defects','warranty','delays','transport','custody','no_third_party_use','retrieval_rights','required_signatories']),
'manufacturing':('Contract manufacturing and quality',['entity_name','factory_identity','rate','charge_basis','resin_additives_packing','material_ownership','tolerances','sample_approval','waste_regrind','reject_remedies','delivery','staged_releases','invoice_terms','authorized_overruns','confidentiality','mold_maintenance_custody_return','required_signatories']),
'customer_supply':('Customer supply and credit',['entity_name','customer_identity','sku_specification','accepted_sample','quantity','unit_carton_prices','vat_basis','delivery','inspection','returns','credit_limit','payment_deadline','reviewed_remedies','required_signatories']),
'joint_resolution':('Joint decision resolution',['entity_name','purpose','exact_terms','amount_vat_basis','documents','conditions','sayem_consent','sami_consent']),
'repayment_resolution':('Repayment or distribution resolution',['entity_name','legal_basis','funding_balance','cash_availability','reserve','tax_provision','amount','beneficiary','counterparty_consent','both_operators']),
'acceptance':('Mold handover, trial and batch acceptance',['entity_name','supplier_identity','mold_reference','sample_version','agreed_tolerances','inspection_results','accepted_rejected_quantity','remedies','handover_date','required_signatories'])}

def missing(contract): return [key for key in TEMPLATES[contract.template][1] if not contract.fields.get(key)]
def pdf(contract):
    buf=io.BytesIO(); styles=getSampleStyleSheet(); story=[]
    def p(text,style='BodyText'): story.extend([Paragraph(escape(text),styles[style]),Spacer(1,10)])
    p(contract.title,'Title'); p('LAWYER-REVIEW DRAFT — NOT READY FOR SIGNATURE','Heading2')
    p('Division management document. Internal joint approval does not bind external parties or establish authority. Uploaded signature evidence is not independently verified.')
    for key in TEMPLATES[contract.template][1]: p(key.replace('_',' ').title()+': '+str(contract.fields.get(key) or '[REQUIRED — not provided]'))
    p('Status: '+contract.status); p('Missing fields: '+', '.join(missing(contract)))
    SimpleDocTemplate(buf).build(story); return buf.getvalue()
