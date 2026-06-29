#!/usr/bin/env bash
# postToolUse — tool succeeded; agent continues.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NOTIFY="$SCRIPT_DIR/semaphore-notify.sh"
"$NOTIFY" cursor running "ferramenta ok" || true
exit 0
