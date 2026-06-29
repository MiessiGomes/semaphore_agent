"""IPC socket tests."""

import json
import threading
import time
from pathlib import Path

from semaphore.config import socket_path
from semaphore.ipc import fetch_status, send_notification, start_socket_server
from semaphore.state import AgentState, StateHub


def test_socket_notification(tmp_path, monkeypatch) -> None:
    sock = tmp_path / "test.sock"
    monkeypatch.setattr("semaphore.config.socket_path", lambda: sock)

    hub = StateHub()
    received: list = []

    def listener(status):
        received.append(status.state)

    hub.add_listener(listener)
    start_socket_server(sock, hub)
    time.sleep(0.2)

    assert send_notification(sock, source="test", state="running", detail="ok")
    time.sleep(0.2)
    assert hub.aggregate().state == AgentState.RUNNING

    raw = fetch_status(sock)
    assert raw is not None
    assert raw["state"] == "running"
