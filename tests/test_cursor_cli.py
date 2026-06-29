"""Tests for Cursor CLI adapter."""

import time

from semaphore.adapters.cursor_cli import CursorCliAdapter
from semaphore.state import AgentState, StateHub


def test_running_on_recent_file_activity(monkeypatch) -> None:
    hub = StateHub()
    adapter = CursorCliAdapter(hub, active_window=10.0)

    now = time.time()
    monkeypatch.setattr(adapter, "_has_askpass", lambda: False)
    monkeypatch.setattr(adapter, "_activity_mtime", lambda: now)

    adapter._poll()
    assert hub.aggregate().state == AgentState.RUNNING


def test_attention_on_askpass(monkeypatch) -> None:
    hub = StateHub()
    adapter = CursorCliAdapter(hub)

    monkeypatch.setattr(adapter, "_has_askpass", lambda: True)
    monkeypatch.setattr(adapter, "_activity_mtime", lambda: 0.0)

    adapter._poll()
    assert hub.aggregate().state == AgentState.ATTENTION


def test_done_when_activity_stops(monkeypatch) -> None:
    hub = StateHub()
    adapter = CursorCliAdapter(hub, active_window=0.0, finalize_grace=0.0)

    t0 = time.time() - 60
    monkeypatch.setattr(adapter, "_has_askpass", lambda: False)
    monkeypatch.setattr(adapter, "_activity_mtime", lambda: t0)

    adapter._poll()
    assert hub.aggregate().state == AgentState.RUNNING

    adapter._last_activity = time.time() - 60
    adapter._poll()
    assert hub.aggregate().state == AgentState.DONE


def test_stale_agent_process_does_not_block_done(monkeypatch) -> None:
    """Regression: background `agent` PIDs must not keep RUNNING forever."""
    hub = StateHub()
    adapter = CursorCliAdapter(hub, active_window=0.0, finalize_grace=0.0)

    old = time.time() - 120
    monkeypatch.setattr(adapter, "_has_askpass", lambda: False)
    monkeypatch.setattr(adapter, "_activity_mtime", lambda: old)

    adapter._poll()
    adapter._last_activity = old
    adapter._poll()

    assert hub.aggregate().state == AgentState.DONE
    assert adapter._done_sent is True


def test_done_persists_until_new_activity(monkeypatch) -> None:
    hub = StateHub()
    adapter = CursorCliAdapter(hub, active_window=0.0, finalize_grace=0.0)

    old = time.time() - 120
    monkeypatch.setattr(adapter, "_has_askpass", lambda: False)
    monkeypatch.setattr(adapter, "_activity_mtime", lambda: old)

    adapter._poll()
    adapter._last_activity = old
    adapter._poll()
    assert hub.aggregate().state == AgentState.DONE

    adapter._poll()
    assert hub.aggregate().state == AgentState.DONE
