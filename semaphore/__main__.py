"""CLI entry point for semaphore-agent."""

from __future__ import annotations

import argparse
import json
import sys
import time

from semaphore import __version__
from semaphore.config import CONFIG_FILE, Config, socket_path
from semaphore.daemon import dismiss, ensure_daemon, get_live_status, notify
from semaphore.hooks_version import HOOKS_VERSION, hooks_outdated, installed_version
from semaphore.state import STATE_NAMES


def cmd_daemon(_args: argparse.Namespace) -> int:
    from semaphore.daemon import SemaphoreDaemon, write_pid_file

    write_pid_file("daemon")
    return SemaphoreDaemon().run_headless()


def cmd_ui(_args: argparse.Namespace) -> int:
    from semaphore.daemon import SemaphoreUI, write_pid_file

    if not ensure_daemon():
        print("Não foi possível iniciar o daemon.", file=sys.stderr)
        return 1
    write_pid_file("ui")
    return SemaphoreUI().run()


def cmd_start(_args: argparse.Namespace) -> int:
    if not ensure_daemon():
        print("Não foi possível iniciar o daemon.", file=sys.stderr)
        return 1
    return cmd_ui(_args)


def cmd_status(_args: argparse.Namespace) -> int:
    data = get_live_status()
    if data is None:
        if not socket_path().exists():
            print("Daemon não está rodando.", file=sys.stderr)
            return 1
        print("Daemon ativo, mas status indisponível.", file=sys.stderr)
        return 0
    print(json.dumps(data, indent=2, ensure_ascii=False))
    print(f"\nEstado agregado: {data.get('state', '?')}")
    if hooks_outdated():
        print(f"\n⚠ Hooks desatualizados (instalado={installed_version()}, atual={HOOKS_VERSION})")
        print("  Execute: semaphore install-hooks --force")
    elif installed_version():
        print(f"\nHooks Cursor: v{installed_version()} (ok)")
    return 0


def cmd_watch(args: argparse.Namespace) -> int:
    last = None
    try:
        while True:
            data = get_live_status()
            state = (data or {}).get("state", "offline")
            if state != last:
                dom = (data or {}).get("dominant_source", "")
                print(f"{time.strftime('%H:%M:%S')} {state} {dom}")
                last = state
            time.sleep(args.interval)
    except KeyboardInterrupt:
        return 0


def cmd_dismiss(_args: argparse.Namespace) -> int:
    if not dismiss(socket_path()):
        print("Falha ao enviar dismiss.", file=sys.stderr)
        return 1
    return 0


def cmd_raise(_args: argparse.Namespace) -> int:
    import shutil
    import subprocess

    if shutil.which("wmctrl"):
        try:
            out = subprocess.run(
                ["wmctrl", "-l"],
                capture_output=True,
                text=True,
                timeout=3,
                check=False,
            )
            for line in out.stdout.splitlines():
                if "Semaphore" in line:
                    win_id = line.split()[0]
                    subprocess.run(["wmctrl", "-ia", win_id], check=False, timeout=3)
                    return 0
        except (OSError, subprocess.SubprocessError):
            pass
    print("Overlay não encontrado. Use o tray ou: semaphore ui", file=sys.stderr)
    return 1


def cmd_notify(args: argparse.Namespace) -> int:
    if not ensure_daemon() and args.source != "cli":
        pass
    ok = notify(args.source, args.state, detail=args.detail or "", heuristic=args.heuristic)
    if not ok:
        print("Falha ao notificar daemon.", file=sys.stderr)
        return 1
    return 0


def cmd_set(args: argparse.Namespace) -> int:
    return cmd_notify(
        argparse.Namespace(
            source="cli", state=args.state, detail=args.detail or "", heuristic=False
        )
    )


def cmd_install_hooks(args: argparse.Namespace) -> int:
    from semaphore.adapters.cursor import install_hooks

    for line in install_hooks(force=args.force):
        print(line)
    return 0


def cmd_config(args: argparse.Namespace) -> int:
    cfg = Config.load()
    if args.show:
        print(f"Arquivo: {CONFIG_FILE}")
        for field in (
            "anchor", "layout", "margin_x", "margin_y", "window_x", "window_y",
            "tray_enabled", "overlay_enabled", "done_timeout", "cursor_done_timeout",
            "claude_done_timeout", "heuristic_ttl", "stay_on_top_ms",
            "desktop_notifications", "sound_on_done", "global_shortcut", "adapters",
        ):
            print(f"  {field} = {getattr(cfg, field, cfg.adapters if field == 'adapters' else '?')}")
        return 0

    if args.anchor:
        cfg.anchor = args.anchor
    if args.layout:
        cfg.layout = args.layout
    if args.margin_x is not None:
        cfg.margin_x = args.margin_x
    if args.margin_y is not None:
        cfg.margin_y = args.margin_y
    if args.done_timeout is not None:
        cfg.done_timeout = args.done_timeout
    if args.tray_enabled is not None:
        cfg.tray_enabled = args.tray_enabled
    if args.overlay_enabled is not None:
        cfg.overlay_enabled = args.overlay_enabled

    cfg.save()
    print(f"Config salva em {CONFIG_FILE}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="semaphore",
        description="Semáforo visual multi-agente para Wayland",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("daemon", help="Hub headless (IPC + adapters)")
    sub.add_parser("ui", help="Overlay + tray (requer daemon)")
    sub.add_parser("start", help="daemon + ui")
    sub.add_parser("status", help="Estado agregado")
    sub.add_parser("dismiss", help="Marcar como visto (idle)")

    p_watch = sub.add_parser("watch", help="Monitora mudanças de estado")
    p_watch.add_argument("--interval", type=float, default=1.0)

    sub.add_parser("raise", help="Dica para mostrar overlay")

    p_notify = sub.add_parser("notify", help="Envia atualização ao daemon")
    p_notify.add_argument("--source", "-s", required=True)
    p_notify.add_argument("--state", "-t", required=True, choices=list(STATE_NAMES))
    p_notify.add_argument("--detail", "-d", default="")
    p_notify.add_argument("--heuristic", action="store_true")

    p_set = sub.add_parser("set", help="Atalho notify")
    p_set.add_argument("state", choices=list(STATE_NAMES))
    p_set.add_argument("detail", nargs="?", default="")

    p_hooks = sub.add_parser("install-hooks", help="Hooks Cursor")
    p_hooks.add_argument("--force", action="store_true")

    p_cfg = sub.add_parser("config", help="Configuração")
    p_cfg.add_argument("--show", action="store_true")
    p_cfg.add_argument("--anchor", choices=["top-right", "top-left", "bottom-right", "bottom-left"])
    p_cfg.add_argument("--layout", choices=["vertical", "horizontal", "compact"])
    p_cfg.add_argument("--margin-x", type=int, dest="margin_x")
    p_cfg.add_argument("--margin-y", type=int, dest="margin_y")
    p_cfg.add_argument("--done-timeout", type=float, dest="done_timeout")
    p_cfg.add_argument("--tray-enabled", type=bool, dest="tray_enabled")
    p_cfg.add_argument("--overlay-enabled", type=bool, dest="overlay_enabled")

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    handlers = {
        "daemon": cmd_daemon,
        "ui": cmd_ui,
        "start": cmd_start,
        "status": cmd_status,
        "watch": cmd_watch,
        "dismiss": cmd_dismiss,
        "raise": cmd_raise,
        "notify": cmd_notify,
        "set": cmd_set,
        "install-hooks": cmd_install_hooks,
        "config": cmd_config,
    }
    return handlers[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
