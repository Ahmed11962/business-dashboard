import uuid
from concurrent.futures import ThreadPoolExecutor
import pytest
from django.db import close_old_connections,transaction,DatabaseError
from django.contrib.auth.models import User
from django.utils import timezone
from core.models import *
from core import services
from core.finance import BusinessError
from .conftest import payload,authorize,perform
pytestmark=pytest.mark.django_db(transaction=True)

def draft(world):
    d,a,b,doc=world
    return services.draft_decision(d,a,'Synthetic payment','funding_direct',payload(amount='10000',party='Test funder',classification='loan',evidence_id=str(doc.pk)))

def test_one_partner_duplicate_and_stale(world):
    d,a,b,_=world; decision=draft(world); v=decision.versions.get(number=1)
    services.transition(d,a,decision.pk,1,'submit')
    services.sign(d,a,decision.pk,1,v.digest,'fresh-auth')
    with pytest.raises(BusinessError): services.execute(d,a,decision.pk,1,'one-signature')
    with pytest.raises(BusinessError): services.sign(d,a,decision.pk,1,v.digest,'fresh-auth')
    with pytest.raises(BusinessError): services.sign(d,b,decision.pk,2,v.digest,'fresh-auth')
    with pytest.raises(BusinessError): services.sign(d,b,decision.pk,1,'wrong-hash','fresh-auth')
    assert Execution.objects.count()==0 and Journal.objects.count()==0

@pytest.mark.parametrize('field,value',[('amount','11000'),('beneficiary','Changed bank'),('conditions','Changed terms')])
def test_material_edits_create_new_unsigned_version(world,field,value):
    d,a,b,doc=world; dec=authorize(world,'funding_direct',amount='10000',party='Test',classification='loan',evidence_id=str(doc.pk)); v=dec.versions.get(number=1)
    p=v.payload.copy(); p[field]=value
    services.draft_decision(d,a,dec.title,dec.kind,p,dec.pk)
    dec.refresh_from_db(); assert dec.current_version==2 and dec.status=='draft'
    assert v.signatures.count()==2 and dec.versions.get(number=2).signatures.count()==0
    with pytest.raises(BusinessError): services.execute(d,a,dec.pk,1,'stale')
    with pytest.raises(BusinessError): services.execute(d,a,dec.pk,2,'unsigned')

def test_document_replacement_requires_new_signatures(world):
    d,a,b,doc=world; dec=authorize(world,'funding_direct',amount='10000',party='Test',classification='loan',evidence_id=str(doc.pk)); v=dec.versions.get(number=1)
    new=services.upload(d,a,'changed.txt','text/plain',b'Changed bytes',str(doc.pk))
    p=v.payload.copy(); p['evidence_id']=str(new.pk)
    services.draft_decision(d,a,dec.title,dec.kind,p,dec.pk)
    assert dec.versions.get(number=2).digest!=v.digest and v.signatures.count()==2
    with pytest.raises(DatabaseError),transaction.atomic(): Document.objects.filter(pk=doc.pk).update(content=b'tampered')
    with pytest.raises(DatabaseError),transaction.atomic(): Signature.objects.filter(version=v).delete()

def test_concurrent_signatures_and_duplicate_execution(world):
    d,a,b,_=world; dec=draft(world); v=dec.versions.get(number=1); services.transition(d,a,dec.pk,1,'submit')
    def signer(uid):
        close_old_connections()
        try: return services.sign(Division.objects.get(pk=d.pk),User.objects.get(pk=uid),dec.pk,1,v.digest,'concurrent-auth').status
        finally: close_old_connections()
    with ThreadPoolExecutor(max_workers=2) as pool: results=list(pool.map(signer,[a.pk,b.pk]))
    assert set(results)=={'one_signature','authorized'}
    def executor(_):
        close_old_connections()
        try: return services.execute(Division.objects.get(pk=d.pk),User.objects.get(pk=a.pk),dec.pk,1,'same-execution').pk
        finally: close_old_connections()
    with ThreadPoolExecutor(max_workers=4) as pool: results=list(pool.map(executor,range(4)))
    assert len(set(results))==1 and Journal.objects.count()==1 and Execution.objects.count()==1

def test_concurrent_reservations_do_not_oversell(world,batch):
    d,a,b,_=world
    extra=dict(stock_id=batch.result['stock_id'],party='Test',quantity='60000',unit_price='2',vat_rate='0',due_date=str(timezone.localdate()))
    first=authorize(world,'sales_order',**extra); second=authorize(world,'sales_order',**extra)
    def reserve(pk):
        close_old_connections()
        try:
            services.execute(Division.objects.get(pk=d.pk),User.objects.get(pk=a.pk),pk,1,str(pk)); return 'ok'
        except BusinessError: return 'blocked'
        finally: close_old_connections()
    with ThreadPoolExecutor(max_workers=2) as pool: results=list(pool.map(reserve,[first.pk,second.pk]))
    assert sorted(results)==['blocked','ok']
    assert Stock.objects.get(pk=batch.result['stock_id']).reserved==60000

def test_admin_no_approval_authority(world):
    d,a,b,_=world; admin=User.objects.create_superuser('admin@example.invalid',password='synthetic-password')
    Membership.objects.create(division=d,user=admin,role='technical')
    dec=draft(world); services.transition(d,a,dec.pk,1,'submit'); v=dec.versions.get(number=1)
    with pytest.raises(BusinessError): services.sign(d,admin,dec.pk,1,v.digest,'auth')

def test_document_replacement_automatically_invalidates_pending_approval(world):
    d,a,b,doc=world
    dec=authorize(world,'funding_direct',amount='10000',party='Test',classification='loan',evidence_id=str(doc.pk))
    services.upload(d,a,'replacement.txt','text/plain',b'New authoritative evidence',str(doc.pk))
    dec.refresh_from_db()
    assert dec.current_version==2 and dec.status=='draft'
    assert dec.versions.get(number=1).signatures.count()==2
    assert dec.versions.get(number=2).signatures.count()==0
    with pytest.raises(BusinessError): services.execute(d,a,dec.pk,1,'old-document')
