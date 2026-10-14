import hashlib,secrets
from pathlib import Path
from datetime import timedelta
from django.core.management.base import BaseCommand,CommandError
from django.core.validators import validate_email
from django.db import transaction
from django.utils import timezone
from core.models import Division,Invitation,Membership
from core.services import audit,lock
class Command(BaseCommand):
    help='Initial operator invitation only. Writes a private one-use enrollment path; sends nothing.'
    def add_arguments(self,p):
        p.add_argument('division'); p.add_argument('slot',choices=['sayem','sami']); p.add_argument('email'); p.add_argument('--output',required=True); p.add_argument('--governance-reference',required=True)
    @transaction.atomic
    def handle(self,*args,**o):
        validate_email(o['email']); div=lock(Division.objects.get(pk=o['division']))
        if Membership.objects.filter(division=div,slot=o['slot']).exists(): raise CommandError('Replacement requires documented recovery/governance; this bootstrap command cannot replace operators.')
        inv=Invitation.objects.get(division=div,slot=o['slot'])
        if inv.accepted_at: raise CommandError('Invitation already accepted.')
        token=secrets.token_urlsafe(32); inv.email=o['email']; inv.token_hash=hashlib.sha256(token.encode()).hexdigest(); inv.expires_at=timezone.now()+timedelta(hours=48); inv.save()
        path=Path(o['output']); import os
        fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,'w') as f: f.write('/enroll/'+token+'/\n')
        audit(div,None,'invitation.issued',inv.pk,{'slot':o['slot'],'governance_reference':o['governance_reference']})
        self.stdout.write('One-time enrollment path saved privately. Deliver through an authorized secure channel; no message was sent.')
