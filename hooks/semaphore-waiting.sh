#!/usr/bin/env bash
# Agent finished a message — may still need user approval for tools/shell.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NOTIFY="$SCRIPT_DIR/semaphore-notify.sh"
"$NOTIFY" cursor waiting "aguardando ação" || true
exit 0
