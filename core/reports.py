from collections import defaultdict
from datetime import timedelta
from decimal import Decimal
from django.utils import timezone
from .models import Line,OpenItem,Stock,BankRow,Record,Audit,Journal,Movement
from .services import digest

def trial_balance(division):
    result=defaultdict(lambda:{'debit':Decimal(0),'credit':Decimal(0),'balance':Decimal(0)})
    for line in Line.objects.filter(journal__division=division):
        row=result[line.account]; row['debit']+=line.debit; row['credit']+=line.credit; row['balance']+=line.debit-line.credit
    return [{'account':k,**v} for k,v in sorted(result.items())]

def report(division):
    trial=trial_balance(division); balances={x['account']:x['balance'] for x in trial}; b=lambda k:balances.get(k,Decimal(0))
    today=timezone.localdate(); aging=[]
    for item in OpenItem.objects.filter(division=division):
        days=(today-item.due_date).days
        aging.append({'id':str(item.pk),'side':item.side,'party':item.party,'reference':item.reference,'due':str(item.due_date),'outstanding':item.total-item.settled,'bucket':'current' if days<=0 else '1–30' if days<=30 else '31–60' if days<=60 else '61–90' if days<=90 else '90+'})
    stock=sum((s.value for s in Stock.objects.filter(division=division)),Decimal(0))
    ar=sum((x['outstanding'] for x in aging if x['side']=='receivable'),Decimal(0)); ap=sum((x['outstanding'] for x in aging if x['side']=='payable'),Decimal(0))
    return {'trial_balance':trial,'aging':aging,'revenue':-b('revenue'),'gross_profit':-b('revenue')-b('cogs'),'operating_result':-b('revenue')-b('cogs')-b('expense')-b('abnormal_waste')-b('depreciation')-b('compensation'),'cash':b('bank')+b('petty_cash') if division.opening_confirmed else None,'recorded_cash_movement':b('bank')+b('petty_cash'),'receivable':ar,'payable':ap,'funding':-sum((b(k) for k in ('funding_loan','funding_parent_current','funding_proprietor')),Decimal(0)),'inventory_value':stock,'vat_output':-b('vat_output'),'unreconciled':BankRow.objects.filter(division=division,matched_line__isnull=True).count(),'last_statement':BankRow.objects.filter(division=division).order_by('-date').values_list('date',flat=True).first(),'ties':{'inventory':stock==b('inventory'),'receivable':ar==b('receivable'),'payable':ap==-b('payable'),'trial_balance':sum(balances.values())==0},'as_of':str(today),'opening_confirmed':division.opening_confirmed}

def forecast(division):
    """Explicitly entered weekly cash forecast; never contributes to actual reports."""
    cash=report(division)['cash']; rows=[]; today=timezone.localdate()
    forecasts=list(Record.objects.filter(division=division,kind='forecast'))
    from .finance import decimal
    for i in range(13):
        start=today+timedelta(weeks=i); end=start+timedelta(days=6); incoming=Decimal(0); outgoing=Decimal(0)
        for r in forecasts:
            if str(start)<=r.data.get('date','')<=str(end):
                incoming+=decimal(r.data.get('inflow','0'),nonnegative=True); outgoing+=decimal(r.data.get('outflow','0'),nonnegative=True)
        if cash is not None: cash+=incoming-outgoing
        rows.append({'week':i+1,'start':start,'inflow':incoming,'outflow':outgoing,'ending_cash':cash,'warning':cash is not None and cash<0})
    return rows

def verify_audit(division):
    previous=''
    for a in Audit.objects.filter(division=division).order_by('created_at','id'):
        data={'actor':str(a.actor_id) if a.actor_id else None,'event':a.event,'object':a.object_id,'detail':a.detail,'previous':previous}
        if a.previous_hash!=previous or a.digest!=digest(data): return False
        previous=a.digest
    return True

def statements(division):
    """All actual statement amounts derive from posted ledger lines."""
    r=report(division); b={x['account']:x['balance'] for x in r['trial_balance']}
    asset_names={'bank','petty_cash','supplier_advance','inventory','raw_material','wip','mold_asset','accumulated_depreciation','receivable','vat_input'}
    liability_names={'payable','goods_received_unbilled','customer_deposit','customer_credit','vat_output','funding_loan','funding_parent_current','funding_proprietor'}
    assets=[{'account':k,'amount':b.get(k,Decimal(0))} for k in sorted(asset_names)]
    liabilities=[{'account':k,'amount':-b.get(k,Decimal(0))} for k in sorted(liability_names)]
    equity=-b.get('equity',Decimal(0))-b.get('distribution',Decimal(0))+r['operating_result']
    cashflow=defaultdict(lambda:Decimal(0)); funding=[]
    for line in Line.objects.filter(journal__division=division).select_related('journal__decision'):
        if line.account in ('bank','petty_cash'):
            kind=line.journal.decision.kind
            category='financing' if kind in ('funding_cash','repayment') else 'investing' if kind=='supplier_advance' else 'unclassified_manual' if kind in ('journal','reversal') else 'operating'
            cashflow[category]+=line.debit-line.credit
        if line.account.startswith('funding_'):
            funding.append({'date':line.journal.date,'reference':line.journal.reference,'decision_id':str(line.journal.decision_id),'account':line.account,'principal_added':line.credit,'principal_repaid_or_reversed':line.debit})
    commits=[]
    for rec in Record.objects.filter(division=division,kind__in=['purchase_order','commitment']):
        commits.append({'id':str(rec.pk),'title':rec.title,'source':rec.source_status,'status':rec.status,'amount':rec.data.get('amount',rec.data.get('amount_sar')),'due':rec.data.get('due_date'),'released_quantity':rec.data.get('released'),'notice':'Commitment record; do not add to payables without matching and accounting recognition.'})
    profit=defaultdict(lambda:{'revenue':Decimal(0),'cost':Decimal(0),'units':Decimal(0)})
    for rec in Record.objects.filter(division=division,kind='delivery',source_status='verified_posted'):
        p=rec.data; row=profit[p['stock_id']]; row['revenue']+=Decimal(p['net']); row['cost']+=Decimal(p['cost']); row['units']+=Decimal(p['quantity'])
    # Returns reverse original delivery values using the same cumulative rounding convention.
    from .finance import money
    for rec in Record.objects.filter(division=division,kind='delivery',source_status='verified_posted'):
        p=rec.data; fraction=Decimal(p['returned'])/Decimal(p['quantity']); row=profit[p['stock_id']]
        row['revenue']-=money(Decimal(p['net'])*fraction); row['cost']-=money(Decimal(p['cost'])*fraction); row['units']-=Decimal(p['returned'])
    batches=[{'stock_id':key,**value,'gross_profit':value['revenue']-value['cost']} for key,value in profit.items()]
    return {'assets':assets,'liabilities':liabilities,'management_equity':equity,'position_balances':sum(x['amount'] for x in assets)==sum(x['amount'] for x in liabilities)+equity,'cashflow':dict(cashflow),'funding':funding,'commitments':commits,'batches':batches,'approval_exceptions':list(Record.objects.filter(division=division,status='review_required').values('id','title','kind','source_status'))}
