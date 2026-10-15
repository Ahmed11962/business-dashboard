from django.db import transaction
from .models import Entity,Division,Invitation,Record
from .contracts import TEMPLATES
from .models import Contract

@transaction.atomic
def seed(is_demo=False):
    existing=Division.objects.filter(is_demo=is_demo).first()
    if existing: return existing
    entity=Entity.objects.create(name='Test entity — synthetic only' if is_demo else 'Legal entity — confirmation required')
    div=Division.objects.create(legal_entity=entity,name='Test workspace' if is_demo else 'Business workspace',is_demo=is_demo,configuration={'accounting_source':'Accountant must confirm authoritative books','live_execution':'disabled','currency':'SAR','timezone':'Asia/Riyadh','go_live':['legal identities and authority','opening balances','accounting review','hosting, MFA and recovery review','backup retention and restore drill']})
    for slot in ('sayem','sami'): Invitation.objects.create(division=div,slot=slot)
    # Starting a workspace never invents a payer, balance, liability or sale.
    for key,(title,_) in TEMPLATES.items(): Contract.objects.create(division=div,template=key,title=title)
    return div
