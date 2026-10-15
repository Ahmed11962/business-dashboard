"""A repeatable, synthetic basket walkthrough in the isolated Test workspace."""
import base64
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from core.models import (Division,Membership,Product,Mold,ProductionBatch,SalesInvoice,
                         InvoiceLine,CapitalContribution,FinanceTransaction,WorkflowAttachment,Record,TransactionRevision)
from core.manufacturing import record_payment,receive,dispatch
from core import services

class Command(BaseCommand):
    help='Add a clearly synthetic basket mold, production, stock, sale, and capital walkthrough to Test only.'

    @transaction.atomic
    def handle(self,*args,**kwargs):
        div=Division.objects.filter(is_demo=True).first()
        if not div: raise CommandError('Test workspace is missing.')
        services.lock(div)
        if Product.objects.filter(division=div,sku='SYN-BASKET-01').exists():
            self.stdout.write('Manufacturing sample already exists; preserved current test data.'); return
        actor=User.objects.filter(username='manufacturing-sample@example.invalid').first()
        if not actor:
            actor=User(username='manufacturing-sample@example.invalid',first_name='Synthetic Sample',is_active=False)
            actor.set_unusable_password(); actor.save()
        Membership.objects.get_or_create(division=div,user=actor,defaults={'role':'reviewer'})
        today=timezone.localdate()
        product=Product.objects.create(division=div,name='Synthetic Plastic Basket',sku='SYN-BASKET-01',default_price='6.00')
        mold=Mold.objects.create(division=div,name='Synthetic Basket Mold',code='SYN-MOLD-01',product=product,
            supplier='Synthetic Mold Supplier',purchase_date=today,price='20000',status='delivered',ownership_confirmed=True,
            notes='TRAINING SAMPLE ONLY. No real supplier order or payment.')
        record_payment(div,actor,mold,'10000','SYN-MOLD-PAY-01',today,party='Synthetic Mold Supplier')
        record_payment(div,actor,mold,'10000','SYN-MOLD-PAY-02',today,party='Synthetic Mold Supplier')
        batch=ProductionBatch.objects.create(division=div,number='SYN-BATCH-01',mold=mold,manufacturer='Synthetic Factory',
            order_date=today,quantity=5000,weight_grams='120',price_per_gram='0.02',other_cost='500',status='ordered',
            notes='Calculated estimate and agreed cost: SAR 12,500. Training sample only.')
        record_payment(div,actor,batch,'5000','SYN-PRODUCTION-PAY-01',today,party='Synthetic Factory')
        receive(div,actor,batch,5000,0,0,'SYN-DELIVERY-01')
        invoice=SalesInvoice.objects.create(division=div,number='SYN-SALE-01',customer='Synthetic Customer',date=today,
            notes='Internal sample document. No real sale or tax invoice.')
        line=InvoiceLine.objects.create(invoice=invoice,product=product,quantity=1500,unit_price='6.00')
        dispatch(div,actor,line,1500,'SYN-DISPATCH-01')
        record_payment(div,actor,invoice,'3000','SYN-COLLECTION-01',today,party='Synthetic Customer')
        t=FinanceTransaction.objects.create(division=div,date=today,direction='received',amount='100000',
            category='Capital contribution',description='Synthetic sample capital',party='Synthetic Funder',
            method='bank',reference='SYN-CAPITAL-01',treatment='none',recognized_amount=0,created_by=actor)
        from core.simple import snapshot
        TransactionRevision.objects.create(transaction=t,actor=actor,snapshot=snapshot(t))
        CapitalContribution.objects.create(division=div,contributor='Synthetic Funder',kind='repayable',
            terms='Training assumption only; no actual loan or repayment obligation.',transaction=t)
        services.audit(div,actor,'capital.sample_contributed',t.pk,{'amount':'100000','external_action':'none'})
        png=base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9WfNOr8AAAAASUVORK5CYII=')
        image=services.upload(div,actor,'synthetic-basket.png','image/png',png)
        product.image=image; product.save(update_fields=['image'])
        mold.image=image; mold.save(update_fields=['image'])
        quote=services.upload(div,actor,'synthetic-quotation.pdf','application/pdf',b'%PDF-1.4\n% SYNTHETIC TRAINING QUOTATION ONLY\n')
        WorkflowAttachment.objects.create(document=quote,mold=mold)
        Record.objects.create(division=div,kind='manufacturing_sample',title='Synthetic basket workflow',
            status='sample_only',source_status='synthetic',data={'external_actions':'none','sku':product.sku})
        services.audit(div,actor,'manufacturing_sample.installed',div.pk,{'sku':product.sku})
        self.stdout.write('Synthetic basket workflow installed in Test only. No external action occurred.')
