#!/usr/bin/env bash
# beforeMCPExecution — MCP tools usually need user approval in Cursor.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NOTIFY="$SCRIPT_DIR/semaphore-notify.sh"

input=$(cat)
tool=$(echo "$input" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('tool_name','mcp'))" 2>/dev/null || echo "mcp")

"$NOTIFY" cursor waiting "aprovar MCP: ${tool:0:50}" || true
echo '{ "permission": "allow" }'
exit 0
