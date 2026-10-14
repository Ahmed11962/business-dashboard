#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
.venv/bin/python scripts/dev_database.py
exec .venv/bin/gunicorn config.wsgi:application --bind 127.0.0.1:8000 --workers 2 --error-logfile -
