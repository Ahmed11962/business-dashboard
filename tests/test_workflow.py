import uuid
from decimal import Decimal
import pytest
from django.db import transaction,DatabaseError,IntegrityError,connection
from django.utils import timezone
from core import services,reports
from core.finance import BusinessError
from core.models import *
from .conftest import authorize,perform,payload
pytestmark=pytest.mark.django_db(transaction=True)

def test_unverified_seeds_do_not_post(world):
    d,*_=world
    assert Journal.objects.count()==0 and Stock.objects.count()==0
    assert reports.report(d)['cash'] is None
    assert not Record.objects.filter(division=d,kind='funding_draft').exists()
    assert not Record.objects.filter(division=d,kind='commitment').exists()
    assert reports.forecast(d)[0]['ending_cash'] is None

def test_direct_funding_and_duplicate_source(world):
    d,a,b,doc=world
    ex=perform(world,'funding_direct',amount='10000',party='Test funder',classification='loan',evidence_id=str(doc.pk))
    assert services.balance(d,'supplier_advance')==10000
    assert services.balance(d,'funding_loan')==-10000
    assert services.balance(d,'bank')==0
    p=ex.version.payload.copy(); p['document_ids']=[]
    second=services.draft_decision(d,a,'Duplicate source','funding_direct',p)
    services.transition(d,a,second.pk,1,'submit'); v=second.versions.get(number=1)
    services.sign(d,a,second.pk,1,v.digest,'a'); services.sign(d,b,second.pk,1,v.digest,'b')
    with pytest.raises(IntegrityError): services.execute(d,a,second.pk,1,'duplicate-source')
    assert Journal.objects.count()==1

def test_delivery_invoice_partial_collection_once(world,sold):
    d,a,b,doc=world
    assert services.balance(d,'revenue')==-2000
    assert services.balance(d,'cogs')==369
    assert services.balance(d,'inventory')==36531
    invoice=perform(world,'customer_invoice',delivery_id=sold.result['delivery_id'])
    assert services.balance(d,'revenue')==-2000 and services.balance(d,'cogs')==369
    with pytest.raises(BusinessError): perform(world,'customer_invoice',delivery_id=sold.result['delivery_id'])
    ex=perform(world,'collection',item_id=sold.result['item_id'],amount='700',evidence_id=str(doc.pk))
    assert services.balance(d,'bank')==700 and services.balance(d,'receivable')==1300
    assert services.execute(d,a,ex.decision_id,1,ex.idempotency_key).pk==ex.pk
    assert services.balance(d,'bank')==700
    assert all(reports.report(d)['ties'].values())

def test_partial_bills_and_exact_payment_beneficiary(world,batch):
    d,a,b,doc=world
    perform(world,'funding_cash',amount='50000',party='Test funder',classification='loan',evidence_id=str(doc.pk))
    bill=perform(world,'supplier_bill',receipt_id=batch.result['receipt_id'],party='Test factory',amount='10000',due_date=str(timezone.localdate()),beneficiary='TEST-IBAN-A')
    with pytest.raises(BusinessError): perform(world,'supplier_payment',item_id=bill.result['item_id'],amount='5000',beneficiary='TEST-IBAN-B',evidence_id=str(doc.pk))
    perform(world,'supplier_payment',item_id=bill.result['item_id'],amount='5000',beneficiary='TEST-IBAN-A',evidence_id=str(doc.pk))
    assert services.balance(d,'bank')==45000 and services.balance(d,'payable')==-5000
    assert services.balance(d,'goods_received_unbilled')==-26900
    assert all(reports.report(d)['ties'].values())

def test_returns_refunds_and_quarantine(world,sold):
    d,a,b,doc=world
    perform(world,'collection',item_id=sold.result['item_id'],amount='2000',evidence_id=str(doc.pk))
    ret=perform(world,'customer_return',delivery_id=sold.result['delivery_id'],quantity='100',inspection='Synthetic return inspection pending')
    assert ret.result['credit']=='200.00'
    assert services.balance(d,'revenue')==-1800 and services.balance(d,'cogs')==Decimal('332.10')
    s=Stock.objects.get(lot__startswith='return-')
    assert s.status=='quarantined'
    with pytest.raises(Stock.DoesNotExist): perform(world,'sales_order',stock_id=str(s.pk),party='Test customer',quantity='1',unit_price='2',vat_rate='0',due_date=str(timezone.localdate()))
    perform(world,'customer_refund',return_id=ret.result['return_id'],amount='200',beneficiary='TEST-CUSTOMER',evidence_id=str(doc.pk))
    assert services.balance(d,'customer_credit')==0 and services.balance(d,'bank')==1800
    assert all(reports.report(d)['ties'].values())

def test_rejects_and_negative_stock(world):
    d,a,b,doc=world
    po=perform(world,'purchase_order',party='Test factory',sku='A',quantity='100',amount='100',due_date=str(timezone.localdate()))
    prod=perform(world,'production_release',purchase_order_id=po.result['record_id'],party='Test factory',sku='A',quantity='100',mold='TEST',rate='1',charge_basis='pieces',material_ownership='factory')
    rec=perform(world,'goods_receipt',production_id=prod.result['record_id'],sku='A',location='Test',lot='L',quantity='100',amount='100')
    perform(world,'quality_release',stock_id=rec.result['stock_id'],accepted_quantity='95',inspection='5 defective')
    assert services.balance(d,'abnormal_waste')==5
    with pytest.raises(BusinessError): perform(world,'sales_order',stock_id=rec.result['stock_id'],party='Test',quantity='96',unit_price='2',vat_rate='0',due_date=str(timezone.localdate()))
    assert all(reports.report(d)['ties'].values())

def test_repayment_principal_not_profit(world):
    d,a,b,doc=world
    perform(world,'funding_cash',amount='10000',party='Test funder',classification='loan',evidence_id=str(doc.pk))
    perform(world,'repayment',amount='2000',beneficiary='Test funder',evidence_id=str(doc.pk),counterparty_consent='Synthetic written agreement')
    assert services.balance(d,'bank')==8000 and services.balance(d,'funding_loan')==-8000
    assert reports.report(d)['operating_result']==0
    with pytest.raises(BusinessError): perform(world,'journal',lines=[{'account':'compensation','debit':'100'},{'account':'bank','credit':'100'}],reason='Unapproved structure')

def test_reversal_closed_period_and_db_immutability(world):
    d,a,b,doc=world
    ex=perform(world,'funding_direct',amount='10000',party='Test',classification='loan',evidence_id=str(doc.pk))
    j=Journal.objects.get(pk=ex.result['journal_id'])
    with pytest.raises(DatabaseError),transaction.atomic(): Journal.objects.filter(pk=j.pk).update(description='edited')
    with pytest.raises(DatabaseError),transaction.atomic(): Line.objects.create(journal=j,account='bank',debit=100)
    perform(world,'reversal',journal_id=str(j.pk),reason='Synthetic correction')
    assert services.balance(d,'supplier_advance')==0 and Journal.objects.count()==2
    perform(world,'close_period',through=str(timezone.localdate()))
    with pytest.raises(BusinessError): perform(world,'funding_direct',amount='1',party='Test',classification='loan',evidence_id=str(doc.pk))
    assert Journal.objects.count()==2

def test_bank_dedup_and_matching(world,sold):
    d,a,b,doc=world
    perform(world,'collection',item_id=sold.result['item_id'],amount='700',evidence_id=str(doc.pk))
    content=f'external_id,date,amount,memo\nROW-1,{timezone.localdate()},700,Test receipt\n'
    assert services.import_bank(d,a,content,'division-allocation')['inserted']==1
    assert services.import_bank(d,a,content,'division-allocation')['duplicates']==1
    row=BankRow.objects.get(); line=Line.objects.get(account='bank')
    services.match_bank(d,a,row.pk,line.pk)
    assert reports.report(d)['unreconciled']==0
    with pytest.raises(BusinessError): services.import_bank(d,a,content.replace('700','701'),'division-allocation')
    assert reports.verify_audit(d)

def test_live_execution_blocked(world):
    d,a,b,doc=world; d.is_demo=False; d.save(update_fields=['is_demo'])
    with pytest.raises(BusinessError,match='Live execution is locked'):
        perform(world,'funding_direct',amount='10000',party='Test',classification='loan',evidence_id=str(doc.pk))

def test_nested_request_transactions_allow_initial_lines_only(world):
    d,a,b,doc=world
    with transaction.atomic():
        with transaction.atomic():
            ex=perform(world,'funding_direct',amount='10000',party='Test',classification='loan',evidence_id=str(doc.pk))
    j=Journal.objects.get(pk=ex.result['journal_id'])
    assert j.lines.count()==2
    with pytest.raises(DatabaseError),transaction.atomic(): Line.objects.create(journal=j,account='bank',debit=1)

def test_deposit_is_liability_then_applied_without_duplicate_revenue(world,sold):
    d,a,b,doc=world
    deposit=perform(world,'customer_deposit',party='Test customer',amount='500',evidence_id=str(doc.pk))
    assert services.balance(d,'customer_deposit')==-500 and services.balance(d,'bank')==500
    perform(world,'apply_deposit',deposit_id=deposit.result['deposit_id'],item_id=sold.result['item_id'],amount='300')
    assert services.balance(d,'customer_deposit')==-200 and services.balance(d,'receivable')==1700
    assert services.balance(d,'revenue')==-2000
    assert all(reports.report(d)['ties'].values())

def test_management_statements_reconcile(world,sold):
    d,a,b,doc=world
    perform(world,'collection',item_id=sold.result['item_id'],amount='500',evidence_id=str(doc.pk))
    r=reports.statements(d)
    assert r['position_balances']
    assert r['cashflow']['operating']==500
    assert sum(x['gross_profit'] for x in r['batches'])==reports.report(d)['gross_profit']
    assert len(r['commitments'])==1

def test_supplier_advance_refund_and_mold_asset_not_double_expensed(world):
    d,a,b,doc=world
    perform(world,'funding_cash',amount='20000',party='Test funder',classification='loan',evidence_id=str(doc.pk))
    perform(world,'supplier_advance',party='Test mold supplier',amount='10000',beneficiary='Test supplier',evidence_id=str(doc.pk))
    perform(world,'supplier_refund',party='Test mold supplier',amount='1000',evidence_id=str(doc.pk))
    assert services.balance(d,'supplier_advance')==9000 and services.balance(d,'bank')==11000
    mold=Record.objects.create(division=d,kind='mold',title='Synthetic mold',source_status='synthetic')
    perform(world,'mold_acceptance',amount='9000',inspection='Synthetic mold accepted',mold_id=str(mold.pk))
    assert services.balance(d,'mold_asset')==9000 and reports.report(d)['operating_result']==0
    perform(world,'depreciation',amount='100',mold_id=str(mold.pk),policy='Synthetic reviewed policy',allocation='operating')
    assert reports.report(d)['operating_result']==-100
    assert reports.statements(d)['position_balances']

def test_unauthorized_db_posting_and_unbalanced_commit_rejected(world):
    d,a,b,doc=world
    decision=services.draft_decision(d,a,'Unapproved','resolution',payload(terms='Test'))
    with pytest.raises(DatabaseError),transaction.atomic():
        Journal.objects.create(division=d,decision=decision,reference='bad',description='bad',date=timezone.localdate())
    approved=authorize(world,'journal',lines=[{'account':'bank','debit':'1'},{'account':'equity','credit':'1'}],reason='Synthetic balance')
    with pytest.raises(DatabaseError),transaction.atomic():
        j=Journal.objects.create(division=d,decision=approved,reference='unbalanced',description='bad',date=timezone.localdate())
        Line.objects.create(journal=j,account='bank',debit=1)
    assert Journal.objects.count()==0
