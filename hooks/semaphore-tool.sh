#!/usr/bin/env bash
# preToolUse / postToolUse — map tool type to semaphore state.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NOTIFY="$SCRIPT_DIR/semaphore-notify.sh"

input=$(cat)
read -r tool_name command <<EOF
$(echo "$input" | python3 -c "
import json, sys
try:
    d = json.load(sys.stdin)
except json.JSONDecodeError:
    print('', '')
    sys.exit(0)
tool = d.get('tool_name', '') or ''
cmd = ''
ti = d.get('tool_input') or {}
if isinstance(ti, dict):
    cmd = str(ti.get('command') or ti.get('target_file') or ti.get('path') or '')
print(tool)
print(cmd)
" 2>/dev/null || echo -e "\n")
EOF

_build_re='(npm|yarn|pnpm|pytest|cargo|make|docker|build|install|test|mvn|gradle)'

case "$tool_name" in
  Shell)
    if [[ -n "$command" ]] && [[ "$command" =~ $_build_re ]]; then
      "$NOTIFY" cursor waiting "shell: ${command:0:60}" || true
    else
      "$NOTIFY" cursor waiting "aprovar shell: ${command:-?}" || true
    fi
    ;;
  Write|Delete|StrReplace|Edit|ApplyPatch)
    "$NOTIFY" cursor waiting "aprovar edição" || true
    ;;
  Read|Grep|Glob|List|Search|SemanticSearch)
    "$NOTIFY" cursor running "ferramenta ativa" || true
    ;;
  Task)
    "$NOTIFY" cursor running "subagente" || true
    ;;
  *)
    if [[ "$tool_name" == MCP* ]] || [[ "$tool_name" == *MCP* ]] || [[ "$tool_name" == mcp_* ]]; then
      "$NOTIFY" cursor waiting "aprovar MCP: ${tool_name:0:50}" || true
    elif [[ -n "$tool_name" ]]; then
      "$NOTIFY" cursor waiting "aprovar: ${tool_name:0:50}" || true
    else
      "$NOTIFY" cursor running "ferramenta ativa" || true
    fi
    ;;
esac
exit 0
