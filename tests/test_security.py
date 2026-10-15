import hashlib,io,json,time,uuid,zipfile
import pytest,pyotp
from django.contrib.auth.models import User
from django.db import connection,transaction,DatabaseError
from django.urls import reverse
from django.utils import timezone
from core.models import *
from core import services,contracts
from core.finance import BusinessError
from .conftest import authorize,perform,payload
pytestmark=pytest.mark.django_db(transaction=True)

def test_api_rejects_bypass_and_cross_tenant(world,client):
    d,a,b,doc=world
    dec=services.draft_decision(d,a,'Unsigned','resolution',payload(terms='Test terms'))
    client.force_login(a); session=client.session; session['reauth_at']=time.time(); session['auth_event']='test-auth'; session.save()
    response=client.post(reverse('api_decision',args=[d.pk,dec.pk,'execute']),data=json.dumps({'version':1,'idempotency_key':'bypass'}),content_type='application/json')
    assert response.status_code==400 and Execution.objects.count()==0
    outsider=User.objects.create_user('outsider@example.invalid'); client.force_login(outsider)
    assert client.get(reverse('download',args=[d.pk,doc.pk])).status_code==400
    assert client.get(reverse('export',args=[d.pk,'archive'])).status_code==400

def test_readonly_can_read_not_mutate(world,client):
    d,a,b,doc=world; reader=User.objects.create_user('reader@example.invalid')
    Membership.objects.create(division=d,user=reader,role='reader'); client.force_login(reader)
    assert client.get(reverse('download',args=[d.pk,doc.pk])).status_code==200
    response=client.post(reverse('fact_new',args=[d.pk]),{'kind':'outside_payment','title':'bypass','data':'{}'})
    assert response.status_code==400
    assert client.get(reverse('export',args=[d.pk,'json'])).status_code==200

def test_authenticated_csrf_enforced(world):
    from django.test import Client
    d,a,*_=world; c=Client(enforce_csrf_checks=True); c.force_login(a)
    assert c.post(reverse('fact_new',args=[d.pk]),{}).status_code==403

def test_mfa_reauth_and_revocation(world,client):
    d,a,b,doc=world; secret=pyotp.random_base32(); AuthFactor.objects.create(user=a,secret=secret,enabled=True)
    client.force_login(a)
    response=client.post(reverse('reauth'),{'password':'synthetic-test-password','code':pyotp.TOTP(secret).now()})
    assert response.status_code==302 and client.session.get('auth_event')
    again=client.post(reverse('reauth'),{'password':'synthetic-test-password','code':pyotp.TOTP(secret).now()})
    assert b'already-used' in again.content
    Membership.objects.filter(user=a,division=d).update(active=False)
    assert client.get(reverse('dashboard',args=[d.pk])).status_code==400

def test_all_pages_and_no_forecast_as_actual(world,client):
    d,a,*_=world; client.force_login(a)
    from core.views import NAV
    for section,_,_ in NAV:
        r=client.get(reverse('page',args=[d.pk,section])); assert r.status_code==200,(section,r.content[:200])
    r=client.get(reverse('dashboard',args=[d.pk])); assert b'Not set' in r.content and b'Estimated profit' in r.content
    assert client.get(reverse('scenario',args=[d.pk])).status_code==200

def test_contract_internal_approval_never_external_execution(world,client):
    d,a,b,doc=world; c=Contract.objects.filter(division=d).first()
    perform(world,'contract_approval',contract_id=str(c.pk)); c.refresh_from_db()
    assert c.status=='internally_approved' and c.provider_reference==''
    client.force_login(a)
    assert client.post(reverse('contract_evidence',args=[d.pk,c.pk]),{'document_id':str(doc.pk)}).status_code==302
    c.refresh_from_db(); assert c.status=='uploaded_evidence_unverified'
    assert contracts.pdf(c).startswith(b'%PDF-') and contracts.missing(c)
    assert client.post('/webhooks/signing/',data='{}',content_type='application/json').status_code==404

def test_contract_edit_invalidates_snapshot(world):
    d,a,b,doc=world; c=Contract.objects.filter(division=d).first()
    dec=authorize(world,'contract_approval',contract_id=str(c.pk))
    c.fields={'entity_name':'Changed after approval'}; c.save(update_fields=['fields'])
    with pytest.raises(BusinessError,match='Contract content changed'): services.execute(d,a,dec.pk,1,'contract-change')

def test_archive_private_document_integrity(world,client):
    d,a,b,doc=world; client.force_login(a)
    r=client.get(reverse('export',args=[d.pk,'archive'])); assert r.status_code==200
    raw=b''.join(r.streaming_content)
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        manifest=json.loads(z.read('manifest.json'))
        for path,expected in manifest.items(): assert hashlib.sha256(z.read(path)).hexdigest()==expected
        assert z.read('documents/'+str(doc.pk))==bytes(doc.content)
        assert b'password' not in z.read('access.json')

def test_postgres_row_security_with_nonowner_role(world):
    d,a,b,doc=world; outsider=User.objects.create_user('other@example.invalid')
    entry=FinanceTransaction.objects.create(division=d,date=timezone.localdate(),direction='paid',amount='10',category='Test',description='Synthetic RLS entry',method='bank',treatment='expense',recognized_amount='10',created_by=a)
    DocumentLink.objects.create(document=doc,transaction=entry)
    # Ephemeral role is created by the test database owner; web deployment uses the same non-owner pattern.
    role='rls_test_'+uuid.uuid4().hex[:12]
    with connection.cursor() as c:
        c.execute(f'CREATE ROLE {role} NOLOGIN'); c.execute(f'GRANT USAGE ON SCHEMA public TO {role}'); c.execute(f'GRANT SELECT ON ALL TABLES IN SCHEMA public TO {role}')
    try:
        with transaction.atomic(),connection.cursor() as c:
            c.execute(f'SET LOCAL ROLE {role}'); c.execute("SELECT set_config('app.user_id',%s,true)",[str(outsider.pk)])
            c.execute('SELECT count(*) FROM core_document'); assert c.fetchone()[0]==0
            c.execute('SELECT count(*) FROM core_financetransaction'); assert c.fetchone()[0]==0
            c.execute('SELECT count(*) FROM core_documentlink'); assert c.fetchone()[0]==0
            c.execute("SELECT set_config('app.user_id',%s,true)",[str(a.pk)])
            c.execute('SELECT count(*) FROM core_document'); assert c.fetchone()[0]==1
            c.execute('SELECT count(*) FROM core_financetransaction'); assert c.fetchone()[0]==1
            c.execute('SELECT count(*) FROM core_documentlink'); assert c.fetchone()[0]==1
    finally:
        with connection.cursor() as c: c.execute(f'DROP OWNED BY {role}'); c.execute(f'DROP ROLE {role}')

def test_live_upload_download_quarantine(world,client):
    d,a,b,doc=world; d.is_demo=False; d.save(update_fields=['is_demo']); AuthFactor.objects.create(user=a,secret=pyotp.random_base32(),enabled=True)
    client.force_login(a)
    r=client.get(reverse('download',args=[d.pk,doc.pk])); assert r.status_code==400 and b'quarantined' in r.content

def test_nonowner_runtime_role_can_post_through_nested_services(world):
    import os,subprocess,sys
    from pathlib import Path
    import psycopg
    from urllib.parse import urlencode,quote
    d,a,b,doc=world; role='runtime_test_'+uuid.uuid4().hex[:10]
    params=connection.get_connection_params(); source=f"postgresql://{quote(params.get('user',''))}@/{params['dbname']}?"+urlencode({'host':params.get('host',''),'port':params.get('port','5432')})
    env=os.environ.copy(); env.update(DATABASE_URL=source,APP_DB_ROLE=role,APP_DB_PASSWORD=uuid.uuid4().hex)
    script=Path(__file__).resolve().parent.parent/'scripts/provision_runtime_role.py'
    subprocess.run([sys.executable,str(script)],env=env,check=True,capture_output=True)
    try:
        with transaction.atomic(),connection.cursor() as c:
            c.execute(f'SET LOCAL ROLE {role}'); c.execute("SELECT set_config('app.user_id',%s,true)",[str(a.pk)])
            dec=services.draft_decision(d,a,'Restricted role','funding_direct',payload(amount='10000',party='Test',classification='loan',evidence_id=str(doc.pk)))
            services.transition(d,a,dec.pk,1,'submit'); v=dec.versions.get(number=1)
            services.sign(d,a,dec.pk,1,v.digest,'a')
            c.execute("SELECT set_config('app.user_id',%s,true)",[str(b.pk)]); services.sign(d,b,dec.pk,1,v.digest,'b')
            services.execute(d,b,dec.pk,1,'runtime-role')
        assert services.balance(d,'supplier_advance')==10000
    finally:
        with connection.cursor() as c: c.execute(f'DROP OWNED BY {role}'); c.execute(f'DROP ROLE {role}')
