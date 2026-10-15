"""Add a small synthetic management-register walkthrough to the Test workspace."""
from decimal import Decimal
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand,CommandError
from django.db import transaction
from django.utils import timezone
from core.models import Division,FinanceTransaction,TransactionRevision,SavedScenario,SimpleDecision,DecisionVote,DocumentLink,Document,Record
from core import services
from core.simple import snapshot

class Command(BaseCommand):
    help='Add repeatable synthetic payments, scenario and approved decision to an unused simple Test workspace.'
    @transaction.atomic
    def handle(self,*args,**kwargs):
        div=Division.objects.filter(is_demo=True).first()
        if not div: raise CommandError('Test workspace is missing.')
        services.lock(div)
        if Record.objects.filter(division=div,kind='simple_sample_dataset').exists():
            self.stdout.write('Simple sample data already installed; preserved existing entries.'); return
        if FinanceTransaction.objects.filter(division=div).exists() or SimpleDecision.objects.filter(division=div).exists():
            self.stdout.write('Existing Test workspace entries found; no sample data added.'); return
        actors=list(User.objects.filter(username__startswith='sample-').order_by('id')[:2])
        if len(actors)<2:
            actors=[]
            for name in ('A','B'):
                user=User(username=f'simple-sample-{name.lower()}@example.invalid',first_name='Sample '+name,is_active=False)
                user.set_unusable_password(); user.save(); actors.append(user)
        day=timezone.localdate(); a,b=actors
        scenario=SavedScenario.objects.create(division=div,name='Sample manufacturing: 1,000 units',investment=Decimal('2000'),unit_cost=Decimal('3.50'),selling_price=Decimal('8.00'),quantity=1000,extra_expenses=Decimal('500'),created_by=a)
        services.audit(div,a,'scenario.sample_created',scenario.pk)
        decision=SimpleDecision.objects.create(division=div,title='Sample equipment purchase',description='Synthetic quotation review only.',estimated_cost=Decimal('2000'),expected_benefit='Lower sample unit cost',risks='Supplier timing is uncertain',scenario=scenario,required_approvals=2,created_by=a)
        for user in actors: DecisionVote.objects.create(decision=decision,user=user,choice='approve')
        decision.status='approved'; decision.save(update_fields=['status'])
        services.audit(div,a,'simple_decision.sample_approved',decision.pk,{'voters':[str(x.pk) for x in actors]})
        examples=[
            dict(direction='paid',amount='200',total_due='500',category='Materials',description='Sample supplier bill',party='Sample supplier',method='bank',reference='SAMPLE-SIMPLE-1',treatment='expense',recognized_amount='500',decision=decision),
            dict(direction='received',amount='700',total_due='1200',category='Sales',description='Sample customer sale',party='Sample customer',method='bank',reference='SAMPLE-SIMPLE-2',treatment='income',recognized_amount='1200'),
            dict(direction='paid',amount='100',category='Transport',description='Sample delivery cost',party='',method='cash',reference='SAMPLE-SIMPLE-3',treatment='expense',recognized_amount='100'),
        ]
        entries=[]
        for data in examples:
            entry=FinanceTransaction.objects.create(division=div,date=day,created_by=a,**data)
            TransactionRevision.objects.create(transaction=entry,actor=a,snapshot=snapshot(entry))
            services.audit(div,a,'simple_transaction.sample_created',entry.pk)
            entries.append(entry)
        entry=FinanceTransaction.objects.create(division=div,date=day,created_by=a,direction='paid',amount='100',category='Materials',description='Sample partial payment',method='bank',reference='SAMPLE-SIMPLE-4',treatment='none',recognized_amount=0,settles=entries[0])
        TransactionRevision.objects.create(transaction=entry,actor=a,snapshot=snapshot(entry))
        services.audit(div,a,'simple_transaction.sample_created',entry.pk)
        evidence=Document.objects.filter(division=div,name='SYNTHETIC-WALKTHROUGH.txt').first()
        if evidence: DocumentLink.objects.create(document=evidence,transaction=entries[0],category='Materials',supplier='Sample supplier',reference='SAMPLE-SIMPLE-1')
        Record.objects.create(division=div,kind='simple_sample_dataset',title='Simple synthetic walkthrough',status='sample_only',source_status='synthetic',data={'external_actions':'none'})
        services.audit(div,a,'simple_sample.installed',div.pk,{'transactions':4,'scenario':1,'decisions':1})
        self.stdout.write('Simple synthetic Test workspace walkthrough installed; no external action occurred.')
