"""Claude adapter session mapping."""

from semaphore.adapters.claude import ClaudeAdapter
from semaphore.state import AgentState, StateHub


def _adapter() -> ClaudeAdapter:
    return ClaudeAdapter(StateHub(), interval=999)


def test_idle_status_is_not_waiting() -> None:
    adapter = _adapter()
    state, _ = adapter._map_session({"status": "idle", "name": "foo"})
    assert state == AgentState.IDLE


def test_done_via_status() -> None:
    adapter = _adapter()
    state, detail = adapter._map_session({"status": "done"})
    assert state == AgentState.DONE
    assert "concluída" in detail


def test_working_status_is_running() -> None:
    adapter = _adapter()
    state, detail = adapter._map_session({"status": "working", "name": "my-agent"})
    assert state == AgentState.RUNNING
    assert detail == "my-agent"


def test_done_wins_over_idle_session() -> None:
    hub = StateHub()
    adapter = ClaudeAdapter(hub, interval=999)
    adapter._apply_sessions(
        [
            {"status": "idle", "name": "bg"},
            {"state": "done", "name": "finished"},
        ],
    )
    assert hub.aggregate().state == AgentState.DONE


def test_poll_clears_when_all_sessions_idle() -> None:
    hub = StateHub()
    adapter = ClaudeAdapter(hub, interval=999)
    hub.update("claude", AgentState.WAITING, detail="aguardando")
    adapter._apply_sessions([{"status": "idle", "cwd": "/tmp"}])
    assert "claude" not in hub.aggregate().sources
    assert hub.aggregate().state == AgentState.IDLE
