"""Alert manager on state transitions."""

from unittest.mock import patch

from semaphore.alerts import AlertManager
from semaphore.config import Config
from semaphore.state import AgentState, StateHub


def test_sound_on_transition_to_done() -> None:
    hub = StateHub()
    cfg = Config()
    cfg.sound_on_done = True
    cfg.notify_on_done = False
    alerts = AlertManager(cfg)

    with patch.object(alerts, "_play_sound") as play:
        hub.update("claude", AgentState.RUNNING)
        alerts.on_status(hub.aggregate())
        hub.update("claude", AgentState.DONE, detail="ok")
        alerts.on_status(hub.aggregate())
        play.assert_called_once()


def test_no_sound_when_already_done() -> None:
    hub = StateHub()
    cfg = Config()
    cfg.sound_on_done = True
    cfg.notify_on_done = False
    alerts = AlertManager(cfg)
    alerts.on_status(hub.aggregate())

    with patch.object(alerts, "_play_sound") as play:
        hub.update("claude", AgentState.DONE)
        alerts.on_status(hub.aggregate())
        hub.update("claude", AgentState.DONE, detail="still")
        alerts.on_status(hub.aggregate())
        play.assert_called_once()
