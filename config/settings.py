import os
from pathlib import Path
from urllib.parse import urlparse, unquote
BASE_DIR = Path(__file__).resolve().parent.parent
RUNTIME = BASE_DIR / '.runtime'
RUNTIME.mkdir(exist_ok=True, mode=0o700)
DEBUG = os.environ.get('APP_ENV', 'development') != 'production'
STAGING_PREVIEW = os.environ.get('STAGING_PREVIEW') == '1'
if not DEBUG and not os.environ.get('DJANGO_SECRET_KEY'):
    raise RuntimeError('DJANGO_SECRET_KEY is required in production')
if DEBUG and not os.environ.get('DJANGO_SECRET_KEY'):
    key_file = RUNTIME / 'secret-key'
    if not key_file.exists():
        from django.core.management.utils import get_random_secret_key
        fd = os.open(key_file, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, 'w') as f: f.write(get_random_secret_key())
    SECRET_KEY = key_file.read_text()
else:
    SECRET_KEY = os.environ['DJANGO_SECRET_KEY']
ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', 'localhost,127.0.0.1,testserver').split(',')
CSRF_TRUSTED_ORIGINS = [x for x in os.environ.get('CSRF_TRUSTED_ORIGINS','').split(',') if x]
if STAGING_PREVIEW:
    # Only the loopback-bound application behind the local tunnel uses this.
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
INSTALLED_APPS = ['django.contrib.auth','django.contrib.contenttypes','django.contrib.sessions','django.contrib.messages','django.contrib.staticfiles','core']
MIDDLEWARE = ['django.middleware.security.SecurityMiddleware','whitenoise.middleware.WhiteNoiseMiddleware','django.contrib.sessions.middleware.SessionMiddleware','django.middleware.common.CommonMiddleware','django.middleware.clickjacking.XFrameOptionsMiddleware','django.middleware.csrf.CsrfViewMiddleware','django.contrib.auth.middleware.AuthenticationMiddleware','django.contrib.messages.middleware.MessageMiddleware','core.middleware.SecurityHeaders']
ROOT_URLCONF = 'config.urls'
TEMPLATES = [{'BACKEND':'django.template.backends.django.DjangoTemplates','DIRS':[], 'APP_DIRS':True,'OPTIONS':{'context_processors':['django.template.context_processors.request','django.contrib.auth.context_processors.auth','django.contrib.messages.context_processors.messages']}}]
WSGI_APPLICATION = 'config.wsgi.application'
_db_url = os.environ.get('DATABASE_URL')
if not _db_url and (RUNTIME / 'database-url').exists(): _db_url = (RUNTIME / 'database-url').read_text().strip()
if not _db_url: _db_url = 'postgresql://plastics:configure@127.0.0.1:5432/plastics'
u = urlparse(_db_url)
from urllib.parse import parse_qs
DATABASES = {'default': {'ENGINE':'django.db.backends.postgresql','NAME':u.path.lstrip('/'),'USER':unquote(u.username or ''),'PASSWORD':unquote(u.password or ''),'HOST':u.hostname or '', 'PORT':u.port or '', 'OPTIONS': {k:v[0] for k,v in parse_qs(u.query).items()}, 'CONN_MAX_AGE':0}}
AUTH_PASSWORD_VALIDATORS = [{'NAME':'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},{'NAME':'django.contrib.auth.password_validation.MinimumLengthValidator','OPTIONS':{'min_length':12}},{'NAME':'django.contrib.auth.password_validation.CommonPasswordValidator'},{'NAME':'django.contrib.auth.password_validation.NumericPasswordValidator'}]
LANGUAGE_CODE='en'
TIME_ZONE='Asia/Riyadh'
USE_I18N=True
USE_TZ=True
STATIC_URL='/static/'
STATIC_ROOT=BASE_DIR/'staticfiles'
DEFAULT_AUTO_FIELD='django.db.models.BigAutoField'
LOGIN_URL='/login/'
SESSION_COOKIE_HTTPONLY=True
SESSION_COOKIE_SAMESITE='Strict'
CSRF_COOKIE_SAMESITE='Strict'
SESSION_COOKIE_SECURE=not DEBUG
CSRF_COOKIE_SECURE=not DEBUG
SESSION_COOKIE_AGE=3600
SECURE_SSL_REDIRECT=not DEBUG
SECURE_HSTS_SECONDS=31536000 if not DEBUG else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS=not DEBUG
SECURE_HSTS_PRELOAD=not DEBUG
SECURE_CONTENT_TYPE_NOSNIFF=True
X_FRAME_OPTIONS='DENY'
DATA_UPLOAD_MAX_MEMORY_SIZE=12*1024*1024
FILE_UPLOAD_MAX_MEMORY_SIZE=10*1024*1024
# No public signup, SMTP, bank transfers or tax-invoice issuing integrations.
