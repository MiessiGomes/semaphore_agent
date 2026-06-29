#!/usr/bin/env bash
# Register global shortcut for semaphore (GNOME). Run once.
set -euo pipefail
SHORTCUT="${1:-<Super><Shift>s}"
SCHEMA="org.gnome.settings-daemon.plugins.media-keys"
PATH_KEY="/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/semaphore-agent/"
SCRIPT="$(command -v semaphore)"

if [[ -z "$SCRIPT" ]]; then
  echo "semaphore não encontrado no PATH" >&2
  exit 1
fi

gsettings set "$SCHEMA" custom-keybindings "['semaphore-agent/']"
gsettings set "$SCHEMA.custom-keybinding:$PATH_KEY" name "Semaphore Raise"
gsettings set "$SCHEMA.custom-keybinding:$PATH_KEY" command "$SCRIPT dismiss"
gsettings set "$SCHEMA.custom-keybinding:$PATH_KEY" binding "$SHORTCUT"

echo "Atalho registrado: $SHORTCUT -> semaphore dismiss"
echo "Para mostrar overlay use o tray ou: semaphore ui"
