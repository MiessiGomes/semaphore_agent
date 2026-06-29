#!/usr/bin/env bash
# postToolUseFailure — permission denied / blocked tool.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NOTIFY="$SCRIPT_DIR/semaphore-notify.sh"

input=$(cat)
failure=$(echo "$input" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('failure_type',''))" 2>/dev/null || true)
tool=$(echo "$input" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('tool_name',''))" 2>/dev/null || true)

if [[ "$failure" == "permission_denied" ]]; then
  "$NOTIFY" cursor attention "bloqueado: ${tool:-ferramenta}" || true
else
  "$NOTIFY" cursor waiting "falha: ${tool:-ferramenta}" || true
fi
exit 0
