"""Main daemon (headless) and UI runner."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

from semaphore.alerts import AlertManager
from semaphore.config import Config, socket_path
from semaphore.ipc import dismiss, fetch_status, start_socket_server
from semaphore.persistence import persist_status
from semaphore.state import AggregatedStatus, StateHub


class SemaphoreDaemon:
    """Headless hub: IPC, adapters, alerts, status persistence."""

    def __init__(self, config: Config | None = None) -> None:
        self.config = config or Config.load()
        self.hub = StateHub(
            done_timeout=self.config.done_timeout,
            source_ttl=self.config.source_ttl,
            heuristic_ttl=self.config.heuristic_ttl,
            cursor_done_timeout=self.config.cursor_done_timeout,
            claude_done_timeout=self.config.claude_done_timeout,
        )
        self._socket_path = socket_path()
        self._stop_event = threading.Event()
        self._threads: list[threading.Thread] = []
        self._alerts = AlertManager(self.config)

    def start_adapters(self) -> None:
        from semaphore.adapters.claude import ClaudeAdapter
        from semaphore.adapters.codex import CodexAdapter
        from semaphore.adapters.process import ProcessScanner

        adapters = []
        if self.config.adapters.get("cursor", True):
            from semaphore.adapters.cursor_cli import CursorCliAdapter

            adapters.append(
                CursorCliAdapter(
                    self.hub,
                    interval=1.0,
                    active_window=float(getattr(self.config, "cursor_cli_active_window", 12.0)),
                    finalize_grace=float(getattr(self.config, "cursor_cli_finalize_grace", 4.0)),
                    stop_event=self._stop_event,
                )
            )
        if self.config.adapters.get("claude", True):
            adapters.append(
                ClaudeAdapter(self.hub, interval=self.config.claude_poll_interval, stop_event=self._stop_event)
            )
        if self.config.adapters.get("codex", True):
            adapters.append(
                CodexAdapter(self.hub, idle_seconds=self.config.codex_idle_seconds, stop_event=self._stop_event)
            )
        if self.config.adapters.get("process", True):
            adapters.append(
                ProcessScanner(self.hub, interval=self.config.process_scan_interval, stop_event=self._stop_event)
            )
        for adapter in adapters:
            t = threading.Thread(target=adapter.run, name=adapter.name, daemon=True)
            t.start()
            self._threads.append(t)

    def _on_status(self, status: AggregatedStatus) -> None:
        persist_status(status)
        self._alerts.on_status(status)

    def run_headless(self) -> int:
        self.hub.add_listener(self._on_status)
        start_socket_server(self._socket_path, self.hub)
        self.start_adapters()

        def prune_loop() -> None:
            while not self._stop_event.wait(10.0):
                self.hub.prune_stale()

        t = threading.Thread(target=prune_loop, name="semaphore-prune", daemon=True)
        t.start()
        self._threads.append(t)

        def _shutdown(*_args: object) -> None:
            self._stop_event.set()

        signal.signal(signal.SIGINT, _shutdown)
        signal.signal(signal.SIGTERM, _shutdown)

        persist_status(self.hub.aggregate())
        while not self._stop_event.wait(1.0):
            persist_status(self.hub.aggregate())

        if self._socket_path.exists():
            self._socket_path.unlink()
        return 0


class SemaphoreUI:
    """GTK overlay + tray; polls daemon status via socket/file."""

    def __init__(self, config: Config | None = None) -> None:
        self.config = config or Config.load()
        self._stop_event = threading.Event()
        self._overlay = None

    def run(self) -> int:
        from semaphore.ui.platform import is_gnome_session, prepare_gnome_backend
        from semaphore.ui.startup import log_startup_diagnostics

        if is_gnome_session():
            prepare_gnome_backend()
        log_startup_diagnostics(self.config)

        if not self.config.overlay_enabled and not self.config.tray_enabled:
            print("overlay_enabled e tray_enabled estão false; nada para exibir.", file=sys.stderr)
            return 1

        try:
            if self.config.overlay_enabled:
                from semaphore.ui.overlay import run_overlay_polling

                return run_overlay_polling(self.config, self._stop_event)
            from semaphore.ui.tray import run_tray_only

            return run_tray_only(self.config, self._stop_event)
        except (OSError, ImportError) as exc:
            print(f"UI indisponível: {exc}", file=sys.stderr)
            return 1

    def run_legacy_combined(self, hub: StateHub) -> int:
        """Single-process mode (daemon + overlay share hub)."""
        from semaphore.ui.platform import is_gnome_session, prepare_gnome_backend

        if is_gnome_session():
            prepare_gnome_backend()
        from semaphore.ui.overlay import run_overlay

        def on_status(status: AggregatedStatus) -> None:
            if self._overlay:
                self._overlay.update_status(status)

        hub.add_listener(on_status)
        self._overlay = run_overlay(self.config, hub, self._stop_event)
        return 0


def daemon_running() -> bool:
    return socket_path().exists()


def ensure_daemon(config: Config | None = None) -> bool:
    if daemon_running():
        return True
    cfg = config or Config.load()
    env = os.environ.copy()
    proc = subprocess.Popen(
        [sys.executable, "-m", "semaphore", "daemon"],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    for _ in range(50):
        if socket_path().exists():
            return True
        if proc.poll() is not None:
            return False
        time.sleep(0.1)
    return daemon_running()


def write_pid_file(name: str = "daemon") -> Path:
    pid_path = Path.home() / ".local" / "share" / "semaphore_agent" / f"{name}.pid"
    pid_path.parent.mkdir(parents=True, exist_ok=True)
    pid_path.write_text(str(os.getpid()), encoding="utf-8")
    return pid_path


def notify(source: str, state: str, detail: str = "", heuristic: bool = False) -> bool:
    from semaphore.ipc import send_notification

    return send_notification(
        socket_path(),
        source=source,
        state=state,
        detail=detail,
        heuristic=heuristic,
    )


def get_live_status() -> dict | None:
    data = fetch_status(socket_path())
    if data:
        return data
    from semaphore.persistence import read_status_json

    return read_status_json()
