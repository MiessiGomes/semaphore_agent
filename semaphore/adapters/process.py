"""Generic process scanner for AI CLI tools."""

from __future__ import annotations

import os
import re
import time
from pathlib import Path

from semaphore.adapters import BaseAdapter
from semaphore.state import AgentState

# Process name / cmdline patterns -> source label
PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"gemini", re.I), "gemini"),
    (re.compile(r"\baider\b", re.I), "aider"),
    (re.compile(r"opencode", re.I), "opencode"),
    (re.compile(r"\bcodex\b", re.I), "codex-cli"),
    (re.compile(r"openai.*api", re.I), "openai-cli"),
    (re.compile(r"\bmanus\b", re.I), "manus"),
]

SKIP = re.compile(r"semaphore|grep|pgrep", re.I)


class ProcessScanner(BaseAdapter):
    name = "process-scanner"

    def __init__(self, hub, interval: float = 3.0, stop_event=None) -> None:
        super().__init__(hub, stop_event)  # type: ignore[arg-type]
        self.interval = interval
        self._seen: dict[str, float] = {}

    def _scan_proc(self) -> dict[str, str]:
        found: dict[str, str] = {}
        proc_root = Path("/proc")
        if not proc_root.exists():
            return found

        for entry in os.listdir("/proc"):
            if not entry.isdigit():
                continue
            cmdline_path = f"/proc/{entry}/cmdline"
            try:
                raw = open(cmdline_path, "rb").read().decode("utf-8", errors="replace")
            except OSError:
                continue
            if not raw or SKIP.search(raw):
                continue
            for pattern, label in PATTERNS:
                if pattern.search(raw):
                    found[label] = raw.replace("\0", " ")[:120]
                    break
        return found

    def _poll(self) -> None:
        found = self._scan_proc()
        now = time.time()
        active_labels = set(found)

        for label, cmd in found.items():
            key = f"proc:{label}"
            prev = self._seen.get(key)
            self._seen[key] = now
            if prev is None or now - prev < 8:
                self.hub.update(key, AgentState.RUNNING, detail=cmd[:60], heuristic=True)
            else:
                self.hub.update(key, AgentState.WAITING, detail="processo ocioso", heuristic=True)

        stale = [k for k in self._seen if k.removeprefix("proc:") not in active_labels]
        for key in stale:
            del self._seen[key]
            self.hub.clear_source(key)

        if not found:
            for key in list(self._seen):
                del self._seen[key]
                self.hub.clear_source(key)

    def run(self) -> None:
        while not self.stop_event.wait(self.interval):
            self._poll()
