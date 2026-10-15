"""Transactional manufacturing workflow; FinanceTransaction is the only cash register."""
from datetime import date
from calendar import monthrange
from decimal import Decimal, ROUND_CEILING
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from .finance import BusinessError, decimal, money
from .models import (Mold, Product, ProductionBatch, SalesInvoice, InvoiceLine,
                     StockEvent, FinanceTransaction, CapitalContribution, CapitalRepayment,
                     InvoiceCredit, CashAccount, TransactionRevision)
from . import services

ZERO=Decimal('0.00')

def production_cost(quantity, grams, price_per_gram, *charges):
    units=int(decimal(quantity,positive=True))
    if units!=decimal(quantity): raise BusinessError('Units must be a whole number.')
    material=money(decimal(grams,positive=True)*decimal(price_per_gram,nonnegative=True)*units)
    extras=money(sum((decimal(x,nonnegative=True) for x in charges),Decimal(0)))
    return {'material':material,'extras':extras,'total':money(material+extras),
            'unit':money((material+extras)/units)}

def batch_cost(batch):
    estimate=production_cost(batch.quantity,batch.weight_grams,batch.price_per_gram,
                             batch.setup_cost,batch.packaging_cost,batch.transport_cost,batch.other_cost)
    contracted=money(batch.quoted_cost) if batch.quoted_cost is not None else estimate['total']
    return {**estimate,'contracted':contracted,'basis':money(batch.final_cost) if batch.final_cost is not None else contracted}

def net_payments(record):
    paid=ZERO
    for t in record.payments.all(): paid+=t.amount if t.direction=='paid' else -t.amount
    return money(paid)

def invoice_total(invoice):
    if invoice.status=='cancelled': return ZERO
    subtotal=sum((decimal(line.unit_price)*line.quantity for line in invoice.lines.all()),ZERO)
    credits=invoice.credits.aggregate(v=Sum('amount'))['v'] or ZERO
    return money(subtotal-decimal(invoice.discount)+decimal(invoice.tax)-credits)

def invoice_revenue(invoice):
    if invoice.status=='cancelled': return ZERO
    subtotal=sum((decimal(line.unit_price)*line.quantity for line in invoice.lines.all()),ZERO)
    credits=sum((c.amount-c.tax_amount for c in invoice.credits.all()),ZERO)
    return money(subtotal-decimal(invoice.discount)-credits)

def invoice_received(invoice):
    return money(sum((t.amount if t.direction=='received' else -t.amount for t in invoice.payments.all()),ZERO))

def balance(record):
    if isinstance(record,Mold): return money(decimal(record.price)-net_payments(record))
    if isinstance(record,ProductionBatch):
        return ZERO if record.status in ('planned','cancelled') else money(batch_cost(record)['basis']-net_payments(record))
    if isinstance(record,SalesInvoice): return money(invoice_total(record)-invoice_received(record))
    raise BusinessError('Unsupported record.')

@transaction.atomic
def record_payment(div,user,record,amount,reference,paid_on,method='bank',party='',notes='',account=None,refund_of=None):
    services.lock(div)
    amount=money(decimal(amount,positive=True)); reference=reference.strip()
    if not reference: raise BusinessError('A unique payment reference is required.')
    if method not in ('bank','cash','other'): raise BusinessError('Choose a valid payment method.')
    if account and account.kind!=method: raise BusinessError('Account and payment method must match.')
    if FinanceTransaction.objects.filter(division=div,reference=reference).exists(): raise BusinessError('This payment reference already exists.')
    if record.division_id!=div.id or (account and account.division_id!=div.id): raise BusinessError('Record belongs to another workspace.')
    if isinstance(record,Mold): link={'mold':record}; direction='paid'; category='Mold payment'; maximum=balance(record)
    elif isinstance(record,ProductionBatch): link={'batch':record}; direction='paid'; category='Production payment'; maximum=balance(record)
    elif isinstance(record,SalesInvoice): link={'invoice':record}; direction='received'; category='Customer payment'; maximum=balance(record)
    else: raise BusinessError('Unsupported payment record.')
    if refund_of:
        if refund_of.division_id!=div.id or getattr(refund_of,list(link)[0]+'_id')!=record.id or refund_of.refund_of_id:
            raise BusinessError('Refund must refer to a payment for this record.')
        refunded=refund_of.refunds.aggregate(v=Sum('amount'))['v'] or ZERO
        if amount>refund_of.amount-refunded: raise BusinessError('Refund exceeds original payment.')
        direction='received' if direction=='paid' else 'paid'
    elif amount>maximum: raise BusinessError('Payment exceeds the remaining balance.')
    t=FinanceTransaction.objects.create(division=div,date=paid_on,direction=direction,amount=amount,
        category=category,description=f'{category}: {record}',party=party,method=method,
        reference=reference,notes=notes,treatment='none',recognized_amount=0,created_by=user,
        account=account,refund_of=refund_of,**link)
    from .simple import snapshot
    TransactionRevision.objects.create(transaction=t,actor=user,snapshot=snapshot(t))
    services.audit(div,user,'workflow.payment',t.pk,{'reference':reference,'amount':str(amount),'direction':direction,'record':str(record.pk)})
    return t

@transaction.atomic
def receive(div,user,batch,accepted,rejected,damaged,reference):
    services.lock(div)
    if StockEvent.objects.filter(division=div,reference=reference).exists(): raise BusinessError('This stock reference already exists.')
    batch=ProductionBatch.objects.select_for_update().select_related('mold__product').get(pk=batch.pk,division=div)
    if batch.status not in ('ordered','in_production','partially_received'): raise BusinessError('Only ordered or active production can be received.')
    values=[decimal(x,nonnegative=True) for x in (accepted,rejected,damaged)]
    if not all(value==int(value) for value in values):
        raise BusinessError('Enter whole units received, rejected, or damaged.')
    accepted,rejected,damaged=map(int,values)
    if accepted+rejected+damaged<=0: raise BusinessError('Enter units received, rejected, or damaged.')
    previous=sum((e.accepted+e.rejected+e.damaged for e in StockEvent.objects.filter(batch=batch,kind='receipt')),0)
    if previous+accepted+rejected+damaged>batch.quantity: raise BusinessError('Receipt exceeds ordered quantity.')
    product=Product.objects.select_for_update().get(pk=batch.mold.product_id)
    cost=money(batch_cost(batch)['basis']*accepted/batch.quantity)
    if accepted:
        product.quantity+=accepted; product.inventory_value+=cost
        product.save(update_fields=['quantity','inventory_value'])
    event=StockEvent.objects.create(division=div,product=product,batch=batch,kind='receipt',quantity=accepted,
        value=cost,accepted=accepted,rejected=rejected,damaged=damaged,reference=reference,actor=user)
    batch.status='completed' if previous+accepted+rejected+damaged==batch.quantity else 'partially_received'
    batch.save(update_fields=['status'])
    services.audit(div,user,'inventory.received',event.pk,{'batch':str(batch.pk),'accepted':accepted,'rejected':rejected,'damaged':damaged,'cost':str(cost)})
    return event

@transaction.atomic
def dispatch(div,user,line,quantity,reference):
    services.lock(div)
    if StockEvent.objects.filter(division=div,reference=reference).exists(): raise BusinessError('This stock reference already exists.')
    line=InvoiceLine.objects.select_for_update().select_related('invoice','product').get(pk=line.pk,invoice__division=div)
    if line.invoice.status!='issued': raise BusinessError('Only an issued invoice can be fulfilled.')
    units=int(decimal(quantity,positive=True))
    if decimal(quantity)!=units or line.fulfilled+units>line.quantity: raise BusinessError('Dispatch exceeds invoice quantity.')
    product=Product.objects.select_for_update().get(pk=line.product_id)
    if units>product.quantity-product.reserved: raise BusinessError('Insufficient available stock.')
    cost=product.inventory_value if units==product.quantity else money(product.inventory_value*units/product.quantity)
    product.quantity-=units; product.inventory_value-=cost
    product.save(update_fields=['quantity','inventory_value'])
    line.fulfilled+=units; line.save(update_fields=['fulfilled'])
    event=StockEvent.objects.create(division=div,product=product,invoice_line=line,kind='dispatch',quantity=-units,
        value=-cost,reference=reference,actor=user)
    services.audit(div,user,'inventory.dispatched',event.pk,{'line':line.pk,'quantity':units,'cost':str(cost)})
    return event

@transaction.atomic
def return_goods(div,user,dispatch_event,quantity,reference):
    services.lock(div)
    if StockEvent.objects.filter(division=div,reference=reference).exists(): raise BusinessError('This stock reference already exists.')
    if dispatch_event.division_id!=div.id or dispatch_event.kind!='dispatch': raise BusinessError('Select a dispatch.')
    units=int(decimal(quantity,positive=True))
    previous=sum((x.quantity for x in StockEvent.objects.filter(reverses=dispatch_event,kind='return')),0)
    dispatched=-dispatch_event.quantity
    if decimal(quantity)!=units or previous+units>dispatched: raise BusinessError('Return exceeds this dispatch quantity.')
    product=Product.objects.select_for_update().get(pk=dispatch_event.product_id)
    unit_cost=(-dispatch_event.value)/(-dispatch_event.quantity)
    value=money(-dispatch_event.value-(StockEvent.objects.filter(reverses=dispatch_event,kind='return').aggregate(v=Sum('value'))['v'] or ZERO)) if previous+units==dispatched else money(unit_cost*units)
    product.quantity+=units; product.inventory_value+=value; product.save(update_fields=['quantity','inventory_value'])
    event=StockEvent.objects.create(division=div,product=product,invoice_line=dispatch_event.invoice_line,
        kind='return',quantity=units,value=value,reference=reference,actor=user,reverses=dispatch_event)
    services.audit(div,user,'inventory.returned',event.pk,{'quantity':units,'value':str(value)})
    return event

@transaction.atomic
def writeoff(div,user,product,quantity,reference,reason):
    services.lock(div)
    if StockEvent.objects.filter(division=div,reference=reference).exists(): raise BusinessError('This stock reference already exists.')
    product=Product.objects.select_for_update().get(pk=product.pk,division=div)
    units=int(decimal(quantity,positive=True))
    if decimal(quantity)!=units or units>product.quantity-product.reserved: raise BusinessError('Insufficient available stock.')
    value=product.inventory_value if units==product.quantity else money(product.inventory_value*units/product.quantity)
    product.quantity-=units; product.inventory_value-=value; product.save(update_fields=['quantity','inventory_value'])
    event=StockEvent.objects.create(division=div,product=product,kind='damage',quantity=-units,value=-value,reference=reference,actor=user)
    services.audit(div,user,'inventory.written_off',event.pk,{'quantity':units,'value':str(value),'reason':reason})
    return event

@transaction.atomic
def adjust_stock(div,user,product,change,reference,reason,unit_cost=0):
    services.lock(div)
    if StockEvent.objects.filter(division=div,reference=reference).exists(): raise BusinessError('This stock reference already exists.')
    raw=decimal(change); change=int(raw)
    if raw!=change or not change: raise BusinessError('Adjustment must change a whole number of units.')
    if not reason.strip(): raise BusinessError('Enter a reason for the adjustment.')
    product=Product.objects.select_for_update().get(pk=product.pk,division=div)
    if change<0:
        if -change>product.quantity-product.reserved: raise BusinessError('Insufficient available stock.')
        value=-product.inventory_value if -change==product.quantity else -money(product.inventory_value*(-change)/product.quantity)
    else:
        value=money(decimal(unit_cost,positive=True)*change)
    product.quantity+=change; product.inventory_value+=value
    product.save(update_fields=['quantity','inventory_value'])
    event=StockEvent.objects.create(division=div,product=product,kind='adjustment',quantity=change,value=value,
                                    reference=reference,actor=user)
    services.audit(div,user,'inventory.adjusted',event.pk,{'quantity':change,'value':str(value),'reason':reason})
    return event

@transaction.atomic
def issue_credit(div,user,invoice,amount,reference,reason,tax_amount=0):
    services.lock(div)
    invoice=SalesInvoice.objects.select_for_update().get(pk=invoice.pk,division=div)
    if invoice.status!='issued': raise BusinessError('Only issued invoices can be credited.')
    amount=money(decimal(amount,positive=True))
    if amount>invoice_total(invoice): raise BusinessError('Credit exceeds remaining invoice value.')
    tax_amount=money(decimal(tax_amount,nonnegative=True))
    previous_tax=invoice.credits.aggregate(v=Sum('tax_amount'))['v'] or ZERO
    if tax_amount>amount or tax_amount>decimal(invoice.tax)-previous_tax: raise BusinessError('Credit tax exceeds the available tax amount.')
    if amount-tax_amount>invoice_revenue(invoice): raise BusinessError('Credit excluding tax exceeds remaining sales revenue.')
    if not reference.strip() or not reason.strip(): raise BusinessError('Credit reference and reason are required.')
    credit=InvoiceCredit.objects.create(division=div,invoice=invoice,amount=amount,tax_amount=tax_amount,reference=reference.strip(),
                                        reason=reason.strip(),actor=user)
    services.audit(div,user,'invoice.credited',credit.pk,{'invoice':str(invoice.pk),'amount':str(amount),'tax_amount':str(tax_amount),'reason':reason})
    return credit

def capital_outstanding(contribution):
    if contribution.kind!='repayable': return ZERO
    paid=sum((r.transaction.amount for r in contribution.repayments.all()),ZERO)
    return money(max(ZERO,contribution.transaction.amount-paid))

@transaction.atomic
def repay_capital(div,user,contribution,amount,reference,paid_on,account=None,method='bank'):
    services.lock(div)
    contribution=CapitalContribution.objects.select_for_update().select_related('transaction').get(pk=contribution.pk,division=div)
    amount=money(decimal(amount,positive=True))
    if contribution.kind!='repayable': raise BusinessError('Only confirmed repayable funding can be repaid.')
    if amount>capital_outstanding(contribution): raise BusinessError('Repayment exceeds confirmed outstanding amount.')
    if not reference.strip(): raise BusinessError('Unique reference is required.')
    if account and account.division_id!=div.id: raise BusinessError('Account belongs to another workspace.')
    if method not in ('bank','cash','other') or (account and account.kind!=method): raise BusinessError('Choose a matching account and payment method.')
    t=FinanceTransaction.objects.create(division=div,date=paid_on,direction='paid',amount=amount,
        category='Capital repayment',description=f'Capital repayment to {contribution.contributor}',
        party=contribution.contributor,method=method,account=account,
        reference=reference.strip(),treatment='none',recognized_amount=0,created_by=user)
    from .simple import snapshot
    TransactionRevision.objects.create(transaction=t,actor=user,snapshot=snapshot(t))
    repayment=CapitalRepayment.objects.create(division=div,contribution=contribution,transaction=t)
    services.audit(div,user,'capital.repaid',repayment.pk,{'amount':str(amount),'contribution':str(contribution.pk)})
    return repayment

def repayment_plan(owed,repaid,months,annual_rate=0,extra=0,start=None):
    owed=money(decimal(owed,nonnegative=True)); repaid=money(decimal(repaid,nonnegative=True))
    if repaid>owed: raise BusinessError('Repaid exceeds owed.')
    months_value=decimal(months,positive=True); months=int(months_value)
    if months_value!=months: raise BusinessError('Duration must be a whole number of months.')
    if not 1<=months<=360: raise BusinessError('Choose 1 to 360 months.')
    rate=decimal(annual_rate,nonnegative=True)/1200; extra=money(decimal(extra,nonnegative=True))
    remaining=owed-repaid
    if not remaining: return {'remaining':ZERO,'monthly':ZERO,'total':ZERO,'months':0,'schedule':[]}
    base=money(remaining/months if rate==0 else remaining*rate/(1-(1+rate)**(-months)))
    schedule=[]; total=ZERO
    for index in range(1,361):
        interest=money(remaining*rate); payment=min(remaining+interest,base+extra)
        if index==months and extra==0: payment=remaining+interest
        principal=payment-interest
        if principal<=0: raise BusinessError('Payment does not cover interest.')
        remaining=money(remaining-principal); total+=payment
        schedule.append({'month':index,'payment':payment,'principal':principal,'interest':interest,'remaining':remaining})
        if remaining<=0: break
    if start:
        if isinstance(start,str): start=date.fromisoformat(start)
        month=start.month-1+len(schedule)
        year=start.year+month//12; month=month%12+1
        completion=date(year,month,min(start.day,monthrange(year,month)[1]))
    else: completion=None
    return {'remaining':owed-repaid,'monthly':base+extra,'total':money(total),'months':len(schedule),
            'completion':completion,'schedule':schedule}

def distribution_plan(profit,cash,retention=50,reserves=0,liabilities=0,taxes=0,sayem_repayment=0,sami_repayment=0):
    profit=max(ZERO,money(decimal(profit))); cash=money(decimal(cash))
    reserves,liabilities,taxes,sayem_repayment,sami_repayment=[money(decimal(x,nonnegative=True)) for x in (reserves,liabilities,taxes,sayem_repayment,sami_repayment)]
    pct=decimal(retention,nonnegative=True)
    if pct>100: raise BusinessError('Retention must be 0 to 100%.')
    available=min(profit,max(ZERO,cash-reserves-liabilities-taxes))
    retained=money(available*pct/100); distributed=available-retained
    sayem=money(distributed/2); sami=distributed-sayem
    if sayem_repayment>sayem or sami_repayment>sami: raise BusinessError('Repayment allocation exceeds a partner share.')
    return {'available':available,'retained':retained,'distributed':distributed,'sayem':sayem,'sami':sami,
            'sayem_net':sayem-sayem_repayment,'sami_net':sami-sami_repayment,'cash_after':cash-distributed}

def cash_forecast(opening,monthly_in,monthly_out,months,one_time=0,repayment=0):
    current=money(decimal(opening))
    incoming=money(decimal(monthly_in,nonnegative=True)); outgoing=money(decimal(monthly_out,nonnegative=True))
    investment=money(decimal(one_time,nonnegative=True)); debt=money(decimal(repayment,nonnegative=True))
    count=decimal(months,positive=True)
    if count!=int(count) or count>36: raise BusinessError('Choose 1 to 36 whole months.')
    rows=[]
    for index in range(1,int(count)+1):
        current=money(current+incoming-outgoing-debt-(investment if index==1 else ZERO))
        rows.append({'month':index,'balance':current})
    return {'rows':rows,'ending':current,'affordable':all(row['balance']>=0 for row in rows)}

def manufacturing_totals(div,start=None,end=None,category=None):
    molds=list(Mold.objects.filter(division=div).prefetch_related('payments'))
    batches=list(ProductionBatch.objects.filter(division=div).select_related('mold').prefetch_related('payments'))
    invoice_qs=SalesInvoice.objects.filter(division=div,status='issued').prefetch_related('payments','lines')
    if start: invoice_qs=invoice_qs.filter(date__gte=start)
    if end: invoice_qs=invoice_qs.filter(date__lte=end)
    invoices=list(invoice_qs)
    sales=sum((money(sum((decimal(line.unit_price)*line.quantity for line in x.lines.all()),ZERO)-x.discount) for x in invoices),ZERO)
    credit_qs=InvoiceCredit.objects.filter(division=div,invoice__status='issued')
    if start: credit_qs=credit_qs.filter(created_at__date__gte=start)
    if end: credit_qs=credit_qs.filter(created_at__date__lte=end)
    sales-=sum((c.amount-c.tax_amount for c in credit_qs),ZERO)
    stock=StockEvent.objects.filter(division=div)
    if start: stock=stock.filter(created_at__date__gte=start)
    if end: stock=stock.filter(created_at__date__lte=end)
    cogs=-(stock.filter(kind='dispatch').aggregate(v=Sum('value'))['v'] or ZERO)
    cogs-=(stock.filter(kind='return').aggregate(v=Sum('value'))['v'] or ZERO)
    writeoffs=-(stock.filter(kind='damage').aggregate(v=Sum('value'))['v'] or ZERO)
    adjustments=stock.filter(kind='adjustment').aggregate(v=Sum('value'))['v'] or ZERO
    from .simple_finance import summary
    cash=summary(div,start,end,category)
    contributions=CapitalContribution.objects.filter(division=div).aggregate(v=Sum('transaction__amount'))['v'] or ZERO
    repayments=CapitalRepayment.objects.filter(division=div).aggregate(v=Sum('transaction__amount'))['v'] or ZERO
    funding_due=sum((capital_outstanding(c) for c in CapitalContribution.objects.filter(division=div).select_related('transaction').prefetch_related('repayments__transaction')),ZERO)
    expenses=cash['expenses']+writeoffs
    distribution_entries=FinanceTransaction.objects.filter(division=div,category__iexact='Partner distribution',direction='paid',refund_of__isnull=True).prefetch_related('refunds')
    distributions=sum((t.amount-sum((r.amount for r in t.refunds.all()),ZERO) for t in distribution_entries),ZERO)
    return {'mold_count':len(molds),'molds_owned':sum(1 for x in molds if x.ownership_confirmed and balance(x)<=0),
            'active_batches':sum(1 for x in batches if x.status not in ('completed','cancelled')),
            'mold_due':sum((max(ZERO,balance(x)) for x in molds),ZERO),'mold_paid':sum((net_payments(x) for x in molds),ZERO),
            'production_due':sum((max(ZERO,balance(x)) for x in batches),ZERO),
            'production_paid':sum((net_payments(x) for x in batches),ZERO),
            'receivables':sum((max(ZERO,balance(x)) for x in invoices),ZERO),
            'customer_credit_due':sum((max(ZERO,-balance(x)) for x in invoices),ZERO),
            'inventory_units':Product.objects.filter(division=div).aggregate(v=Sum('quantity'))['v'] or 0,
            'product_count':Product.objects.filter(division=div,quantity__gt=0).count(),
            'inventory_value':Product.objects.filter(division=div).aggregate(v=Sum('inventory_value'))['v'] or ZERO,
            'sales':sales,'cogs':cogs,'expenses':expenses,'gross':sales-cogs,
            'profit':sales-cogs-expenses+cash['income']+adjustments,'adjustments':adjustments,
            'capital':contributions,'capital_repaid':repayments,'funding_due':funding_due,'distributions_paid':distributions,
            'received':cash['received'],'paid':cash['paid'],'net_cash':cash['net_cash']}

def performance_by_period(div,start=None,end=None):
    """Accrual-style month/year comparisons, separate from cash movements."""
    from collections import defaultdict
    def empty(): return {'sales':ZERO,'cogs':ZERO,'expenses':ZERO,'other':ZERO}
    months=defaultdict(empty)
    def within(day): return (not start or day>=start) and (not end or day<=end)
    for invoice in SalesInvoice.objects.filter(division=div,status='issued').prefetch_related('lines'):
        if within(invoice.date):
            months[invoice.date.strftime('%Y-%m')]['sales']+=money(sum((x.unit_price*x.quantity for x in invoice.lines.all()),ZERO)-invoice.discount)
    for credit in InvoiceCredit.objects.filter(division=div,invoice__status='issued'):
        day=timezone.localtime(credit.created_at).date()
        if within(day): months[day.strftime('%Y-%m')]['sales']-=credit.amount-credit.tax_amount
    for event in StockEvent.objects.filter(division=div):
        day=timezone.localtime(event.created_at).date()
        if not within(day): continue
        row=months[day.strftime('%Y-%m')]
        if event.kind in ('dispatch','return'): row['cogs']-=event.value
        elif event.kind=='damage': row['expenses']-=event.value
        elif event.kind=='adjustment': row['other']+=event.value
    for entry in FinanceTransaction.objects.filter(division=div,treatment__in=['income','expense']):
        if within(entry.date):
            row=months[entry.date.strftime('%Y-%m')]
            row['other' if entry.treatment=='income' else 'expenses']+=entry.recognized_amount
    years=defaultdict(empty)
    for month,row in months.items():
        row['profit']=row['sales']-row['cogs']-row['expenses']+row['other']
        year=years[month[:4]]
        for key in ('sales','cogs','expenses','other'): year[key]+=row[key]
    for row in years.values(): row['profit']=row['sales']-row['cogs']-row['expenses']+row['other']
    return {'months':sorted(months.items(),reverse=True),'years':sorted(years.items(),reverse=True)}
