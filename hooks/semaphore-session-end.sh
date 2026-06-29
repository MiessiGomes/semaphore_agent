#!/usr/bin/env bash
# Session ended -> idle
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NOTIFY="$SCRIPT_DIR/semaphore-notify.sh"
"$NOTIFY" cursor idle "sessão encerrada" || true
exit 0
