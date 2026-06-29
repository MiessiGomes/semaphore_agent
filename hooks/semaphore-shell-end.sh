#!/usr/bin/env bash
# After shell completes -> running (agent continues)
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NOTIFY="$SCRIPT_DIR/semaphore-notify.sh"
"$NOTIFY" cursor running "shell concluído" || true
exit 0
