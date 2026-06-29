#!/usr/bin/env bash
# Notify semaphore: session started -> running
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NOTIFY="$SCRIPT_DIR/semaphore-notify.sh"
"$NOTIFY" cursor running "sessão iniciada" || true
exit 0
