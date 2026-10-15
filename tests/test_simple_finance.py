from decimal import Decimal
import io,time
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone
from core.models import FinanceTransaction,DocumentLink,SimpleDecision,DecisionVote,TransactionRevision,CashOpening,Audit
from core.simple_finance import calculate_scenario,summary,outstanding,account_balances
from core.seed import seed
from core.models import Membership
pytestmark=pytest.mark.django_db(transaction=True)

def payment_data(**overrides):
    data={'date':str(timezone.localdate()),'direction':'paid','amount':'200.00','total_due':'500.00','category':'Materials','description':'Synthetic supply bill','party':'','method':'bank','reference':'SIMPLE-1','notes':'Test only','treatment':'expense','settles':'','refund_of':'','decision':''}
    data.update(overrides); return data

def test_calculator_has_correct_profit_break_even_and_no_possible_break_even():
    r=calculate_scenario('1000','2.50','5','1000','500')
    assert r=={'sales':Decimal('5000.00'),'production_cost':Decimal('2500.00'),'fixed_cost':Decimal('1500.00'),'gross_profit':Decimal('2500.00'),'gross_margin_percent':Decimal('50.00'),'projected_profit':Decimal('1000.00'),'break_even_units':600,'roi_percent':Decimal('25.00')}
    assert calculate_scenario('100','6','5','100')['break_even_units'] is None

def test_transaction_partial_refund_duplicate_edit_attachments_and_export(world,client):
    div,first,second,_=world; client.force_login(first)
    pdf=SimpleUploadedFile('receipt.pdf',b'%PDF-1.4\nsynthetic',content_type='application/pdf')
    png=SimpleUploadedFile('photo.png',b'\x89PNG\r\n\x1a\nsynthetic',content_type='image/png')
    url=reverse('simple_transaction_new',args=[div.pk])
    response=client.post(url,{**payment_data(),'files':[pdf,png]})
    assert response.status_code==302, response.context.get("error") if response.context else response.content.decode()[-1000:]
    entry=FinanceTransaction.objects.get(reference='SIMPLE-1')
    assert entry.party=='' and entry.recognized_amount==Decimal('500.00')
    assert DocumentLink.objects.filter(transaction=entry).count()==2
    assert summary(div)['payable']==Decimal('300.00')
    assert client.post(url,payment_data()).status_code==400  # same reference cannot duplicate
    pay=payment_data(reference='SIMPLE-2',amount='100',total_due='',description='Part payment',settles=str(entry.pk),treatment='none')
    assert client.post(url,pay).status_code==302
    assert outstanding(entry)==Decimal('200.00')
    refund=payment_data(reference='SIMPLE-3',direction='received',amount='50',total_due='',description='Supplier refund',refund_of=str(entry.pk),treatment='none')
    assert client.post(url,refund).status_code==302
    assert outstanding(entry)==Decimal('250.00')
    r=summary(div)
    assert r['paid']==Decimal('300.00') and r['received']==Decimal('50.00')
    assert r['expenses']==Decimal('450.00') and r['profit']==Decimal('-450.00')
    assert r['categories']==[('Materials',Decimal('250.00'))]
    changed=payment_data(description='Corrected bill',notes='Corrected note')
    assert client.post(reverse('simple_transaction_edit',args=[div.pk,entry.pk]),changed).status_code==302
    assert TransactionRevision.objects.filter(transaction=entry).count()==2
    assert client.get(reverse('simple_transaction_detail',args=[div.pk,entry.pk])).status_code==200
    assert client.get(reverse('download',args=[div.pk,entry.attachments.first().document_id])).status_code==200
    assert client.get(reverse('simple_document_preview',args=[div.pk,entry.attachments.first().document_id])).status_code==200
    for kind in ('csv','xlsx','pdf'):
        response=client.get(reverse('simple_export',args=[div.pk,kind]))
        assert response.status_code==200
        content=b''.join(response.streaming_content) if response.streaming else response.content
        assert len(content)>100
    assert Audit.objects.filter(division=div,event='simple_transaction.updated').exists()

def test_six_pages_permissions_opening_and_approval(world,client):
    div,a,b,_=world; client.force_login(a)
    for name in ('dashboard','simple_transactions','simple_calculator','simple_decisions','simple_documents','simple_reports'):
        assert client.get(reverse(name,args=[div.pk])).status_code==200
    assert client.post(reverse('simple_opening_balance',args=[div.pk]),{'method':'bank','amount':'1000.00','as_of':str(timezone.localdate())}).status_code==302
    assert account_balances(div)['bank']==Decimal('1000.00')
    assert client.post(reverse('simple_opening_balance',args=[div.pk]),{'method':'bank','amount':'999.00','as_of':str(timezone.localdate())}).status_code==400
    decision={'title':'Buy sample equipment','description':'Synthetic proposal','estimated_cost':'500','expected_benefit':'Lower unit cost','risks':'Delay','scenario':'','required_approvals':'2'}
    assert client.post(reverse('simple_decision_new',args=[div.pk]),decision).status_code==302
    d=SimpleDecision.objects.get(title='Buy sample equipment')
    action=reverse('simple_decision_action',args=[div.pk,d.pk])
    assert client.post(action,{'action':'approve'}).status_code==400  # recent MFA required
    session=client.session; session['reauth_at']=time.time(); session['auth_event']='test-a'; session.save()
    assert client.post(action,{'action':'approve'}).status_code==302
    assert client.post(action,{'action':'approve'}).status_code==400  # same person cannot vote twice
    client.force_login(b)
    session=client.session; session['reauth_at']=time.time(); session['auth_event']='test-b'; session.save()
    assert client.post(action,{'action':'approve'}).status_code==302
    d.refresh_from_db(); assert d.status=='approved' and DecisionVote.objects.filter(decision=d).count()==2
    assert client.post(action,{'action':'comment','text':'Reviewed'}).status_code==302
    assert client.get(reverse('simple_decision_detail',args=[div.pk,d.pk])).status_code==200
    other=seed(False)
    assert client.get(reverse('simple_decision_detail',args=[other.pk,d.pk])).status_code in (400,403,404)

def test_simple_sample_is_repeatable_and_stays_in_test_workspace():
    from django.core.management import call_command
    from core.models import SavedScenario,Document
    live=seed(False); demo=seed(True)
    call_command('seed_simple_sample',verbosity=0)
    assert FinanceTransaction.objects.filter(division=demo).count()==4
    assert FinanceTransaction.objects.filter(division=live).count()==0
    assert SavedScenario.objects.filter(division=demo).count()==1
    assert SimpleDecision.objects.filter(division=demo,status='approved').count()==1
    assert summary(demo)['payable']==Decimal('200.00')
    assert summary(demo)['receivable']==Decimal('500.00')
    call_command('seed_simple_sample',verbosity=0)
    assert FinanceTransaction.objects.filter(division=demo).count()==4

def test_document_search_upload_validation_and_reader_permissions(world,client):
    from django.contrib.auth.models import User
    from core.models import Document
    div,a,_,_=world; client.force_login(a)
    url=reverse('simple_documents',args=[div.pk])
    good=SimpleUploadedFile('quote.pdf',b'%PDF-1.4\nSYNTHETIC',content_type='application/pdf')
    assert client.post(url,{'category':'Quote','supplier':'Synthetic supplier','reference':'QUOTE-1','files':[good]}).status_code==302
    doc=Document.objects.get(name='quote.pdf')
    assert b'quote.pdf' in client.get(url+'?q=QUOTE-1').content
    assert client.get(reverse('simple_document_preview',args=[div.pk,doc.pk])).status_code==200
    bad=SimpleUploadedFile('bad.pdf',b'not a PDF',content_type='application/pdf')
    assert client.post(url,{'files':[bad]}).status_code==400
    assert not Document.objects.filter(name='bad.pdf').exists()
    reader=User.objects.create_user('reader@example.invalid',password='synthetic-test-password')
    Membership.objects.create(division=div,user=reader,role='reader')
    client.force_login(reader)
    assert client.get(url).status_code==200
    assert client.post(reverse('simple_transaction_new',args=[div.pk]),payment_data()).status_code==400
    assert client.post(url,{'files':[SimpleUploadedFile('quote2.pdf',b'%PDF-1.4\nsynthetic',content_type='application/pdf')]}).status_code==400
