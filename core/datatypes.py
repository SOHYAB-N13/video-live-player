"""Shared data types, the session status model and a thread-safe stats collector."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from enum import Enum


class StreamStatus(Enum):
    """Lifecycle state of a streaming session."""

    IDLE = "idle"
    PROBING = "probing"
    CONNECTING = "connecting"
    BUFFERING = "buffering"
    PLAYING = "playing"
    PAUSED = "paused"
    STOPPED = "stopped"
    ERROR = "error"


STATUS_LABEL = {
    StreamStatus.IDLE: "آماده",
    StreamStatus.PROBING: "در حال بررسی لینک",
    StreamStatus.CONNECTING: "در حال اتصال",
    StreamStatus.BUFFERING: "در حال بافرینگ",
    StreamStatus.PLAYING: "در حال پخش",
    StreamStatus.PAUSED: "مکث",
    StreamStatus.STOPPED: "پخش متوقف شد",
    StreamStatus.ERROR: "خطا",
}

#: Statuses during which a playback session is considered active.
ACTIVE_STATUSES = frozenset(
    {
        StreamStatus.PROBING,
        StreamStatus.CONNECTING,
        StreamStatus.BUFFERING,
        StreamStatus.PLAYING,
        StreamStatus.PAUSED,
    }
)

#: MIME types the WebView's HTML5 media element can play natively.
HTML5_PLAYABLE_MIME = frozenset(
    {
        "video/mp4",
        "audio/mp4",
        "video/webm",
        "video/ogg",
        "audio/ogg",
        "application/ogg",
        "video/quicktime",
        "video/mp2t",
    }
)

#: MIME types that only the bundled VLC player can decode.
VLC_ONLY_MIME = frozenset(
    {
        "video/x-matroska",
        "video/x-msvideo",
        "video/x-ms-wmv",
        "video/x-flv",
        "video/3gpp",
        "video/3gpp2",
        "video/x-m4v",
        "video/x-ms-asf",
    }
)


def html5_playable(content_type: object) -> bool:
    """Decide whether a stream should be handed to the HTML5 media element.

    Known-good formats go straight to HTML5; formats that Chromium cannot
    decode go to VLC. An unknown MIME type is attempted with HTML5 first and
    automatically falls back to VLC if the browser rejects it.
    """
    if not content_type:
        return True
    mime = str(content_type).lower().split(";", 1)[0].strip()
    if mime in VLC_ONLY_MIME:
        return False
    if mime in HTML5_PLAYABLE_MIME:
        return True
    # e.g. application/octet-stream - let the browser decide.
    return True


@dataclass(frozen=True)
class MediaInfo:
    """Metadata probed from the remote media server."""

    url: str
    content_length: int | None
    content_type: str | None
    filename: str
    accepts_ranges: bool


@dataclass(frozen=True)
class StatsSnapshot:
    """Immutable snapshot of live statistics consumed by the UI."""

    status: StreamStatus
    bytes_fetched: int
    bytes_total: int | None
    cache_bytes: int
    cache_capacity: int
    speed_bps: float
    position_ms: int
    length_ms: int


class StatsCollector:
    """Thread-safe aggregation of live streaming statistics.

    All mutating methods may be called from worker threads; the UI only
    reads immutable snapshots produced by :meth:`snapshot`.
    """

    def __init__(self, cache_capacity: int) -> None:
        self._lock = threading.Lock()
        self._fetched = 0
        self._window: list[tuple[float, int]] = []
        self._cache_bytes = 0
        self._position_ms = 0
        self._length_ms = 0
        self.status = StreamStatus.IDLE
        self.bytes_total: int | None = None
        self.cache_capacity = cache_capacity

    def add_fetched(self, amount: int) -> None:
        """Record that ``amount`` bytes were received from the remote server."""
        if amount <= 0:
            return
        with self._lock:
            self._fetched += amount
            now = time.perf_counter()
            self._window.append((now, self._fetched))
            cutoff = now - 5.0
            while self._window and self._window[0][0] < cutoff:
                self._window.pop(0)

    def set_cache_bytes(self, value: int) -> None:
        with self._lock:
            self._cache_bytes = max(0, value)

    def set_position(self, position_ms: int, length_ms: int) -> None:
        with self._lock:
            self._position_ms = max(0, position_ms)
            if length_ms > 0:
                self._length_ms = length_ms

    def get_position(self) -> tuple[int, int]:
        """Return ``(position_ms, length_ms)`` thread-safely."""
        with self._lock:
            return self._position_ms, self._length_ms

    def snapshot(self) -> StatsSnapshot:
        with self._lock:
            window = self._window
            speed = 0.0
            if len(window) >= 2:
                dt = window[-1][0] - window[0][0]
                if dt > 0.01:
                    speed = (window[-1][1] - window[0][1]) / dt
            return StatsSnapshot(
                status=self.status,
                bytes_fetched=self._fetched,
                bytes_total=self.bytes_total,
                cache_bytes=self._cache_bytes,
                cache_capacity=self.cache_capacity,
                speed_bps=speed,
                position_ms=self._position_ms,
                length_ms=self._length_ms,
            )
