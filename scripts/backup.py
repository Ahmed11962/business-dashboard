#!/usr/bin/env python
"""Full PostgreSQL database backup/restore, including private document bytes and access state.
Requires pg_dump/pg_restore on PATH (or --bin). DATABASE_URL must name the owner connection.
"""
import argparse,hashlib,os,shutil,subprocess
from pathlib import Path
from urllib.parse import urlsplit,unquote,parse_qsl

def pg_env(url):
    u=urlsplit(url); env=os.environ.copy()
    env.update(PGHOST=u.hostname or '',PGPORT=str(u.port or 5432),PGUSER=unquote(u.username or ''),PGPASSWORD=unquote(u.password or ''),PGDATABASE=u.path.lstrip('/'))
    for key,value in parse_qsl(u.query):
        if key in ('host','port','sslmode'): env['PG'+key.upper()]=value
    return env

def run(action,url,path,bin_dir=None):
    path=Path(path); executable='pg_dump' if action=='backup' else 'pg_restore'
    binary=str(Path(bin_dir)/executable) if bin_dir else shutil.which(executable)
    if not binary: raise RuntimeError(executable+' not found; install PostgreSQL client tools or pass --bin')
    env=pg_env(url)
    if action=='backup':
        if path.exists(): raise RuntimeError('Refusing to overwrite an existing backup')
        fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
        try:
            with os.fdopen(fd,'wb') as out: subprocess.run([binary,'--format=custom','--no-owner','--no-acl'],env=env,stdout=out,check=True)
        except Exception:
            path.unlink(missing_ok=True); raise
        checksum=hashlib.sha256(path.read_bytes()).hexdigest(); path.with_suffix(path.suffix+'.sha256').write_text(checksum+'\n')
    else:
        expected=path.with_suffix(path.suffix+'.sha256').read_text().strip()
        if hashlib.sha256(path.read_bytes()).hexdigest()!=expected: raise RuntimeError('Backup checksum mismatch')
        import psycopg
        with psycopg.connect(url) as conn:
            if conn.execute("SELECT count(*) FROM pg_tables WHERE schemaname='public'").fetchone()[0]: raise RuntimeError('Restore target must be a new empty database')
        subprocess.run([binary,'--no-owner','--no-acl','--exit-on-error','--single-transaction','--dbname',env['PGDATABASE'],str(path)],env=env,check=True)
    return path

if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('action',choices=['backup','restore']); p.add_argument('path'); p.add_argument('--bin'); args=p.parse_args()
    url=os.environ.get('DATABASE_URL')
    if not url: raise SystemExit('DATABASE_URL is required; never pass credentials in command arguments.')
    run(args.action,url,args.path,args.bin); print(args.action+' completed; run application integrity checks before serving a restored database.')
