#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
if [[ ! -f .runtime/database-url ]]; then
  echo "No local database connection found. Stop here and check the existing app folder." >&2
  exit 1
fi
.venv/bin/python scripts/dev_database.py
.venv/bin/python - <<'PY'
from datetime import datetime,timezone
from pathlib import Path
import pgserver
from scripts.backup import run
runtime=Path('.runtime')
folder=runtime/'backups'
folder.mkdir(mode=0o700,parents=True,exist_ok=True)
archive=folder/('before-upgrade-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'.dump')
pg_bin=Path(pgserver.__file__).parent/'pginstall'/'bin'
run('backup',(runtime/'database-url').read_text().strip(),archive,pg_bin)
print('Database and stored attachments backed up to',archive)
print('SHA-256 checksum saved beside the backup. Keep the .runtime folder.')
PY
