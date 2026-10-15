"""Small, direct screens for the manufacturing workflow."""
from datetime import date
from decimal import Decimal
from django import forms
from django.contrib import messages
from django.db.models import Q, Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST
from .finance import BusinessError, decimal, money
from .models import (Mold, Product, ProductionBatch, SalesInvoice, InvoiceLine, StockEvent,
                     WorkflowAttachment, FinanceTransaction, CapitalContribution, CashAccount, ReinvestmentPlan, InvoiceCredit, SimpleDecision)
from .manufacturing import (production_cost, batch_cost, balance, net_payments, invoice_total, invoice_revenue,
    invoice_received, record_payment, receive, dispatch, return_goods, writeoff,
    manufacturing_totals, repayment_plan, distribution_plan)
from .manufacturing import issue_credit, capital_outstanding, repay_capital, cash_forecast
from .simple_finance import summary, account_balances
from .security import require_role
from .views import workspace_view, context
from . import services

def ctx(request,div,section,title,**kwargs):
    return context(request,div,section=section,title=title,**kwargs)

def upload_files(request,div,**parent):
    for item in request.FILES.getlist('files'):
        doc=services.upload(div,request.user,item.name,item.content_type,item.read(10*1024*1024+1))
        source=next(iter(parent.values()))
        link=WorkflowAttachment.objects.create(document=doc,category=source.__class__.__name__[:80],
            supplier=getattr(source,'supplier',getattr(source,'manufacturer',getattr(source,'customer','')))[:200],
            reference=getattr(source,'code',getattr(source,'number',''))[:100],**parent)
        services.audit(div,request.user,'workflow.document_linked',doc.pk,{'parent':str(source.pk),'type':link.category})

def upload_image(request,div):
    item=request.FILES.get('image')
    if not item: return None
    doc=services.upload(div,request.user,item.name,item.content_type,item.read(10*1024*1024+1))
    if doc.media_type not in ('image/png','image/jpeg'): raise BusinessError('Picture must be a PNG or JPG image.')
    return doc

def save_form(form,div,user,event):
    services.lock(div)
    previous=None
    if form.instance.pk:
        old=form._meta.model.objects.filter(pk=form.instance.pk,division=div).values(*form.fields.keys()).first()
        previous={k:str(v) if v is not None else None for k,v in old.items()} if old else None
    item=form.save(commit=False); item.division=div; item.save()
    services.audit(div,user,event,item.pk,{'before':previous,'after':{k:str(v) for k,v in form.cleaned_data.items() if k!='image'}})
    return item

class ProductForm(forms.ModelForm):
    class Meta:
        model=Product; fields=['name','sku','default_price','notes']

class MoldForm(forms.ModelForm):
    class Meta:
        model=Mold; fields=['name','code','product','supplier','purchase_date','price','expected_date','status','ownership_confirmed','notes']
        widgets={'purchase_date':forms.DateInput(attrs={'type':'date'}),'expected_date':forms.DateInput(attrs={'type':'date'})}
    def __init__(self,*args,division=None,**kwargs):
        super().__init__(*args,**kwargs); self.fields['product'].queryset=Product.objects.filter(division=division)
        if self.instance._state.adding: self.fields['purchase_date'].initial=timezone.localdate()
    def clean(self):
        p=super().clean()
        if p.get('price') is not None and not self.instance._state.adding and p['price']<net_payments(self.instance):
            self.add_error('price','Purchase price cannot be less than net payments.')
        if not self.instance._state.adding and self.instance.batches.exists() and p.get('product') and p['product'].pk!=self.instance.product_id:
            self.add_error('product','A mold with production history cannot change product.')
        return p

class BatchForm(forms.ModelForm):
    class Meta:
        model=ProductionBatch
        fields=['number','mold','manufacturer','order_date','expected_date','quantity','weight_grams','price_per_gram','setup_cost','packaging_cost','transport_cost','other_cost','quoted_cost','final_cost','status','notes']
        widgets={'order_date':forms.DateInput(attrs={'type':'date'}),'expected_date':forms.DateInput(attrs={'type':'date'})}
        labels={'quoted_cost':'Supplier agreed / quoted total (optional)','final_cost':'Final actual total (optional)'}
    def __init__(self,*args,division=None,**kwargs):
        super().__init__(*args,**kwargs); self.fields['mold'].queryset=Mold.objects.filter(division=division)
        if self.instance._state.adding: self.fields['order_date'].initial=timezone.localdate()
    def clean(self):
        p=super().clean()
        if all(p.get(k) is not None for k in ('quantity','weight_grams','price_per_gram','setup_cost','packaging_cost','transport_cost','other_cost')):
            production_cost(*(p[k] for k in ('quantity','weight_grams','price_per_gram','setup_cost','packaging_cost','transport_cost','other_cost')))
        if not self.instance._state.adding and self.instance.stockevent_set.exists():
            locked=('mold','quantity','weight_grams','price_per_gram','setup_cost','packaging_cost','transport_cost','other_cost','quoted_cost','final_cost')
            for key in locked:
                if key in p and p[key]!=getattr(self.instance,key): self.add_error(key,'Cost and quantity are locked after the first receipt.')
        if not self.instance._state.adding and p.get('status')=='cancelled' and (self.instance.payments.exists() or self.instance.stockevent_set.exists()):
            self.add_error('status','An order with payments or receipts cannot be cancelled.')
        if not self.instance._state.adding and all(p.get(k) is not None for k in ('quantity','weight_grams','price_per_gram','setup_cost','packaging_cost','transport_cost','other_cost')):
            agreed=p.get('final_cost') if p.get('final_cost') is not None else p.get('quoted_cost')
            if agreed is None: agreed=production_cost(*(p[k] for k in ('quantity','weight_grams','price_per_gram','setup_cost','packaging_cost','transport_cost','other_cost')))['total']
            if agreed<net_payments(self.instance): self.add_error('quoted_cost','Agreed cost cannot be less than net payments.')
        return p

class InvoiceForm(forms.ModelForm):
    class Meta:
        model=SalesInvoice; fields=['number','customer','date','due_date','discount','tax_treatment','tax','notes']
        widgets={'date':forms.DateInput(attrs={'type':'date'}),'due_date':forms.DateInput(attrs={'type':'date'})}
        labels={'tax':'Tax amount, if applicable (SAR)'}
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs); self.fields['date'].initial=timezone.localdate(); self.fields['tax_treatment'].initial='unconfirmed'
    def clean(self):
        p=super().clean()
        for key in ('discount','tax'):
            if p.get(key) is not None and p[key]<0: self.add_error(key,'Amount cannot be negative.')
        if p.get('tax_treatment') in ('zero_rated','exempt','not_applicable') and p.get('tax'):
            self.add_error('tax','This treatment cannot have a tax amount.')
        return p

def photo_url(div,doc):
    return reverse('simple_document_preview',args=[div.pk,doc.pk]) if doc else ''

@workspace_view
def dashboard(request,div):
    from .simple import filters
    start,end,category=filters(request)
    totals=manufacturing_totals(div,start,end,category); cash=summary(div,start,end,category); balances=account_balances(div)
    accounts=[]
    for account in CashAccount.objects.filter(division=div):
        movement=sum((t.amount if t.direction=='received' else -t.amount for t in account.transactions.filter(date__gt=account.opening_date)),Decimal(0))
        accounts.append((account,account.opening+movement))
    known_cash=sum((value for _,value in accounts),Decimal(0)) if accounts else None
    if known_cash is None and all(value is not None for value in balances.values()): known_cash=sum(balances.values(),Decimal(0))
    return render(request,'core/mfg_dashboard.html',ctx(request,div,'dashboard','Dashboard',totals=totals,cash=cash,balances=balances,
        accounts=accounts,known_cash=known_cash,
        available_cash=max(Decimal(0),known_cash-totals['mold_due']-totals['production_due']-totals['funding_due']-totals['customer_credit_due']) if known_cash is not None else None,
        pending=SimpleDecision.objects.filter(division=div,status='pending')[:4],molds=Mold.objects.filter(division=div).order_by('-created_at')[:4],
        batches=ProductionBatch.objects.filter(division=div).exclude(status__in=['completed','cancelled'])[:4],
        transactions=FinanceTransaction.objects.filter(division=div).order_by('-date','-created_at')[:6],
        categories=FinanceTransaction.objects.filter(division=div).order_by('category').values_list('category',flat=True).distinct()))

@workspace_view
def molds(request,div):
    qs=Mold.objects.filter(division=div).select_related('product','image').prefetch_related('payments')
    q=request.GET.get('q','')[:100]
    if q: qs=qs.filter(Q(name__icontains=q)|Q(code__icontains=q)|Q(supplier__icontains=q)|Q(product__name__icontains=q))
    rows=[{'item':m,'paid':net_payments(m),'due':balance(m),'percent':min(100,int(net_payments(m)/m.price*100)) if m.price else 100,
           'image':photo_url(div,m.image),'owned':balance(m)<=0 and m.ownership_confirmed} for m in qs.order_by('-created_at')[:200]]
    return render(request,'core/mfg_molds.html',ctx(request,div,'molds','Molds',rows=rows))

@workspace_view
def mold_form(request,div,item_id=None):
    require_role(request.user,div,('operator',))
    item=get_object_or_404(Mold,division=div,pk=item_id) if item_id else None
    form=MoldForm(request.POST or None,instance=item,division=div)
    if request.method=='POST' and form.is_valid():
        obj=save_form(form,div,request.user,'mold.updated' if item else 'mold.created')
        image=upload_image(request,div)
        if image:
            old=obj.image_id; obj.image=image; obj.save(update_fields=['image'])
            services.audit(div,request.user,'mold.picture_changed',obj.pk,{'old':str(old) if old else None,'new':str(image.pk)})
        upload_files(request,div,mold=obj)
        return redirect('mfg_mold',division_id=div.pk,item_id=obj.pk)
    return render(request,'core/mfg_form.html',ctx(request,div,'molds','Mold',form=form,heading='Edit mold' if item else 'Add mold',item=item,upload=True))

@workspace_view
def mold_detail(request,div,item_id):
    item=get_object_or_404(Mold.objects.select_related('product','image'),division=div,pk=item_id)
    return render(request,'core/mfg_mold_detail.html',ctx(request,div,'molds',item.name,item=item,paid=net_payments(item),due=balance(item),
        image=photo_url(div,item.image),payments=item.payments.order_by('-date'),batches=item.batches.order_by('-order_date'),
        attachments=item.attachments.select_related('document')))

@workspace_view
def products(request,div):
    qs=Product.objects.filter(division=div).select_related('image')
    q=request.GET.get('q','')[:100]
    if q: qs=qs.filter(Q(name__icontains=q)|Q(sku__icontains=q))
    rows=[]
    for item in qs.order_by('name').prefetch_related('molds','stock_events')[:200]:
        events=list(item.stock_events.all())
        average=money(item.inventory_value/item.quantity) if item.quantity else Decimal(0)
        rows.append({'item':item,'received':sum(e.accepted for e in events if e.kind=='receipt'),
            'sold':-sum(e.quantity for e in events if e.kind in ('dispatch','return')),
            'damaged':-sum(e.quantity for e in events if e.kind=='damage'),
            'available':item.quantity-item.reserved,'average':average,'margin':money(item.default_price-average),
            'molds':item.molds.all()})
    return render(request,'core/mfg_products.html',ctx(request,div,'products','Products & Inventory',rows=rows))

@workspace_view
def product_form(request,div,item_id=None):
    require_role(request.user,div,('operator',))
    item=get_object_or_404(Product,division=div,pk=item_id) if item_id else None
    form=ProductForm(request.POST or None,instance=item)
    if request.method=='POST' and form.is_valid():
        obj=save_form(form,div,request.user,'product.updated' if item else 'product.created')
        image=upload_image(request,div)
        if image:
            old=obj.image_id; obj.image=image; obj.save(update_fields=['image'])
            services.audit(div,request.user,'product.picture_changed',obj.pk,{'old':str(old) if old else None,'new':str(image.pk)})
        upload_files(request,div,product=obj)
        return redirect('mfg_product',division_id=div.pk,item_id=obj.pk)
    return render(request,'core/mfg_form.html',ctx(request,div,'products','Product',form=form,heading='Edit product' if item else 'Add product',item=item,upload=True))

@workspace_view
def product_detail(request,div,item_id):
    item=get_object_or_404(Product.objects.select_related('image'),division=div,pk=item_id)
    events=item.stock_events.select_related('batch','invoice_line__invoice').order_by('-created_at')
    return render(request,'core/mfg_product_detail.html',ctx(request,div,'products',item.name,item=item,
        image=photo_url(div,item.image),available=item.quantity-item.reserved,
        average=money(item.inventory_value/item.quantity) if item.quantity else 0,
        margin=money(item.default_price-(money(item.inventory_value/item.quantity) if item.quantity else Decimal(0))),
        received=sum(e.accepted for e in events if e.kind=='receipt'),
        sold=-sum(e.quantity for e in events if e.kind in ('dispatch','return')),
        damaged=-sum(e.quantity for e in events if e.kind=='damage'),events=events[:100],
        attachments=item.attachments.select_related('document')))

@workspace_view
def batches(request,div):
    qs=ProductionBatch.objects.filter(division=div).select_related('mold__product')
    q=request.GET.get('q','')[:100]
    if q: qs=qs.filter(Q(number__icontains=q)|Q(mold__name__icontains=q)|Q(manufacturer__icontains=q))
    rows=[{'item':b,'cost':batch_cost(b),'paid':net_payments(b),'due':balance(b),
           'received':sum(e.accepted for e in b.stockevent_set.filter(kind='receipt'))} for b in qs.order_by('-order_date')[:200]]
    return render(request,'core/mfg_batches.html',ctx(request,div,'production','Production',rows=rows))

@workspace_view
def batch_form(request,div,item_id=None):
    require_role(request.user,div,('operator',))
    item=get_object_or_404(ProductionBatch,division=div,pk=item_id) if item_id else None
    form=BatchForm(request.POST or None,instance=item,division=div)
    if request.method=='POST' and form.is_valid():
        obj=save_form(form,div,request.user,'batch.updated' if item else 'batch.created')
        upload_files(request,div,batch=obj)
        return redirect('mfg_batch',division_id=div.pk,item_id=obj.pk)
    return render(request,'core/mfg_form.html',ctx(request,div,'production','Production',form=form,heading='Edit production order' if item else 'New production order',item=item,upload=True))

@workspace_view
def batch_detail(request,div,item_id):
    item=get_object_or_404(ProductionBatch.objects.select_related('mold__product'),division=div,pk=item_id)
    events=item.stockevent_set.order_by('-created_at')
    return render(request,'core/mfg_batch_detail.html',ctx(request,div,'production',item.number,item=item,cost=batch_cost(item),
        paid=net_payments(item),due=balance(item),received=sum(e.accepted for e in events if e.kind=='receipt'),
        events=events,payments=item.payments.order_by('-date'),attachments=item.attachments.select_related('document')))

@workspace_view
def invoices(request,div):
    qs=SalesInvoice.objects.filter(division=div).prefetch_related('lines','payments')
    q=request.GET.get('q','')[:100]
    if q: qs=qs.filter(Q(number__icontains=q)|Q(customer__icontains=q))
    rows=[{'item':x,'total':invoice_total(x),'received':invoice_received(x),'due':balance(x),
           'overdue':bool(x.due_date and x.due_date<timezone.localdate() and balance(x)>0)} for x in qs.order_by('-date')[:200]]
    return render(request,'core/mfg_invoices.html',ctx(request,div,'sales','Sales & Invoices',rows=rows))

@workspace_view
def invoice_new(request,div):
    require_role(request.user,div,('operator',))
    form=InvoiceForm(request.POST or None)
    products=Product.objects.filter(division=div).order_by('name')
    if request.method=='POST' and form.is_valid():
        ids=request.POST.getlist('product'); quantities=request.POST.getlist('quantity'); prices=request.POST.getlist('unit_price')
        if not (len(ids)==len(quantities)==len(prices) and ids): raise BusinessError('Add at least one product line.')
        lines=[]
        for product_id,qty,price in zip(ids,quantities,prices):
            if not product_id and not qty and not price: continue
            product=get_object_or_404(Product,division=div,pk=product_id)
            units=int(decimal(qty,positive=True))
            if decimal(qty)!=units: raise BusinessError('Invoice quantities must be whole units.')
            lines.append((product,units,money(decimal(price,nonnegative=True))))
        if not lines: raise BusinessError('Add at least one product line.')
        subtotal=sum((p*q for _,q,p in lines),Decimal(0))
        if form.cleaned_data['discount']>subtotal: raise BusinessError('Discount exceeds subtotal.')
        services.lock(div)
        invoice=form.save(commit=False); invoice.division=div; invoice.save()
        for product,units,price in lines: InvoiceLine.objects.create(invoice=invoice,product=product,quantity=units,unit_price=price)
        upload_files(request,div,invoice=invoice)
        services.audit(div,request.user,'invoice.issued',invoice.pk,{'number':invoice.number,'total':str(invoice_total(invoice))})
        return redirect('mfg_invoice',division_id=div.pk,item_id=invoice.pk)
    return render(request,'core/mfg_invoice_form.html',ctx(request,div,'sales','Create sale',form=form,products=products))

@workspace_view
def invoice_detail(request,div,item_id):
    item=get_object_or_404(SalesInvoice,division=div,pk=item_id)
    return render(request,'core/mfg_invoice_detail.html',ctx(request,div,'sales',item.number,item=item,lines=item.lines.select_related('product'),
        total=invoice_total(item),revenue=invoice_revenue(item),received=invoice_received(item),due=balance(item),payments=item.payments.order_by('-date'),
        events=StockEvent.objects.filter(invoice_line__invoice=item).select_related('product').order_by('-created_at'),
        credits=item.credits.order_by('-created_at'),attachments=item.attachments.select_related('document')))

@require_POST
@workspace_view
def action(request,div,kind,item_id):
    require_role(request.user,div,('operator',))
    ref=request.POST.get('reference','').strip()[:100]
    if not ref: raise BusinessError('Enter a unique reference for this action.')
    if kind=='receive':
        item=get_object_or_404(ProductionBatch,division=div,pk=item_id)
        receive(div,request.user,item,request.POST.get('accepted','0'),request.POST.get('rejected','0'),request.POST.get('damaged','0'),ref)
        upload_files(request,div,batch=item)
        return redirect('mfg_batch',division_id=div.pk,item_id=item.pk)
    if kind=='dispatch':
        item=get_object_or_404(InvoiceLine,invoice__division=div,pk=item_id)
        dispatch(div,request.user,item,request.POST.get('quantity',''),ref)
        upload_files(request,div,invoice=item.invoice)
        return redirect('mfg_invoice',division_id=div.pk,item_id=item.invoice_id)
    if kind=='return':
        item=get_object_or_404(StockEvent,division=div,kind='dispatch',pk=item_id)
        return_goods(div,request.user,item,request.POST.get('quantity',''),ref)
        return redirect('mfg_invoice',division_id=div.pk,item_id=item.invoice_line.invoice_id)
    if kind=='damage':
        item=get_object_or_404(Product,division=div,pk=item_id)
        writeoff(div,request.user,item,request.POST.get('quantity',''),ref,request.POST.get('reason','')[:250])
        return redirect('mfg_product',division_id=div.pk,item_id=item.pk)
    if kind=='adjust':
        from .manufacturing import adjust_stock
        item=get_object_or_404(Product,division=div,pk=item_id)
        adjust_stock(div,request.user,item,request.POST.get('change',''),ref,request.POST.get('reason',''),request.POST.get('unit_cost','0'))
        return redirect('mfg_product',division_id=div.pk,item_id=item.pk)
    if kind=='cancel':
        item=get_object_or_404(SalesInvoice,division=div,pk=item_id)
        if item.payments.exists() or item.credits.exists() or StockEvent.objects.filter(invoice_line__invoice=item).exists():
            raise BusinessError('An invoice with payments or dispatches needs a credit or return, not cancellation.')
        item.status='cancelled'; item.save(update_fields=['status'])
        services.audit(div,request.user,'invoice.cancelled',item.pk,{'number':item.number})
        return redirect('mfg_invoice',division_id=div.pk,item_id=item.pk)
    if kind=='credit':
        item=get_object_or_404(SalesInvoice,division=div,pk=item_id)
        issue_credit(div,request.user,item,request.POST.get('amount',''),ref,request.POST.get('reason',''),request.POST.get('tax_amount','0'))
        return redirect('mfg_invoice',division_id=div.pk,item_id=item.pk)
    raise BusinessError('Unknown action.')

@workspace_view
def payment(request,div,kind,item_id):
    require_role(request.user,div,('operator',))
    models={'mold':Mold,'batch':ProductionBatch,'invoice':SalesInvoice}
    if kind not in models: raise BusinessError('Unknown payment type.')
    item=get_object_or_404(models[kind],division=div,pk=item_id)
    if request.method=='POST':
        account=CashAccount.objects.filter(division=div,pk=request.POST.get('account')).first() if request.POST.get('account') else None
        if request.POST.get('account') and not account: raise BusinessError('Choose an account in this workspace.')
        if account and account.kind!=request.POST.get('method','bank'): raise BusinessError('Account and payment method must match.')
        plan=ReinvestmentPlan.objects.filter(division=div,pk=request.POST.get('reinvestment_plan')).first() if request.POST.get('reinvestment_plan') else None
        if request.POST.get('reinvestment_plan') and not plan: raise BusinessError('Choose a reinvestment plan in this workspace.')
        if plan and kind=='invoice': raise BusinessError('A customer collection is not reinvestment spending.')
        refund=FinanceTransaction.objects.filter(division=div,pk=request.POST.get('refund_of')).first() if request.POST.get('refund_of') else None
        if request.POST.get('refund_of') and not refund: raise BusinessError('Choose an earlier payment in this workspace.')
        try: paid_on=date.fromisoformat(request.POST.get('date',''))
        except ValueError: raise BusinessError('Enter a valid payment date.')
        t=record_payment(div,request.user,item,request.POST.get('amount',''),request.POST.get('reference',''),paid_on,
                         request.POST.get('method','bank'),request.POST.get('party','')[:200],request.POST.get('notes',''),account,refund)
        if plan:
            t.reinvestment_plan=plan; t.save(update_fields=['reinvestment_plan'])
        from .simple import files
        files(request,div,{'transaction':t})
        return redirect('mfg_'+kind,division_id=div.pk,item_id=item.pk)
    return render(request,'core/mfg_payment.html',ctx(request,div,'finances','Record payment',item=item,kind=kind,due=balance(item),
        accounts=CashAccount.objects.filter(division=div),plans=ReinvestmentPlan.objects.filter(division=div),payments=item.payments.order_by('-date'),today=timezone.localdate()))

@workspace_view
def finances(request,div):
    totals=manufacturing_totals(div); cash=summary(div); balances=account_balances(div)
    accounts=[]
    for account in CashAccount.objects.filter(division=div):
        movement=sum((t.amount if t.direction=='received' else -t.amount for t in account.transactions.filter(date__gt=account.opening_date)),Decimal(0))
        accounts.append((account,account.opening+movement))
    capital=CapitalContribution.objects.filter(division=div).select_related('transaction')
    capital_rows=[{'item':c,'outstanding':capital_outstanding(c),'repaid':sum((r.transaction.amount for r in c.repayments.select_related('transaction')),Decimal(0))} for c in capital]
    plans=ReinvestmentPlan.objects.filter(division=div)
    plan_rows=[]
    for p in plans:
        spent=sum((t.amount if t.direction=='paid' else -t.amount for t in p.spending.all()),Decimal(0))
        plan_rows.append({'item':p,'spent':spent,'remaining':p.allocated-spent})
    return render(request,'core/mfg_finances.html',ctx(request,div,'finances','Finances',totals=totals,cash=cash,balances=balances,
        accounts=accounts,capital=capital_rows,plans=plan_rows,entries=FinanceTransaction.objects.filter(division=div).order_by('-date')[:30]))

@require_POST
@workspace_view
def finance_action(request,div,kind):
    require_role(request.user,div,('operator',)); services.lock(div)
    if kind=='account':
        if request.POST.get('account_kind') not in ('bank','cash'): raise BusinessError('Choose bank or cash.')
        account=CashAccount.objects.create(division=div,name=request.POST.get('name','').strip()[:100],
            kind=request.POST.get('account_kind','bank'),opening=money(request.POST.get('opening','0')),
            opening_date=date.fromisoformat(request.POST.get('date','')))
        services.audit(div,request.user,'cash_account.created',account.pk,{'name':account.name,'opening':str(account.opening)})
    elif kind=='capital':
        amount=money(decimal(request.POST.get('amount',''),positive=True)); reference=request.POST.get('reference','').strip()
        if not reference: raise BusinessError('Contribution reference is required.')
        funding_kind=request.POST.get('funding_kind','undetermined')
        if funding_kind not in ('undetermined','repayable','equity'): raise BusinessError('Choose a valid funding type.')
        if funding_kind=='repayable' and not request.POST.get('contributor','').strip(): raise BusinessError('Name the contributor for repayable funding.')
        if request.POST.get('method','bank') not in ('bank','cash','other'): raise BusinessError('Choose a valid payment method.')
        account=CashAccount.objects.filter(division=div,pk=request.POST.get('account')).first() if request.POST.get('account') else None
        if request.POST.get('account') and not account: raise BusinessError('Choose an account in this workspace.')
        if account and account.kind!=request.POST.get('method','bank'): raise BusinessError('Account and method must match.')
        t=FinanceTransaction.objects.create(division=div,date=date.fromisoformat(request.POST.get('date','')),
            direction='received',amount=amount,category='Capital contribution',description='Capital contribution',
            party=request.POST.get('contributor','').strip()[:200],reference=reference,method=request.POST.get('method','bank'),
            treatment='none',recognized_amount=0,created_by=request.user,account=account)
        from .models import TransactionRevision
        from .simple import snapshot
        TransactionRevision.objects.create(transaction=t,actor=request.user,snapshot=snapshot(t))
        item=CapitalContribution.objects.create(division=div,contributor=t.party,kind=funding_kind,
            terms=request.POST.get('terms',''),transaction=t)
        from .simple import files
        files(request,div,{'transaction':t})
        services.audit(div,request.user,'capital.contributed',item.pk,{'amount':str(amount),'kind':item.kind})
    elif kind=='reinvestment':
        item=ReinvestmentPlan.objects.create(division=div,name=request.POST.get('name','')[:200],
            allocated=money(decimal(request.POST.get('allocated',''),nonnegative=True)),
            notes=request.POST.get('notes',''),created_by=request.user)
        services.audit(div,request.user,'reinvestment.planned',item.pk,{'allocated':str(item.allocated)})
    elif kind=='classify':
        contribution=get_object_or_404(CapitalContribution,division=div,pk=request.POST.get('contribution'))
        funding_kind=request.POST.get('funding_kind')
        if funding_kind not in ('undetermined','repayable','equity'): raise BusinessError('Choose a valid funding type.')
        if contribution.repayments.exists() and funding_kind!='repayable': raise BusinessError('A contribution with repayments must remain classified as repayable.')
        contributor=request.POST.get('contributor','').strip()[:200]
        if funding_kind=='repayable' and not contributor: raise BusinessError('Name the contributor for repayable funding.')
        previous={'contributor':contribution.contributor,'kind':contribution.kind,'terms':contribution.terms}
        contribution.contributor=contributor; contribution.kind=funding_kind; contribution.terms=request.POST.get('terms','')
        contribution.save(update_fields=['contributor','kind','terms'])
        services.audit(div,request.user,'capital.classified',contribution.pk,{'before':previous,'after':{'contributor':contributor,'kind':funding_kind,'terms':contribution.terms}})
    elif kind=='repayment':
        contribution=get_object_or_404(CapitalContribution,division=div,pk=request.POST.get('contribution'))
        account=CashAccount.objects.filter(division=div,pk=request.POST.get('account')).first() if request.POST.get('account') else None
        if request.POST.get('account') and not account: raise BusinessError('Choose an account in this workspace.')
        r=repay_capital(div,request.user,contribution,request.POST.get('amount',''),request.POST.get('reference',''),
                        date.fromisoformat(request.POST.get('date','')),account,request.POST.get('method','bank'))
        from .simple import files
        files(request,div,{'transaction':r.transaction})
    else: raise BusinessError('Unknown finance action.')
    return redirect('mfg_finances',division_id=div.pk)

@workspace_view
def calculators(request,div):
    repay=distribution=production=forecast=None
    if request.method=='POST':
        kind=request.POST.get('kind')
        if kind=='production':
            production=production_cost(request.POST.get('quantity',''),request.POST.get('grams',''),request.POST.get('price_per_gram',''),
                request.POST.get('extra','0'))
        elif kind=='repayment':
            repay=repayment_plan(request.POST.get('owed',''),request.POST.get('repaid','0'),request.POST.get('months','60'),
                request.POST.get('annual_rate','0'),request.POST.get('extra','0'),request.POST.get('start') or None)
        elif kind=='distribution':
            distribution=distribution_plan(request.POST.get('profit',''),request.POST.get('cash',''),request.POST.get('retention','50'),
                request.POST.get('reserves','0'),request.POST.get('liabilities','0'),request.POST.get('taxes','0'),
                request.POST.get('sayem_repayment','0'),request.POST.get('sami_repayment','0'))
        elif kind=='forecast':
            forecast=cash_forecast(request.POST.get('opening',''),request.POST.get('monthly_in',''),request.POST.get('monthly_out',''),
                request.POST.get('months',''),request.POST.get('one_time','0'),request.POST.get('repayment','0'))
        else: raise BusinessError('Unknown calculator.')
    return render(request,'core/mfg_calculators.html',ctx(request,div,'dashboard','Decision Center',production=production,
        repayment=repay,distribution=distribution,forecast=forecast,totals=manufacturing_totals(div)))

@workspace_view
def invoice_pdf(request,div,item_id):
    item=get_object_or_404(SalesInvoice,division=div,pk=item_id)
    import io,re
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    buffer=io.BytesIO(); pdf=canvas.Canvas(buffer,pagesize=A4)
    pdf.setFont('Helvetica-Bold',16); pdf.drawString(48,800,'INTERNAL SALES DOCUMENT')
    pdf.setFont('Helvetica',10); pdf.drawString(48,780,'Not a verified ZATCA tax invoice')
    pdf.drawString(48,750,f'Invoice {item.number}  |  {item.date}  |  {item.customer}'[:95]); y=715
    for line in item.lines.select_related('product'):
        if y<110:
            pdf.showPage(); pdf.setFont('Helvetica',10); y=800
        pdf.drawString(48,y,f'{line.product.name[:35]}   {line.quantity} x SAR {line.unit_price} = SAR {line.quantity*line.unit_price}'); y-=20
    if y<110: pdf.showPage(); pdf.setFont('Helvetica',10); y=800
    pdf.drawString(48,y-12,f'Discount: SAR {item.discount}   Tax treatment: {item.get_tax_treatment_display()}   Tax amount: SAR {item.tax}')
    pdf.drawString(48,y-34,f'Total: SAR {invoice_total(item)}   Received: SAR {invoice_received(item)}   Due: SAR {balance(item)}')
    pdf.save(); response=HttpResponse(buffer.getvalue(),content_type='application/pdf')
    safe_number=re.sub('[^A-Za-z0-9_-]','_',item.number)[:80]
    response['Content-Disposition']=f'attachment; filename="internal-invoice-{safe_number}.pdf"'
    return response
