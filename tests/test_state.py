"""Unit tests for state aggregation."""

from semaphore.state import AgentState, AggregatedStatus, StateHub, parse_state


def test_parse_state() -> None:
    assert parse_state("running") == AgentState.RUNNING
    assert parse_state("ATTENTION") == AgentState.ATTENTION


def test_priority_aggregation() -> None:
    hub = StateHub()
    hub.update("a", AgentState.DONE)
    hub.update("b", AgentState.RUNNING)
    assert hub.aggregate().state == AgentState.RUNNING

    hub.update("c", AgentState.ATTENTION)
    assert hub.aggregate().state == AgentState.ATTENTION


def test_heuristic_does_not_beat_confirmed_done() -> None:
    hub = StateHub()
    hub.update("cursor", AgentState.DONE)
    hub.update("proc:gemini", AgentState.RUNNING, heuristic=True)
    assert hub.aggregate().state == AgentState.DONE


def test_dismiss_clears() -> None:
    hub = StateHub()
    hub.update("cursor", AgentState.RUNNING)
    hub.dismiss()
    assert hub.aggregate().state == AgentState.IDLE


def test_history_recorded() -> None:
    hub = StateHub()
    hub.update("cursor", AgentState.RUNNING)
    hub.update("cursor", AgentState.DONE)
    assert len(hub.history) >= 2


def test_aggregated_from_dict() -> None:
    hub = StateHub()
    hub.update("cursor", AgentState.DONE, detail="ok")
    data = hub.aggregate().to_dict()
    restored = AggregatedStatus.from_dict(data)
    assert restored.state == AgentState.DONE
    assert "cursor" in restored.sources
    assert restored.sources["cursor"].detail == "ok"
