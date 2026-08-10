"""Minimal in-process publish/subscribe event bus.

Worker threads emit events; the UI subscribes and drains them through a
thread-safe queue. A failure in one subscriber never breaks emission.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Callable


class EventBus:
    def __init__(self) -> None:
        self._subscribers: dict[str, list[Callable[..., None]]] = defaultdict(list)

    def subscribe(self, event: str, callback: Callable[..., None]) -> None:
        self._subscribers[event].append(callback)

    def emit(self, event: str, *args: object, **kwargs: object) -> None:
        for callback in list(self._subscribers.get(event, [])):
            try:
                callback(*args, **kwargs)
            except Exception:  # noqa: BLE001 - never break emission on bad subscriber
                pass
