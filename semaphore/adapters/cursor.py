"""Cursor hooks installation and management."""

from __future__ import annotations

import json
import shutil
import stat
from pathlib import Path

from semaphore.hooks_version import HOOKS_VERSION, write_installed_version

HOOKS_SOURCE_DIR = Path(__file__).resolve().parents[2] / "hooks"
if not HOOKS_SOURCE_DIR.exists():
    HOOKS_SOURCE_DIR = Path(__file__).resolve().parents[1] / "hooks"
CURSOR_HOOKS_DIR = Path.home() / ".cursor" / "hooks"
CURSOR_HOOKS_JSON = Path.home() / ".cursor" / "hooks.json"

HOOK_ENTRIES = {
    "sessionStart": "semaphore-session.sh",
    "sessionEnd": "semaphore-session-end.sh",
    "preToolUse": "semaphore-tool.sh",
    "postToolUse": "semaphore-post-tool.sh",
    "postToolUseFailure": "semaphore-tool-failure.sh",
    "subagentStart": "semaphore-tool.sh",
    "afterAgentResponse": "semaphore-waiting.sh",
    "beforeShellExecution": "semaphore-permission.sh",
    "beforeMCPExecution": "semaphore-mcp.sh",
    "afterShellExecution": "semaphore-shell-end.sh",
    "stop": "semaphore-stop.sh",
}


def install_hooks(force: bool = False) -> list[str]:
    """Install Cursor hook scripts and merge hooks.json. Returns log messages."""
    messages: list[str] = []
    CURSOR_HOOKS_DIR.mkdir(parents=True, exist_ok=True)

    for script_name in sorted({v for v in HOOK_ENTRIES.values()} | {"semaphore-notify.sh"}):
        src = HOOKS_SOURCE_DIR / script_name
        dst = CURSOR_HOOKS_DIR / script_name
        if not src.exists():
            messages.append(f"AVISO: script ausente: {src}")
            continue
        shutil.copy2(src, dst)
        dst.chmod(dst.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        messages.append(f"Instalado: {dst}")

    existing: dict = {"version": 1, "hooks": {}}
    if CURSOR_HOOKS_JSON.exists():
        try:
            existing = json.loads(CURSOR_HOOKS_JSON.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            messages.append("hooks.json existente inválido; será sobrescrito parcialmente")

    hooks = existing.setdefault("hooks", {})
    existing.setdefault("version", 1)

    for event, script in HOOK_ENTRIES.items():
        command = f"./hooks/{script}"
        entry = {"command": command}
        current = hooks.get(event, [])
        if any(h.get("command") == command for h in current):
            messages.append(f"Hook já presente: {event}")
            continue
        if force:
            current = [h for h in current if "semaphore" not in h.get("command", "")]
        current.append(entry)
        hooks[event] = current
        messages.append(f"Registrado hook: {event} -> {command}")

    CURSOR_HOOKS_JSON.parent.mkdir(parents=True, exist_ok=True)
    CURSOR_HOOKS_JSON.write_text(json.dumps(existing, indent=2) + "\n", encoding="utf-8")
    write_installed_version()
    messages.append(f"Versão hooks: {HOOKS_VERSION}")
    messages.append(f"Atualizado: {CURSOR_HOOKS_JSON}")
    return messages
