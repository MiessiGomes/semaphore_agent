"""Unix socket IPC for status notifications."""

from __future__ import annotations

import json
import socket
import threading
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from semaphore.state import StateHub


def _send(path: Path, payload: dict[str, Any]) -> bytes | None:
    data = json.dumps(payload).encode()
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.settimeout(2.0)
            sock.connect(str(path))
            sock.sendall(data)
            try:
                sock.shutdown(socket.SHUT_WR)
            except OSError:
                pass
            chunks: list[bytes] = []
            while True:
                chunk = sock.recv(65536)
                if not chunk:
                    break
                chunks.append(chunk)
            return b"".join(chunks) if chunks else b""
    except OSError:
        return None


def send_notification(
    path: Path,
    *,
    source: str,
    state: str,
    detail: str = "",
    heuristic: bool = False,
) -> bool:
    result = _send(
        path,
        {
            "action": "update",
            "source": source,
            "state": state,
            "detail": detail,
            "heuristic": heuristic,
        },
    )
    return result is not None


def fetch_status(path: Path) -> dict[str, Any] | None:
    raw = _send(path, {"action": "get"})
    if not raw:
        return None
    try:
        return json.loads(raw.decode())
    except json.JSONDecodeError:
        return None


def send_action(path: Path, action: str, **fields: Any) -> bool:
    payload = {"action": action, **fields}
    return _send(path, payload) is not None


def dismiss(path: Path) -> bool:
    return send_action(path, "dismiss")


def start_socket_server(
    path: Path,
    hub: StateHub,
    on_error: Callable[[Exception], None] | None = None,
) -> threading.Thread:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()

    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(str(path))
    server.listen(8)
    server.settimeout(1.0)

    def _handle(msg: dict[str, Any]) -> bytes | None:
        action = msg.get("action", "update")
        if action == "get":
            return json.dumps(hub.aggregate().to_dict()).encode()
        if action == "dismiss":
            hub.dismiss()
            return json.dumps({"ok": True}).encode()
        if action == "update":
            hub.update(
                msg["source"],
                msg["state"],
                detail=msg.get("detail", ""),
                heuristic=bool(msg.get("heuristic", False)),
            )
            return json.dumps({"ok": True}).encode()
        return None

    def _serve() -> None:
        while True:
            try:
                conn, _ = server.accept()
            except TimeoutError:
                continue
            except OSError:
                break
            with conn:
                try:
                    data = conn.recv(65536)
                    if not data:
                        continue
                    msg = json.loads(data.decode())
                    response = _handle(msg)
                    if response:
                        conn.sendall(response)
                except Exception as exc:
                    if on_error:
                        on_error(exc)

    thread = threading.Thread(target=_serve, name="semaphore-ipc", daemon=True)
    thread.start()
    thread._server = server  # type: ignore[attr-defined]
    return thread
