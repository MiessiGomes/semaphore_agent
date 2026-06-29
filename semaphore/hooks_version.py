"""Hook installation version tracking."""

from __future__ import annotations

from pathlib import Path

HOOKS_VERSION = "4"
VERSION_FILE = Path.home() / ".cursor" / "hooks" / ".semaphore-hook-version"


def installed_version() -> str | None:
    if not VERSION_FILE.exists():
        return None
    return VERSION_FILE.read_text(encoding="utf-8").strip()


def write_installed_version() -> None:
    VERSION_FILE.parent.mkdir(parents=True, exist_ok=True)
    VERSION_FILE.write_text(HOOKS_VERSION + "\n", encoding="utf-8")


def hooks_outdated() -> bool:
    current = installed_version()
    return current != HOOKS_VERSION
