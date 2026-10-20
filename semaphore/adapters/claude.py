"""Claude Code adapter via `claude agents --json` polling."""

from __future__ import annotations

import json
import shutil
import subprocess

from semaphore.adapters import BaseAdapter
from semaphore.state import AgentState

_ACTIVE_STATES = frozenset(
    {AgentState.RUNNING, AgentState.WAITING, AgentState.ATTENTION},
)


class ClaudeAdapter(BaseAdapter):
    name = "claude-adapter"

    def __init__(self, hub, interval: float = 1.5, stop_event=None) -> None:
        super().__init__(hub, stop_event)  # type: ignore[arg-type]
        self.interval = interval
        self._claude = shutil.which("claude")
        self._was_engaged = False

    def _finish_or_clear(self) -> None:
        if self._was_engaged:
            self._was_engaged = False
            self.hub.update("claude", AgentState.DONE, detail="sessão concluída")
        else:
            self.hub.clear_source("claude")

    def _map_session(self, session: dict) -> tuple[AgentState, str]:
        state_raw = str(session.get("state", "")).lower()
        status = str(session.get("status", "")).lower()
        waiting_for = str(session.get("waitingFor", "")).lower()

        if state_raw == "done" or status == "done":
            return AgentState.DONE, "sessão concluída"
        if state_raw in ("failed", "stopped"):
            return AgentState.IDLE, state_raw

        if status == "idle" or state_raw == "idle":
            return AgentState.IDLE, ""

        if status == "waiting" or state_raw in ("blocked", "needs-input"):
            if "permission" in waiting_for or "input" in waiting_for:
                return AgentState.ATTENTION, waiting_for or "input necessário"
            return AgentState.WAITING, waiting_for or "aguardando"

        if state_raw == "working" or status == "working":
            return AgentState.RUNNING, session.get("name") or session.get("cwd", "")

        if state_raw:
            return AgentState.RUNNING, state_raw
        return AgentState.IDLE, ""

    def _apply_sessions(self, sessions: list) -> None:
        best_state = AgentState.IDLE
        best_detail = ""
        for session in sessions:
            if not isinstance(session, dict):
                continue
            state, detail = self._map_session(session)
            if state.value > best_state.value:
                best_state = state
                best_detail = detail

        if best_state == AgentState.IDLE:
            self._finish_or_clear()
        else:
            if best_state in _ACTIVE_STATES:
                self._was_engaged = True
            elif best_state == AgentState.DONE:
                self._was_engaged = False
            self.hub.update("claude", best_state, detail=best_detail)

    def _poll(self) -> None:
        if not self._claude:
            return
        try:
            result = subprocess.run(
                [self._claude, "agents", "--json"],
                capture_output=True,
                text=True,
                timeout=5,
            )
        except (subprocess.SubprocessError, OSError):
            return
        if result.returncode != 0 or not result.stdout.strip():
            self._finish_or_clear()
            return

        try:
            sessions = json.loads(result.stdout)
        except json.JSONDecodeError:
            return

        if not isinstance(sessions, list) or not sessions:
            self._finish_or_clear()
            return

        self._apply_sessions(sessions)

    def run(self) -> None:
        while not self.stop_event.wait(self.interval):
            self._poll()
