"""Local loopback staging origin for an authenticated HTTPS tunnel.
Only the synthetic test division is reachable while STAGING_PREVIEW=1.
"""
import os,subprocess,sys
from pathlib import Path
from django.core.management.utils import get_random_secret_key
root=Path(__file__).resolve().parent.parent
os.chdir(root)
subprocess.run([str(root/'.venv/bin/python'),'scripts/dev_database.py'],check=True)
private=root/'.runtime/staging-secret-key'
if not private.exists():
    fd=os.open(private,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    with os.fdopen(fd,'w') as f: f.write(get_random_secret_key())
private.chmod(0o600)
env=os.environ.copy()
env.update(APP_ENV='production',STAGING_PREVIEW='1',DJANGO_SECRET_KEY=private.read_text(),ALLOWED_HOSTS='.trycloudflare.com,127.0.0.1,localhost',CSRF_TRUSTED_ORIGINS='https://*.trycloudflare.com')
os.execve(str(root/'.venv/bin/gunicorn'),[str(root/'.venv/bin/gunicorn'),'config.wsgi:application','--bind','127.0.0.1:8000','--workers','2','--error-logfile','-'],env)
