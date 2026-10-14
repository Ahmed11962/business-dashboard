from django.db import transaction
from .models import Entity,Division,Invitation,Record
from .contracts import TEMPLATES
from .models import Contract

@transaction.atomic
def seed(is_demo=False):
    existing=Division.objects.filter(is_demo=is_demo).first()
    if existing: return existing
    entity=Entity.objects.create(name='Test entity — synthetic only' if is_demo else 'Legal entity — confirmation required')
    div=Division.objects.create(legal_entity=entity,name='Test workspace' if is_demo else 'Plastics division',is_demo=is_demo,configuration={'accounting_source':'No existing system reported; accountant must confirm authoritative books','live_execution':'disabled','currency':'SAR','timezone':'Asia/Riyadh','missing_costs':['resin','waste','packing','freight','storage','sales costs','salaries','VAT'],'go_live':['legal identities and CR','operator authority and agreements','VAT and invoice integration','opening balances','funding evidence and classification','product and factory specification','hosting, MFA and recovery review','backup retention and restore drill']})
    for slot in ('sayem','sami'): Invitation.objects.create(division=div,slot=slot)
    facts=[('product','FLW-001 · Plastic flower holder',{'sku':'FLW-001','weight_g':'82','candidate_prices':['2.00','2.50'],'specification':'pending','vat_basis':'unknown'},'provisional'),('mold','Proposed flower holder mold',{'quote_sar':'20000','vat_basis':'unknown','lead_time':'approximately one month; start and acceptance pending'},'proposed'),('funding_draft','Reported direct payment by father',{'amount_sar':'10000','payment_date':None,'receipt':None,'classification':'pending','bank_cash_effect':'none'},'unverified_history'),('commitment','Remaining mold commitment',{'amount_sar':'10000','due_date':None,'recognized_payable':False},'unverified_commitment'),('production_plan','Planned first batch · not ordered',{'good_units':'100000','unit_weight_g':'82','rate_sar_per_kg':'4.50','rate_status':'indicative','inclusions':'unknown'},'forecast')]
    for kind,title,data,status in facts: Record.objects.create(division=div,kind=kind,title=title,data=data,status=status,source_status='reported_unverified')
    for key,(title,_) in TEMPLATES.items(): Contract.objects.create(division=div,template=key,title=title)
    return div
