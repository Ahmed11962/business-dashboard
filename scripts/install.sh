#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
mkdir -p .runtime
export UV_CACHE_DIR="$PWD/.runtime/uv-cache"
export UV_PYTHON_INSTALL_DIR="$PWD/.runtime/python"
if ! uv python find 3.12 >/dev/null 2>&1; then
  uv python install 3.12
fi
uv sync --frozen --python 3.12
.venv/bin/python scripts/dev_database.py
.venv/bin/python manage.py migrate --noinput
.venv/bin/python manage.py seed_workspace
.venv/bin/python manage.py seed_workspace --demo
.venv/bin/python manage.py seed_sample_transactions
.venv/bin/python manage.py seed_simple_sample
.venv/bin/python manage.py collectstatic --noinput
.venv/bin/python manage.py check
