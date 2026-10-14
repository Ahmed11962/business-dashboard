import hashlib
from decimal import Decimal
from django.core.management.base import BaseCommand,CommandError
from core.models import Division,Document,DecisionVersion,Journal,Execution,Movement,Stock
from core.services import digest
from core.reports import report,verify_audit
class Command(BaseCommand):
    help='Check audit/document hashes, ledger/subledger ties and preserved approval evidence.'
    def handle(self,*a,**o):
        errors=[]
        for div in Division.objects.all():
            if not verify_audit(div): errors.append('Audit chain mismatch '+str(div.pk))
            for name,ok in report(div)['ties'].items():
                if not ok: errors.append('Subledger mismatch '+name)
            for s in Stock.objects.filter(division=div):
                ms=Movement.objects.filter(stock=s)
                if sum((m.quantity for m in ms),Decimal(0))!=s.quantity or sum((m.value for m in ms),Decimal(0))!=s.value: errors.append('Stock movement mismatch '+str(s.pk))
        for d in Document.objects.all():
            if hashlib.sha256(bytes(d.content)).hexdigest()!=d.sha256: errors.append('Document hash mismatch '+str(d.pk))
        for v in DecisionVersion.objects.all():
            if digest(v.payload)!=v.digest: errors.append('Version hash mismatch')
        for j in Journal.objects.all():
            if j.lines.count()<2 or sum((l.debit-l.credit for l in j.lines.all()),Decimal(0))!=0: errors.append('Unbalanced journal '+str(j.pk))
        for e in Execution.objects.select_related('version'):
            if set(e.version.signatures.filter(digest=e.version.digest).values_list('user_id',flat=True))!=set(e.version.payload['approvers']): errors.append('Execution approval mismatch')
        if errors: raise CommandError('; '.join(errors))
        self.stdout.write('PASS: document and decision hashes, audit chains, journals, stock movements, control accounts and execution signatures.')
