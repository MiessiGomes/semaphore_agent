"""Hook payload integration tests."""

from semaphore.state import AgentState, StateHub


def test_cursor_hook_flow() -> None:
    hub = StateHub()

    def simulate(source: str, state: str, detail: str = "") -> None:
        hub.update(source, state, detail=detail)

    simulate("cursor", "running", "sessão iniciada")
    simulate("cursor", "waiting", "aguardando ação")
    simulate("cursor", "waiting", "aprovar shell: git status")
    simulate("cursor", "running", "shell concluído")
    simulate("cursor", "done", "tarefa concluída")

    assert hub.aggregate().state == AgentState.DONE
    assert hub.aggregate().dominant_source == "cursor"


def test_approval_waiting_is_yellow() -> None:
    hub = StateHub()
    hub.update("cursor", AgentState.RUNNING)
    hub.update("cursor", AgentState.WAITING, detail="aprovar shell: npm test")
    assert hub.aggregate().state == AgentState.WAITING


def test_attention_over_done() -> None:
    hub = StateHub()
    hub.update("cursor", AgentState.DONE)
    hub.update("cursor", AgentState.ATTENTION, detail="permissão")
    assert hub.aggregate().state == AgentState.ATTENTION
