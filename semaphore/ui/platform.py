"""Detect desktop/compositor capabilities for overlay mode."""

from __future__ import annotations

import os
from ctypes import CDLL
from ctypes.util import find_library


def is_gnome_session() -> bool:
    desktop = os.environ.get("XDG_CURRENT_DESKTOP", "").lower()
    return "gnome" in desktop or "zorin" in desktop


def layer_shell_available() -> bool:
    if is_gnome_session():
        return False
    lib = find_library("gtk4-layer-shell") or "libgtk4-layer-shell.so.0"
    try:
        CDLL(lib)
        return True
    except OSError:
        return False


def overlay_mode() -> str:
    """Return 'layer_shell' or 'gnome_fallback'."""
    if layer_shell_available():
        return "layer_shell"
    return "gnome_fallback"


def prepare_gnome_backend() -> None:
    """Force XWayland on GNOME so keep_above works. Call before importing Gtk."""
    if not is_gnome_session():
        return
    if os.environ.get("SEMAPHORE_GDK_BACKEND"):
        os.environ["GDK_BACKEND"] = os.environ["SEMAPHORE_GDK_BACKEND"]
        return
    if os.environ.get("GDK_BACKEND", "").lower() == "wayland":
        return
    os.environ.setdefault("GDK_BACKEND", "x11")


def system_girepository_paths() -> list[str]:
    """System typelib dirs (Ayatana AppIndicator is not bundled in conda PyGObject)."""
    from pathlib import Path

    candidates = [
        "/usr/lib/x86_64-linux-gnu/girepository-1.0",
        "/usr/lib/aarch64-linux-gnu/girepository-1.0",
        "/usr/lib/girepository-1.0",
    ]
    return [p for p in candidates if Path(p).is_dir()]


def describe_overlay_mode() -> str:
    mode = overlay_mode()
    if mode == "layer_shell":
        return "layer-shell (overlay acima de todas as janelas)"
    if is_gnome_session():
        backend = os.environ.get("GDK_BACKEND", "x11")
        return (
            f"fallback GNOME/Zorin via {backend} "
            "(keep_above + XWayland; layer-shell indisponível no Mutter)"
        )
    return (
        "fallback GTK (instale libgtk4-layer-shell — veja README ou "
        "scripts/install-gtk4-layer-shell.sh)"
    )
