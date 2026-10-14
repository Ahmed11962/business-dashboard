import uuid
import pytest
from django.contrib.auth.models import User
from django.utils import timezone
from core.models import *
from core import services
from core.seed import seed

@pytest.fixture
def world(db,settings):
    settings.PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher']
    d=seed(True)
    a=User.objects.create_user('operator-a@example.invalid',password='synthetic-test-password',first_name='Test operator A')
    b=User.objects.create_user('operator-b@example.invalid',password='synthetic-test-password',first_name='Test operator B')
    Membership.objects.create(division=d,user=a,role='operator',slot='sayem')
    Membership.objects.create(division=d,user=b,role='operator',slot='sami')
    doc=services.upload(d,a,'synthetic-proof.txt','text/plain',b'SYNTHETIC TEST EVIDENCE - not a real transaction')
    return d,a,b,doc

def payload(**extra):
    day=str(timezone.localdate())
    return dict(purpose='Synthetic acceptance test',reference=str(uuid.uuid4()),date=day,effective_date=day,vat_basis='excluded',risks='Synthetic test only',conditions='Test evidence checked',cash_impact='As specified',stock_impact='As specified',**extra)

def authorize(world,kind,**extra):
    d,a,b,_=world
    decision=services.draft_decision(d,a,'Test '+kind,kind,payload(**extra))
    services.transition(d,a,decision.pk,1,'submit'); v=decision.versions.get(number=1)
    services.sign(d,a,decision.pk,1,v.digest,'test-auth-a'); services.sign(d,b,decision.pk,1,v.digest,'test-auth-b')
    decision.refresh_from_db(); return decision

def perform(world,kind,**extra):
    d,a,_,_=world; decision=authorize(world,kind,**extra)
    return services.execute(d,a,decision.pk,1,str(uuid.uuid4()))

@pytest.fixture
def batch(world):
    d,a,b,doc=world
    po=perform(world,'purchase_order',party='Test factory',quantity='100000',sku='FLW-001',amount='36900',due_date=str(timezone.localdate()))
    prod=perform(world,'production_release',purchase_order_id=po.result['record_id'],party='Test factory',sku='FLW-001',quantity='100000',mold='Test mold',rate='4.50',charge_basis='input_kg',material_ownership='factory')
    receipt=perform(world,'goods_receipt',production_id=prod.result['record_id'],sku='FLW-001',location='Test warehouse',lot='TEST-001',quantity='100000',amount='36900')
    perform(world,'quality_release',stock_id=receipt.result['stock_id'],accepted_quantity='100000',inspection='Synthetic inspection passed')
    return receipt

@pytest.fixture
def sold(world,batch):
    order=perform(world,'sales_order',stock_id=batch.result['stock_id'],party='Test customer',quantity='1000',unit_price='2',vat_rate='0',due_date=str(timezone.localdate()))
    delivery=perform(world,'delivery',order_id=order.result['order_id'],quantity='1000')
    return delivery
