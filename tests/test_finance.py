from decimal import Decimal
import pytest
from core.finance import *

def test_reference_exact():
    s=scenario()
    assert s['output_kg']==Decimal('8200')
    assert s['factory_estimate']==Decimal('36900')
    assert s['unit_factory_cost']==Decimal('.369')
    assert s['mold_and_factory_outlay']==Decimal('56900')
    assert s['remaining_outlay']==Decimal('46900')
    assert s['net_revenue']==Decimal('200000')
    assert s['revenue_less_factory']==Decimal('163100')
    assert s['revenue_less_factory_and_mold']==Decimal('143100')
    assert s['first_batch_allocated_unit_cost']==Decimal('.569')
    assert s['contribution_break_even']==12263
    assert s['cash_recovery_units']==28450
    s=scenario(price='2.5')
    assert s['net_revenue']==250000 and s['revenue_less_factory']==213100
    assert s['revenue_less_factory_and_mold']==193100
    assert s['contribution_break_even']==9386 and s['cash_recovery_units']==22760

def test_yield_and_charge_basis():
    assert money(scenario(yield_percent='95')['factory_estimate'])==Decimal('38842.11')
    assert scenario(yield_percent='95',basis='good_output_kg')['factory_estimate']==36900
    assert scenario(basis='pieces',rate='.02')['factory_estimate']==2000
    assert scenario(basis='machine_hours',rate='100',hours='10')['factory_estimate']==1000
    assert scenario(includes_resin=False,resin_rate='2')['factory_estimate']==53300

def test_total_level_vat_rounding():
    assert split_vat('200000')=={'gross':Decimal('200000'),'net':Decimal('173913.04'),'vat':Decimal('26086.96')}
    assert scenario(price='2.5',vat_inclusive=True)['net_revenue']==Decimal('217391.30')
    assert money('1.005')==Decimal('1.01')

@pytest.mark.parametrize('kwargs',[{'yield_percent':'0'},{'yield_percent':'101'},{'rate':float('nan')},{'price':'NaN'},{'basis':'machine_hours','hours':'0'}])
def test_invalid_financial_inputs(kwargs):
    with pytest.raises(BusinessError): scenario(**kwargs)

def test_repayment_proposal_is_not_distribution():
    assert liquidity('10000','1000','2000','1000','3000','2000','5000')=={'available':Decimal('1000'),'repayment_proposal':Decimal('1000'),'distribution_enabled':False}
