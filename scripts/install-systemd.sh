#!/usr/bin/env bash
# Instala units systemd user para o Semaphore Agent.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
USER_UNIT_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
ENV_FILE="${XDG_CONFIG_HOME:-$HOME/.config}/semaphore_agent/systemd.env"
MODE="${1:-split}"  # split | combined
START_NOW=0

usage() {
  echo "Uso: $0 [split|combined] [-y] [--start]" >&2
  echo "  split     daemon + UI separados (recomendado)" >&2
  echo "  combined  um único serviço (semaphore start)" >&2
  exit 1
}

for arg in "$@"; do
  case "$arg" in
    split|combined) MODE="$arg" ;;
    -y|--yes) START_NOW=1 ;;
    --start) START_NOW=1 ;;
    -h|--help) usage ;;
  esac
done

detect_python() {
  if [[ -n "${SEMAPHORE_PYTHON:-}" ]] && [[ -x "$SEMAPHORE_PYTHON" ]]; then
    echo "$SEMAPHORE_PYTHON"
    return
  fi
  if [[ -x "$HOME/anaconda3/envs/aiTools/bin/python" ]]; then
    echo "$HOME/anaconda3/envs/aiTools/bin/python"
    return
  fi
  if command -v python3 >/dev/null 2>&1; then
    python3 -c "import gi; import semaphore" 2>/dev/null && command -v python3 && return
  fi
  echo "Não encontrei Python com semaphore + gi instalados." >&2
  echo "Use: SEMAPHORE_PYTHON=/caminho/python $0" >&2
  exit 1
}

write_env_file() {
  mkdir -p "$(dirname "$ENV_FILE")"
  {
    echo "# Gerado por scripts/install-systemd.sh — $(date -Iseconds)"
    echo "GDK_BACKEND=x11"
    echo "GI_TYPELIB_PATH=/usr/lib/x86_64-linux-gnu/girepository-1.0"
    echo "PATH=$(dirname "$PYTHON_BIN"):$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin"
    [[ -n "${XDG_RUNTIME_DIR:-}" ]] && echo "XDG_RUNTIME_DIR=$XDG_RUNTIME_DIR"
    [[ -n "${WAYLAND_DISPLAY:-}" ]] && echo "WAYLAND_DISPLAY=$WAYLAND_DISPLAY"
    [[ -n "${DISPLAY:-}" ]] && echo "DISPLAY=$DISPLAY"
    [[ -n "${DBUS_SESSION_BUS_ADDRESS:-}" ]] && echo "DBUS_SESSION_BUS_ADDRESS=$DBUS_SESSION_BUS_ADDRESS"
    [[ -n "${XAUTHORITY:-}" ]] && echo "XAUTHORITY=$XAUTHORITY"
  } >"$ENV_FILE"
  echo "Env: $ENV_FILE"
}

install_unit() {
  local src="$1" name="$2"
  sed "s|@PYTHON@|$PYTHON_BIN|g" "$src" >"$USER_UNIT_DIR/$name"
  echo "Unit: $USER_UNIT_DIR/$name"
}

PYTHON_BIN="$(detect_python)"
write_env_file
mkdir -p "$USER_UNIT_DIR"

case "$MODE" in
  split)
    install_unit "$REPO_ROOT/systemd/semaphore-agent-daemon.service" "semaphore-agent-daemon.service"
    install_unit "$REPO_ROOT/systemd/semaphore-agent-ui.service" "semaphore-agent-ui.service"
    UNITS=(semaphore-agent-daemon.service semaphore-agent-ui.service)
    ;;
  combined)
    install_unit "$REPO_ROOT/systemd/semaphore-agent.service" "semaphore-agent.service"
    UNITS=(semaphore-agent.service)
    ;;
  *)
    echo "Modo inválido: $MODE (use split ou combined)" >&2
    exit 1
    ;;
esac

systemctl --user daemon-reload
systemctl --user enable "${UNITS[@]}"

echo ""
echo "Instalado. Comandos úteis:"
echo "  systemctl --user start ${UNITS[*]}"
echo "  systemctl --user status semaphore-agent-daemon.service"
echo "  journalctl --user -u semaphore-agent-ui.service -f"
echo ""
echo "Para iniciar no login (sessão gráfica), basta fazer login — já está enabled."
echo ""

if [[ "$START_NOW" -eq 1 ]]; then
  systemctl --user start "${UNITS[@]}"
  sleep 1
  systemctl --user --no-pager status "${UNITS[0]}" || true
else
  read -r -p "Iniciar agora? [s/N] " ans
  if [[ "${ans,,}" == "s" || "${ans,,}" == "sim" || "${ans,,}" == "y" ]]; then
    systemctl --user start "${UNITS[@]}"
    sleep 1
    systemctl --user --no-pager status "${UNITS[0]}" || true
  fi
fi
