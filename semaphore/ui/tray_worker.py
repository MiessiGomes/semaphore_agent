"""Standalone system tray (GTK3 + AppIndicator) in a separate process."""

from __future__ import annotations

import os
import sys


def _prepare_typelibs() -> None:
    from semaphore.ui.platform import system_girepository_paths

    paths = system_girepository_paths()
    if not paths:
        return
    extra = ":".join(paths)
    current = os.environ.get("GI_TYPELIB_PATH", "")
    os.environ["GI_TYPELIB_PATH"] = f"{extra}:{current}" if current else extra


def _indicator_category(AppIndicator):
    cat = getattr(AppIndicator, "IndicatorCategory", None)
    if cat is not None:
        return cat.APPLICATION_STATUS
    return AppIndicator.Category.APPLICATION_STATUS


def _indicator_status_active(AppIndicator):
    status = getattr(AppIndicator, "IndicatorStatus", None)
    if status is not None:
        return status.ACTIVE
    return AppIndicator.Status.ACTIVE


def _load_indicator_module():
    import gi

    _prepare_typelibs()
    for namespace in ("AyatanaAppIndicator3", "AppIndicator3"):
        try:
            gi.require_version(namespace, "0.1")
            mod = __import__("gi.repository", fromlist=[namespace])
            return getattr(mod, namespace)
        except (ValueError, ImportError):
            continue
    return None


def _raise_overlay() -> None:
    from semaphore.ui.x11_hints import show_overlay_window

    show_overlay_window()


def main(parent_pid: int | None = None) -> int:
    AppIndicator = _load_indicator_module()
    if AppIndicator is None:
        print(
            "Tray: instale gir1.2-ayatanaappindicator3-0.1 (ou libappindicator3)",
            file=sys.stderr,
        )
        return 1

    import gi

    gi.require_version("Gtk", "3.0")
    from gi.repository import GLib, Gtk

    from semaphore.config import socket_path
    from semaphore.daemon import get_live_status
    from semaphore.ipc import dismiss
    from semaphore.ui.tray import _emoji_for

    indicator = AppIndicator.Indicator.new(
        "semaphore-agent",
        "dialog-information",
        _indicator_category(AppIndicator),
    )
    indicator.set_status(_indicator_status_active(AppIndicator))

    menu = Gtk.Menu()

    item_status = Gtk.MenuItem(label="Status: …")
    item_status.set_sensitive(False)
    menu.append(item_status)

    item_raise = Gtk.MenuItem(label="Mostrar semáforo")
    item_raise.connect("activate", lambda *_: _raise_overlay())
    menu.append(item_raise)

    item_dismiss = Gtk.MenuItem(label="Marcar como visto")
    item_dismiss.connect("activate", lambda *_: dismiss(socket_path()))
    menu.append(item_dismiss)

    item_quit = Gtk.MenuItem(label="Sair tray")
    item_quit.connect("activate", lambda *_: Gtk.main_quit())
    menu.append(item_quit)

    menu.show_all()
    indicator.set_menu(menu)

    def refresh_tray() -> bool:
        data = get_live_status()
        emoji = _emoji_for(data)
        try:
            indicator.set_label(emoji, "")
        except Exception:
            pass
        if data:
            dom = data.get("dominant_source") or "-"
            item_status.set_label(f"Status: {data.get('state', '?')} ({dom})")
        if parent_pid is not None:
            try:
                os.kill(parent_pid, 0)
            except OSError:
                return False
        return True

    GLib.timeout_add(800, refresh_tray)
    refresh_tray()
    Gtk.main()
    return 0


if __name__ == "__main__":
    ppid = int(sys.argv[1]) if len(sys.argv) > 1 else None
    raise SystemExit(main(ppid))
