import uuid
from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone

class Entity(models.Model):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    name=models.CharField(max_length=200,default='Legal entity — not confirmed')
    cr=models.CharField(max_length=100,blank=True)
    vat_number=models.CharField(max_length=100,blank=True)
    accounting_source=models.CharField(max_length=200,blank=True)

class Division(models.Model):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    legal_entity=models.ForeignKey(Entity,on_delete=models.PROTECT)
    name=models.CharField(max_length=100,default='Plastics division')
    is_demo=models.BooleanField(default=False)
    opening_confirmed=models.BooleanField(default=False)
    closed_through=models.DateField(null=True,blank=True)
    created_at=models.DateTimeField(default=timezone.now)
    # Business/legal gates are deliberately not editable as an admin bypass.
    configuration=models.JSONField(default=dict)

class Scoped(models.Model):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    division=models.ForeignKey(Division,on_delete=models.PROTECT)
    created_at=models.DateTimeField(default=timezone.now)
    class Meta: abstract=True
    @property
    def legal_entity_id(self): return self.division.legal_entity_id

class Membership(Scoped):
    ROLES=[('operator','Operator'),('reader','Read only'),('reviewer','Accountant / reviewer'),('technical','Technical administrator')]
    user=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    role=models.CharField(max_length=20,choices=ROLES)
    slot=models.CharField(max_length=10,null=True,blank=True,choices=[('sayem','Sayem'),('sami','Sami')])
    active=models.BooleanField(default=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['division','user'],name='one_membership'),models.UniqueConstraint(fields=['division','slot'],condition=Q(active=True,slot__isnull=False),name='distinct_operator_slot'),models.CheckConstraint(condition=Q(role='operator',slot__isnull=False)|(~Q(role='operator')&Q(slot__isnull=True)),name='operator_slot_required')]

class Invitation(Scoped):
    slot=models.CharField(max_length=10)
    email=models.EmailField(blank=True)
    token_hash=models.CharField(max_length=64,blank=True)
    expires_at=models.DateTimeField(null=True)
    accepted_at=models.DateTimeField(null=True)
    class Meta: constraints=[models.UniqueConstraint(fields=['division','slot'],name='one_invitation_slot')]

class AuthFactor(models.Model):
    user=models.OneToOneField(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    secret=models.CharField(max_length=64)
    enabled=models.BooleanField(default=False)
    last_counter=models.BigIntegerField(default=-1)

class RateLimit(models.Model):
    key=models.CharField(max_length=64,primary_key=True)
    window=models.DateTimeField(default=timezone.now)
    count=models.PositiveIntegerField(default=0)

class Record(Scoped):
    kind=models.CharField(max_length=40)
    title=models.CharField(max_length=200)
    status=models.CharField(max_length=40,default='draft')
    data=models.JSONField(default=dict)
    source_status=models.CharField(max_length=30,default='unverified')
    updated_at=models.DateTimeField(auto_now=True)

class Document(Scoped):
    name=models.CharField(max_length=200)
    category=models.CharField(max_length=80,blank=True)
    supplier=models.CharField(max_length=200,blank=True)
    reference=models.CharField(max_length=100,blank=True)
    media_type=models.CharField(max_length=100)
    sha256=models.CharField(max_length=64)
    content=models.BinaryField()
    size=models.PositiveIntegerField()
    scan_status=models.CharField(max_length=30,default='quarantined')
    uploaded_by=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    replaces=models.ForeignKey('self',null=True,blank=True,on_delete=models.PROTECT)

class Decision(Scoped):
    title=models.CharField(max_length=200)
    kind=models.CharField(max_length=40)
    status=models.CharField(max_length=30,default='draft')
    current_version=models.PositiveIntegerField(default=1)
    created_by=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    expires_at=models.DateTimeField(null=True,blank=True)
    executed_at=models.DateTimeField(null=True,blank=True)

class DecisionVersion(models.Model):
    decision=models.ForeignKey(Decision,on_delete=models.PROTECT,related_name='versions')
    number=models.PositiveIntegerField()
    payload=models.JSONField()
    digest=models.CharField(max_length=64)
    created_at=models.DateTimeField(default=timezone.now)
    class Meta: constraints=[models.UniqueConstraint(fields=['decision','number'],name='unique_decision_version')]

class Signature(models.Model):
    version=models.ForeignKey(DecisionVersion,on_delete=models.PROTECT,related_name='signatures')
    user=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    signed_at=models.DateTimeField(default=timezone.now)
    auth_event=models.CharField(max_length=100)
    consent=models.TextField(default='I approve this exact decision version, its conditions and document hashes.')
    digest=models.CharField(max_length=64)
    class Meta: constraints=[models.UniqueConstraint(fields=['version','user'],name='one_signature_per_person')]

class Execution(Scoped):
    decision=models.OneToOneField(Decision,on_delete=models.PROTECT)
    version=models.ForeignKey(DecisionVersion,on_delete=models.PROTECT)
    idempotency_key=models.CharField(max_length=100)
    result=models.JSONField(default=dict)
    class Meta: constraints=[models.UniqueConstraint(fields=['division','idempotency_key'],name='unique_execution_key')]

class Journal(Scoped):
    reference=models.CharField(max_length=100)
    description=models.CharField(max_length=250)
    date=models.DateField()
    decision=models.ForeignKey(Decision,on_delete=models.PROTECT)
    reversal_of=models.OneToOneField('self',null=True,blank=True,on_delete=models.PROTECT)
    class Meta: constraints=[models.UniqueConstraint(fields=['division','reference'],name='journal_external_reference_unique')]

class Line(models.Model):
    journal=models.ForeignKey(Journal,on_delete=models.PROTECT,related_name='lines')
    account=models.CharField(max_length=40)
    debit=models.DecimalField(max_digits=22,decimal_places=2,default=0)
    credit=models.DecimalField(max_digits=22,decimal_places=2,default=0)
    class Meta: constraints=[models.CheckConstraint(condition=(Q(debit__gt=0)&Q(credit=0))|(Q(credit__gt=0)&Q(debit=0)),name='one_positive_side')]

class Stock(Scoped):
    sku=models.CharField(max_length=80)
    location=models.CharField(max_length=100)
    lot=models.CharField(max_length=100)
    status=models.CharField(max_length=30,default='quarantined')
    owner=models.CharField(max_length=30,default='company')
    quantity=models.DecimalField(max_digits=20,decimal_places=3,default=0)
    reserved=models.DecimalField(max_digits=20,decimal_places=3,default=0)
    value=models.DecimalField(max_digits=22,decimal_places=2,default=0)
    class Meta: constraints=[models.UniqueConstraint(fields=['division','sku','location','lot'],name='unique_stock_lot'),models.CheckConstraint(condition=Q(quantity__gte=0,reserved__gte=0,value__gte=0)&Q(quantity__gte=models.F('reserved')),name='nonnegative_available_stock')]

class Movement(Scoped):
    stock=models.ForeignKey(Stock,on_delete=models.PROTECT)
    decision=models.ForeignKey(Decision,on_delete=models.PROTECT)
    quantity=models.DecimalField(max_digits=20,decimal_places=3)
    value=models.DecimalField(max_digits=22,decimal_places=2)
    kind=models.CharField(max_length=30)

class OpenItem(Scoped):
    side=models.CharField(max_length=20)
    party=models.CharField(max_length=200)
    reference=models.CharField(max_length=100)
    total=models.DecimalField(max_digits=22,decimal_places=2)
    settled=models.DecimalField(max_digits=22,decimal_places=2,default=0)
    due_date=models.DateField()
    decision=models.ForeignKey(Decision,on_delete=models.PROTECT)
    class Meta: constraints=[models.UniqueConstraint(fields=['division','side','reference'],name='unique_open_item'),models.CheckConstraint(condition=Q(total__gte=0,settled__gte=0)&Q(total__gte=models.F('settled')),name='settlement_within_total')]

class BankRow(Scoped):
    account_reference=models.CharField(max_length=100)
    external_id=models.CharField(max_length=100)
    date=models.DateField()
    amount=models.DecimalField(max_digits=22,decimal_places=2)
    memo=models.CharField(max_length=250,blank=True)
    matched_line=models.OneToOneField(Line,null=True,blank=True,on_delete=models.PROTECT)
    class Meta: constraints=[models.UniqueConstraint(fields=['division','account_reference','external_id'],name='dedup_bank_row')]

class Audit(Scoped):
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,null=True,on_delete=models.PROTECT)
    event=models.CharField(max_length=100)
    object_id=models.CharField(max_length=100)
    detail=models.JSONField(default=dict)
    previous_hash=models.CharField(max_length=64,blank=True)
    digest=models.CharField(max_length=64)

class Contract(Scoped):
    template=models.CharField(max_length=80)
    title=models.CharField(max_length=200)
    fields=models.JSONField(default=dict)
    status=models.CharField(max_length=40,default='lawyer_review_draft')
    internal_decision=models.ForeignKey(Decision,null=True,on_delete=models.PROTECT)
    evidence=models.ForeignKey(Document,null=True,on_delete=models.PROTECT)
    provider_reference=models.CharField(max_length=200,blank=True)

# The simple management register is additive. Historical journals and decisions
# remain immutable and available for reconciliation/export.
class FinanceTransaction(Scoped):
    date=models.DateField()
    direction=models.CharField(max_length=12,choices=[('received','Money in'),('paid','Money out')])
    amount=models.DecimalField(max_digits=22,decimal_places=2,default=0)
    total_due=models.DecimalField(max_digits=22,decimal_places=2,null=True,blank=True)
    category=models.CharField(max_length=80)
    description=models.CharField(max_length=250)
    party=models.CharField(max_length=200,blank=True)
    method=models.CharField(max_length=40,choices=[('bank','Bank'),('cash','Cash'),('other','Other')],default='bank')
    reference=models.CharField(max_length=100,blank=True)
    notes=models.TextField(blank=True)
    treatment=models.CharField(max_length=20,choices=[('income','Income'),('expense','Expense'),('asset','Asset purchase'),('transfer','Transfer'),('none','No profit effect')],default='none')
    recognized_amount=models.DecimalField(max_digits=22,decimal_places=2,default=0)
    settles=models.ForeignKey('self',null=True,blank=True,on_delete=models.PROTECT,related_name='payments')
    refund_of=models.ForeignKey('self',null=True,blank=True,on_delete=models.PROTECT,related_name='refunds')
    decision=models.ForeignKey('SimpleDecision',null=True,blank=True,on_delete=models.PROTECT,related_name='transactions')
    mold=models.ForeignKey('Mold',null=True,blank=True,on_delete=models.PROTECT,related_name='payments')
    batch=models.ForeignKey('ProductionBatch',null=True,blank=True,on_delete=models.PROTECT,related_name='payments')
    invoice=models.ForeignKey('SalesInvoice',null=True,blank=True,on_delete=models.PROTECT,related_name='payments')
    account=models.ForeignKey('CashAccount',null=True,blank=True,on_delete=models.PROTECT,related_name='transactions')
    reinvestment_plan=models.ForeignKey('ReinvestmentPlan',null=True,blank=True,on_delete=models.PROTECT,related_name='spending')
    created_by=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    updated_at=models.DateTimeField(auto_now=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['division','reference'],condition=~Q(reference=''),name='simple_transaction_unique_reference'),models.CheckConstraint(condition=Q(amount__gte=0),name='simple_transaction_nonnegative_cash'),models.CheckConstraint(condition=Q(total_due__gte=0)|Q(total_due__isnull=True),name='simple_transaction_nonnegative_due')]

class TransactionRevision(models.Model):
    transaction=models.ForeignKey(FinanceTransaction,on_delete=models.PROTECT,related_name='revisions')
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    snapshot=models.JSONField()
    created_at=models.DateTimeField(default=timezone.now)

class DocumentLink(models.Model):
    document=models.ForeignKey(Document,on_delete=models.PROTECT,related_name='simple_links')
    transaction=models.ForeignKey(FinanceTransaction,null=True,blank=True,on_delete=models.PROTECT,related_name='attachments')
    decision=models.ForeignKey('SimpleDecision',null=True,blank=True,on_delete=models.PROTECT,related_name='attachments')
    category=models.CharField(max_length=80,blank=True)
    supplier=models.CharField(max_length=200,blank=True)
    reference=models.CharField(max_length=100,blank=True)
    class Meta: constraints=[models.CheckConstraint(condition=Q(transaction__isnull=True)|Q(decision__isnull=True),name='document_link_one_parent')]

class SavedScenario(Scoped):
    name=models.CharField(max_length=200)
    investment=models.DecimalField(max_digits=22,decimal_places=2,default=0)
    unit_cost=models.DecimalField(max_digits=22,decimal_places=2)
    selling_price=models.DecimalField(max_digits=22,decimal_places=2)
    quantity=models.PositiveIntegerField()
    extra_expenses=models.DecimalField(max_digits=22,decimal_places=2,default=0)
    created_by=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)

class SimpleDecision(Scoped):
    title=models.CharField(max_length=200)
    description=models.TextField()
    estimated_cost=models.DecimalField(max_digits=22,decimal_places=2,default=0)
    expected_benefit=models.TextField(blank=True)
    risks=models.TextField(blank=True)
    scenario=models.ForeignKey(SavedScenario,null=True,blank=True,on_delete=models.PROTECT)
    required_approvals=models.PositiveSmallIntegerField(default=2)
    status=models.CharField(max_length=20,default='pending')
    created_by=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    class Meta: constraints=[models.CheckConstraint(condition=Q(required_approvals__in=[1,2]),name='simple_decision_approval_count')]

class DecisionVote(models.Model):
    decision=models.ForeignKey(SimpleDecision,on_delete=models.PROTECT,related_name='votes')
    user=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    choice=models.CharField(max_length=10,choices=[('approve','Approve'),('reject','Reject')])
    created_at=models.DateTimeField(default=timezone.now)
    class Meta: constraints=[models.UniqueConstraint(fields=['decision','user'],name='simple_decision_one_vote_per_user')]

class DecisionComment(models.Model):
    decision=models.ForeignKey(SimpleDecision,on_delete=models.PROTECT,related_name='comments')
    user=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    text=models.TextField()
    created_at=models.DateTimeField(default=timezone.now)

class CashOpening(Scoped):
    method=models.CharField(max_length=10,choices=[('bank','Bank'),('cash','Cash')])
    amount=models.DecimalField(max_digits=22,decimal_places=2)
    as_of=models.DateField()
    recorded_by=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    class Meta: constraints=[models.UniqueConstraint(fields=['division','method'],name='one_simple_opening_per_method')]

# Manufacturing records extend the existing management register. All cash movements
# remain FinanceTransaction rows; these records never hold a second cash ledger.
class Product(Scoped):
    name=models.CharField(max_length=200)
    sku=models.CharField(max_length=80)
    default_price=models.DecimalField(max_digits=22,decimal_places=2,default=0)
    quantity=models.PositiveIntegerField(default=0)
    reserved=models.PositiveIntegerField(default=0)
    inventory_value=models.DecimalField(max_digits=22,decimal_places=2,default=0)
    notes=models.TextField(blank=True)
    image=models.ForeignKey(Document,null=True,blank=True,on_delete=models.PROTECT,related_name='+')
    class Meta: constraints=[models.UniqueConstraint(fields=['division','sku'],name='product_sku_per_workspace'),models.CheckConstraint(condition=Q(quantity__gte=models.F('reserved')),name='product_reserve_within_stock'),models.CheckConstraint(condition=Q(inventory_value__gte=0),name='product_nonnegative_value')]
    def __str__(self): return f'{self.name} ({self.sku})'

class Mold(Scoped):
    name=models.CharField(max_length=200)
    code=models.CharField(max_length=80)
    product=models.ForeignKey(Product,on_delete=models.PROTECT,related_name='molds')
    supplier=models.CharField(max_length=200,blank=True)
    purchase_date=models.DateField()
    price=models.DecimalField(max_digits=22,decimal_places=2)
    expected_date=models.DateField(null=True,blank=True)
    status=models.CharField(max_length=30,default='ordered',choices=[(x,x.title()) for x in ('ordered','manufacturing','ready','delivered')])
    ownership_confirmed=models.BooleanField(default=False)
    notes=models.TextField(blank=True)
    image=models.ForeignKey(Document,null=True,blank=True,on_delete=models.PROTECT,related_name='+')
    class Meta: constraints=[models.UniqueConstraint(fields=['division','code'],name='mold_code_per_workspace'),models.CheckConstraint(condition=Q(price__gte=0),name='mold_price_nonnegative')]
    def __str__(self): return f'{self.name} ({self.code})'

class ProductionBatch(Scoped):
    number=models.CharField(max_length=80)
    mold=models.ForeignKey(Mold,on_delete=models.PROTECT,related_name='batches')
    manufacturer=models.CharField(max_length=200,blank=True)
    order_date=models.DateField()
    expected_date=models.DateField(null=True,blank=True)
    quantity=models.PositiveIntegerField()
    weight_grams=models.DecimalField(max_digits=18,decimal_places=3)
    price_per_gram=models.DecimalField(max_digits=18,decimal_places=5)
    setup_cost=models.DecimalField(max_digits=22,decimal_places=2,default=0)
    packaging_cost=models.DecimalField(max_digits=22,decimal_places=2,default=0)
    transport_cost=models.DecimalField(max_digits=22,decimal_places=2,default=0)
    other_cost=models.DecimalField(max_digits=22,decimal_places=2,default=0)
    quoted_cost=models.DecimalField(max_digits=22,decimal_places=2,null=True,blank=True)
    final_cost=models.DecimalField(max_digits=22,decimal_places=2,null=True,blank=True)
    status=models.CharField(max_length=30,default='planned',choices=[(x,x.replace('_',' ').title()) for x in ('planned','ordered','in_production','partially_received','completed','cancelled')])
    notes=models.TextField(blank=True)
    class Meta: constraints=[models.UniqueConstraint(fields=['division','number'],name='batch_number_per_workspace'),models.CheckConstraint(condition=Q(quantity__gt=0,weight_grams__gt=0,price_per_gram__gte=0),name='batch_valid_inputs'),models.CheckConstraint(condition=Q(setup_cost__gte=0,packaging_cost__gte=0,transport_cost__gte=0,other_cost__gte=0)&(Q(quoted_cost__gte=0)|Q(quoted_cost__isnull=True))&(Q(final_cost__gte=0)|Q(final_cost__isnull=True)),name='batch_nonnegative_costs')]
    def __str__(self): return self.number

class SalesInvoice(Scoped):
    number=models.CharField(max_length=80)
    customer=models.CharField(max_length=200)
    date=models.DateField()
    due_date=models.DateField(null=True,blank=True)
    discount=models.DecimalField(max_digits=22,decimal_places=2,default=0)
    tax=models.DecimalField(max_digits=22,decimal_places=2,default=0)
    tax_treatment=models.CharField(max_length=20,default='unconfirmed',choices=[('unconfirmed','Not confirmed'),('standard','Standard'),('zero_rated','Zero rated'),('exempt','Exempt'),('not_applicable','Not applicable')])
    status=models.CharField(max_length=20,default='issued',choices=[(x,x.title()) for x in ('issued','cancelled')])
    notes=models.TextField(blank=True)
    class Meta: constraints=[models.UniqueConstraint(fields=['division','number'],name='invoice_number_per_workspace'),models.CheckConstraint(condition=Q(discount__gte=0,tax__gte=0),name='invoice_nonnegative_adjustments')]
    def __str__(self): return self.number

class InvoiceLine(models.Model):
    invoice=models.ForeignKey(SalesInvoice,on_delete=models.PROTECT,related_name='lines')
    product=models.ForeignKey(Product,on_delete=models.PROTECT)
    quantity=models.PositiveIntegerField()
    unit_price=models.DecimalField(max_digits=22,decimal_places=2)
    fulfilled=models.PositiveIntegerField(default=0)
    class Meta: constraints=[models.CheckConstraint(condition=Q(quantity__gt=0,fulfilled__lte=models.F('quantity'),unit_price__gte=0),name='invoice_line_valid_quantity')]

class StockEvent(Scoped):
    product=models.ForeignKey(Product,on_delete=models.PROTECT,related_name='stock_events')
    batch=models.ForeignKey(ProductionBatch,null=True,blank=True,on_delete=models.PROTECT)
    invoice_line=models.ForeignKey(InvoiceLine,null=True,blank=True,on_delete=models.PROTECT)
    reverses=models.ForeignKey('self',null=True,blank=True,on_delete=models.PROTECT,related_name='returns')
    kind=models.CharField(max_length=20,choices=[(x,x.title()) for x in ('receipt','dispatch','return','damage','adjustment')])
    quantity=models.IntegerField()
    value=models.DecimalField(max_digits=22,decimal_places=2)
    accepted=models.PositiveIntegerField(default=0)
    rejected=models.PositiveIntegerField(default=0)
    damaged=models.PositiveIntegerField(default=0)
    reference=models.CharField(max_length=100)
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    class Meta: constraints=[models.UniqueConstraint(fields=['division','reference'],name='stock_event_unique_reference'),models.CheckConstraint(condition=(
        Q(kind='receipt',quantity__gte=0,value__gte=0)|Q(kind='dispatch',quantity__lt=0,value__lte=0)|
        Q(kind='return',quantity__gt=0,value__gte=0)|Q(kind='damage',quantity__lt=0,value__lte=0)|
        Q(kind='adjustment',quantity__gt=0,value__gt=0)|Q(kind='adjustment',quantity__lt=0,value__lte=0)),name='stock_event_direction_valid')]

class WorkflowAttachment(models.Model):
    document=models.ForeignKey(Document,on_delete=models.PROTECT)
    category=models.CharField(max_length=80,blank=True)
    supplier=models.CharField(max_length=200,blank=True)
    reference=models.CharField(max_length=100,blank=True)
    mold=models.ForeignKey(Mold,null=True,blank=True,on_delete=models.PROTECT,related_name='attachments')
    product=models.ForeignKey(Product,null=True,blank=True,on_delete=models.PROTECT,related_name='attachments')
    batch=models.ForeignKey(ProductionBatch,null=True,blank=True,on_delete=models.PROTECT,related_name='attachments')
    invoice=models.ForeignKey(SalesInvoice,null=True,blank=True,on_delete=models.PROTECT,related_name='attachments')
    class Meta: constraints=[models.CheckConstraint(condition=(
        Q(mold__isnull=False,product__isnull=True,batch__isnull=True,invoice__isnull=True)|
        Q(mold__isnull=True,product__isnull=False,batch__isnull=True,invoice__isnull=True)|
        Q(mold__isnull=True,product__isnull=True,batch__isnull=False,invoice__isnull=True)|
        Q(mold__isnull=True,product__isnull=True,batch__isnull=True,invoice__isnull=False)),name='workflow_attachment_one_parent')]

class CapitalContribution(Scoped):
    contributor=models.CharField(max_length=200)
    kind=models.CharField(max_length=20,choices=[(x,x.title()) for x in ('undetermined','repayable','equity')],default='undetermined')
    terms=models.TextField(blank=True)
    transaction=models.OneToOneField(FinanceTransaction,on_delete=models.PROTECT,related_name='capital_contribution')

class CapitalRepayment(Scoped):
    contribution=models.ForeignKey(CapitalContribution,on_delete=models.PROTECT,related_name='repayments')
    transaction=models.OneToOneField(FinanceTransaction,on_delete=models.PROTECT,related_name='capital_repayment')

class InvoiceCredit(Scoped):
    invoice=models.ForeignKey(SalesInvoice,on_delete=models.PROTECT,related_name='credits')
    reference=models.CharField(max_length=100)
    amount=models.DecimalField(max_digits=22,decimal_places=2)
    tax_amount=models.DecimalField(max_digits=22,decimal_places=2,default=0)
    reason=models.TextField()
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    class Meta: constraints=[models.UniqueConstraint(fields=['division','reference'],name='invoice_credit_unique_reference'),models.CheckConstraint(condition=Q(amount__gt=0,tax_amount__gte=0,tax_amount__lte=models.F('amount')),name='invoice_credit_positive')]

class ReinvestmentPlan(Scoped):
    name=models.CharField(max_length=200)
    allocated=models.DecimalField(max_digits=22,decimal_places=2)
    notes=models.TextField(blank=True)
    created_by=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)

class CashAccount(Scoped):
    name=models.CharField(max_length=100)
    kind=models.CharField(max_length=10,choices=[('bank','Bank'),('cash','Cash')])
    opening=models.DecimalField(max_digits=22,decimal_places=2,default=0)
    opening_date=models.DateField()
    class Meta: constraints=[models.UniqueConstraint(fields=['division','name'],name='cash_account_name_per_workspace')]
