"""Configuration loading and persistence."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

CONFIG_DIR = Path.home() / ".config" / "semaphore_agent"
CONFIG_FILE = CONFIG_DIR / "config.toml"
SOCKET_NAME = "semaphore_agent/status.sock"


def runtime_dir() -> Path:
    import os

    base = os.environ.get("XDG_RUNTIME_DIR")
    if base:
        return Path(base)
    return Path("/tmp")


def socket_path() -> Path:
    return runtime_dir() / SOCKET_NAME


@dataclass
class Config:
    # UI
    anchor: str = "top-right"
    margin_x: int = 16
    margin_y: int = 16
    window_x: int | None = None
    window_y: int | None = None
    layout: str = "vertical"  # vertical | horizontal | compact
    tray_enabled: bool = True
    overlay_enabled: bool = True

    # Timing
    done_timeout: float = 15.0
    cursor_done_timeout: float = 15.0
    claude_done_timeout: float = 15.0
    source_ttl: float = 300.0
    heuristic_ttl: float = 15.0
    claude_poll_interval: float = 1.5
    process_scan_interval: float = 3.0
    codex_idle_seconds: float = 30.0
    stay_on_top_ms: int = 500
    cursor_cli_active_window: float = 12.0
    cursor_cli_finalize_grace: float = 4.0
    cursor_cli_done_cooldown: float = 45.0

    # Alerts
    desktop_notifications: bool = True
    notify_on_done: bool = True
    notify_on_attention: bool = True
    sound_on_done: bool = True
    sound_file: str = ""

    # Shortcuts (see scripts/register-shortcut.sh)
    global_shortcut: str = "<Super><Shift>s"

    adapters: dict[str, bool] = field(
        default_factory=lambda: {
            "cursor": True,
            "claude": True,
            "codex": True,
            "process": True,
        }
    )

    @classmethod
    def load(cls) -> Config:
        if not CONFIG_FILE.exists():
            return cls()
        with CONFIG_FILE.open("rb") as f:
            data = tomllib.load(f)
        ui = data.get("ui", {})
        timing = data.get("timing", {})
        alerts = data.get("alerts", {})
        adapters_raw = data.get("adapters", {})
        wx, wy = ui.get("window_x"), ui.get("window_y")
        cfg = cls(
            anchor=ui.get("anchor", "top-right"),
            margin_x=int(ui.get("margin_x", 16)),
            margin_y=int(ui.get("margin_y", 16)),
            window_x=int(wx) if wx is not None else None,
            window_y=int(wy) if wy is not None else None,
            layout=ui.get("layout", "vertical"),
            tray_enabled=bool(ui.get("tray_enabled", True)),
            overlay_enabled=bool(ui.get("overlay_enabled", True)),
            done_timeout=float(timing.get("done_timeout", 15.0)),
            cursor_done_timeout=float(timing.get("cursor_done_timeout", 15.0)),
            claude_done_timeout=float(timing.get("claude_done_timeout", 15.0)),
            source_ttl=float(timing.get("source_ttl", 300.0)),
            heuristic_ttl=float(timing.get("heuristic_ttl", 15.0)),
            claude_poll_interval=float(timing.get("claude_poll_interval", 1.5)),
            process_scan_interval=float(timing.get("process_scan_interval", 3.0)),
            codex_idle_seconds=float(timing.get("codex_idle_seconds", 30.0)),
            stay_on_top_ms=int(timing.get("stay_on_top_ms", 500)),
            cursor_cli_active_window=float(timing.get("cursor_cli_active_window", 12.0)),
            cursor_cli_finalize_grace=float(timing.get("cursor_cli_finalize_grace", 4.0)),
            cursor_cli_done_cooldown=float(timing.get("cursor_cli_done_cooldown", 45.0)),
            desktop_notifications=bool(alerts.get("desktop_notifications", True)),
            notify_on_done=bool(alerts.get("notify_on_done", True)),
            notify_on_attention=bool(alerts.get("notify_on_attention", True)),
            sound_on_done=bool(alerts.get("sound_on_done", True)),
            sound_file=str(alerts.get("sound_file", "")),
            global_shortcut=str(alerts.get("global_shortcut", "<Super><Shift>s")),
        )
        for key in cfg.adapters:
            if key in adapters_raw:
                cfg.adapters[key] = bool(adapters_raw[key])
        return cfg

    def save(self) -> None:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        lines = [
            "[ui]",
            f'anchor = "{self.anchor}"',
            f"margin_x = {self.margin_x}",
            f"margin_y = {self.margin_y}",
            f'layout = "{self.layout}"',
            f"tray_enabled = {str(self.tray_enabled).lower()}",
            f"overlay_enabled = {str(self.overlay_enabled).lower()}",
        ]
        if self.window_x is not None:
            lines.append(f"window_x = {self.window_x}")
        if self.window_y is not None:
            lines.append(f"window_y = {self.window_y}")
        lines.extend(
            [
                "",
                "[timing]",
                f"done_timeout = {self.done_timeout}",
                f"cursor_done_timeout = {self.cursor_done_timeout}",
                f"claude_done_timeout = {self.claude_done_timeout}",
                f"source_ttl = {self.source_ttl}",
                f"heuristic_ttl = {self.heuristic_ttl}",
                f"claude_poll_interval = {self.claude_poll_interval}",
                f"process_scan_interval = {self.process_scan_interval}",
                f"codex_idle_seconds = {self.codex_idle_seconds}",
                f"stay_on_top_ms = {self.stay_on_top_ms}",
                f"cursor_cli_active_window = {self.cursor_cli_active_window}",
                f"cursor_cli_finalize_grace = {self.cursor_cli_finalize_grace}",
                f"cursor_cli_done_cooldown = {self.cursor_cli_done_cooldown}",
                "",
                "[alerts]",
                f"desktop_notifications = {str(self.desktop_notifications).lower()}",
                f"notify_on_done = {str(self.notify_on_done).lower()}",
                f"notify_on_attention = {str(self.notify_on_attention).lower()}",
                f"sound_on_done = {str(self.sound_on_done).lower()}",
                f'sound_file = "{self.sound_file}"',
                f'global_shortcut = "{self.global_shortcut}"',
                "",
                "[adapters]",
            ]
        )
        for key, enabled in self.adapters.items():
            lines.append(f"{key} = {str(enabled).lower()}")
        CONFIG_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
