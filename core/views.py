import csv,hashlib,io,json,secrets,time,uuid
from functools import wraps
from datetime import datetime
import pyotp
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate,login,logout
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError,ObjectDoesNotExist
from django.db import transaction,IntegrityError,connection
from django.http import HttpResponse,JsonResponse,HttpResponseForbidden,FileResponse
from django.shortcuts import render,redirect,get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST
from .models import *
from .finance import BusinessError,scenario,liquidity
from . import services,reports,contracts
from .security import require_role,rate_limit,verify_factor,require_reauth
NAV=[('dashboard','Overview','◈'),('sales','Sales & customers','↗'),('purchasing','Purchasing & suppliers','↙'),('production','Production & quality','▧'),('inventory','Inventory','▦'),('cash','Cash & banking','▤'),('accounting','Accounting','≡'),('funding','Funding & distributions','◇'),('decisions','Decisions & approvals','✓'),('contracts','Contracts & documents','▱'),('reports','Reports','▥'),('settings','Settings','⚙')]

def context(request,division,**extra):
    m=Membership.objects.filter(user=request.user,division=division,active=True).first()
    return {'division':division,'nav':NAV,'membership':m,'can_write':bool(m and m.role in ('operator','reviewer')),'is_operator':bool(m and m.role=='operator'),**extra}

def workspace_view(fn):
    @wraps(fn)
    def wrapped(request,division_id,*args,**kwargs):
        if not request.user.is_authenticated: return redirect('login')
        with transaction.atomic():
            with connection.cursor() as c: c.execute("SELECT set_config('app.user_id',%s,true)",[str(request.user.pk)])
            div=get_object_or_404(Division,pk=division_id)
            if settings.STAGING_PREVIEW and not div.is_demo: return HttpResponse(status=404)
            try:
                require_role(request.user,div,('operator','reader','reviewer'))
                if (settings.STAGING_PREVIEW or not div.is_demo) and not AuthFactor.objects.filter(user=request.user,enabled=True).exists(): return redirect('mfa')
                with transaction.atomic():
                    return fn(request,div,*args,**kwargs)
            except (BusinessError,ValidationError,ValueError,KeyError,ObjectDoesNotExist,IntegrityError) as e:
                # Do not leak database internals, object existence across tenants or sensitive payloads.
                message=str(e) if isinstance(e,(BusinessError,ValidationError)) else 'Invalid request or conflicting record. Review the current workspace and try again.'
                if request.path.startswith('/api/'): return JsonResponse({'error':message},status=400)
                return render(request,'core/error.html',context(request,div,error=message),status=400)
    return wrapped

def home(request):
    if not request.user.is_authenticated: return render(request,'core/welcome.html')
    memberships=Membership.objects.filter(user=request.user,active=True).exclude(role='technical').select_related('division')
    if settings.STAGING_PREVIEW: memberships=memberships.filter(division__is_demo=True)
    return render(request,'core/workspaces.html',{'memberships':memberships})

def login_view(request):
    error=None
    if request.method=='POST':
        username=request.POST.get('username','').strip().lower()
        if not rate_limit('login:'+username): error='Too many attempts. Wait five minutes.'
        else:
            user=authenticate(request,username=username,password=request.POST.get('password',''))
            if not user: error='Sign-in details could not be verified.'
            else:
                try:
                    verify_factor(user,request.POST.get('code',''),required=False)
                    login(request,user); return redirect('home')
                except BusinessError as e: error=str(e)
    return render(request,'core/login.html',{'error':error})

@require_POST
def logout_view(request): logout(request); return redirect('home')

@transaction.atomic
def enroll(request,token):
    token_hash=hashlib.sha256(token.encode()).hexdigest()
    inv=Invitation.objects.select_for_update().filter(token_hash=token_hash,accepted_at__isnull=True,expires_at__gt=timezone.now()).first()
    if not inv: return render(request,'core/login.html',{'error':'This invitation is invalid or expired.'},status=400)
    error=None
    if request.method=='POST':
        if not rate_limit('enroll:'+token_hash): return HttpResponse('Too many attempts',status=429)
        try:
            if User.objects.filter(username=inv.email.lower()).exists(): raise BusinessError('This account already exists; contact the governance administrator for linking review.')
            user=User(username=inv.email.lower(),email=inv.email,first_name=request.POST.get('name','')[:150])
            validate_password(request.POST.get('password',''),user); user.set_password(request.POST['password']); user.save()
            div=services.lock(inv.division)
            Membership.objects.create(division=div,user=user,role='operator',slot=inv.slot)
            inv.accepted_at=timezone.now(); inv.save(update_fields=['accepted_at']); services.audit(div,user,'invitation.accepted',inv.pk)
            # Initial operator enrollment also grants the matching slot in the
            # isolated sample workspace. A second human identity remains
            # necessary for new joint decisions in either workspace.
            if not div.is_demo:
                demo=Division.objects.filter(is_demo=True).first()
                if demo and not Membership.objects.filter(division=demo,slot=inv.slot,active=True).exists():
                    services.lock(demo)
                    Membership.objects.create(division=demo,user=user,role='operator',slot=inv.slot)
                    demo_inv=Invitation.objects.filter(division=demo,slot=inv.slot,accepted_at__isnull=True).first()
                    if demo_inv:
                        demo_inv.email=inv.email; demo_inv.accepted_at=timezone.now()
                        demo_inv.save(update_fields=['email','accepted_at'])
                    services.audit(demo,user,'test_workspace.access_granted',demo.pk,{'slot':inv.slot,'source_invitation':str(inv.pk)})
            login(request,user); return redirect('mfa')
        except (BusinessError,ValidationError) as e: error=str(e)
    return render(request,'core/enroll.html',{'invitation':inv,'error':error})

def mfa(request):
    if not request.user.is_authenticated: return redirect('login')
    factor=AuthFactor.objects.filter(user=request.user,enabled=True).first(); error=None
    if factor: return render(request,'core/mfa.html',{'enabled':True})
    if 'mfa_pending' not in request.session: request.session['mfa_pending']=pyotp.random_base32()
    secret=request.session['mfa_pending']
    if request.method=='POST':
        if not rate_limit('mfa:'+str(request.user.pk)): error='Too many attempts. Wait five minutes.'
        elif not request.user.check_password(request.POST.get('password','')): error='Password is incorrect.'
        elif not pyotp.TOTP(secret).verify(request.POST.get('code','')): error='Authenticator code is incorrect.'
        else:
            AuthFactor.objects.update_or_create(user=request.user,defaults={'secret':secret,'enabled':True,'last_counter':int(time.time())//30})
            del request.session['mfa_pending']; return redirect('home')
    return render(request,'core/mfa.html',{'secret':secret,'error':error})

def reauth(request):
    if not request.user.is_authenticated: return redirect('login')
    error=None
    if request.method=='POST':
        try:
            if not rate_limit('sign-auth:'+str(request.user.pk)): raise BusinessError('Too many attempts. Wait five minutes.')
            if not request.user.check_password(request.POST.get('password','')): raise BusinessError('Password is incorrect.')
            verify_factor(request.user,request.POST.get('code',''))
            request.session.cycle_key(); request.session['reauth_at']=time.time(); request.session['auth_event']=str(uuid.uuid4())
            return redirect('home')
        except BusinessError as e: error=str(e)
    return render(request,'core/reauth.html',{'error':error})

@workspace_view
def page(request,div,section='dashboard'):
    if section not in dict((x[0],x[1]) for x in NAV): return HttpResponse(status=404)
    r=reports.report(div)
    ctx=context(request,div,section=section,title=dict((x[0],x[1]) for x in NAV)[section],report=r)
    kinds={'sales':['customer','sales_order','delivery','customer_invoice','customer_return'],'purchasing':['supplier','purchase_order','goods_receipt','commitment'],'production':['mold','production_plan','production_release','quality_inspection','physical_count'],'funding':['funding_draft','commitment'],'dashboard':['product','mold','funding_draft','commitment','production_plan']}
    ctx['records']=Record.objects.filter(division=div,kind__in=kinds.get(section,[])).order_by('-created_at')
    if section=='dashboard': ctx.update(decisions=Decision.objects.filter(division=div).exclude(status__in=['closed','executed'])[:5],scenario=services.strings(scenario()),checks=div.configuration.get('go_live',[]))
    if section=='decisions': ctx['decisions']=Decision.objects.filter(division=div).order_by('-created_at')
    if section=='inventory': ctx['stocks']=Stock.objects.filter(division=div)
    if section=='cash':
        ctx.update(bank_rows=BankRow.objects.filter(division=div).select_related('matched_line'),bank_lines=Line.objects.filter(journal__division=div,account='bank'),forecast=reports.forecast(div))
    if section in ('accounting','reports','funding'): ctx.update(journals=Journal.objects.filter(division=div).prefetch_related('lines').order_by('-date'),forecast=reports.forecast(div),audit_ok=reports.verify_audit(div),statements=reports.statements(div))
    if section=='contracts': ctx.update(contracts=Contract.objects.filter(division=div),documents=Document.objects.filter(division=div).defer('content'))
    if section=='settings': ctx.update(invitations=Invitation.objects.filter(division=div),memberships=Membership.objects.filter(division=div).select_related('user'))
    return render(request,'core/page.html',ctx)

@workspace_view
def record_detail(request,div,record_id):
    r=get_object_or_404(Record,pk=record_id,division=div)
    return render(request,'core/record.html',context(request,div,record=r,data=services.canonical(r.data)))

@workspace_view
def fact_new(request,div):
    require_role(request.user,div,('operator','reviewer'))
    if request.method=='POST':
        r=services.log_fact(div,request.user,request.POST['kind'],request.POST['title'],json.loads(request.POST['data']))
        return redirect('record',division_id=div.pk,record_id=r.pk)
    return render(request,'core/fact_form.html',context(request,div))

@workspace_view
def decision_form(request,div,decision_id=None):
    require_role(request.user,div)
    d=get_object_or_404(Decision,pk=decision_id,division=div) if decision_id else None
    kind=request.POST.get('kind') or request.GET.get('kind') or (d.kind if d else 'resolution')
    if kind not in services.FIELDS: raise BusinessError('Unsupported decision kind.')
    current=d.versions.get(number=d.current_version).payload if d else {}
    if request.method=='POST':
        payload={key:request.POST.get(key,'') for key in services.FIELDS[kind]+services.COMMON}
        if 'lines' in payload: payload['lines']=json.loads(payload['lines'])
        payload['document_ids']=request.POST.getlist('document_ids')
        d=services.draft_decision(div,request.user,request.POST['title'],kind,payload,d.pk if d else None)
        return redirect('decision',division_id=div.pk,decision_id=d.pk)
    fields=[{'key':key,'label':key.replace('_',' ').title(),'value':current.get(key,''),'help':FIELD_HELP.get(key,'')} for key in services.COMMON+services.FIELDS[kind]]
    return render(request,'core/decision_form.html',context(request,div,decision=d,fields=fields,kind=kind,kinds=services.FIELDS,documents=Document.objects.filter(division=div).defer('content')))

FIELD_HELP={'reference':'Unique source reference. Repeated external postings with this reference will be rejected.','date':'Posting date, YYYY-MM-DD. Closed periods are protected.','effective_date':'Earliest execution date, YYYY-MM-DD.','vat_basis':'excluded, included, not_applicable or unknown. Sales cannot use unknown.','evidence_id':'UUID of private evidence uploaded under Contracts & documents.','stock_id':'Stock lot UUID from Inventory.','inspection':'Actual acceptance criteria and measured inspection results.','lines':'JSON list: [{"account":"bank","debit":"1000"},{"account":"equity","credit":"1000"}]','conditions':'Execution conditions to verify manually; approval does not perform a bank transfer.','charge_basis':'input_kg, good_output_kg, pieces or machine_hours.','classification':'loan, parent_current or proprietor — must match the reviewed legal relationship.'}

@workspace_view
def decision_detail(request,div,decision_id):
    d=get_object_or_404(Decision,pk=decision_id,division=div)
    v=d.versions.get(number=d.current_version)
    return render(request,'core/decision.html',context(request,div,decision=d,version=v,payload=json.dumps(v.payload,indent=2,ensure_ascii=False),versions=d.versions.prefetch_related('signatures__user').order_by('-number'),execution=Execution.objects.filter(decision=d).first()))

@require_POST
@workspace_view
def decision_action(request,div,decision_id,action):
    version=int(request.POST.get('version',0))
    if action=='sign':
        if not rate_limit('sign:'+str(request.user.pk),20): raise BusinessError('Signing rate limit reached.')
        services.sign(div,request.user,decision_id,version,request.POST['digest'],require_reauth(request))
    elif action=='execute':
        require_reauth(request)
        services.execute(div,request.user,decision_id,version,request.POST['idempotency_key'])
    else: services.transition(div,request.user,decision_id,version,action)
    return redirect('decision',division_id=div.pk,decision_id=decision_id)

@workspace_view
def api_decision(request,div,decision_id,action):
    if request.method!='POST': return JsonResponse({'error':'POST required'},status=405)
    p=json.loads(request.body)
    if action=='sign':
        if not rate_limit('sign:'+str(request.user.pk),20): raise BusinessError('Signing rate limit reached.')
        result=services.sign(div,request.user,decision_id,p['version'],p['digest'],require_reauth(request)); result={'status':result.status}
    elif action=='execute':
        require_reauth(request); ex=services.execute(div,request.user,decision_id,p['version'],p['idempotency_key']); result={'id':str(ex.pk),'result':ex.result}
    else: raise BusinessError('Unknown action.')
    return JsonResponse(result)

@workspace_view
def scenario_view(request,div):
    output=None
    if request.method=='POST':
        keys=['good','grams','rate','yield_percent','price','mold','paid','basis','resin_rate','extras','hours']
        output=scenario(**{k:request.POST[k] for k in keys},vat_inclusive=request.POST.get('vat_inclusive')=='on',includes_resin=request.POST.get('includes_resin')=='on')
    return render(request,'core/scenario.html',context(request,div,output=output))

@workspace_view
def repayment_proposal(request,div):
    result=None
    if request.method=='POST':
        result=liquidity(**{key:request.POST[key] for key in ('cash','tax','commitments','operating','next_cycle','reserve','principal')})
    fields=[('cash','Verified cash available'),('tax','Tax provision'),('commitments','Committed payments'),('operating','Operating needs'),('next_cycle','Next approved production cycle'),('reserve','Minimum cash reserve'),('principal','Verified funding principal')]
    return render(request,'core/repayment.html',context(request,div,result=result,fields=fields))

@workspace_view
def document_upload(request,div):
    if request.method=='POST':
        f=request.FILES['file']; services.upload(div,request.user,f.name,f.content_type,f.read(10*1024*1024+1),request.POST.get('replaces') or None)
        return redirect('page',division_id=div.pk,section='contracts')
    return render(request,'core/upload.html',context(request,div))

@workspace_view
def download(request,div,document_id):
    doc=get_object_or_404(Document,pk=document_id,division=div)
    if doc.scan_status!='clean' and not div.is_demo: raise BusinessError('File is quarantined pending a configured malware scanner. Live downloads are blocked.')
    return FileResponse(io.BytesIO(bytes(doc.content)),as_attachment=True,filename=doc.name,content_type='application/octet-stream')

@workspace_view
def contract_view(request,div,contract_id):
    c=get_object_or_404(Contract,pk=contract_id,division=div)
    if request.method=='POST':
        require_role(request.user,div); services.lock(div)
        if c.internal_decision_id: raise BusinessError('Approved contract fields are locked. Create a new contract draft for amendments.')
        c.fields={key:request.POST.get(key,'') for key in contracts.TEMPLATES[c.template][1]}; c.save(update_fields=['fields'])
        services.audit(div,request.user,'contract.draft_edited',c.pk,{'fields_hash':services.digest(c.fields)})
    return render(request,'core/contract.html',context(request,div,contract=c,fields=[{'key':k,'label':k.replace('_',' ').title(),'value':c.fields.get(k,'')} for k in contracts.TEMPLATES[c.template][1]],missing=contracts.missing(c)))

@workspace_view
def contract_pdf(request,div,contract_id):
    c=get_object_or_404(Contract,pk=contract_id,division=div)
    return FileResponse(io.BytesIO(contracts.pdf(c)),as_attachment=True,filename='lawyer-review-draft.pdf',content_type='application/pdf')

@require_POST
@workspace_view
def contract_evidence(request,div,contract_id):
    require_role(request.user,div); services.lock(div)
    c=get_object_or_404(Contract,pk=contract_id,division=div); doc=get_object_or_404(Document,pk=request.POST['document_id'],division=div)
    if not c.internal_decision_id: raise BusinessError('Internal approval is required before attaching execution evidence.')
    c.evidence=doc; c.status='uploaded_evidence_unverified'; c.save(update_fields=['evidence','status'])
    services.audit(div,request.user,'contract.evidence_uploaded',c.pk,{'document_hash':doc.sha256,'verified_provider':False})
    return redirect('contract',division_id=div.pk,contract_id=c.pk)

@workspace_view
def bank_import(request,div):
    if request.method=='POST':
        f=request.FILES['file']
        if f.size>2*1024*1024: raise BusinessError('CSV limit is 2 MB.')
        result=services.import_bank(div,request.user,f.read().decode('utf-8-sig'),request.POST['account_reference']); messages.success(request,f"Imported {result['inserted']} rows; skipped {result['duplicates']} duplicates.")
        return redirect('page',division_id=div.pk,section='cash')
    return render(request,'core/bank_import.html',context(request,div))

@require_POST
@workspace_view
def bank_match(request,div):
    services.match_bank(div,request.user,request.POST['row_id'],request.POST['line_id'])
    return redirect('page',division_id=div.pk,section='cash')

@workspace_view
def search(request,div):
    q=request.GET.get('q','').strip()[:100]
    rs=Record.objects.filter(division=div,title__icontains=q)[:30] if q else []
    ds=Decision.objects.filter(division=div,title__icontains=q)[:30] if q else []
    docs=Document.objects.filter(division=div,name__icontains=q).defer('content')[:30] if q else []
    return render(request,'core/search.html',context(request,div,query=q,records=rs,decisions=ds,documents=docs))

@workspace_view
def export(request,div,format):
    r=reports.report(div)
    if format=='csv':
        out=io.StringIO(); w=csv.writer(out); w.writerow(['Management trial balance — not statutory accounts']); w.writerow(['account','debit','credit','balance'])
        for x in r['trial_balance']: w.writerow([x['account'],str(x['debit']),str(x['credit']),str(x['balance'])])
        response=HttpResponse(out.getvalue(),content_type='text/csv'); response['Content-Disposition']='attachment; filename="trial-balance.csv"'; return response
    if format=='json':
        from django.core.serializers.json import DjangoJSONEncoder
        return JsonResponse(services.strings(dict(r,statements=reports.statements(div))),encoder=DjangoJSONEncoder)
    if format=='archive':
        if not div.is_demo and Document.objects.filter(division=div).exclude(scan_status='clean').exists(): raise BusinessError('Live archive downloads containing quarantined documents are blocked pending malware scanning.')
        from .archive import workspace_archive
        return FileResponse(io.BytesIO(workspace_archive(div)),as_attachment=True,filename='division-archive.zip',content_type='application/zip')
    raise BusinessError('Unsupported export format.')

def health(request): return JsonResponse({'status':'ok','live_execution':'disabled'})
