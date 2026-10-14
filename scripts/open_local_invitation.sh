#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
if [[ ! -f .runtime/sayem-local-invitation.txt ]]; then
  echo "First run ./scripts/prepare_local_test.sh YOUR_EMAIL" >&2
  exit 1
fi
invitation_path=$(<.runtime/sayem-local-invitation.txt)
open "http://127.0.0.1:8000${invitation_path}"
