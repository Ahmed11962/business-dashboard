from datetime import timedelta
import hashlib
import pytest
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from core.models import Division,Invitation,Membership,Decision,DecisionVersion
from core.seed import seed
from core import services
from core.finance import BusinessError
from .conftest import payload

pytestmark=pytest.mark.django_db(transaction=True)

def test_sayem_enrollment_grants_isolated_test_access_and_sami_stays_pending(client,settings):
    settings.PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher']
    settings.STAGING_PREVIEW=True
    live=seed(False); demo=seed(True)
    invite=Invitation.objects.get(division=live,slot='sayem')
    invite.email='sayem@example.invalid'; invite.token_hash=hashlib.sha256(b'private-test-token').hexdigest(); invite.expires_at=timezone.now()+timedelta(hours=48); invite.save()
    response=client.post(reverse('enroll',args=['private-test-token']),{'name':'Sayem','password':'Private-Test-Password-2026!'})
    assert response.status_code==302 and response.url==reverse('mfa')
    user=User.objects.get(username='sayem@example.invalid')
    assert Membership.objects.get(division=live,slot='sayem').user_id==user.pk
    assert Membership.objects.get(division=demo,slot='sayem').user_id==user.pk
    assert Membership.objects.filter(division=demo,slot='sami',active=True).count()==0
    assert Invitation.objects.get(division=live,slot='sami').email==''
    assert client.get(reverse('dashboard',args=[demo.pk])).status_code==302  # MFA required
    decision=services.draft_decision(demo,user,'Sample draft','resolution',payload(terms='Training decision only'))
    assert decision.status=='draft'
    with pytest.raises(BusinessError,match='Sami'):
        services.transition(demo,user,decision.pk,1,'submit')
    assert decision.versions.count()==1 and decision.versions.first().signatures.count()==0
    sami=User.objects.create_user('sami@example.invalid',password='Private-Test-Password-2026!')
    Membership.objects.create(division=demo,user=sami,role='operator',slot='sami')
    services.transition(demo,user,decision.pk,1,'submit')
    decision.refresh_from_db()
    assert decision.current_version==2 and decision.status=='submitted'
    assert decision.versions.get(number=1).payload['approvers']==[user.pk]
    assert decision.versions.get(number=2).payload['approvers']==[sami.pk,user.pk] or set(decision.versions.get(number=2).payload['approvers'])=={user.pk,sami.pk}
