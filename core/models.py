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
