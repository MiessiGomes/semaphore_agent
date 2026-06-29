#!/usr/bin/env bash
# Agent loop stopped — green only when completed successfully.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NOTIFY="$SCRIPT_DIR/semaphore-notify.sh"

input=$(cat)
status=$(echo "$input" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('status','completed'))" 2>/dev/null || echo "completed")

if [[ "$status" == "completed" ]]; then
  "$NOTIFY" cursor done "tarefa concluída" || true
else
  "$NOTIFY" cursor idle "agente parou ($status)" || true
fi
exit 0
