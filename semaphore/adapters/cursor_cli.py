"""Cursor Agent CLI adapter (`agent` in terminal / VS Code)."""

from __future__ import annotations

import os
import re
import time
from pathlib import Path

from semaphore.adapters import BaseAdapter
from semaphore.state import AgentState

CURSOR_CHATS = Path.home() / ".cursor" / "chats"
CURSOR_PROJECTS = Path.home() / ".cursor" / "projects"
SOURCE = "cursor-cli"

ASKPASS = re.compile(r"cursor-askpass", re.I)
SKIP = re.compile(r"semaphore|grep|pgrep", re.I)


class CursorCliAdapter(BaseAdapter):
    """Track CLI agent via file activity — not process list (stale agents stay open)."""

    name = "cursor-cli-adapter"

    def __init__(
        self,
        hub,
        interval: float = 1.0,
        active_window: float = 12.0,
        finalize_grace: float = 4.0,
        stop_event=None,
    ) -> None:
        super().__init__(hub, stop_event)  # type: ignore[arg-type]
        self.interval = interval
        self.active_window = active_window
        self.finalize_grace = finalize_grace
        self._session_active = False
        self._done_sent = False
        self._last_activity = 0.0
        self._last_seen_mtime = 0.0

    def _read_cmdline(self, pid: str) -> str:
        try:
            raw = open(f"/proc/{pid}/cmdline", "rb").read().decode("utf-8", errors="replace")
        except OSError:
            return ""
        return raw.replace("\0", " ")

    def _has_askpass(self) -> bool:
        proc_root = Path("/proc")
        if not proc_root.exists():
            return False
        for entry in os.listdir("/proc"):
            if not entry.isdigit():
                continue
            flat = self._read_cmdline(entry)
            if flat and not SKIP.search(flat) and ASKPASS.search(flat):
                return True
        return False

    def _activity_mtime(self) -> float:
        latest = 0.0

        def bump(path: Path) -> None:
            nonlocal latest
            try:
                latest = max(latest, path.stat().st_mtime)
            except OSError:
                pass

        if CURSOR_CHATS.exists():
            for name in ("store.db", "meta.json"):
                for path in CURSOR_CHATS.rglob(name):
                    bump(path)

        if CURSOR_PROJECTS.exists():
            for path in CURSOR_PROJECTS.glob("*/agent-transcripts/*/*.jsonl"):
                bump(path)

        import tempfile

        log_root = Path(tempfile.gettempdir())
        for path in log_root.glob("cursor-agent-logs-*/*"):
            if path.is_file():
                bump(path)

        return latest

    def _note_activity(self, mtime: float, now: float) -> None:
        if mtime > self._last_seen_mtime + 0.01:
            self._last_seen_mtime = mtime
            self._last_activity = now
            self._session_active = True
            self._done_sent = False

    def _poll(self) -> None:
        now = time.time()
        mtime = self._activity_mtime()
        self._note_activity(mtime, now)

        if self._has_askpass():
            self._session_active = True
            self._done_sent = False
            self._last_activity = now
            self.hub.update(
                SOURCE,
                AgentState.ATTENTION,
                detail="agent CLI — aprovação necessária",
                heuristic=False,
            )
            return

        if self._done_sent:
            return

        if not self._session_active:
            self.hub.clear_source(SOURCE)
            return

        age = now - self._last_activity

        if age <= self.active_window:
            self.hub.update(
                SOURCE,
                AgentState.RUNNING,
                detail="agent CLI ativo",
                heuristic=False,
            )
            return

        if age <= self.active_window + self.finalize_grace:
            self.hub.update(
                SOURCE,
                AgentState.WAITING,
                detail="agent CLI finalizando",
                heuristic=False,
            )
            return

        self.hub.update(
            SOURCE,
            AgentState.DONE,
            detail="agent CLI concluído",
            heuristic=False,
        )
        self._done_sent = True
        self._session_active = False

    def run(self) -> None:
        while not self.stop_event.wait(self.interval):
            self._poll()
