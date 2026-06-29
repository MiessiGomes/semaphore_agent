#!/usr/bin/env bash
# beforeShellExecution — waiting for builds, attention for sensitive, else waiting (approval).
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NOTIFY="$SCRIPT_DIR/semaphore-notify.sh"

input=$(cat)
command=$(echo "$input" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('command',''))" 2>/dev/null || true)

if [[ -n "$command" ]] && [[ "$command" =~ (curl|wget|ssh|sudo|npm[[:space:]]+publish|git[[:space:]]+push) ]]; then
  "$NOTIFY" cursor attention "aprovação: ${command:0:60}" || true
  cat <<EOF
{
  "permission": "allow",
  "user_message": "Comando sensível — semáforo em vermelho piscando.",
  "agent_message": "Aguardando permissão do usuário."
}
EOF
  exit 0
fi

if [[ -n "$command" ]] && [[ "$command" =~ (npm|yarn|pnpm|pytest|cargo|make|docker|build|install|test) ]]; then
  "$NOTIFY" cursor waiting "shell: ${command:0:60}" || true
  echo '{ "permission": "allow" }'
  exit 0
fi

if [[ -n "$command" ]]; then
  "$NOTIFY" cursor waiting "aprovar shell: ${command:0:60}" || true
fi
echo '{ "permission": "allow" }'
exit 0
