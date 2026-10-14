"""Deterministic SAR calculations. Decimal inputs only; round posted lines half-up to halalas."""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, ROUND_CEILING, localcontext

class BusinessError(ValueError): pass

def decimal(value, *, positive=False, nonnegative=False):
    if isinstance(value, (float,bool)): raise BusinessError('Use decimal strings, never binary floats.')
    try: result=Decimal(str(value))
    except (InvalidOperation,ValueError): raise BusinessError('Enter a valid decimal amount.')
    if not result.is_finite() or abs(result)>Decimal('1000000000000'): raise BusinessError('Amount outside permitted range.')
    if positive and result<=0: raise BusinessError('Amount must be positive.')
    if nonnegative and result<0: raise BusinessError('Amount cannot be negative.')
    return result

def money(value): return decimal(value).quantize(Decimal('.01'),rounding=ROUND_HALF_UP)
def quantity(value):
    value=decimal(value,positive=True)
    if value!=value.quantize(Decimal('.001')): raise BusinessError('Quantity precision is 0.001 units.')
    return value

def split_vat(gross,rate='15'):
    gross=money(gross); rate=decimal(rate,nonnegative=True)
    net=money(gross/(1+rate/100))
    return {'gross':gross,'net':net,'vat':gross-net}

def scenario(good='100000',grams='82',rate='4.50',yield_percent='100',price='2',mold='20000',paid='10000',vat_inclusive=False,vat_rate='15',basis='input_kg',resin_rate='0',extras='0',hours='0',includes_resin=True):
    with localcontext() as ctx:
        ctx.prec=36
        good=decimal(good,positive=True); grams=decimal(grams,positive=True)
        y=decimal(yield_percent,positive=True)/100
        if y>1: raise BusinessError('Yield cannot exceed 100%.')
        rate=decimal(rate,nonnegative=True); price=decimal(price,positive=True)
        output=good*grams/1000; gross_input=output/y
        bases={'input_kg':gross_input,'good_output_kg':output,'pieces':good,'machine_hours':decimal(hours,nonnegative=True)}
        if basis not in bases: raise BusinessError('Unknown charge basis.')
        if basis=='machine_hours' and bases[basis]<=0: raise BusinessError('Machine hours are required.')
        factory=bases[basis]*rate+(0 if includes_resin else gross_input*decimal(resin_rate,nonnegative=True))+decimal(extras,nonnegative=True)
        net_price=price/(1+decimal(vat_rate,nonnegative=True)/100) if vat_inclusive else price
        mold=decimal(mold,nonnegative=True); paid=decimal(paid,nonnegative=True)
        if paid>mold+factory: raise BusinessError('Reported payment exceeds scenario outlay.')
        variable=factory/good; contribution=net_price-variable
        return {'good_units':good,'output_kg':output,'input_kg':gross_input,'factory_estimate':factory,'unit_factory_cost':variable,'mold_and_factory_outlay':mold+factory,'remaining_outlay':mold+factory-paid,'net_revenue':money(good*net_price),'revenue_less_factory':money(good*net_price-factory),'revenue_less_factory_and_mold':money(good*net_price-factory-mold),'first_batch_allocated_unit_cost':(mold+factory)/good,'contribution_break_even':(mold/contribution).to_integral_value(rounding=ROUND_CEILING) if contribution>0 else None,'cash_recovery_units':((mold+factory)/net_price).to_integral_value(rounding=ROUND_CEILING)}

def liquidity(cash,tax,commitments,operating,next_cycle,reserve,principal):
    values=[decimal(x,nonnegative=True) for x in (cash,tax,commitments,operating,next_cycle,reserve,principal)]
    available=max(Decimal(0),values[0]-sum(values[1:6]))
    return {'available':money(available),'repayment_proposal':money(min(available,values[6])),'distribution_enabled':False}
