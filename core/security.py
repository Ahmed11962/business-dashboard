import hashlib, time, uuid
from datetime import timedelta
import pyotp
from django.db import transaction
from django.utils import timezone
from .models import Membership, AuthFactor, RateLimit
from .finance import BusinessError

def require_role(user,division,roles=('operator',)):
    m=Membership.objects.filter(user=user,division=division,active=True).first()
    if not m or m.role not in roles: raise BusinessError('This account is not authorized for this workspace action.')
    return m

@transaction.atomic
def rate_limit(key,limit=8,seconds=300):
    key=hashlib.sha256(key.encode()).hexdigest()
    RateLimit.objects.get_or_create(key=key)
    r=RateLimit.objects.select_for_update().get(pk=key)
    if timezone.now()-r.window>timedelta(seconds=seconds): r.count=0; r.window=timezone.now()
    r.count+=1; r.save()
    return r.count<=limit

@transaction.atomic
def verify_factor(user,code,required=True):
    factor=AuthFactor.objects.select_for_update().filter(user=user,enabled=True).first()
    if not factor:
        if required: raise BusinessError('Enroll your authenticator before signing or using a live workspace.')
        return
    counter=int(time.time())//30
    if counter<=factor.last_counter or not pyotp.TOTP(factor.secret).verify(str(code),valid_window=0):
        raise BusinessError('Invalid or already-used authenticator code. Use the next code.')
    factor.last_counter=counter; factor.save(update_fields=['last_counter'])

def require_reauth(request):
    if time.time()-request.session.get('reauth_at',0)>300: raise BusinessError('Reauthenticate before signing (valid for five minutes).')
    if not request.session.get('auth_event'): raise BusinessError('Missing authentication event.')
    return request.session['auth_event']
