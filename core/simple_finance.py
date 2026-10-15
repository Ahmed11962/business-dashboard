"""Management-register calculations; historical posted journals are reported separately."""
from collections import defaultdict
from decimal import Decimal, ROUND_CEILING
from django.db.models import Q
from .finance import BusinessError, decimal, money
from .models import FinanceTransaction,CashOpening

ZERO=Decimal('0.00')

def calculate_scenario(investment, unit_cost, selling_price, quantity, extra_expenses=0):
    fixed=money(decimal(investment,nonnegative=True)+decimal(extra_expenses,nonnegative=True))
    unit=money(decimal(unit_cost,nonnegative=True))
    price=money(decimal(selling_price,positive=True))
    units=decimal(quantity,positive=True)
    if units!=units.to_integral_value(): raise BusinessError('Quantity must be a whole number.')
    sales=money(price*units); variable=money(unit*units)
    gross=money(sales-variable); profit=money(gross-fixed)
    contribution=price-unit
    break_even=int((fixed/contribution).to_integral_value(rounding=ROUND_CEILING)) if contribution>0 else None
    outlay=money(fixed+variable)
    return {'sales':sales,'production_cost':variable,'fixed_cost':fixed,'gross_profit':gross,
            'gross_margin_percent':money(gross/sales*100) if sales else ZERO,
            'projected_profit':profit,'break_even_units':break_even,
            'roi_percent':money(profit/outlay*100) if outlay else None}

def outstanding(entry):
    if entry.total_due is None: return ZERO
    settled=entry.amount+sum((x.amount for x in entry.payments.all()),ZERO)
    refunded=sum((x.amount for x in entry.refunds.all()),ZERO)
    return max(ZERO,entry.total_due-settled+refunded)

def summary(division, start=None, end=None, category=None):
    all_entries=FinanceTransaction.objects.filter(division=division).select_related('settles','refund_of').prefetch_related('payments','refunds')
    entries=all_entries
    if start: entries=entries.filter(date__gte=start)
    if end: entries=entries.filter(date__lte=end)
    if category: entries=entries.filter(category=category)
    received=paid=income=expenses=ZERO
    by_category=defaultdict(lambda:ZERO)
    by_month=defaultdict(lambda:{'received':ZERO,'paid':ZERO,'income':ZERO,'expenses':ZERO})
    by_year=defaultdict(lambda:{'received':ZERO,'paid':ZERO,'income':ZERO,'expenses':ZERO})
    for t in entries:
        if t.direction=='received': received+=t.amount; by_month[t.date.strftime('%Y-%m')]['received']+=t.amount; by_year[str(t.date.year)]['received']+=t.amount
        else: paid+=t.amount; by_month[t.date.strftime('%Y-%m')]['paid']+=t.amount; by_year[str(t.date.year)]['paid']+=t.amount
        if t.treatment=='income':
            income+=t.recognized_amount; by_month[t.date.strftime('%Y-%m')]['income']+=t.recognized_amount; by_year[str(t.date.year)]['income']+=t.recognized_amount
        if t.treatment=='expense':
            expenses+=t.recognized_amount; by_month[t.date.strftime('%Y-%m')]['expenses']+=t.recognized_amount; by_year[str(t.date.year)]['expenses']+=t.recognized_amount
        if t.direction=='paid': by_category[t.category]+=t.amount
        elif t.refund_of_id and t.refund_of.direction=='paid': by_category[t.refund_of.category]-=t.amount
    receivable=payable=ZERO
    # Outstanding items are balances as of now, independent of the activity filter.
    for t in all_entries.filter(total_due__isnull=False,settles__isnull=True,refund_of__isnull=True):
        if t.direction=='received': receivable+=outstanding(t)
        else: payable+=outstanding(t)
    peak=max([row[key] for row in by_month.values() for key in ('received','paid')]+[Decimal(1)])
    for row in by_month.values():
        row['received_pct']=int(row['received']/peak*100)
        row['paid_pct']=int(row['paid']/peak*100)
        row['profit']=row['income']-row['expenses']
    for row in by_year.values(): row['profit']=row['income']-row['expenses']
    return {'received':received,'paid':paid,'net_cash':received-paid,'income':income,'expenses':expenses,
            'profit':income-expenses,'receivable':receivable,'payable':payable,
            'categories':sorted(by_category.items(),key=lambda row:-row[1]),
            'months':sorted(by_month.items(),reverse=True),'years':sorted(by_year.items(),reverse=True)}

def account_balances(division):
    result={}
    for method,account in [('bank','bank'),('cash','petty_cash')]:
        opening=CashOpening.objects.filter(division=division,method=method).first()
        if not opening:
            result[method]=None
            continue
        movement=ZERO
        for t in FinanceTransaction.objects.filter(division=division,method=method,date__gt=opening.as_of):
            movement+=t.amount if t.direction=='received' else -t.amount
        result[method]=opening.amount+movement
    return result
