"""Optional, repeatable synthetic walkthrough. Never touches the live division."""
import uuid
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from core.models import Division, Membership, Record, Stock, Decision, Invitation
from core import services
from core.reports import report, verify_audit

class Command(BaseCommand):
    help='Create an isolated, clearly synthetic purchase-to-collection walkthrough.'

    @transaction.atomic
    def handle(self, *args, **options):
        demo=Division.objects.filter(is_demo=True).first()
        if not demo: raise CommandError('Seed the test workspace first.')
        services.lock(demo)
        if Record.objects.filter(division=demo,kind='sample_dataset').exists():
            self.stdout.write('Synthetic walkthrough already installed; preserved existing test data.')
            return
        if Membership.objects.filter(division=demo,active=True).exists():
            raise CommandError('Sample setup requires an unused test workspace. Existing people and work were preserved.')
        actors=[]
        for slot in ('sayem','sami'):
            username=f'sample-{slot}-{uuid.uuid4().hex[:12]}@example.invalid'
            user=User(username=username,first_name='Sample '+slot.title(),is_active=False)
            user.set_unusable_password(); user.save()
            Membership.objects.create(division=demo,user=user,role='operator',slot=slot)
            actors.append(user)
        first,second=actors
        evidence=services.upload(demo,first,'SYNTHETIC-WALKTHROUGH.txt','text/plain',b'SYNTHETIC TRAINING RECORD ONLY. No money moved. No customer or supplier transaction occurred.')
        today=str(timezone.localdate())
        def action(kind,**specific):
            payload={**specific,'purpose':'Synthetic walkthrough only','reference':'SAMPLE-'+uuid.uuid4().hex[:20],'date':today,'effective_date':today,'vat_basis':'included' if kind=='sales_order' else 'not_applicable','risks':'Synthetic test only; no external transaction','conditions':'Sample data, internally simulated','cash_impact':'Simulated ledger only','stock_impact':'Simulated units only'}
            dec=services.draft_decision(demo,first,'Sample '+kind.replace('_',' '),kind,payload)
            services.transition(demo,first,dec.pk,1,'submit')
            version=dec.versions.get(number=1)
            services.sign(demo,first,dec.pk,1,version.digest,'synthetic-auth-event-a')
            services.sign(demo,second,dec.pk,1,version.digest,'synthetic-auth-event-b')
            return services.execute(demo,first,dec.pk,1,'sample-'+str(dec.pk))
        action('funding_direct',amount='10000',party='Sample funder',classification='loan',evidence_id=str(evidence.pk))
        action('funding_cash',amount='60000',party='Sample funder',classification='loan',evidence_id=str(evidence.pk))
        mold=Record.objects.get(division=demo,kind='mold')
        action('mold_acceptance',amount='10000',inspection='Synthetic acceptance only',mold_id=str(mold.pk))
        purchase=action('purchase_order',party='Sample factory',quantity='100000',sku='FLW-001',amount='36900',due_date=today)
        production=action('production_release',purchase_order_id=purchase.result['record_id'],party='Sample factory',sku='FLW-001',quantity='100000',mold='Sample mold',rate='4.50',charge_basis='input_kg',material_ownership='factory')
        receipt=action('goods_receipt',production_id=production.result['record_id'],sku='FLW-001',location='Sample warehouse',lot='SAMPLE-LOT-1',quantity='100000',amount='36900')
        action('quality_release',stock_id=receipt.result['stock_id'],accepted_quantity='100000',inspection='Synthetic inspection: accepted')
        bill=action('supplier_bill',receipt_id=receipt.result['receipt_id'],party='Sample factory',amount='36900',due_date=today,beneficiary='SAMPLE-BENEFICIARY-ONLY')
        action('supplier_payment',item_id=bill.result['item_id'],amount='10000',beneficiary='SAMPLE-BENEFICIARY-ONLY',evidence_id=str(evidence.pk))
        sale=action('sales_order',stock_id=receipt.result['stock_id'],party='Sample customer',quantity='1000',unit_price='2.00',vat_rate='15',due_date=today)
        delivery=action('delivery',order_id=sale.result['order_id'],quantity='1000')
        action('customer_invoice',delivery_id=delivery.result['delivery_id'])
        action('collection',item_id=delivery.result['item_id'],amount='700',evidence_id=str(evidence.pk))
        action('repayment',amount='1000',beneficiary='Sample funder',evidence_id=str(evidence.pk),counterparty_consent='Synthetic consent for walkthrough')
        Record.objects.create(division=demo,kind='sample_dataset',title='Synthetic walkthrough installed',status='sample_only',source_status='synthetic',data={'purpose':'training only','external_actions':'none','decision_count':Decision.objects.filter(division=demo).count()})
        # Preserve historical approval evidence; these example identities cannot
        # sign in or approve the real operators' future test decisions.
        Membership.objects.filter(division=demo,user__in=actors).update(active=False)
        r=report(demo)
        if not all(r['ties'].values()) or not verify_audit(demo): raise CommandError('Synthetic report integrity check failed; transaction rolled back.')
        self.stdout.write(f'Synthetic walkthrough installed in test workspace: {Decision.objects.filter(division=demo).count()} signed decisions, {Stock.objects.filter(division=demo).count()} stock lot, balanced reports. No external action occurred.')
