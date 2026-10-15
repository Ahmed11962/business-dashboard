from datetime import date
from decimal import Decimal
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone
from core.finance import BusinessError
from core.models import (Product,Mold,ProductionBatch,SalesInvoice,InvoiceLine,StockEvent,
                         FinanceTransaction,CapitalContribution,Audit,WorkflowAttachment)
from core.manufacturing import (production_cost,batch_cost,balance,record_payment,receive,
    dispatch,return_goods,writeoff,invoice_total,manufacturing_totals,repayment_plan,distribution_plan,
    issue_credit,repay_capital,capital_outstanding,cash_forecast,invoice_revenue,performance_by_period)
from core.reports import verify_audit

pytestmark=pytest.mark.django_db(transaction=True)

def test_basket_end_to_end_with_cash_inventory_returns_and_planning(world,client):
    div,sayem,sami,_=world; today=timezone.localdate(); client.force_login(sayem)
    p=Product.objects.create(division=div,name='Plastic Basket',sku='BASKET-01',default_price='6.00')
    mold=Mold.objects.create(division=div,name='Plastic Basket Mold',code='MOLD-BASKET',product=p,
                             supplier='Synthetic mold supplier',purchase_date=today,price='20000',status='ordered')
    assert client.get(reverse('mfg_molds',args=[div.pk])).status_code==200
    pay_url=reverse('mfg_payment',args=[div.pk,'mold',mold.pk])
    assert client.post(pay_url,{'date':str(today),'amount':'10000','reference':'MOLD-PAY-1','method':'bank'}).status_code==302
    assert balance(mold)==Decimal('10000.00')
    assert client.post(pay_url,{'date':str(today),'amount':'10000','reference':'MOLD-PAY-2','method':'bank'}).status_code==302
    mold.ownership_confirmed=True; mold.status='delivered'; mold.save()
    assert balance(mold)==0
    batch=ProductionBatch.objects.create(division=div,number='BATCH-BASKET',mold=mold,manufacturer='Synthetic factory',
        order_date=today,quantity=5000,weight_grams='120',price_per_gram='0.02',other_cost='500',status='ordered')
    cost=batch_cost(batch)
    assert cost['material']==Decimal('12000.00') and cost['total']==Decimal('12500.00')
    assert client.post(reverse('mfg_payment',args=[div.pk,'batch',batch.pk]),
        {'date':str(today),'amount':'5000','reference':'BATCH-PAY-1','method':'bank'}).status_code==302
    assert balance(batch)==Decimal('7500.00')
    assert p.quantity==0
    event=receive(div,sayem,batch,5000,0,0,'DELIVERY-1')
    p.refresh_from_db(); assert p.quantity==5000 and p.inventory_value==Decimal('12500.00')
    assert event.value==Decimal('12500.00')
    invoice=SalesInvoice.objects.create(division=div,number='SALE-1',customer='Synthetic buyer',date=today)
    line=InvoiceLine.objects.create(invoice=invoice,product=p,quantity=1500,unit_price='6')
    assert invoice_total(invoice)==Decimal('9000.00')
    p.refresh_from_db(); assert p.quantity==5000  # issuing has no stock effect
    movement=dispatch(div,sayem,line,1500,'DISPATCH-1')
    p.refresh_from_db(); assert p.quantity==3500 and p.inventory_value==Decimal('8750.00')
    assert movement.value==Decimal('-3750.00')
    with pytest.raises(BusinessError): dispatch(div,sayem,line,1500,'DISPATCH-DUPLICATE')
    assert client.post(reverse('mfg_payment',args=[div.pk,'invoice',invoice.pk]),
        {'date':str(today),'amount':'3000','reference':'COLLECT-1','method':'bank'}).status_code==302
    assert balance(invoice)==Decimal('6000.00')
    totals=manufacturing_totals(div)
    assert totals['sales']==Decimal('9000.00') and totals['cogs']==Decimal('3750.00')
    assert totals['gross']==Decimal('5250.00') and totals['receivables']==Decimal('6000.00')
    assert totals['received']==Decimal('3000.00') and totals['paid']==Decimal('25000.00')
    assert FinanceTransaction.objects.filter(division=div).count()==4
    capital=client.post(reverse('mfg_finance_action',args=[div.pk,'capital']),
        {'date':str(today),'amount':'100000','reference':'CAP-1','contributor':'Synthetic contributor','funding_kind':'repayable','method':'bank'})
    assert capital.status_code==302
    totals=manufacturing_totals(div)
    assert totals['received']==Decimal('103000.00') and totals['sales']==Decimal('9000.00')
    assert totals['capital']==Decimal('100000.00') and CapitalContribution.objects.get(division=div).kind=='repayable'
    repayment=repayment_plan('100000','0',60)
    assert repayment['monthly']==Decimal('1666.67') and repayment['schedule'][-1]['remaining']==0
    distribution=distribution_plan('20000','20000',50)
    assert distribution['retained']==Decimal('10000.00') and distribution['sayem']==Decimal('5000.00') and distribution['sami']==Decimal('5000.00')
    forecast=cash_forecast('30000','10000','5000',3,'12500','1000')
    assert forecast['rows'][0]['balance']==Decimal('21500.00') and forecast['ending']==Decimal('29500.00')
    assert forecast['affordable']
    returned=return_goods(div,sayem,movement,50,'RETURN-1')
    p.refresh_from_db(); assert p.quantity==3550 and returned.value==Decimal('125.00')
    issue_credit(div,sayem,invoice,'300','CREDIT-1','50 returned baskets')
    assert invoice_total(invoice)==Decimal('8700.00') and balance(invoice)==Decimal('5700.00')
    writeoff(div,sayem,p,50,'DAMAGE-1','Synthetic damaged goods')
    p.refresh_from_db(); assert p.quantity==3500
    refund=FinanceTransaction.objects.get(reference='MOLD-PAY-1')
    record_payment(div,sayem,mold,'500','MOLD-REFUND-1',today,refund_of=refund)
    assert balance(mold)==Decimal('500.00')
    with pytest.raises(BusinessError): record_payment(div,sayem,mold,'500','MOLD-REFUND-1',today,refund_of=refund)
    contribution=CapitalContribution.objects.get(division=div)
    repay_capital(div,sayem,contribution,'20000','CAP-REPAY-1',today)
    assert capital_outstanding(contribution)==Decimal('80000.00')
    assert manufacturing_totals(div)['capital_repaid']==Decimal('20000.00')
    with pytest.raises(BusinessError): repay_capital(div,sayem,contribution,'80001','CAP-REPAY-2',today)
    assert client.post(reverse('mfg_finance_action',args=[div.pk,'classify']),
        {'contribution':str(contribution.pk),'contributor':'Synthetic contributor','funding_kind':'repayable','terms':'Synthetic agreement only'}).status_code==302
    assert client.post(reverse('mfg_finance_action',args=[div.pk,'repayment']),
        {'contribution':str(contribution.pk),'date':str(today),'amount':'1000','reference':'CAP-REPAY-3','method':'cash'}).status_code==302
    assert capital_outstanding(contribution)==Decimal('79000.00')
    assert client.get(reverse('mfg_finances',args=[div.pk])).status_code==200
    assert client.get(reverse('dashboard',args=[div.pk])).status_code==200
    forecast_page=client.post(reverse('mfg_calculators',args=[div.pk]),{'kind':'forecast','opening':'30000',
        'monthly_in':'10000','monthly_out':'5000','one_time':'12500','repayment':'1000','months':'3'})
    assert forecast_page.status_code==200 and b'29500.00' in forecast_page.content
    assert verify_audit(div)

def test_pages_attachments_permissions_and_persistence(world,client):
    div,sayem,sami,_=world; client.force_login(sayem)
    for name in ('dashboard','mfg_molds','mfg_batches','mfg_products','mfg_invoices','mfg_finances','mfg_calculators'):
        assert client.get(reverse(name,args=[div.pk])).status_code==200
    image=SimpleUploadedFile('basket.png',b'\x89PNG\r\n\x1a\nsynthetic',content_type='image/png')
    pdf=SimpleUploadedFile('quote.pdf',b'%PDF-1.4\nsynthetic',content_type='application/pdf')
    assert client.post(reverse('mfg_product_new',args=[div.pk]),{'name':'Basket','sku':'B-1','default_price':'6','notes':'',
        'image':image,'files':[pdf]}).status_code==302
    product=Product.objects.get(sku='B-1')
    assert product.image_id and WorkflowAttachment.objects.filter(product=product).count()==1
    doc=product.attachments.first().document
    assert client.get(reverse('download',args=[div.pk,doc.pk])).status_code==200
    assert client.get(reverse('simple_document_preview',args=[div.pk,product.image_id])).status_code==200
    assert client.get(reverse('mfg_product',args=[div.pk,product.pk])).status_code==200
    from django.contrib.auth.models import User
    from core.models import Membership
    reader=User.objects.create_user('mfg-reader@example.invalid',password='synthetic-password')
    Membership.objects.create(division=div,user=reader,role='reader')
    client.force_login(reader)
    assert client.get(reverse('mfg_products',args=[div.pk])).status_code==200
    assert client.post(reverse('mfg_product_new',args=[div.pk]),{'name':'Forbidden','sku':'NO','default_price':'1'}).status_code==400
    assert not Product.objects.filter(sku='NO').exists()
    product.refresh_from_db(); assert product.name=='Basket'  # persisted across requests

def test_cost_and_refund_guards(world):
    div,user,_,_=world; today=timezone.localdate()
    assert production_cost(5000,120,'0.02',500)['total']==Decimal('12500.00')
    p=Product.objects.create(division=div,name='Basket',sku='P',default_price='6')
    m=Mold.objects.create(division=div,name='M',code='M',product=p,purchase_date=today,price=20000)
    with pytest.raises(BusinessError): record_payment(div,user,m,20001,'TOO-MUCH',today)
    with pytest.raises(BusinessError): receive(div,user,ProductionBatch.objects.create(division=div,number='B',mold=m,
        order_date=today,quantity=5000,weight_grams=120,price_per_gram='0.02'),5001,0,0,'TOO-MANY')
    with pytest.raises(BusinessError): receive(div,user,ProductionBatch.objects.get(division=div,number='B'),'1.5',0,0,'FRACTIONAL')
    assert p.quantity==0

def test_click_through_forms_and_reports(world,client):
    div,user,_,_=world; client.force_login(user); today=str(timezone.localdate())
    def post(name,*args,data):
        response=client.post(reverse(name,args=[div.pk,*args]),data)
        assert response.status_code==302, (name,response.status_code,response.content.decode()[-500:])
    post('mfg_product_new',data={'name':'Container','sku':'CON-1','default_price':'5','notes':''})
    product=Product.objects.get(division=div,sku='CON-1')
    post('mfg_mold_new',data={'name':'Container Mold','code':'M-CON','product':str(product.pk),
        'supplier':'Synthetic Supplier','purchase_date':today,'price':'1000','status':'ordered','notes':''})
    mold=Mold.objects.get(division=div,code='M-CON')
    post('mfg_batch_new',data={'number':'B-CON','mold':str(mold.pk),'manufacturer':'Synthetic Factory',
        'order_date':today,'quantity':'100','weight_grams':'50','price_per_gram':'0.02',
        'setup_cost':'0','packaging_cost':'0','transport_cost':'0','other_cost':'0',
        'quoted_cost':'','final_cost':'','status':'ordered','notes':''})
    batch=ProductionBatch.objects.get(division=div,number='B-CON')
    receipt=SimpleUploadedFile('delivery.pdf',b'%PDF-1.4\nsynthetic',content_type='application/pdf')
    post('mfg_action','receive',batch.pk,data={'accepted':'100','rejected':'0','damaged':'0','reference':'DEL-CON','files':[receipt]})
    product.refresh_from_db(); assert product.quantity==100
    assert WorkflowAttachment.objects.filter(batch=batch).count()==1
    post('mfg_invoice_new',data={'number':'INV-CON','customer':'Synthetic Buyer','date':today,'due_date':'',
        'discount':'0','tax_treatment':'unconfirmed','tax':'0','notes':'','product':[str(product.pk)],'quantity':['20'],'unit_price':['5']})
    invoice=SalesInvoice.objects.get(division=div,number='INV-CON'); line=invoice.lines.first()
    post('mfg_action','dispatch',line.pk,data={'quantity':'20','reference':'SHIP-CON'})
    product.refresh_from_db(); assert product.quantity==80
    post('mfg_payment','invoice',invoice.pk,data={'date':today,'amount':'50','reference':'COL-CON','method':'bank'})
    assert balance(invoice)==Decimal('50.00')
    post('mfg_action','credit',invoice.pk,data={'amount':'10','reference':'CREDIT-CON','reason':'Price allowance'})
    assert balance(invoice)==Decimal('40.00')
    t=FinanceTransaction.objects.get(reference='COL-CON')
    assert client.post(reverse('simple_transaction_edit',args=[div.pk,t.pk]),{}).status_code==400
    pdf=SimpleUploadedFile('collection.pdf',b'%PDF-1.4\nsynthetic',content_type='application/pdf')
    post('simple_transaction_detail',t.pk,data={'files':[pdf]})
    assert t.attachments.count()==1
    for route in ('mfg_mold','mfg_batch','mfg_product','mfg_invoice'):
        obj={'mfg_mold':mold,'mfg_batch':batch,'mfg_product':product,'mfg_invoice':invoice}[route]
        assert client.get(reverse(route,args=[div.pk,obj.pk])).status_code==200
    assert client.get(reverse('mfg_invoice_pdf',args=[div.pk,invoice.pk])).status_code==200
    assert client.get(reverse('simple_reports',args=[div.pk])).status_code==200
    assert client.get(reverse('simple_export',args=[div.pk,'xlsx'])).status_code==200

def test_new_records_obey_nonowner_row_security(world):
    import os,subprocess,sys,uuid
    from pathlib import Path
    from urllib.parse import urlencode,quote
    from django.db import connection,transaction
    from django.contrib.auth.models import User
    div,user,_,_=world; today=timezone.localdate()
    p=Product.objects.create(division=div,name='Synthetic Item',sku='RLS-ITEM',default_price='5')
    m=Mold.objects.create(division=div,name='Synthetic Mold',code='RLS-MOLD',product=p,purchase_date=today,price=100)
    batch=ProductionBatch.objects.create(division=div,number='RLS-BATCH',mold=m,order_date=today,quantity=10,
        weight_grams=100,price_per_gram='0.01',status='ordered')
    invoice=SalesInvoice.objects.create(division=div,number='RLS-SALE',customer='Synthetic',date=today)
    line=InvoiceLine.objects.create(invoice=invoice,product=p,quantity=5,unit_price=5)
    outsider=User.objects.create_user('mfg-outsider@example.invalid')
    role='mfg_runtime_'+uuid.uuid4().hex[:10]
    params=connection.get_connection_params()
    source=f"postgresql://{quote(params.get('user',''))}@/{params['dbname']}?"+urlencode({'host':params.get('host',''),'port':params.get('port','5432')})
    env=os.environ.copy(); env.update(DATABASE_URL=source,APP_DB_ROLE=role,APP_DB_PASSWORD=uuid.uuid4().hex)
    script=Path(__file__).resolve().parent.parent/'scripts/provision_runtime_role.py'
    subprocess.run([sys.executable,str(script)],env=env,check=True,capture_output=True)
    updates=script.with_name('grant_runtime_updates.py')
    subprocess.run([sys.executable,str(updates)],env=env,check=True,capture_output=True)
    try:
        with transaction.atomic(),connection.cursor() as c:
            c.execute(f'SET LOCAL ROLE {role}')
            c.execute("SELECT set_config('app.user_id',%s,true)",[str(outsider.pk)])
            c.execute('SELECT count(*) FROM core_product'); assert c.fetchone()[0]==0
            c.execute('SELECT count(*) FROM core_stockevent'); assert c.fetchone()[0]==0
            c.execute("SELECT set_config('app.user_id',%s,true)",[str(user.pk)])
            receive(div,user,batch,10,0,0,'RLS-RECEIPT')
            dispatch(div,user,line,5,'RLS-DISPATCH')
            c.execute('SELECT count(*) FROM core_stockevent'); assert c.fetchone()[0]==2
        p.refresh_from_db(); assert p.quantity==5
    finally:
        with connection.cursor() as c: c.execute(f'DROP OWNED BY {role}'); c.execute(f'DROP ROLE {role}')

def test_invoice_tax_is_cash_due_but_not_sales_revenue(world):
    div,user,_,_=world; today=timezone.localdate()
    p=Product.objects.create(division=div,name='Tax example',sku='TAX-1')
    invoice=SalesInvoice.objects.create(division=div,number='TAX-INVOICE',customer='Synthetic buyer',
        date=today,tax_treatment='standard',tax='15')
    InvoiceLine.objects.create(invoice=invoice,product=p,quantity=10,unit_price='10')
    assert invoice_total(invoice)==Decimal('115.00')
    assert invoice_revenue(invoice)==Decimal('100.00')
    issue_credit(div,user,invoice,'11.50','TAX-CREDIT','One unit allowance','1.50')
    assert invoice_total(invoice)==Decimal('103.50')
    assert invoice_revenue(invoice)==Decimal('90.00')
    assert manufacturing_totals(div)['sales']==Decimal('90.00')
    period=performance_by_period(div)['months'][0][1]
    assert period['sales']==Decimal('90.00') and period['profit']==Decimal('90.00')

def test_synthetic_install_is_repeatable_and_never_seeds_live():
    from django.core.management import call_command
    from core.seed import seed
    demo=seed(True); live=seed(False)
    call_command('seed_manufacturing_sample',verbosity=0)
    assert Product.objects.filter(division=demo,sku='SYN-BASKET-01').count()==1
    assert Product.objects.filter(division=live).count()==0
    assert FinanceTransaction.objects.filter(division=demo).count()==5
    assert FinanceTransaction.objects.filter(division=live).count()==0
    call_command('seed_manufacturing_sample',verbosity=0)
    assert Product.objects.filter(division=demo,sku='SYN-BASKET-01').count()==1
    assert FinanceTransaction.objects.filter(division=demo).count()==5
