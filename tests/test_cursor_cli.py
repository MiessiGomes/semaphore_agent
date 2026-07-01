"""Tests for Cursor CLI adapter."""

import time

from semaphore.adapters.cursor_cli import CursorCliAdapter
from semaphore.state import AgentState, StateHub


def _mtimes(cli: float, shared: float = 0.0):
    return lambda: (cli, shared)


def test_running_on_recent_file_activity(monkeypatch) -> None:
    hub = StateHub()
    adapter = CursorCliAdapter(hub, active_window=10.0)

    now = time.time()
    monkeypatch.setattr(adapter, "_has_askpass", lambda: False)
    monkeypatch.setattr(adapter, "_activity_mtimes", _mtimes(now))

    adapter._poll()
    assert hub.aggregate().state == AgentState.RUNNING


def test_attention_on_askpass(monkeypatch) -> None:
    hub = StateHub()
    adapter = CursorCliAdapter(hub)

    monkeypatch.setattr(adapter, "_has_askpass", lambda: True)
    monkeypatch.setattr(adapter, "_activity_mtimes", _mtimes(0.0))

    adapter._poll()
    assert hub.aggregate().state == AgentState.ATTENTION


def test_done_when_activity_stops(monkeypatch) -> None:
    hub = StateHub()
    adapter = CursorCliAdapter(hub, active_window=0.0, finalize_grace=0.0)

    t0 = time.time() - 60
    monkeypatch.setattr(adapter, "_has_askpass", lambda: False)
    monkeypatch.setattr(adapter, "_activity_mtimes", _mtimes(t0))

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
    monkeypatch.setattr(adapter, "_activity_mtimes", _mtimes(old))

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
    monkeypatch.setattr(adapter, "_activity_mtimes", _mtimes(old))

    adapter._poll()
    adapter._last_activity = old
    adapter._poll()
    assert hub.aggregate().state == AgentState.DONE

    adapter._poll()
    assert hub.aggregate().state == AgentState.DONE


def test_shared_mtime_noise_does_not_restart_after_done(monkeypatch) -> None:
    """store.db / meta.json bumps must not flip RUNNING after CLI session ended."""
    hub = StateHub()
    adapter = CursorCliAdapter(
        hub, active_window=0.0, finalize_grace=0.0, done_cooldown=60.0
    )

    cli_old = time.time() - 120
    shared_new = time.time()

    monkeypatch.setattr(adapter, "_has_askpass", lambda: False)
    monkeypatch.setattr(adapter, "_activity_mtimes", _mtimes(cli_old, 0.0))

    adapter._poll()
    adapter._last_activity = cli_old
    adapter._poll()
    assert hub.aggregate().state == AgentState.DONE
    assert adapter._done_sent is True

    monkeypatch.setattr(adapter, "_activity_mtimes", _mtimes(cli_old, shared_new))
    adapter._poll()
    assert hub.aggregate().state == AgentState.DONE
    assert adapter._done_sent is True


def test_shared_mtime_alone_does_not_start_session(monkeypatch) -> None:
    hub = StateHub()
    adapter = CursorCliAdapter(hub)

    monkeypatch.setattr(adapter, "_has_askpass", lambda: False)
    monkeypatch.setattr(adapter, "_activity_mtimes", _mtimes(0.0, time.time()))

    adapter._poll()
    assert hub.aggregate().state == AgentState.IDLE
    assert adapter._session_active is False


def test_cli_restart_after_done_cooldown(monkeypatch) -> None:
    hub = StateHub()
    adapter = CursorCliAdapter(
        hub, active_window=10.0, finalize_grace=0.0, done_cooldown=1.0
    )

    cli_old = time.time() - 120
    monkeypatch.setattr(adapter, "_has_askpass", lambda: False)
    monkeypatch.setattr(adapter, "_activity_mtimes", _mtimes(cli_old))

    adapter._poll()
    adapter._last_activity = cli_old
    adapter._poll()
    assert hub.aggregate().state == AgentState.DONE

    adapter._done_at = time.time() - 5.0
    cli_new = time.time()
    monkeypatch.setattr(adapter, "_activity_mtimes", _mtimes(cli_new))
    adapter._poll()
    assert hub.aggregate().state == AgentState.RUNNING
    assert adapter._done_sent is False


def test_done_cooldown_blocks_immediate_cli_restart(monkeypatch) -> None:
    hub = StateHub()
    adapter = CursorCliAdapter(
        hub, active_window=10.0, finalize_grace=0.0, done_cooldown=60.0
    )

    cli_old = time.time() - 120
    monkeypatch.setattr(adapter, "_has_askpass", lambda: False)
    monkeypatch.setattr(adapter, "_activity_mtimes", _mtimes(cli_old))

    adapter._poll()
    adapter._last_activity = cli_old
    adapter._poll()
    assert hub.aggregate().state == AgentState.DONE

    cli_new = time.time()
    monkeypatch.setattr(adapter, "_activity_mtimes", _mtimes(cli_new))
    adapter._poll()
    assert hub.aggregate().state == AgentState.DONE
    assert adapter._done_sent is True
