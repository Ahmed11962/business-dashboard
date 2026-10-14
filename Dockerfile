FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir uv==0.12.23
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev
COPY config config
COPY core core
COPY manage.py ./
COPY scripts scripts
RUN mkdir -p .runtime && .venv/bin/python manage.py collectstatic --noinput && useradd --uid 10001 --create-home app && chown -R app:app /app
USER app
EXPOSE 8443
# Supply valid certificates as read-only runtime secrets. No access log with invitation URLs.
CMD [".venv/bin/gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8443", "--workers", "2", "--certfile", "/run/secrets/tls_cert", "--keyfile", "/run/secrets/tls_key", "--error-logfile", "-"]
