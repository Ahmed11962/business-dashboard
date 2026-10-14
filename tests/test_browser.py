"""Real Chromium, two independent sessions, all controlled actions through CSRF-protected forms."""
import json,shutil,time,uuid
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import pytest,pyotp
from django.utils import timezone
from django.urls import reverse
from core.models import *
from core import reports
from .conftest import payload
pytestmark=pytest.mark.django_db(transaction=True)

def test_two_operator_browser_workflow(world,live_server):
    from playwright.sync_api import sync_playwright,expect
    binary=shutil.which('chromium')
    if not binary: pytest.skip('Install Chromium to run the real-browser acceptance test.')
    d,a,b,doc=world
    secrets={u.pk:pyotp.random_base32() for u in (a,b)}
    for u in (a,b): AuthFactor.objects.create(user=u,secret=secrets[u.pk],enabled=True)
    base=live_server.url
    def dbcall(fn):
        from django.db import close_old_connections
        def isolated():
            close_old_connections()
            try: return fn()
            finally: close_old_connections()
        with ThreadPoolExecutor(max_workers=1) as pool: return pool.submit(isolated).result()
    with sync_playwright() as pw:
        browser=pw.chromium.launch(executable_path=binary,args=['--no-sandbox'])
        contexts=[browser.new_context(viewport={'width':1440,'height':1100}) for _ in range(2)]
        pages=[c.new_page() for c in contexts]
        codes={}
        for p,u in zip(pages,(a,b)):
            p.goto(base+'/login/'); p.locator('[name=username]').fill(u.username); p.locator('[name=password]').fill('synthetic-test-password')
            code=pyotp.TOTP(secrets[u.pk]).now(); codes[u.pk]=code; p.locator('[name=code]').fill(code); p.get_by_role('button',name='Sign in').click(); expect(p.get_by_role('heading',name='Choose a workspace')).to_be_visible()
        # TOTP is one-use; wait for a genuinely new code rather than weakening replay protections.
        while any(pyotp.TOTP(secrets[u.pk]).now()==codes[u.pk] for u in (a,b)): time.sleep(.3)
        for p,u in zip(pages,(a,b)):
            p.goto(base+'/security/reauth/'); p.locator('[name=password]').fill('synthetic-test-password'); p.locator('[name=code]').fill(pyotp.TOTP(secrets[u.pk]).now()); p.get_by_role('button',name='Verify for signing').click(); expect(p.get_by_role('heading',name='Choose a workspace')).to_be_visible()
        first,second=pages
        def action(kind,**extra):
            data=payload(**extra); first.goto(base+reverse('decision_new',args=[d.pk])+'?kind='+kind)
            first.locator('[name=title]').fill('Browser test '+kind)
            for key,value in data.items(): first.locator('[name="'+key+'"]').fill(str(value))
            first.get_by_role('button',name='Save draft').click(); decision_url=first.url
            first.get_by_role('button',name='Submit for joint approval').click()
            first.get_by_label('I approve this exact version, its conditions and document hashes.').check(); first.get_by_role('button',name='Sign this version').click()
            second.goto(decision_url); second.get_by_label('I approve this exact version, its conditions and document hashes.').check(); second.get_by_role('button',name='Sign this version').click()
            first.goto(decision_url); first.get_by_label('I verified the execution conditions and actual event evidence.').check(); first.get_by_role('button',name='Record execution',exact=True).click()
            expect(first.get_by_role('heading',name='Execution result')).to_be_visible()
            dec_id=decision_url.rstrip('/').split('/')[-1]; return dbcall(lambda:Execution.objects.get(decision_id=dec_id))
        po=action('purchase_order',party='Synthetic factory',quantity='100000',sku='FLW-001',amount='36900',due_date=str(timezone.localdate()))
        prod=action('production_release',purchase_order_id=po.result['record_id'],party='Synthetic factory',sku='FLW-001',quantity='100000',mold='Synthetic mold',rate='4.50',charge_basis='input_kg',material_ownership='factory')
        receipt=action('goods_receipt',production_id=prod.result['record_id'],sku='FLW-001',location='Test warehouse',lot='BROWSER-TEST',quantity='100000',amount='36900')
        action('quality_release',stock_id=receipt.result['stock_id'],accepted_quantity='100000',inspection='Synthetic acceptance passed')
        action('supplier_bill',receipt_id=receipt.result['receipt_id'],party='Synthetic factory',amount='36900',due_date=str(timezone.localdate()),beneficiary='TEST-FACTORY')
        order=action('sales_order',stock_id=receipt.result['stock_id'],party='Synthetic customer',quantity='1000',unit_price='2',vat_rate='0',due_date=str(timezone.localdate()))
        sale=action('delivery',order_id=order.result['order_id'],quantity='1000')
        action('customer_invoice',delivery_id=sale.result['delivery_id'])
        action('collection',item_id=sale.result['item_id'],amount='1000',evidence_id=str(doc.pk))
        first.goto(base+reverse('bank_import',args=[d.pk])); first.locator('[name=account_reference]').fill('TEST-DIVISION')
        first.locator('[name=file]').set_input_files({'name':'test-statement.csv','mimeType':'text/csv','buffer':f'external_id,date,amount,memo\nBROWSER-1,{timezone.localdate()},1000,Synthetic collection\n'.encode()})
        first.get_by_role('button',name='Import & deduplicate').click(); first.get_by_role('button',name='Match',exact=True).click()
        result=dbcall(lambda:reports.report(d))
        assert result['unreconciled']==0 and all(result['ties'].values())
        assert result['revenue']==2000 and result['gross_profit']==1631
        assert dbcall(lambda:Signature.objects.count())==18 and dbcall(lambda:Execution.objects.count())==9
        first.goto(base+reverse('dashboard',args=[d.pk])); expect(first.get_by_role('heading',name='Business overview')).to_be_visible()
        shots=Path(__file__).resolve().parent.parent/'docs'/'screenshots'; shots.mkdir(exist_ok=True)
        first.screenshot(path=str(shots/'desktop-test-workspace.png'),full_page=True)
        first.set_viewport_size({'width':390,'height':844}); first.screenshot(path=str(shots/'mobile-test-workspace.png'),full_page=True)
        assert first.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
        browser.close()
