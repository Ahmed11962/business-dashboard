"""Tenant-scoped portable export. Full disaster recovery uses pg_dump separately."""
import base64,hashlib,io,json,zipfile
from django.core import serializers
from django.contrib.auth.models import User
from .models import *

def workspace_archive(division):
    buffer=io.BytesIO(); manifest={}; objects=[]
    # Exclude authentication secrets from user-facing portability exports.
    for model in [Record,Document,Decision,Execution,Journal,Stock,Movement,OpenItem,BankRow,Audit,Contract,Membership]:
        qs=model.objects.filter(division=division)
        if model is Document:
            for d in qs:
                name='documents/'+str(d.pk); raw=bytes(d.content); manifest[name]=hashlib.sha256(raw).hexdigest()
        objects.extend(list(qs))
    for qs in [DecisionVersion.objects.filter(decision__division=division),Signature.objects.filter(version__decision__division=division),Line.objects.filter(journal__division=division)]: objects.extend(list(qs))
    serialized=json.loads(serializers.serialize('json',[division.legal_entity,division,*objects]))
    for obj in serialized:
        if obj['model']=='core.document': obj['fields'].pop('content',None)
    raw=json.dumps(serialized,ensure_ascii=False,indent=2).encode(); manifest['records.json']=hashlib.sha256(raw).hexdigest()
    access=json.dumps(list(Membership.objects.filter(division=division).values('user_id','user__username','user__first_name','role','slot','active')),indent=2).encode()
    manifest['access.json']=hashlib.sha256(access).hexdigest()
    with zipfile.ZipFile(buffer,'w',zipfile.ZIP_DEFLATED) as z:
        z.writestr('records.json',raw); z.writestr('access.json',access)
        for d in Document.objects.filter(division=division): z.writestr('documents/'+str(d.pk),bytes(d.content))
        z.writestr('manifest.json',json.dumps(manifest,indent=2))
        z.writestr('README.txt','Private division portability export. Not a full disaster recovery backup. Auth credentials and MFA secrets are omitted. Verify manifest SHA-256 values. Use the database backup procedure for transactional restore including user access and original approval evidence.')
    return buffer.getvalue()
