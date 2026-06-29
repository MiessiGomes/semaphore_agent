"""Base adapter interface."""

from __future__ import annotations

import threading
from abc import ABC, abstractmethod

from semaphore.state import StateHub


class BaseAdapter(ABC):
    name: str = "base"

    def __init__(self, hub: StateHub, stop_event: threading.Event) -> None:
        self.hub = hub
        self.stop_event = stop_event

    @abstractmethod
    def run(self) -> None:
        ...
