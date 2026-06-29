"""Startup diagnostics for UI mode."""

from __future__ import annotations

import os
import shutil
import sys

from semaphore.config import Config


def log_startup_diagnostics(config: Config) -> None:
    from semaphore.ui.platform import describe_overlay_mode

    lines = [f"Semáforo: {describe_overlay_mode()}"]
    backend = os.environ.get("GDK_BACKEND", "(default)")
    lines.append(f"  GDK_BACKEND={backend}")
    lines.append(f"  wmctrl={'sim' if shutil.which('wmctrl') else 'não'}")
    lines.append(f"  notify-send={'sim' if shutil.which('notify-send') else 'não'}")
    lines.append(f"  layout={config.layout} tray={config.tray_enabled} overlay={config.overlay_enabled}")
    if config.window_x is not None:
        lines.append(f"  posição salva=({config.window_x}, {config.window_y})")
    for line in lines:
        print(line, file=sys.stderr)
