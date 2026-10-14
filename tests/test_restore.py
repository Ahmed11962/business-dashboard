import hashlib,os,uuid
from pathlib import Path
from urllib.parse import urlsplit,urlunsplit
import pytest,psycopg,pgserver
from django.db import connection
from core.models import *
from core import services
from scripts.backup import run
from .conftest import perform
pytestmark=pytest.mark.django_db(transaction=True)

def test_clean_database_restore_with_documents_approvals_and_access(world,tmp_path):
    d,a,b,doc=world
    ex=perform(world,'funding_direct',amount='10000',party='Test funder',classification='loan',evidence_id=str(doc.pk))
    params=connection.get_connection_params()
    source=psycopg.conninfo.make_conninfo(**{k:v for k,v in params.items() if k in ('dbname','user','password','host','port')})
    # backup helper takes URLs. Preserve Unix-socket hosts via query parameters.
    from urllib.parse import urlencode,quote
    host=params.get('host',''); user=params.get('user',''); db=params['dbname']; port=params.get('port','5432')
    url=f'postgresql://{quote(user)}@/{db}?'+urlencode({'host':host,'port':port})
    target_name='restore_'+uuid.uuid4().hex[:12]
    target_url=f'postgresql://{quote(user)}@/{target_name}?'+urlencode({'host':host,'port':port})
    bin_dir=Path(pgserver.__file__).parent/'pginstall'/'bin'
    backup=tmp_path/'business.dump'
    run('backup',url,backup,bin_dir)
    with psycopg.connect(source,autocommit=True) as admin: admin.execute(psycopg.sql.SQL('CREATE DATABASE {}').format(psycopg.sql.Identifier(target_name)))
    try:
        run('restore',target_url,backup,bin_dir)
        with psycopg.connect(target_url) as restored:
            assert restored.execute('SELECT count(*) FROM core_journal').fetchone()[0]==1
            assert restored.execute('SELECT count(*) FROM core_signature').fetchone()[0]==2
            assert restored.execute('SELECT count(*) FROM core_execution').fetchone()[0]==1
            assert restored.execute('SELECT count(*) FROM core_membership WHERE active').fetchone()[0]==2
            assert restored.execute('SELECT count(*) FROM auth_user WHERE password <> %s',['']).fetchone()[0]==2
            raw,sha=restored.execute('SELECT content,sha256 FROM core_document WHERE id=%s',[doc.pk]).fetchone()
            assert bytes(raw)==bytes(doc.content) and hashlib.sha256(bytes(raw)).hexdigest()==sha
            assert restored.execute('SELECT SUM(debit)-SUM(credit) FROM core_line').fetchone()[0]==0
            assert restored.execute('SELECT count(*) FROM core_audit').fetchone()[0]==Audit.objects.count()
        with pytest.raises(RuntimeError,match='new empty'): run('restore',target_url,backup,bin_dir)
    finally:
        with psycopg.connect(source,autocommit=True) as admin: admin.execute(psycopg.sql.SQL('DROP DATABASE {} WITH (FORCE)').format(psycopg.sql.Identifier(target_name)))
