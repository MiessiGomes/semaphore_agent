"""Desktop notifications and sounds on state transitions."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from semaphore.config import CONFIG_DIR, Config
from semaphore.state import AgentState, AggregatedStatus


class AlertManager:
    def __init__(self, config: Config) -> None:
        self.config = config
        self._last_state: AgentState | None = None

    def on_status(self, status: AggregatedStatus) -> None:
        if status.state == self._last_state:
            return
        prev = self._last_state
        self._last_state = status.state

        if status.state == AgentState.DONE:
            if self.config.notify_on_done:
                self._notify("Tarefa concluída", self._summary(status))
            if self.config.sound_on_done:
                self._play_sound()
        elif status.state == AgentState.ATTENTION and self.config.notify_on_attention:
            if prev != AgentState.ATTENTION:
                self._notify("Atenção necessária", self._summary(status))

    def _summary(self, status: AggregatedStatus) -> str:
        if not status.sources:
            return "Semáforo: done"
        parts = []
        for s in sorted(status.sources.values(), key=lambda x: -x.state.value)[:3]:
            parts.append(f"{s.source}: {s.detail or s.state.name.lower()}")
        return "; ".join(parts)

    def _notify(self, title: str, body: str) -> None:
        if not self.config.desktop_notifications:
            return
        if not shutil.which("notify-send"):
            return
        try:
            subprocess.run(
                ["notify-send", "-a", "semaphore-agent", "-i", "dialog-information", title, body],
                check=False,
                timeout=3,
            )
        except (OSError, subprocess.SubprocessError):
            pass

    def _play_sound(self) -> None:
        path = self.config.sound_file.strip()
        if path:
            custom = Path(path).expanduser()
            if custom.is_file():
                self._play_file(custom)
                return
        default = CONFIG_DIR / "done.wav"
        if default.is_file():
            self._play_file(default)
            return
        if shutil.which("paplay"):
            try:
                subprocess.run(["paplay", "/usr/share/sounds/freedesktop/stereo/complete.oga"], check=False, timeout=3)
            except (OSError, subprocess.SubprocessError):
                pass
        elif shutil.which("aplay"):
            try:
                subprocess.run(["aplay", "/usr/share/sounds/freedesktop/stereo/complete.oga"], check=False, timeout=3)
            except (OSError, subprocess.SubprocessError):
                pass

    def _play_file(self, path: Path) -> None:
        for cmd in (["paplay", str(path)], ["aplay", str(path)]):
            if shutil.which(cmd[0]):
                try:
                    subprocess.run(cmd, check=False, timeout=5)
                    return
                except (OSError, subprocess.SubprocessError):
                    pass
