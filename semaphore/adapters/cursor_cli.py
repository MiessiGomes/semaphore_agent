"""Cursor Agent CLI adapter (`agent` in terminal / VS Code)."""

from __future__ import annotations

import os
import re
import tempfile
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
    """Track CLI agent via high-confidence file activity (logs, transcripts)."""

    name = "cursor-cli-adapter"

    def __init__(
        self,
        hub,
        interval: float = 1.0,
        active_window: float = 12.0,
        finalize_grace: float = 4.0,
        done_cooldown: float = 45.0,
        stop_event=None,
    ) -> None:
        super().__init__(hub, stop_event)  # type: ignore[arg-type]
        self.interval = interval
        self.active_window = active_window
        self.finalize_grace = finalize_grace
        self.done_cooldown = done_cooldown
        self._session_active = False
        self._done_sent = False
        self._done_at = 0.0
        self._last_activity = 0.0
        self._last_seen_cli_mtime = 0.0

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

    def _activity_mtimes(self) -> tuple[float, float]:
        """Return (cli_mtime, shared_mtime). Only cli_mtime drives session state."""
        cli_latest = 0.0
        shared_latest = 0.0

        def bump_cli(path: Path) -> None:
            nonlocal cli_latest
            try:
                cli_latest = max(cli_latest, path.stat().st_mtime)
            except OSError:
                pass

        def bump_shared(path: Path) -> None:
            nonlocal shared_latest
            try:
                shared_latest = max(shared_latest, path.stat().st_mtime)
            except OSError:
                pass

        if CURSOR_PROJECTS.exists():
            for path in CURSOR_PROJECTS.glob("*/agent-transcripts/*/*.jsonl"):
                bump_cli(path)

        log_root = Path(tempfile.gettempdir())
        for path in log_root.glob("cursor-agent-logs-*/*"):
            if path.is_file():
                bump_cli(path)

        if CURSOR_CHATS.exists():
            for name in ("store.db", "meta.json"):
                for path in CURSOR_CHATS.rglob(name):
                    bump_shared(path)

        return cli_latest, shared_latest

    def _note_cli_activity(self, cli_mtime: float, now: float) -> None:
        if cli_mtime <= self._last_seen_cli_mtime + 0.01:
            return
        self._last_seen_cli_mtime = cli_mtime
        if self._done_sent and now < self._done_at + self.done_cooldown:
            return
        self._last_activity = now
        self._session_active = True
        self._done_sent = False

    def _poll(self) -> None:
        now = time.time()
        cli_mtime, _shared_mtime = self._activity_mtimes()
        self._note_cli_activity(cli_mtime, now)

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
        self._done_at = now
        self._session_active = False

    def run(self) -> None:
        while not self.stop_event.wait(self.interval):
            self._poll()
