"""Persist aggregated status to disk for CLI status command."""

from __future__ import annotations

import json
from pathlib import Path

from semaphore.state import AggregatedStatus

STATUS_FILE = Path.home() / ".local" / "share" / "semaphore_agent" / "status.json"


def persist_status(status: AggregatedStatus) -> None:
    STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATUS_FILE.write_text(json.dumps(status.to_dict(), indent=2), encoding="utf-8")


def read_status_json() -> dict | None:
    if not STATUS_FILE.exists():
        return None
    try:
        return json.loads(STATUS_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
