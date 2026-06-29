"""System tray icon — runs in a subprocess (GTK3 AppIndicator + overlay GTK4)."""

from __future__ import annotations

import os
import subprocess
import sys
import threading
from typing import TYPE_CHECKING

from semaphore.config import Config
from semaphore.state import AgentState

if TYPE_CHECKING:
    pass

STATE_EMOJI = {
    AgentState.IDLE: "⚫",
    AgentState.DONE: "🟢",
    AgentState.WAITING: "🟡",
    AgentState.RUNNING: "🔴",
    AgentState.ATTENTION: "🔴",
}

_tray_proc: subprocess.Popen | None = None


def _emoji_for(data: dict | None) -> str:
    if not data:
        return "⚫"
    try:
        state = AgentState[str(data.get("state", "idle")).upper()]
    except KeyError:
        return "⚫"
    return STATE_EMOJI.get(state, "⚫")


def _spawn_tray_worker() -> subprocess.Popen | None:
    global _tray_proc
    if _tray_proc is not None and _tray_proc.poll() is None:
        return _tray_proc

    from semaphore.ui.platform import system_girepository_paths

    env = os.environ.copy()
    paths = system_girepository_paths()
    if paths:
        extra = ":".join(paths)
        current = env.get("GI_TYPELIB_PATH", "")
        env["GI_TYPELIB_PATH"] = f"{extra}:{current}" if current else extra

    cmd = [sys.executable, "-m", "semaphore.ui.tray_worker", str(os.getpid())]
    try:
        _tray_proc = subprocess.Popen(
            cmd,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            start_new_session=False,
        )
        return _tray_proc
    except OSError as exc:
        print(f"Tray: falha ao iniciar subprocesso ({exc})", file=sys.stderr)
        return None


def _tray_started_message(proc: subprocess.Popen | None) -> None:
    if proc is None:
        return
    import time

    time.sleep(0.4)
    if proc.poll() is not None:
        err = proc.stderr.read().decode(errors="replace").strip() if proc.stderr else ""
        if err:
            print(err, file=sys.stderr)
        return
    print("Tray: ativo (subprocesso GTK3)", file=sys.stderr)


def attach_tray(_app, config: Config, stop_event: threading.Event, overlay_window=None) -> None:
    del config, overlay_window
    proc = _spawn_tray_worker()
    _tray_started_message(proc)

    import gi

    gi.require_version("Gtk", "4.0")
    from gi.repository import GLib

    def watch_tray() -> bool:
        if stop_event.is_set():
            global _tray_proc
            if _tray_proc is not None and _tray_proc.poll() is None:
                _tray_proc.terminate()
            return False
        return True

    GLib.timeout_add(500, watch_tray)


def run_tray_only(config: Config, stop_event: threading.Event) -> int:
    del config
    proc = _spawn_tray_worker()
    if proc is None:
        return 1
    try:
        while not stop_event.wait(0.5):
            if proc.poll() is not None:
                err = proc.stderr.read().decode(errors="replace").strip() if proc.stderr else ""
                if err:
                    print(err, file=sys.stderr)
                return proc.returncode or 1
    except KeyboardInterrupt:
        pass
    if proc.poll() is None:
        proc.terminate()
    return 0
