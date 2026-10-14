#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
if [[ $# -ne 1 ]]; then
  echo "Usage: ./scripts/prepare_local_test.sh YOUR_EMAIL" >&2
  exit 2
fi
mkdir -p .runtime
chmod 700 .runtime
if [[ -e .runtime/sayem-local-invitation.txt ]]; then
  echo "Existing private invitation: .runtime/sayem-local-invitation.txt"
  exit 0
fi
division_id=$(.venv/bin/python manage.py shell -c "from core.models import Division; print(Division.objects.get(is_demo=False).pk)")
.venv/bin/python manage.py invite_operator "$division_id" sayem "$1" \
  --governance-reference 'Owner requested local testing; no live authority granted' \
  --output .runtime/sayem-local-invitation.txt
echo "Start the app, then run ./scripts/open_local_invitation.sh in another Terminal window."
