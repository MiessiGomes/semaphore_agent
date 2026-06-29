"""Agent state model and priority aggregation."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any


class AgentState(IntEnum):
    IDLE = 0
    DONE = 1
    WAITING = 2
    RUNNING = 3
    ATTENTION = 4


STATE_NAMES: dict[str, AgentState] = {
    "idle": AgentState.IDLE,
    "done": AgentState.DONE,
    "waiting": AgentState.WAITING,
    "running": AgentState.RUNNING,
    "attention": AgentState.ATTENTION,
}


def parse_state(value: str) -> AgentState:
    key = value.strip().lower()
    if key not in STATE_NAMES:
        raise ValueError(f"Unknown state: {value!r}. Expected one of: {', '.join(STATE_NAMES)}")
    return STATE_NAMES[key]


def _effective_value(status: SourceStatus) -> int:
    value = status.state.value
    if status.heuristic:
        return min(value, AgentState.WAITING.value)
    return value


@dataclass
class SourceStatus:
    source: str
    state: AgentState
    detail: str = ""
    updated_at: float = field(default_factory=time.time)
    heuristic: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "state": self.state.name.lower(),
            "detail": self.detail,
            "updated_at": self.updated_at,
            "heuristic": self.heuristic,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SourceStatus:
        state_raw = data.get("state", "idle")
        if isinstance(state_raw, int):
            state = AgentState(state_raw)
        else:
            state = parse_state(str(state_raw))
        return cls(
            source=str(data["source"]),
            state=state,
            detail=str(data.get("detail", "")),
            updated_at=float(data.get("updated_at", time.time())),
            heuristic=bool(data.get("heuristic", False)),
        )


@dataclass
class HistoryEntry:
    ts: float
    source: str
    from_state: str | None
    to_state: str
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "ts": self.ts,
            "source": self.source,
            "from": self.from_state,
            "to": self.to_state,
            "detail": self.detail,
        }


@dataclass
class AggregatedStatus:
    state: AgentState
    sources: dict[str, SourceStatus]
    done_until: float | None = None
    history: list[HistoryEntry] = field(default_factory=list)
    dominant_source: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "state": self.state.name.lower(),
            "sources": {k: v.to_dict() for k, v in self.sources.items()},
            "done_until": self.done_until,
            "history": [h.to_dict() for h in self.history],
            "dominant_source": self.dominant_source,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AggregatedStatus:
        sources = {
            k: SourceStatus.from_dict(v) for k, v in data.get("sources", {}).items()
        }
        history = [
            HistoryEntry(
                ts=float(h["ts"]),
                source=str(h["source"]),
                from_state=h.get("from"),
                to_state=str(h["to"]),
                detail=str(h.get("detail", "")),
            )
            for h in data.get("history", [])
        ]
        return cls(
            parse_state(str(data.get("state", "idle"))),
            sources,
            data.get("done_until"),
            history,
            str(data.get("dominant_source", "")),
        )


class StateHub:
    def __init__(
        self,
        done_timeout: float = 45.0,
        source_ttl: float = 300.0,
        heuristic_ttl: float = 15.0,
        cursor_done_timeout: float = 45.0,
        claude_done_timeout: float = 60.0,
    ) -> None:
        self.done_timeout = done_timeout
        self.source_ttl = source_ttl
        self.heuristic_ttl = heuristic_ttl
        self.cursor_done_timeout = cursor_done_timeout
        self.claude_done_timeout = claude_done_timeout
        self._sources: dict[str, SourceStatus] = {}
        self._done_until: float | None = None
        self._listeners: list[Any] = []
        self.history: list[HistoryEntry] = []

    def add_listener(self, callback: Any) -> None:
        self._listeners.append(callback)

    def _record_history(self, source: str, old: SourceStatus | None, new: SourceStatus) -> None:
        if old and old.state == new.state and old.detail == new.detail:
            return
        self.history.append(
            HistoryEntry(
                ts=time.time(),
                source=source,
                from_state=old.state.name.lower() if old else None,
                to_state=new.state.name.lower(),
                detail=new.detail,
            )
        )
        self.history = self.history[-10:]

    def _done_timeout_for(self, source: str) -> float:
        if source.startswith("proc:"):
            return self.heuristic_ttl
        if source == "cursor":
            return self.cursor_done_timeout
        if source == "claude":
            return self.claude_done_timeout
        return self.done_timeout

    def _notify(self) -> None:
        status = self.aggregate()
        for cb in self._listeners:
            cb(status)

    def update(
        self,
        source: str,
        state: AgentState | str,
        *,
        detail: str = "",
        heuristic: bool = False,
    ) -> None:
        if isinstance(state, str):
            state = parse_state(state)
        old = self._sources.get(source)
        new = SourceStatus(
            source=source,
            state=state,
            detail=detail,
            updated_at=time.time(),
            heuristic=heuristic,
        )
        self._sources[source] = new
        self._record_history(source, old, new)

        if state == AgentState.DONE:
            self._done_until = time.time() + self._done_timeout_for(source)
        elif state in (AgentState.RUNNING, AgentState.ATTENTION, AgentState.WAITING):
            self._done_until = None
        self._notify()

    def clear_source(self, source: str) -> None:
        if source in self._sources:
            del self._sources[source]
            self._notify()

    def dismiss(self) -> None:
        self._sources.clear()
        self._done_until = None
        self._notify()

    def prune_stale(self) -> None:
        now = time.time()
        stale = []
        for name, s in self._sources.items():
            ttl = self.heuristic_ttl if s.heuristic else self.source_ttl
            if s.state != AgentState.DONE and now - s.updated_at > ttl:
                stale.append(name)
        for name in stale:
            del self._sources[name]
        if stale:
            self._notify()

    def aggregate(self) -> AggregatedStatus:
        now = time.time()
        self.prune_stale()

        if not self._sources:
            if self._done_until and now < self._done_until:
                return AggregatedStatus(
                    AgentState.DONE, {}, self._done_until, list(self.history), ""
                )
            self._done_until = None
            return AggregatedStatus(AgentState.IDLE, {}, None, list(self.history), "")

        confirmed = [s for s in self._sources.values() if not s.heuristic]
        heuristic = [s for s in self._sources.values() if s.heuristic]

        if confirmed:
            best = max(confirmed, key=_effective_value)
        elif heuristic:
            best = max(heuristic, key=_effective_value)
        else:
            return AggregatedStatus(AgentState.IDLE, {}, None, list(self.history), "")

        state = AgentState(_effective_value(best))

        if state == AgentState.DONE:
            if self._done_until and now >= self._done_until:
                self._sources = {k: v for k, v in self._sources.items() if v.state != AgentState.DONE}
                if not self._sources:
                    self._done_until = None
                    return AggregatedStatus(AgentState.IDLE, {}, None, list(self.history), "")
            elif not self._done_until:
                self._done_until = now + self._done_timeout_for(best.source)

        return AggregatedStatus(
            state,
            dict(self._sources),
            self._done_until,
            list(self.history),
            best.source,
        )
