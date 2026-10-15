import pytest
from django.core.management import call_command
from core.seed import seed
from core.models import Decision,Journal,Membership,Record,Stock
from django.contrib.auth.models import User
from core.reports import report,verify_audit

pytestmark=pytest.mark.django_db(transaction=True)

def test_sample_walkthrough_is_repeatable_isolated_and_balanced():
    live=seed(False)
    demo=seed(True)
    call_command('seed_sample_transactions',verbosity=0)
    assert Decision.objects.filter(division=demo,status='executed').count()==13
    assert Decision.objects.filter(division=live).count()==0
    assert Journal.objects.filter(division=live).count()==0
    assert Stock.objects.filter(division=live).count()==0
    assert Membership.objects.filter(division=demo,active=True).count()==0
    assert all(not u.has_usable_password() and not u.is_active for u in User.objects.filter(username__startswith='sample-'))
    r=report(demo)
    assert all(r['ties'].values()) and verify_audit(demo)
    assert r['revenue']>0 and r['inventory_value']>0 and r['funding']==0
    assert Record.objects.get(division=demo,kind='sample_dataset').source_status=='synthetic'
    call_command('seed_sample_transactions',verbosity=0)
    assert Decision.objects.filter(division=demo).count()==13
