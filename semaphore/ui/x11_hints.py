"""X11 EWMH hints for sticky always-on-top (GNOME via XWayland)."""

from __future__ import annotations

import ctypes
import ctypes.util
import logging
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

SHOW_OVERLAY_REQUEST = Path.home() / ".local/share/semaphore_agent/show_overlay.request"


def request_show_overlay() -> None:
    """Signal the overlay UI process to show its window (tray runs in another process)."""
    SHOW_OVERLAY_REQUEST.parent.mkdir(parents=True, exist_ok=True)
    SHOW_OVERLAY_REQUEST.touch()


def consume_show_overlay_request() -> bool:
    if SHOW_OVERLAY_REQUEST.exists():
        SHOW_OVERLAY_REQUEST.unlink(missing_ok=True)
        return True
    return False


def _x11() -> Any | None:
    path = ctypes.util.find_library("X11")
    if not path:
        return None
    lib = ctypes.CDLL(path)
    lib.XInternAtom.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int]
    lib.XInternAtom.restype = ctypes.c_ulong
    lib.XRootWindow.argtypes = [ctypes.c_void_p, ctypes.c_int]
    lib.XRootWindow.restype = ctypes.c_ulong
    lib.XRaiseWindow.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
    lib.XSendEvent.argtypes = [
        ctypes.c_void_p,
        ctypes.c_ulong,
        ctypes.c_int,
        ctypes.c_long,
        ctypes.c_void_p,
    ]
    lib.XChangeProperty.argtypes = [
        ctypes.c_void_p,
        ctypes.c_ulong,
        ctypes.c_ulong,
        ctypes.c_ulong,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_void_p,
        ctypes.c_int,
    ]
    lib.XFlush.argtypes = [ctypes.c_void_p]
    return lib


class _ClientMessage(ctypes.Structure):
    _fields_ = [
        ("type", ctypes.c_int),
        ("serial", ctypes.c_ulong),
        ("send_event", ctypes.c_int),
        ("display", ctypes.c_void_p),
        ("window", ctypes.c_ulong),
        ("message_type", ctypes.c_ulong),
        ("format", ctypes.c_int),
        ("data", ctypes.c_long * 5),
    ]


def _void_p(obj) -> ctypes.c_void_p:
    """Convert PyGObject Xlib Display or int to Display* for ctypes."""
    if isinstance(obj, int):
        return ctypes.c_void_p(obj)
    try:
        return ctypes.c_void_p(int(obj))
    except (TypeError, ValueError):
        return ctypes.c_void_p(hash(obj))


def _x11_window(window) -> tuple[Any, int] | None:
    try:
        import gi

        gi.require_version("GdkX11", "4.0")
        from gi.repository import Gdk, GdkX11
    except (ImportError, ValueError):
        return None

    surface = window.get_surface()
    if surface is None or not isinstance(surface, GdkX11.X11Surface):
        return None

    xid = int(GdkX11.X11Surface.get_xid(surface))
    if not xid:
        return None

    display = window.get_display() or Gdk.Display.get_default()
    if display is None:
        return None
    xdisplay = GdkX11.X11Display.get_xdisplay(display)
    if not xdisplay:
        return None
    return xdisplay, xid


def _intern(display, name: str) -> int:
    lib = _x11()
    if not lib:
        return 0
    return int(lib.XInternAtom(_void_p(display), name.encode("utf-8"), False))


def is_x11_window(window) -> bool:
    return _x11_window(window) is not None


def apply_sticky_above(window) -> bool:
    """Set _NET_WM_STATE_ABOVE/STICKY/SKIP_TASKBAR (no DOCK — allows moving)."""
    try:
        return _apply_sticky_above_impl(window)
    except Exception as exc:
        log.debug("apply_sticky_above failed: %s", exc)
        return False


def _apply_sticky_above_impl(window) -> bool:
    info = _x11_window(window)
    lib = _x11()
    if not info or not lib:
        return False
    xdisplay, xid = info
    dptr = _void_p(xdisplay)

    net_wm_state = _intern(xdisplay, "_NET_WM_STATE")
    if not net_wm_state:
        return False

    root = int(lib.XRootWindow(dptr, 0))
    states = [
        "_NET_WM_STATE_ABOVE",
        "_NET_WM_STATE_STICKY",
        "_NET_WM_STATE_SKIP_TASKBAR",
        "_NET_WM_STATE_SKIP_PAGER",
    ]

    for state_name in states:
        state_atom = _intern(xdisplay, state_name)
        if not state_atom:
            continue
        ev = _ClientMessage()
        ev.type = 33  # ClientMessage
        ev.send_event = 1
        ev.display = dptr
        ev.window = xid
        ev.message_type = net_wm_state
        ev.format = 32
        ev.data[0] = 1  # _NET_WM_STATE_ADD
        ev.data[1] = state_atom
        ev.data[2] = 0
        ev.data[3] = 1
        ev.data[4] = 0
        lib.XSendEvent(dptr, root, True, 0xFFFFFF, ctypes.byref(ev))

    lib.XFlush(dptr)
    return True


def get_window_position(window) -> tuple[int, int] | None:
    """Root-window coordinates for an X11/XWayland window."""
    try:
        info = _x11_window(window)
        lib = _x11()
        if not info or not lib:
            return None
        xdisplay, xid = info
        dptr = _void_p(xdisplay)
        root = int(lib.XRootWindow(dptr, 0))
        lib.XTranslateCoordinates.argtypes = [
            ctypes.c_void_p,
            ctypes.c_ulong,
            ctypes.c_ulong,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.POINTER(ctypes.c_int),
            ctypes.POINTER(ctypes.c_int),
            ctypes.POINTER(ctypes.c_ulong),
        ]
        rx = ctypes.c_int()
        ry = ctypes.c_int()
        child = ctypes.c_ulong()
        ok = lib.XTranslateCoordinates(dptr, xid, root, 0, 0, ctypes.byref(rx), ctypes.byref(ry), ctypes.byref(child))
        if not ok:
            return None
        return int(rx.value), int(ry.value)
    except Exception as exc:
        log.debug("get_window_position failed: %s", exc)
        return None


def raise_window(window) -> bool:
    """Raise in stacking order without activating (no focus steal)."""
    try:
        info = _x11_window(window)
        lib = _x11()
        if not info or not lib:
            return False
        xdisplay, xid = info
        dptr = _void_p(xdisplay)
        lib.XRaiseWindow(dptr, xid)
        lib.XFlush(dptr)
        return True
    except Exception as exc:
        log.debug("raise_window failed: %s", exc)
        return False


def wmctrl_sticky(title: str = "Semaphore") -> bool:
    """Optional fallback if wmctrl is installed (sudo apt install wmctrl)."""
    import shutil
    import subprocess

    wmctrl = shutil.which("wmctrl")
    if not wmctrl:
        return False
    try:
        r = subprocess.run(
            [wmctrl, "-r", title, "-b", "add,above,sticky,skip_taskbar,skip_pager"],
            capture_output=True,
            timeout=2,
            check=False,
        )
        return r.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def show_overlay_window(title: str = "Semaphore") -> bool:
    """Show and raise the overlay window (e.g. after GTK set_visible(False) or wmctrl hidden)."""
    import shutil
    import subprocess

    request_show_overlay()

    wmctrl = shutil.which("wmctrl")
    if not wmctrl:
        return False
    try:
        out = subprocess.run(
            [wmctrl, "-l"],
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
        )
        for line in out.stdout.splitlines():
            if title in line:
                win_id = line.split()[0]
                subprocess.run(
                    [wmctrl, "-i", "-r", win_id, "-b", "remove,hidden"],
                    capture_output=True,
                    timeout=3,
                    check=False,
                )
                subprocess.run(
                    [wmctrl, "-ia", win_id],
                    capture_output=True,
                    timeout=3,
                    check=False,
                )
                return True
    except (OSError, subprocess.SubprocessError):
        pass
    return True
