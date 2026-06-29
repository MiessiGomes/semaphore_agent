"""OpenAI Codex adapter via session directory activity."""

from __future__ import annotations

import time
from pathlib import Path

from semaphore.adapters import BaseAdapter
from semaphore.state import AgentState

CODEX_SESSIONS = Path.home() / ".codex" / "sessions"


class CodexAdapter(BaseAdapter):
    name = "codex-adapter"

    def __init__(self, hub, idle_seconds: float = 30.0, stop_event=None) -> None:
        super().__init__(hub, stop_event)  # type: ignore[arg-type]
        self.idle_seconds = idle_seconds
        self._last_activity: float | None = None
        self._had_sessions = False

    def _latest_mtime(self) -> float | None:
        if not CODEX_SESSIONS.exists():
            return None
        latest = None
        for path in CODEX_SESSIONS.rglob("*"):
            if path.is_file() and path.suffix in (".jsonl", ".json", ".log"):
                mtime = path.stat().st_mtime
                if latest is None or mtime > latest:
                    latest = mtime
        return latest

    def _poll(self) -> None:
        mtime = self._latest_mtime()
        now = time.time()

        if mtime is None:
            if self._had_sessions:
                self.hub.update("codex", AgentState.DONE, detail="sessão encerrada")
                self._had_sessions = False
                self._last_activity = None
            else:
                self.hub.clear_source("codex")
            return

        self._had_sessions = True
        if self._last_activity is None or mtime > self._last_activity:
            self._last_activity = mtime

        age = now - (self._last_activity or now)
        if age <= 5:
            self.hub.update("codex", AgentState.RUNNING, detail="atividade recente")
        elif age <= self.idle_seconds:
            self.hub.update("codex", AgentState.WAITING, detail=f"idle {int(age)}s")
        else:
            self.hub.update("codex", AgentState.WAITING, detail="processo ocioso")

    def run(self) -> None:
        while not self.stop_event.wait(2.0):
            self._poll()
