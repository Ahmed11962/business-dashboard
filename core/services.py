import csv, hashlib, io, json, copy
from datetime import date
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from .models import *
from .finance import BusinessError, decimal, money, quantity
from .security import require_role

def canonical(value): return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)
def digest(value): return hashlib.sha256(canonical(value).encode()).hexdigest()
def strings(value):
    if isinstance(value,Decimal): return str(value)
    if isinstance(value,dict): return {k:strings(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)): return [strings(v) for v in value]
    return value

def lock(division): return Division.objects.select_for_update().get(pk=division.pk)

def audit(division,user,event,obj,detail=None):
    # Caller holds the division row lock, serializing the hash chain.
    previous=Audit.objects.filter(division=division).order_by('-created_at','-id').first()
    previous_hash=previous.digest if previous else ''
    data={'actor':str(user.pk) if user else None,'event':event,'object':str(obj),'detail':detail or {},'previous':previous_hash}
    return Audit.objects.create(division=division,actor=user,event=event,object_id=str(obj),detail=data['detail'],previous_hash=previous_hash,digest=digest(data))

# These are implemented execution capabilities, not arbitrary client-selected handlers.
FIELDS={
 'purchase_order':['party','quantity','sku','amount','due_date'],
 'production_release':['purchase_order_id','party','sku','quantity','mold','rate','charge_basis','material_ownership'],
 'goods_receipt':['production_id','sku','location','lot','quantity','amount'],
 'quality_release':['stock_id','accepted_quantity','inspection'],
 'supplier_bill':['receipt_id','party','amount','due_date','beneficiary'],
 'sales_order':['stock_id','party','quantity','unit_price','vat_rate','due_date'],
 'delivery':['order_id','quantity'],
 'customer_invoice':['delivery_id'],
 'collection':['item_id','amount','evidence_id'],
 'customer_deposit':['party','amount','evidence_id'],
 'apply_deposit':['deposit_id','item_id','amount'],
 'supplier_advance':['party','amount','beneficiary','evidence_id'],
 'supplier_payment':['item_id','amount','beneficiary','evidence_id'],
 'funding_direct':['amount','party','classification','evidence_id'],
 'funding_cash':['amount','party','classification','evidence_id'],
 'repayment':['amount','beneficiary','evidence_id','counterparty_consent'],
 'mold_acceptance':['amount','inspection','mold_id'],
 'depreciation':['amount','mold_id','policy','allocation'],
 'customer_return':['delivery_id','quantity','inspection'],
 'customer_refund':['return_id','amount','beneficiary','evidence_id'],
 'supplier_refund':['amount','party','evidence_id'],
 'stock_adjustment':['stock_id','quantity_delta','reason'],
 'journal':['lines','reason'],
 'reversal':['journal_id','reason'],
 'close_period':['through'],
 'reopen_period':['through','reason'],
 'contract_approval':['contract_id'],
 'resolution':['terms'],
}
COMMON=['purpose','reference','date','vat_basis','risks','conditions','effective_date','cash_impact','stock_impact']

def validate_payload(kind,p):
    if kind not in FIELDS: raise BusinessError('Unsupported decision type.')
    for key in FIELDS[kind]+COMMON:
        if key not in p or p[key] in ('',None): raise BusinessError(f'Missing field: {key.replace("_"," ")}')
    if p.get('currency','SAR')!='SAR': raise BusinessError('Only SAR posting is supported.')
    if p['vat_basis'] not in ('excluded','included','not_applicable','unknown'): raise BusinessError('Invalid VAT basis.')
    for field in ('date','effective_date','due_date','through'):
        if field in p:
            try: date.fromisoformat(p[field])
            except (ValueError,TypeError): raise BusinessError(f'{field} must be YYYY-MM-DD.')
    if len(str(p['reference']))>100: raise BusinessError('Reference is too long.')
    for key in ('amount','unit_price','rate'):
        if key in p: decimal(p[key],positive=True)
    for key in ('quantity','accepted_quantity'):
        if key in p: decimal(p[key],nonnegative=key=='accepted_quantity',positive=key=='quantity')
    if kind in ('funding_direct','funding_cash') and p['classification'] not in ('loan','parent_current','proprietor'):
        raise BusinessError('Select a reviewed funding classification.')
    if kind=='sales_order' and (decimal(p['vat_rate'],nonnegative=True)>100 or p['vat_basis']=='unknown'):
        raise BusinessError('Sales require an explicit VAT basis and rate.')
    if kind=='production_release' and p['charge_basis'] not in ('input_kg','good_output_kg','pieces','machine_hours'):
        raise BusinessError('Specify the contractual charge basis.')
    if kind=='journal':
        if not isinstance(p['lines'],list): raise BusinessError('Journal lines must be a list.')
        validate_lines(p['lines'])
    return p

@transaction.atomic
def draft_decision(division,user,title,kind,payload,decision_id=None):
    division=lock(division); require_role(user,division)
    if not title or len(title)>200: raise BusinessError('A decision title of up to 200 characters is required.')
    payload=dict(payload); validate_payload(kind,payload)
    if kind=='contract_approval':
        c=Contract.objects.get(pk=payload['contract_id'],division=division)
        payload['contract_snapshot']={'template':c.template,'fields':c.fields}
        payload['contract_hash']=digest(payload['contract_snapshot'])
    docs=[]
    for document_id in payload.pop('document_ids',[]):
        doc=Document.objects.get(pk=document_id,division=division)
        docs.append({'id':str(doc.pk),'sha256':doc.sha256,'name':doc.name,'scan_status':doc.scan_status})
    if payload.get('evidence_id'):
        doc=Document.objects.get(pk=payload['evidence_id'],division=division)
        docs.append({'id':str(doc.pk),'sha256':doc.sha256,'name':doc.name,'scan_status':doc.scan_status})
    approvers=list(Membership.objects.filter(division=division,role='operator',active=True).order_by('slot').values_list('user_id',flat=True))
    if not 1<=len(approvers)<=2 or len(set(approvers))!=len(approvers):
        raise BusinessError('Decision drafts require at least one active operator; approvals require two distinct operators.')
    payload.update({'documents':docs,'approvers':approvers,'currency':'SAR','kind':kind,'title':title,'division_id':str(division.pk),'legal_entity_id':str(division.legal_entity_id)})
    if decision_id:
        d=Decision.objects.get(pk=decision_id,division=division)
        if d.status in ('executed','closed'): raise BusinessError('Executed decisions cannot be edited. Use a reversal or new decision.')
        d.current_version+=1; d.title=title; d.kind=kind; d.status='draft'; d.save()
    else: d=Decision.objects.create(division=division,created_by=user,title=title,kind=kind)
    DecisionVersion.objects.create(decision=d,number=d.current_version,payload=payload,digest=digest(payload))
    audit(division,user,'decision.version_created',d.pk,{'version':d.current_version})
    return d

@transaction.atomic
def transition(division,user,decision_id,version,action):
    division=lock(division); require_role(user,division)
    d=Decision.objects.get(pk=decision_id,division=division)
    if d.current_version!=int(version): raise BusinessError('Stale version. Reload and review the current payload.')
    allowed={'submit':(('draft',),'submitted'),'withdraw':(('draft','submitted','one_signature','authorized'),'withdrawn'),'reject':(('submitted','one_signature','authorized'),'rejected'),'close':(('executed',),'closed')}
    if action not in allowed or d.status not in allowed[action][0]: raise BusinessError('This transition is not allowed.')
    if action=='submit':
        approvers=list(Membership.objects.filter(division=division,role='operator',active=True).order_by('slot').values_list('user_id',flat=True))
        if len(approvers)!=2 or len(set(approvers))!=2:
            raise BusinessError('Sami must accept his own invitation before joint approval can begin. This draft is saved.')
        current=d.versions.get(number=d.current_version)
        if current.payload['approvers']!=approvers:
            payload=dict(current.payload,approvers=approvers)
            d.current_version+=1; d.save(update_fields=['current_version'])
            DecisionVersion.objects.create(decision=d,number=d.current_version,payload=payload,digest=digest(payload))
            audit(division,user,'decision.approvers_attached',d.pk,{'version':d.current_version})
    d.status=allowed[action][1]; d.save(update_fields=['status'])
    audit(division,user,'decision.'+action,d.pk,{'version':d.current_version})
    return d

@transaction.atomic
def sign(division,user,decision_id,version,expected_hash,auth_event):
    division=lock(division); require_role(user,division)
    d=Decision.objects.get(pk=decision_id,division=division)
    if d.current_version!=int(version): raise BusinessError('Stale version. Approvals bind to exact versions.')
    v=d.versions.get(number=version)
    if d.status not in ('submitted','one_signature'): raise BusinessError('This decision is not open for signing.')
    if d.expires_at and d.expires_at<=timezone.now(): raise BusinessError('Decision expired.')
    if v.digest!=expected_hash or digest(v.payload)!=v.digest: raise BusinessError('Payload hash mismatch.')
    if user.pk not in v.payload['approvers']: raise BusinessError('You are not a named approver for this version.')
    if v.signatures.filter(user=user).exists(): raise BusinessError('The same person cannot sign twice.')
    if not auth_event: raise BusinessError('Reauthentication evidence is required.')
    Signature.objects.create(version=v,user=user,digest=v.digest,auth_event=auth_event)
    d.status='authorized' if v.signatures.count()==2 else 'one_signature'; d.save(update_fields=['status'])
    audit(division,user,'decision.signed',d.pk,{'version':version,'hash':v.digest})
    return d

ACCOUNTS={'bank','petty_cash','supplier_advance','inventory','raw_material','wip','mold_asset','accumulated_depreciation','receivable','payable','goods_received_unbilled','customer_deposit','customer_credit','vat_output','vat_input','funding_loan','funding_parent_current','funding_proprietor','revenue','cogs','abnormal_waste','expense','depreciation','equity','compensation','distribution'}

def validate_lines(lines):
    if len(lines)<2: raise BusinessError('A journal requires at least two lines.')
    out=[]
    for line in lines:
        if line['account'] not in ACCOUNTS: raise BusinessError('Unknown ledger account.')
        dr=money(line.get('debit','0')); cr=money(line.get('credit','0'))
        if dr<0 or cr<0 or (dr>0)==(cr>0): raise BusinessError('Each line must have one positive debit or credit.')
        out.append({'account':line['account'],'debit':dr,'credit':cr})
    if sum(x['debit']-x['credit'] for x in out)!=0: raise BusinessError('Journal does not balance.')
    return out

def post(d,p,lines,suffix='',reversal=None):
    day=date.fromisoformat(p['date'])
    if d.division.closed_through and day<=d.division.closed_through: raise BusinessError('This accounting period is closed.')
    lines=validate_lines(lines)
    j=Journal.objects.create(division=d.division,decision=d,reference=p['reference']+suffix,description=d.title,date=day,reversal_of=reversal)
    Line.objects.bulk_create([Line(journal=j,**x) for x in lines])
    return j

def pair(debit,credit,amount):
    amount=money(amount)
    return [{'account':debit,'debit':str(amount)},{'account':credit,'credit':str(amount)}]

def balance(division,account):
    return sum((x.debit-x.credit for x in Line.objects.filter(journal__division=division,account=account)),Decimal(0))

def record(d,kind,data,status='recorded'):
    return Record.objects.create(division=d.division,kind=kind,title=d.title,status=status,source_status='verified_posted',data=strings(dict(data,decision_id=str(d.pk))))

def ensure_live_gates(division):
    if division.is_demo: return
    raise BusinessError('Live execution is locked pending accountant, legal, tax and deployment validation. This release supports test-workspace execution only; see docs/GO_LIVE.md.')

@transaction.atomic
def execute(division,user,decision_id,version,idempotency_key):
    division=lock(division); require_role(user,division)
    if not idempotency_key or len(idempotency_key)>100: raise BusinessError('An idempotency key of up to 100 characters is required.')
    d=Decision.objects.get(pk=decision_id,division=division); d.division=division
    if d.current_version!=int(version): raise BusinessError('Stale version cannot execute.')
    existing=Execution.objects.filter(decision=d).first()
    if existing:
        if existing.idempotency_key!=idempotency_key: raise BusinessError('Already executed with a different idempotency key.')
        return existing
    if Execution.objects.filter(division=division,idempotency_key=idempotency_key).exists(): raise BusinessError('Idempotency key belongs to another action.')
    if d.status!='authorized': raise BusinessError('Both distinct operators must sign before execution.')
    v=d.versions.get(number=version); p=v.payload
    signed=set(v.signatures.filter(digest=v.digest).values_list('user_id',flat=True))
    active=set(Membership.objects.filter(division=division,role='operator',active=True).values_list('user_id',flat=True))
    if len(signed)!=2 or signed!=set(p['approvers']) or signed!=active or digest(p)!=v.digest: raise BusinessError('Two current operator signatures on this exact payload are required.')
    if d.expires_at and d.expires_at<=timezone.now(): raise BusinessError('Decision expired.')
    if date.fromisoformat(p['effective_date'])>timezone.localdate(): raise BusinessError('Effective date has not arrived.')
    ensure_live_gates(division)
    for doc in p['documents']:
        current=Document.objects.get(pk=doc['id'],division=division)
        if current.sha256!=doc['sha256'] or hashlib.sha256(bytes(current.content)).hexdigest()!=doc['sha256']: raise BusinessError('Document integrity mismatch.')
        if current.scan_status!='clean' and not division.is_demo: raise BusinessError('Quarantined evidence cannot authorize a live action.')
    result=apply_action(d,p)
    ex=Execution.objects.create(division=division,decision=d,version=v,idempotency_key=idempotency_key,result=strings(result))
    d.status='executed'; d.executed_at=timezone.now(); d.save(update_fields=['status','executed_at'])
    audit(division,user,'decision.executed',d.pk,{'version':version,'result':ex.result})
    return ex

def scoped_record(division,pk,kind):
    return Record.objects.get(pk=pk,division=division,kind=kind,source_status='verified_posted')

def apply_action(d,p):
    div=d.division; k=d.kind; result={}
    if k in ('purchase_order','production_release','resolution'):
        if k=='production_release':
            po=scoped_record(div,p['purchase_order_id'],'purchase_order')
            if po.data['sku']!=p['sku'] or po.data['party']!=p['party']: raise BusinessError('Production must match the approved purchase SKU and factory.')
            released=decimal(po.data.get('released','0'))+quantity(p['quantity'])
            if released>decimal(po.data['quantity']): raise BusinessError('Production exceeds the approved purchase quantity.')
            po.data['released']=str(released); po.save(update_fields=['data'])
        r=record(d,k,p,'approved'); result={'record_id':str(r.pk)}
    elif k in ('funding_direct','funding_cash'):
        j=post(d,p,pair('supplier_advance' if k=='funding_direct' else 'bank','funding_'+p['classification'],p['amount']))
        result={'journal_id':str(j.pk)}
    elif k=='goods_receipt':
        prod=scoped_record(div,p['production_id'],'production_release')
        if prod.data['sku']!=p['sku']: raise BusinessError('SKU differs from the approved production order.')
        q=quantity(p['quantity']); received=decimal(prod.data.get('received','0'))
        if received+q>decimal(prod.data['quantity']): raise BusinessError('Receipt exceeds approved production quantity.')
        s=Stock.objects.create(division=div,sku=p['sku'],location=p['location'],lot=p['lot'],quantity=q,value=money(p['amount']),status='quarantined')
        j=post(d,p,pair('inventory','goods_received_unbilled',p['amount']))
        Movement.objects.create(division=div,stock=s,decision=d,quantity=q,value=s.value,kind='receipt')
        r=record(d,k,dict(p,stock_id=str(s.pk),billed='0'))
        prod.data['received']=str(received+q); prod.save(update_fields=['data'])
        result={'stock_id':str(s.pk),'receipt_id':str(r.pk),'journal_id':str(j.pk)}
    elif k=='quality_release':
        s=Stock.objects.get(pk=p['stock_id'],division=div,status='quarantined',owner='company')
        accepted=decimal(p['accepted_quantity'],nonnegative=True)
        if accepted>s.quantity: raise BusinessError('Accepted quantity exceeds received quantity.')
        rejected=s.quantity-accepted; loss=money(s.value*rejected/s.quantity)
        if loss: post(d,p,pair('abnormal_waste','inventory',loss))
        if rejected: Movement.objects.create(division=div,stock=s,decision=d,quantity=-rejected,value=-loss,kind='quality_reject')
        s.quantity=accepted; s.value-=loss; s.status='available' if accepted else 'scrapped'; s.save()
        # Perpetual weighted average over interchangeable, company-owned available goods by SKU/location.
        pool=list(Stock.objects.filter(division=div,sku=s.sku,location=s.location,status='available',owner='company',quantity__gt=0).order_by('id'))
        total_q=sum((x.quantity for x in pool),Decimal(0)); total_v=sum((x.value for x in pool),Decimal(0)); allocated=Decimal(0)
        for i,x in enumerate(pool):
            value=total_v-allocated if i==len(pool)-1 else money(total_v*x.quantity/total_q)
            if value!=x.value: Movement.objects.create(division=div,stock=x,decision=d,quantity=0,value=value-x.value,kind='average_cost_allocation')
            x.value=value; x.save(update_fields=['value']); allocated+=value
        result={'accepted':str(accepted),'rejected':str(rejected)}
    elif k=='supplier_bill':
        receipt=scoped_record(div,p['receipt_id'],'goods_receipt'); amount=money(p['amount']); billed=money(receipt.data['billed'])
        if amount+billed>money(receipt.data['amount']): raise BusinessError('Bill exceeds accepted receipt cost; approve a separate discrepancy.')
        stock=Stock.objects.get(pk=receipt.data['stock_id'],division=div)
        if stock.status!='available': raise BusinessError('Quality acceptance is required before supplier billing.')
        post(d,p,pair('goods_received_unbilled','payable',amount))
        item=OpenItem.objects.create(division=div,side='payable',party=p['party'],reference=p['reference'],total=amount,due_date=p['due_date'],decision=d)
        receipt.data['billed']=str(billed+amount); receipt.save(update_fields=['data']); result={'item_id':str(item.pk)}
    elif k=='sales_order':
        if date.fromisoformat(p['due_date'])>timezone.localdate() and OpenItem.objects.filter(division=div,side='receivable',party=p['party'],due_date__lt=timezone.localdate(),total__gt=models.F('settled')).exists():
            raise BusinessError('Customer has overdue debt. New credit is blocked; settle or resolve it through an approved adjustment.')
        s=Stock.objects.get(pk=p['stock_id'],division=div,status='available',owner='company'); q=quantity(p['quantity'])
        if q>s.quantity-s.reserved: raise BusinessError('Insufficient available stock; quarantined or reserved units cannot be sold.')
        s.reserved+=q; s.save(update_fields=['reserved'])
        r=record(d,k,dict(p,delivered='0'),'reserved'); result={'order_id':str(r.pk)}
    elif k=='delivery':
        order=scoped_record(div,p['order_id'],'sales_order'); q=quantity(p['quantity']); op=order.data
        delivered=decimal(op['delivered']); s=Stock.objects.get(pk=op['stock_id'],division=div,status='available',owner='company')
        if q>decimal(op['quantity'])-delivered or q>s.quantity or q>s.reserved: raise BusinessError('Delivery exceeds reserved quantity.')
        rate=decimal(op['vat_rate'])/100; total=q*decimal(op['unit_price'])
        if op['vat_basis']=='included': gross=money(total); net=money(total/(1+rate)); vat=gross-net
        else: net=money(total); vat=money(net*rate); gross=net+vat
        cost=s.value if q==s.quantity else money(s.value*q/s.quantity)
        lines=[{'account':'receivable','debit':gross},{'account':'revenue','credit':net}]
        if vat: lines.append({'account':'vat_output','credit':vat})
        if cost: lines+=pair('cogs','inventory',cost)
        post(d,p,lines)
        s.quantity-=q; s.reserved-=q; s.value-=cost; s.save()
        Movement.objects.create(division=div,stock=s,decision=d,quantity=-q,value=-cost,kind='delivery')
        item=OpenItem.objects.create(division=div,side='receivable',party=op['party'],reference=p['reference'],total=gross,due_date=op['due_date'],decision=d)
        r=record(d,k,dict(p,stock_id=str(s.pk),item_id=str(item.pk),gross=gross,net=net,vat=vat,cost=cost,returned='0',invoiced=False))
        order.data['delivered']=str(delivered+q); order.save(update_fields=['data']); result={'delivery_id':str(r.pk),'item_id':str(item.pk)}
    elif k=='customer_invoice':
        delivery=scoped_record(div,p['delivery_id'],'delivery')
        if delivery.data['invoiced']: raise BusinessError('This delivery already has a management invoice.')
        r=record(d,k,dict(delivery.data,invoice_reference=p['reference'],notice='Management record — NOT a tax invoice'))
        delivery.data['invoiced']=True; delivery.save(update_fields=['data']); result={'invoice_id':str(r.pk)}
    elif k in ('collection','supplier_payment'):
        side='receivable' if k=='collection' else 'payable'; item=OpenItem.objects.get(pk=p['item_id'],division=div,side=side)
        amount=money(p['amount'])
        if amount>item.total-item.settled: raise BusinessError('Payment exceeds the outstanding balance.')
        if k=='supplier_payment':
            bp=item.decision.versions.get(number=item.decision.current_version).payload
            if p['beneficiary']!=bp['beneficiary']: raise BusinessError('Beneficiary differs from the approved supplier bill.')
            if balance(div,'bank')<amount: raise BusinessError('Insufficient recorded cash.')
        post(d,p,pair('bank','receivable',amount) if k=='collection' else pair('payable','bank',amount))
        item.settled+=amount; item.save(update_fields=['settled']); result={'item_id':str(item.pk),'outstanding':str(item.total-item.settled)}
    elif k=='customer_deposit':
        post(d,p,pair('bank','customer_deposit',p['amount']))
        r=record(d,k,dict(p,allocated='0')); result={'deposit_id':str(r.pk)}
    elif k=='apply_deposit':
        deposit=scoped_record(div,p['deposit_id'],'customer_deposit')
        item=OpenItem.objects.get(pk=p['item_id'],division=div,side='receivable')
        amount=money(p['amount']); allocated=money(deposit.data['allocated'])
        if item.party!=deposit.data['party']: raise BusinessError('Deposit and receivable belong to different customers.')
        if amount>money(deposit.data['amount'])-allocated or amount>item.total-item.settled: raise BusinessError('Allocation exceeds deposit or receivable balance.')
        post(d,p,pair('customer_deposit','receivable',amount))
        deposit.data['allocated']=str(allocated+amount); deposit.save(update_fields=['data'])
        item.settled+=amount; item.save(update_fields=['settled'])
    elif k=='supplier_advance':
        if money(p['amount'])>balance(div,'bank'): raise BusinessError('Insufficient recorded cash.')
        post(d,p,pair('supplier_advance','bank',p['amount']))
    elif k=='repayment':
        amount=money(p['amount']); account=p.get('funding_account','funding_loan')
        if account not in ('funding_loan','funding_parent_current','funding_proprietor'): raise BusinessError('Invalid funding account.')
        if amount>balance(div,'bank') or amount>-balance(div,account): raise BusinessError('Repayment exceeds cash or funding principal.')
        post(d,p,pair(account,'bank',amount))
    elif k=='mold_acceptance':
        if money(p['amount'])>balance(div,'supplier_advance'): raise BusinessError('Acceptance exceeds recorded advances.')
        mold=Record.objects.get(pk=p['mold_id'],division=div,kind='mold')
        post(d,p,pair('mold_asset','supplier_advance',p['amount'])); mold.status='accepted'; mold.save(update_fields=['status'])
    elif k=='depreciation':
        if p['allocation']!='operating': raise BusinessError('Inventory depreciation allocation needs a reviewed production costing integration; do not double count.')
        if money(p['amount'])>balance(div,'mold_asset')+balance(div,'accumulated_depreciation'): raise BusinessError('Depreciation exceeds net asset value.')
        post(d,p,pair('depreciation','accumulated_depreciation',p['amount']))
    elif k=='customer_return':
        delivery=scoped_record(div,p['delivery_id'],'delivery'); dp=delivery.data; q=quantity(p['quantity']); returned=decimal(dp['returned'])
        if q>decimal(dp['quantity'])-returned: raise BusinessError('Return exceeds delivered quantity.')
        # Cumulative allocation avoids a halala drift on repeated partial returns.
        def increment(key): return money(decimal(dp[key])*(returned+q)/decimal(dp['quantity']))-money(decimal(dp[key])*returned/decimal(dp['quantity']))
        net=increment('net'); vat=increment('vat'); cost=increment('cost'); gross=net+vat
        item=OpenItem.objects.get(pk=dp['item_id'],division=div); offset=min(gross,item.total-item.settled); credit=gross-offset
        lines=[{'account':'revenue','debit':net}]
        if vat: lines.append({'account':'vat_output','debit':vat})
        if offset: lines.append({'account':'receivable','credit':offset})
        if credit: lines.append({'account':'customer_credit','credit':credit})
        if cost: lines+=pair('inventory','cogs',cost)
        post(d,p,lines); item.total-=offset; item.save(update_fields=['total'])
        old=Stock.objects.get(pk=dp['stock_id'],division=div)
        s=Stock.objects.create(division=div,sku=old.sku,location=old.location,lot='return-'+str(d.pk),quantity=q,value=cost,status='quarantined')
        Movement.objects.create(division=div,stock=s,decision=d,quantity=q,value=cost,kind='return')
        delivery.data['returned']=str(returned+q); delivery.save(update_fields=['data'])
        r=record(d,k,dict(p,credit=credit,refunded='0',stock_id=str(s.pk))); result={'return_id':str(r.pk),'credit':str(credit)}
    elif k=='customer_refund':
        r=scoped_record(div,p['return_id'],'customer_return'); amount=money(p['amount'])
        if amount>money(r.data['credit'])-money(r.data['refunded']) or amount>balance(div,'bank'): raise BusinessError('Refund exceeds customer credit or available cash.')
        post(d,p,pair('customer_credit','bank',amount)); r.data['refunded']=str(money(r.data['refunded'])+amount); r.save(update_fields=['data'])
    elif k=='supplier_refund':
        if money(p['amount'])>balance(div,'supplier_advance'): raise BusinessError('Refund exceeds recorded supplier advances.')
        post(d,p,pair('bank','supplier_advance',p['amount']))
    elif k=='stock_adjustment':
        s=Stock.objects.get(pk=p['stock_id'],division=div,owner='company'); delta=decimal(p['quantity_delta'])
        if delta>=0: raise BusinessError('Positive adjustments require a verified receipt and cost; use goods receipt.')
        if -delta>s.quantity-s.reserved: raise BusinessError('Adjustment would consume reserved or unavailable stock.')
        cost=money(s.value*(-delta)/s.quantity)
        post(d,p,pair('abnormal_waste','inventory',cost)); s.quantity+=delta; s.value-=cost; s.save()
        Movement.objects.create(division=div,stock=s,decision=d,quantity=delta,value=-cost,kind='adjustment')
    elif k=='journal':
        if any(x['account'] in ('inventory','receivable','payable','goods_received_unbilled','customer_credit') for x in p['lines']): raise BusinessError('Use the subledger workflow for stock, customer and supplier control accounts.')
        if any(x['account'] in ('distribution','compensation') for x in p['lines']): raise BusinessError('Payout activation requires the legally reviewed arrangement; disabled in this release.')
        j=post(d,p,p['lines']); result={'journal_id':str(j.pk)}
    elif k=='reversal':
        j=Journal.objects.get(pk=p['journal_id'],division=div)
        if j.decision.kind not in ('journal','funding_direct','funding_cash','depreciation'): raise BusinessError('Use linked returns/refunds for subledger events to preserve reconciliation.')
        reverse=post(d,p,[{'account':x.account,'debit':x.credit,'credit':x.debit} for x in j.lines.all()],reversal=j); result={'journal_id':str(reverse.pk)}
    elif k in ('close_period','reopen_period'):
        through=date.fromisoformat(p['through'])
        if k=='close_period' and div.closed_through and through<div.closed_through: raise BusinessError('Use a jointly approved reopen decision.')
        if k=='reopen_period' and (not div.closed_through or through>=div.closed_through): raise BusinessError('Reopen must move the lock date earlier.')
        div.closed_through=through; div.save(update_fields=['closed_through'])
    elif k=='contract_approval':
        c=Contract.objects.get(pk=p['contract_id'],division=div)
        if digest({'template':c.template,'fields':c.fields})!=p['contract_hash']: raise BusinessError('Contract content changed. Create a new decision version and obtain fresh signatures.')
        c.internal_decision=d; c.status='internally_approved'; c.save()
        result={'contract_id':str(c.pk),'external_status':'External signatures still required; internal approval is not external execution.'}
    return result

@transaction.atomic
def log_fact(division,user,kind,title,data):
    division=lock(division); require_role(user,division,('operator','reviewer'))
    if not isinstance(data,dict) or not title or len(title)>200: raise BusinessError('A title and JSON object are required.')
    if kind=='forecast':
        try: date.fromisoformat(data['date'])
        except (KeyError,ValueError,TypeError): raise BusinessError('Forecast requires a date in YYYY-MM-DD format.')
        decimal(data.get('inflow','0'),nonnegative=True); decimal(data.get('outflow','0'),nonnegative=True)
    if kind not in ('receipt_fact','physical_count','outside_payment','customer','supplier','product','mold','forecast','funding_draft','commitment','quality_inspection'):
        raise BusinessError('Unsupported factual record type.')
    r=Record.objects.create(division=division,kind=kind,title=title,data=data,status='review_required',source_status='reported_unverified')
    audit(division,user,'fact.recorded',r.pk,{'kind':kind,'authorization':'not granted; both operators must review posting'})
    return r

@transaction.atomic
def import_bank(division,user,content,account_reference):
    division=lock(division); require_role(user,division,('operator','reviewer'))
    reader=csv.DictReader(io.StringIO(content)); required={'external_id','date','amount','memo'}
    if not reader.fieldnames or not required.issubset(reader.fieldnames): raise BusinessError('CSV requires external_id,date,amount,memo headers.')
    count=0; duplicates=0
    for i,row in enumerate(reader):
        if i>=5000: raise BusinessError('Limit imports to 5,000 lines.')
        day=date.fromisoformat(row['date']); amount=money(row['amount'])
        if not row['external_id'] or len(row['external_id'])>100: raise BusinessError('A stable statement row ID is required.')
        existing=BankRow.objects.filter(division=division,account_reference=account_reference,external_id=row['external_id']).first()
        if existing:
            if existing.date!=day or existing.amount!=amount: raise BusinessError('Duplicate bank row ID has conflicting data.')
            duplicates+=1; continue
        BankRow.objects.create(division=division,account_reference=account_reference,external_id=row['external_id'],date=day,amount=amount,memo=row['memo'][:250]); count+=1
    audit(division,user,'bank.imported',account_reference,{'inserted':count,'duplicates':duplicates})
    return {'inserted':count,'duplicates':duplicates}

@transaction.atomic
def match_bank(division,user,row_id,line_id):
    division=lock(division); require_role(user,division,('operator','reviewer'))
    row=BankRow.objects.get(pk=row_id,division=division)
    line=Line.objects.get(pk=line_id,journal__division=division,account='bank')
    if row.matched_line_id or row.amount!=line.debit-line.credit: raise BusinessError('Select an unmatched row and an exact matching bank amount.')
    row.matched_line=line; row.save(update_fields=['matched_line']); audit(division,user,'bank.matched',row.pk,{'line':line_id})

@transaction.atomic
def upload(division,user,name,media_type,content,replaces=None):
    division=lock(division); require_role(user,division,('operator','reviewer'))
    if not content or len(content)>10*1024*1024: raise BusinessError('Files must be between 1 byte and 10 MB.')
    allowed={'application/pdf':b'%PDF-','image/png':b'\x89PNG\r\n\x1a\n','image/jpeg':b'\xff\xd8\xff','text/plain':None}
    if media_type not in allowed: raise BusinessError('Only PDF, PNG, JPEG and plain text evidence is accepted.')
    if allowed[media_type] and not content.startswith(allowed[media_type]): raise BusinessError('File bytes do not match the claimed type.')
    if media_type=='text/plain':
        try: content.decode('utf-8')
        except UnicodeDecodeError: raise BusinessError('Text evidence must be UTF-8.')
    old=Document.objects.get(pk=replaces,division=division) if replaces else None
    doc=Document.objects.create(division=division,uploaded_by=user,name=name[:200],media_type=media_type,content=content,size=len(content),sha256=hashlib.sha256(content).hexdigest(),replaces=old)
    audit(division,user,'document.uploaded',doc.pk,{'hash':doc.sha256,'scan_status':'quarantined'})
    if old:
        for d in Decision.objects.filter(division=division,status__in=['draft','submitted','one_signature','authorized']):
            v=d.versions.get(number=d.current_version)
            if any(x['id']==str(old.pk) for x in v.payload['documents']):
                p=copy.deepcopy(v.payload)
                p['documents']=[{'id':str(doc.pk),'sha256':doc.sha256,'name':doc.name,'scan_status':doc.scan_status} if x['id']==str(old.pk) else x for x in p['documents']]
                if p.get('evidence_id')==str(old.pk): p['evidence_id']=str(doc.pk)
                d.current_version+=1; d.status='draft'; d.save(update_fields=['current_version','status'])
                DecisionVersion.objects.create(decision=d,number=d.current_version,payload=p,digest=digest(p))
                audit(division,user,'decision.document_superseded',d.pk,{'version':d.current_version,'old_document':str(old.pk),'new_document':str(doc.pk)})
    return doc
