"""GTK4 layer-shell traffic light overlay."""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from semaphore.config import Config
    from semaphore.state import AggregatedStatus, StateHub

from semaphore.state import AgentState, AggregatedStatus

CSS = """
window {
    background: transparent;
}

.semaphore-box {
    background: rgba(20, 20, 24, 0.88);
    border-radius: 14px;
    padding: 10px 12px;
    border: 1px solid rgba(255, 255, 255, 0.08);
}

.led {
    min-width: 28px;
    min-height: 28px;
    border-radius: 50%;
    margin: 5px 0;
    opacity: 0.18;
    transition: opacity 0.25s ease, box-shadow 0.25s ease;
}

.led-red.off, .led-yellow.off, .led-green.off {
    background: #3a3a3a;
    box-shadow: inset 0 2px 4px rgba(0, 0, 0, 0.5);
}

.led-red.on {
    background: #e53935;
    opacity: 1;
    box-shadow: 0 0 12px rgba(229, 57, 53, 0.85);
}

.led-red.blink {
    background: #e53935;
    opacity: 1;
    animation: blink-fast 0.9s step-start infinite;
}

.led-yellow.on {
    background: #fdd835;
    opacity: 1;
    box-shadow: 0 0 10px rgba(253, 216, 53, 0.75);
}

.led-green.on {
    background: #43a047;
    opacity: 1;
    box-shadow: 0 0 10px rgba(67, 160, 71, 0.75);
}

@keyframes blink-fast {
    0%, 49% { opacity: 1; }
    50%, 100% { opacity: 0.25; }
}

.detail-label {
    font-size: 12px;
    padding: 2px 0;
}

.badge {
    font-size: 10px;
    color: rgba(255, 255, 255, 0.7);
    margin-top: 4px;
}

.layout-compact .led {
    min-width: 36px;
    min-height: 36px;
}

.history-title {
    font-size: 11px;
    opacity: 0.7;
    margin-top: 8px;
}
"""


class SemaphoreOverlay:
    def __init__(self, window, red_led, yellow_led, green_led, badge_label, *, layout: str = "vertical") -> None:
        self.window = window
        self.red_led = red_led
        self.yellow_led = yellow_led
        self.green_led = green_led
        self.badge_label = badge_label
        self.layout = layout
        self._last_status: AggregatedStatus | None = None
        self._details_window = None

    def update_status(self, status: AggregatedStatus) -> None:
        from gi.repository import GLib

        GLib.idle_add(self._apply_status, status)

    def update_from_dict(self, data: dict) -> None:
        self.update_status(AggregatedStatus.from_dict(data))

    def _apply_status(self, status: AggregatedStatus) -> bool:
        self._last_status = status

        self._set_led(self.red_led, "led-red", False, False)
        self._set_led(self.yellow_led, "led-yellow", False, False)
        self._set_led(self.green_led, "led-green", False, False)

        if status.state == AgentState.IDLE:
            pass
        elif status.state == AgentState.RUNNING:
            self._set_led(self.red_led, "led-red", True, False)
        elif status.state == AgentState.ATTENTION:
            self._set_led(self.red_led, "led-red", True, True)
        elif status.state == AgentState.WAITING:
            self._set_led(self.yellow_led, "led-yellow", True, False)
        elif status.state == AgentState.DONE:
            self._set_led(self.green_led, "led-green", True, False)

        if self.layout == "compact":
            self._apply_compact(status.state)

        active = [s for s in status.sources.values() if s.state != AgentState.IDLE]
        if len(active) > 1:
            self.badge_label.set_text(str(len(active)))
            self.badge_label.set_visible(True)
        else:
            self.badge_label.set_visible(False)

        if self._details_window and self._details_window.get_visible():
            self._refresh_details_window()

        return False

    def _apply_compact(self, state: AgentState) -> None:
        self._set_led(self.yellow_led, "led-yellow", False, False)
        self._set_led(self.green_led, "led-green", False, False)
        self._set_led(self.red_led, "led-red", False, False)
        target = self.red_led
        if state == AgentState.WAITING:
            target = self.yellow_led
        elif state == AgentState.DONE:
            target = self.green_led
        blink = state == AgentState.ATTENTION
        on = state != AgentState.IDLE
        base = "led-red" if target is self.red_led else ("led-yellow" if target is self.yellow_led else "led-green")
        self._set_led(target, base, on, blink)
        target.set_visible(True)
        for w in (self.red_led, self.yellow_led, self.green_led):
            if w is not target:
                w.set_visible(False)

    def _set_led(self, widget, base_class: str, on: bool, blink: bool) -> None:
        widget.set_visible(True)
        widget.remove_css_class("off")
        widget.remove_css_class("on")
        widget.remove_css_class("blink")
        if on and blink:
            widget.add_css_class("blink")
        elif on:
            widget.add_css_class("on")
        else:
            widget.add_css_class("off")

    def on_click(self, _gesture, _n_press, _x, _y) -> None:
        self._toggle_details_window()

    def _toggle_details_window(self) -> None:
        from gi.repository import Gtk

        if self._details_window and self._details_window.get_visible():
            self._details_window.destroy()
            self._details_window = None
            return

        app = self.window.get_application()
        win = Gtk.Window(application=app)
        win.set_title("Semaphore — agentes")
        win.set_default_size(320, 160)
        win.set_resizable(True)

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        outer.set_margin_top(12)
        outer.set_margin_bottom(12)
        outer.set_margin_start(14)
        outer.set_margin_end(14)
        win.set_child(outer)
        win._detail_box = outer  # type: ignore[attr-defined]

        self._details_window = win
        self._refresh_details_window()

        def on_close(_w) -> bool:
            self._details_window = None
            return False

        win.connect("close-request", on_close)
        _apply_stay_on_top(win, grab_focus=False)
        win.present()

    def _refresh_details_window(self) -> None:
        from gi.repository import Gtk

        if not self._details_window:
            return
        box = getattr(self._details_window, "_detail_box", None)
        if box is None:
            return

        while child := box.get_first_child():
            box.remove(child)

        status = self._last_status
        if status is None or not status.sources:
            label = Gtk.Label(label="Nenhum agente ativo")
            label.add_css_class("detail-label")
            box.append(label)
            return

        for src in sorted(status.sources.values(), key=lambda s: -s.state.value):
            hint = " (heurístico)" if src.heuristic else ""
            text = f"{src.source}: {src.state.name.lower()}{hint}"
            if src.detail:
                text += f" — {src.detail}"
            label = Gtk.Label(label=text)
            label.add_css_class("detail-label")
            label.set_xalign(0)
            label.set_wrap(True)
            box.append(label)

        if status.history:
            import datetime

            title = Gtk.Label(label="Histórico recente")
            title.add_css_class("history-title")
            title.set_xalign(0)
            box.append(title)
            for entry in reversed(status.history[-5:]):
                ts = datetime.datetime.fromtimestamp(entry.ts).strftime("%H:%M:%S")
                fr = entry.from_state or "—"
                line = f"{ts} {entry.source}: {fr} → {entry.to_state}"
                if entry.detail:
                    line += f" ({entry.detail[:40]})"
                label = Gtk.Label(label=line)
                label.add_css_class("detail-label")
                label.set_xalign(0)
                label.set_wrap(True)
                box.append(label)


def _monitor_workarea(monitor):
    """Monitor usable rect; get_workarea unavailable on some Wayland backends."""
    if hasattr(monitor, "get_workarea"):
        return monitor.get_workarea()
    return monitor.get_geometry()


def _begin_window_move(window, gesture, x: float, y: float) -> None:
    from gi.repository import Gdk, Gtk

    surface = window.get_surface()
    if surface is None:
        return
    display = window.get_display() or Gdk.Display.get_default()
    if display is None:
        return
    seat = display.get_default_seat()
    if seat is None:
        return
    device = seat.get_pointer()
    if device is None:
        return
    timestamp = 0
    if gesture is not None and hasattr(gesture, "get_current_event_time"):
        try:
            timestamp = gesture.get_current_event_time()
        except Exception:
            pass
    if not timestamp and hasattr(Gtk, "get_current_event_time"):
        try:
            timestamp = Gtk.get_current_event_time()
        except Exception:
            timestamp = 0
    Gdk.Toplevel.begin_move(surface, device, Gdk.BUTTON_PRIMARY, x, y, timestamp)


def _apply_stay_on_top(window, *, grab_focus: bool = False, reapply_hints: bool = False) -> None:
    """Best-effort always-on-top; prefer X11 EWMH over present() on GNOME."""
    from semaphore.ui.x11_hints import (
        apply_sticky_above,
        is_x11_window,
        raise_window,
        wmctrl_sticky,
    )

    title = None
    try:
        title = window.get_title()
    except (AttributeError, TypeError):
        pass

    if not grab_focus:
        try:
            window.set_can_focus(False)
        except (AttributeError, TypeError):
            pass
        try:
            if hasattr(window, "set_accept_focus"):
                window.set_accept_focus(False)
        except (AttributeError, TypeError):
            pass
        try:
            if hasattr(window, "set_focus_on_click"):
                window.set_focus_on_click(False)
        except (AttributeError, TypeError):
            pass

    try:
        window.set_keep_above(True)
    except (AttributeError, TypeError):
        pass

    if is_x11_window(window):
        if reapply_hints:
            apply_sticky_above(window)
            if title:
                wmctrl_sticky(title)
        raise_window(window)
        return

    try:
        window.present()
    except (AttributeError, TypeError):
        pass


def _stay_on_top_tick(window) -> bool:
    if not window.get_visible():
        return True
    _apply_stay_on_top(window, reapply_hints=False)
    return True


def _on_window_realized(window, *_args) -> None:
    try:
        _apply_stay_on_top(window, reapply_hints=True)
    except Exception:
        pass


def _save_window_position(window, config: Config) -> None:
    from semaphore.ui.x11_hints import get_window_position

    pos = get_window_position(window)
    if pos is None:
        return
    config.window_x, config.window_y = pos
    config.save()


def _wire_position_save(window, config: Config) -> None:
    from gi.repository import GLib

    debounce_id: list[int | None] = [None]

    def schedule_save() -> None:
        if debounce_id[0] is not None:
            GLib.source_remove(debounce_id[0])

        def do_save() -> bool:
            debounce_id[0] = None
            _save_window_position(window, config)
            return False

        debounce_id[0] = GLib.timeout_add(400, do_save)

    def on_released(_gesture, _n, _x, _y) -> None:
        schedule_save()

    return on_released


def _apply_anchors(window, config: Config) -> None:
    from gi.repository import Gtk4LayerShell as LayerShell

    for edge in LayerShell.Edge:
        LayerShell.set_anchor(window, edge, False)

    anchor = config.anchor
    if "top" in anchor:
        LayerShell.set_anchor(window, LayerShell.Edge.TOP, True)
        LayerShell.set_margin(window, LayerShell.Edge.TOP, config.margin_y)
    if "bottom" in anchor:
        LayerShell.set_anchor(window, LayerShell.Edge.BOTTOM, True)
        LayerShell.set_margin(window, LayerShell.Edge.BOTTOM, config.margin_y)
    if "left" in anchor:
        LayerShell.set_anchor(window, LayerShell.Edge.LEFT, True)
        LayerShell.set_margin(window, LayerShell.Edge.LEFT, config.margin_x)
    if "right" in anchor:
        LayerShell.set_anchor(window, LayerShell.Edge.RIGHT, True)
        LayerShell.set_margin(window, LayerShell.Edge.RIGHT, config.margin_x)


def run_overlay(config: Config, hub: StateHub, stop_event: threading.Event) -> SemaphoreOverlay:
    import sys

    from semaphore.ui.platform import describe_overlay_mode, is_gnome_session, layer_shell_available

    if layer_shell_available():
        return _run_layer_shell_overlay(config, hub, stop_event)

    if is_gnome_session():
        print(f"Semáforo: {describe_overlay_mode()}", file=sys.stderr)
        return _run_gnome_fallback_overlay(config, hub, stop_event)

    raise OSError(
        "libgtk4-layer-shell.so.0 não encontrada. "
        "Execute: ./scripts/install-gtk4-layer-shell.sh "
        "ou instale libgtk4-layer-shell0 (Ubuntu 25.04+)."
    )


def _run_layer_shell_overlay(
    config: Config, hub: StateHub, stop_event: threading.Event
) -> SemaphoreOverlay:
    from ctypes import CDLL

    CDLL("libgtk4-layer-shell.so.0")

    import gi

    gi.require_version("Gtk", "4.0")
    gi.require_version("Gtk4LayerShell", "1.0")

    from gi.repository import Gtk
    from gi.repository import Gtk4LayerShell as LayerShell

    overlay_ref: list[SemaphoreOverlay | None] = [None]

    def on_activate(app: Gtk.Application) -> None:
        _setup_css()
        window = Gtk.Window(application=app)
        window.set_decorated(False)
        window.set_resizable(False)
        window.set_default_size(52, 140)

        LayerShell.init_for_window(window)
        LayerShell.set_layer(window, LayerShell.Layer.OVERLAY)
        LayerShell.set_keyboard_mode(window, LayerShell.KeyboardMode.NONE)
        _apply_anchors(window, config)

        overlay_ref[0] = _build_window(app, window, hub, stop_event, config)
        overlay_ref[0].update_status(hub.aggregate())
        window.present()

    app = Gtk.Application(application_id="com.ev0lux.semaphore-agent")
    app.connect("activate", on_activate)
    _wire_stop(app, stop_event)
    app.run(None)
    return overlay_ref[0]  # type: ignore[return-value]


def run_overlay_polling(config: Config, stop_event: threading.Event) -> int:
    _run_gnome_fallback_overlay(config, None, stop_event, poll=True)
    return 0


def _run_gnome_fallback_overlay(
    config: Config,
    hub: StateHub | None,
    stop_event: threading.Event,
    *,
    poll: bool = False,
) -> SemaphoreOverlay:
    from semaphore.ui.platform import prepare_gnome_backend

    prepare_gnome_backend()

    import gi

    gi.require_version("Gtk", "4.0")
    gi.require_version("Gdk", "4.0")

    from gi.repository import GLib, Gtk

    from semaphore.daemon import get_live_status

    overlay_ref: list[SemaphoreOverlay | None] = [None]
    window_ref: list = []

    def on_activate(app: Gtk.Application) -> None:
        _setup_css()
        window = Gtk.Window(application=app)
        window.set_decorated(False)
        window.set_resizable(False)
        layout = config.layout
        if layout == "horizontal":
            window.set_default_size(140, 52)
        elif layout == "compact":
            window.set_default_size(52, 52)
        else:
            window.set_default_size(52, 140)
        window.set_title("Semaphore")
        window_ref.append(window)

        overlay_ref[0] = _build_window(
            app, window, hub, stop_event, config, enable_drag=True, poll=poll
        )
        if hub and not poll:
            overlay_ref[0].update_status(hub.aggregate())
        elif poll:
            data = get_live_status()
            if data:
                overlay_ref[0].update_from_dict(data)

        window.connect("realize", _on_window_realized)
        _apply_stay_on_top(window, reapply_hints=True)
        window.present()

        def position_once() -> bool:
            try:
                _position_gnome_window(window, config)
            except Exception:
                pass
            _apply_stay_on_top(window, reapply_hints=True)
            return False

        GLib.idle_add(position_once)
        GLib.timeout_add(config.stay_on_top_ms, _stay_on_top_tick, window)

        if poll:

            def poll_status() -> bool:
                if stop_event.is_set():
                    return False
                data = get_live_status()
                if data and overlay_ref[0]:
                    overlay_ref[0].update_from_dict(data)
                return True

            GLib.timeout_add(400, poll_status)

        if config.tray_enabled:
            try:
                from semaphore.ui.tray import attach_tray

                attach_tray(app, config, stop_event, window)
            except Exception as exc:
                print(f"Tray indisponível: {exc}", file=__import__("sys").stderr)

    app = Gtk.Application(application_id="com.ev0lux.semaphore-agent")
    app.connect("activate", on_activate)
    _wire_stop(app, stop_event)
    app.run(None)
    return overlay_ref[0]  # type: ignore[return-value]


def _setup_css() -> None:
    import gi

    gi.require_version("Gtk", "4.0")
    gi.require_version("Gdk", "4.0")

    from gi.repository import Gdk, Gtk

    display = Gdk.Display.get_default()
    if display is None:
        return

    css_provider = Gtk.CssProvider()
    css_provider.load_from_string(CSS)
    Gtk.StyleContext.add_provider_for_display(
        display,
        css_provider,
        Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
    )


def _wire_stop(app, stop_event: threading.Event) -> None:
    from gi.repository import GLib

    def _stop(*_args: object) -> None:
        app.quit()

    GLib.timeout_add(500, lambda: stop_event.is_set() and (_stop(), False)[-1] or True)


def _position_gnome_window(window, config: Config) -> None:
    if config.window_x is not None and config.window_y is not None:
        try:
            if hasattr(window, "move"):
                window.move(int(config.window_x), int(config.window_y))
                return
        except (AttributeError, TypeError):
            pass

    from gi.repository import Gdk

    display = Gdk.Display.get_default()
    if display is None:
        return
    monitors = display.get_monitors()
    if monitors.get_n_items() == 0:
        return
    monitor = monitors.get_item(0)
    workarea = _monitor_workarea(monitor)
    width, height = 52, 140
    mx, my = config.margin_x, config.margin_y
    anchor = config.anchor

    if "right" in anchor:
        x = workarea.x + workarea.width - width - mx
    else:
        x = workarea.x + mx
    if "bottom" in anchor:
        y = workarea.y + workarea.height - height - my
    else:
        y = workarea.y + my

    try:
        if hasattr(window, "move"):
            window.move(int(x), int(y))
    except (AttributeError, TypeError):
        pass


def _build_window(
    app,
    window,
    hub: StateHub | None,
    stop_event: threading.Event,
    config: Config,
    *,
    enable_drag: bool = False,
    poll: bool = False,
) -> SemaphoreOverlay:
    from gi.repository import Gdk, GLib, Gtk

    from semaphore.config import socket_path
    from semaphore.ipc import dismiss

    layout = config.layout
    orient = Gtk.Orientation.HORIZONTAL if layout == "horizontal" else Gtk.Orientation.VERTICAL
    box = Gtk.Box(orientation=orient, spacing=0)
    box.add_css_class("semaphore-box")
    if layout == "compact":
        box.add_css_class("layout-compact")

    red = Gtk.Box()
    red.add_css_class("led")
    red.add_css_class("led-red")
    red.add_css_class("off")

    yellow = Gtk.Box()
    yellow.add_css_class("led")
    yellow.add_css_class("led-yellow")
    yellow.add_css_class("off")

    green = Gtk.Box()
    green.add_css_class("led")
    green.add_css_class("led-green")
    green.add_css_class("off")

    badge = Gtk.Label(label="")
    badge.add_css_class("badge")
    badge.set_visible(False)

    box.append(red)
    box.append(yellow)
    box.append(green)
    box.append(badge)
    window.set_child(box)

    overlay = SemaphoreOverlay(window, red, yellow, green, badge, layout=layout)

    if enable_drag:
        move_click = Gtk.GestureClick()
        move_click.set_button(Gdk.BUTTON_PRIMARY)

        def on_move_pressed(gesture, n, x, y) -> None:
            if n == 2:
                dismiss(socket_path())
                return
            _begin_window_move(window, gesture, x, y)

        on_released = _wire_position_save(window, config)
        move_click.connect("pressed", on_move_pressed)
        move_click.connect("released", on_released)
        box.add_controller(move_click)

        detail_click = Gtk.GestureClick()
        detail_click.set_button(Gdk.BUTTON_SECONDARY)
        detail_click.connect("pressed", overlay.on_click)
        box.add_controller(detail_click)
    else:
        click = Gtk.GestureClick()
        click.connect("pressed", overlay.on_click)
        box.add_controller(click)

    def tick() -> bool:
        if stop_event.is_set():
            app.quit()
            return False
        return True

    GLib.timeout_add(500, tick)
    if hub is not None and not poll:
        hub.add_listener(overlay.update_status)
    return overlay
