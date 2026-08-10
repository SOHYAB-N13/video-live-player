"""Data movers: on-demand range fetching and sequential (no-range) feeding.

These two components decide *how* bytes travel from the remote server into
the :class:`core.cache.BlockCache`:

* :class:`RangeFetcher` is used when the server supports HTTP Range
  requests. It fetches exactly the ranges the player needs, deduplicates
  concurrent requests and bounds the number of parallel connections.
* :class:`SequentialFeeder` is used as a fallback for servers without Range
  support. It streams the file from the beginning and is deliberately paced
  so it never runs far ahead of what the player has consumed.
"""

from __future__ import annotations

import threading
from typing import Callable, Optional

from .cache import BLOCK_SIZE, BlockCache
from .datatypes import StatsCollector
from .events import EventBus
from .remote import RemoteStream


class RangeFetcher:
    """Fetches byte ranges from the remote server on demand, deduplicated."""

    MAX_RUN_BLOCKS = 32  # ~2 MiB per remote request
    MAX_CONCURRENT = 8  # cap on simultaneous remote connections

    def __init__(
        self,
        remote: RemoteStream,
        cache: BlockCache,
        total: Optional[int],
        metrics: StatsCollector,
        log: Callable[[str, str], None],
    ) -> None:
        self.remote = remote
        self.cache = cache
        self.total = total
        self.metrics = metrics
        self.log = log
        self._lock = threading.Lock()
        self._inflight: dict[tuple[int, int], threading.Condition] = {}
        self._slots = threading.Semaphore(self.MAX_CONCURRENT)

    def get_span(self, start: int, end: int, cancelled: Optional[Callable[[], bool]] = None) -> Optional[bytes]:
        """Return bytes for ``[start, end)`` or ``None`` if they could not be fetched."""
        if end <= start:
            return b""
        if self.total is not None:
            end = min(end, self.total)
            if end <= start:
                return None

        first, last = self.cache.block_span(start, end)
        idx = first
        while idx <= last:
            if self.cache.has_block(idx):
                idx += 1
                continue
            run_end = min(last, idx + self.MAX_RUN_BLOCKS - 1)
            bstart = idx * BLOCK_SIZE
            bend = (run_end + 1) * BLOCK_SIZE - 1
            if self.total is not None:
                bend = min(bend, self.total - 1)
            if not self._ensure(bstart, bend, cancelled):
                return None
            for i in range(idx, run_end + 1):
                if not self.cache.has_block(i):
                    return None
            idx = run_end + 1
        return self.cache.read_span(start, end)

    def _ensure(self, bstart: int, bend: int, cancelled: Optional[Callable[[], bool]]) -> bool:
        """Make sure bytes ``[bstart, bend]`` are cached, fetching if needed.

        Concurrent callers asking for the same range wait for the single
        fetching thread, so identical data is never downloaded twice.
        """
        key = (bstart, bend)
        with self._lock:
            cond = self._inflight.get(key)
            if cond is None:
                cond = threading.Condition(self._lock)
                self._inflight[key] = cond
                mine = True
            else:
                mine = False

        if mine:
            ok = True
            try:
                self._slots.acquire()
                try:
                    pos = bstart
                    for chunk in self.remote.iter_range(
                        bstart,
                        bend,
                        on_bytes=self.metrics.add_fetched,
                        cancelled=cancelled,
                    ):
                        self.cache.store_bytes(pos, chunk)
                        pos += len(chunk)
                finally:
                    self._slots.release()
            except Exception as exc:  # noqa: BLE001
                self.log(f"دریافت داده ناموفق بود ({bstart}-{bend}): {exc}", "error")
                ok = False
            finally:
                with self._lock:
                    self._inflight.pop(key, None)
                    cond.notify_all()
            return ok

        with cond:
            while key in self._inflight:
                cond.wait(timeout=1.0)
        first_idx = bstart // BLOCK_SIZE
        last_idx = bend // BLOCK_SIZE
        for i in range(first_idx, last_idx + 1):
            if not self.cache.has_block(i):
                return False
        return True


class SequentialFeeder(threading.Thread):
    """Streams the media sequentially when the server does not support ranges.

    The download is paced by the player's consumption so the program never
    downloads the whole file or lets RAM grow unbounded: it stays at most
    ``keep_ahead`` bytes ahead of the player's read position.
    """

    def __init__(
        self,
        remote: RemoteStream,
        cache: BlockCache,
        keep_ahead: int,
        metrics: StatsCollector,
        bus: EventBus,
        log: Callable[[str, str], None],
    ) -> None:
        super().__init__(name="sequential-feeder", daemon=True)
        self.remote = remote
        self.cache = cache
        self.keep_ahead = max(int(keep_ahead), 4 * 1024 * 1024)
        self.metrics = metrics
        self.bus = bus
        self.log = log
        self._cond = threading.Condition()
        self._stop_event = threading.Event()
        self._stored = 0
        self._consumed = 0
        self._done = False
        self._error: Optional[BaseException] = None

    # ------------------------------------------------------------------ worker

    def run(self) -> None:
        position = 0  # absolute file offset of the next chunk's first byte
        try:
            for chunk in self.remote.iter_stream(
                on_bytes=self.metrics.add_fetched,
                cancelled=self._stop_event.is_set,
            ):
                if self._stop_event.is_set():
                    break
                stored = self.cache.store_bytes(position, chunk)
                position += len(chunk)
                with self._cond:
                    self._stored += stored
                    self._cond.notify_all()
                while (self._stored - self._consumed) > self.keep_ahead and not self._stop_event.is_set():
                    with self._cond:
                        self._cond.wait(timeout=0.25)
            with self._cond:
                self._stored += self.cache.flush_pending()
                self._cond.notify_all()
            self._done = True
        except Exception as exc:  # noqa: BLE001
            self._error = exc
            self._done = True
            self.bus.emit("log", f"دریافت جریان متوقف شد: {exc}", "error")
        finally:
            with self._cond:
                self._cond.notify_all()

    # ------------------------------------------------------------------ API

    def available(self) -> int:
        """Number of contiguous committed bytes available from offset 0."""
        with self._cond:
            return self._stored

    def wait_until(self, want: int) -> int:
        """Block until at least ``want`` bytes are available (or the feeder ends)."""
        with self._cond:
            while self._stored < want and not self._done and not self._stop_event.is_set():
                self._cond.wait(timeout=0.2)
            return self._stored

    def set_consumed(self, position: int) -> None:
        with self._cond:
            if position > self._consumed:
                self._consumed = position
                self._cond.notify_all()

    def is_done(self) -> bool:
        return self._done

    def error(self) -> Optional[BaseException]:
        return self._error

    def stop(self) -> None:
        self._stop_event.set()
        with self._cond:
            self._done = True
            self._cond.notify_all()


class ReadAhead(threading.Thread):
    """Proactively downloads the media ahead of the playback position.

    A set of worker threads fetch non-overlapping chunks through the
    :class:`RangeFetcher` in parallel, so a server that throttles individual
    connections can still deliver data faster overall (the same idea as
    download accelerators). The download is paced: it never runs more than
    ``keep_ahead`` bytes ahead of the actual playback position, which keeps
    RAM usage bounded and avoids evicting data the player still needs.
    """

    CHUNK = 4 * 1024 * 1024  #: bytes each parallel worker pulls per request
    RESET_THRESHOLD = 4 * 1024 * 1024  #: a seek ahead bigger than this resets the cursor

    def __init__(
        self,
        cache: BlockCache,
        fetcher: RangeFetcher,
        metrics: StatsCollector,
        total: Optional[int],
        keep_ahead: int,
        workers: int = 3,
        initial_cursor: int = 0,
        log: Optional[Callable[[str, str], None]] = None,
    ) -> None:
        super().__init__(name="read-ahead", daemon=True)
        self.cache = cache
        self.fetcher = fetcher
        self.metrics = metrics
        self.total = total or 0
        self.keep_ahead = max(int(keep_ahead), 8 * 1024 * 1024)
        self.workers = max(1, int(workers))
        self.log = log or (lambda msg, level="info": None)
        self._cond = threading.Condition()
        self._stop_event = threading.Event()
        self._cursor = max(0, int(initial_cursor))

    # ------------------------------------------------------------------ pacing

    def _played_bytes(self) -> int:
        """Estimate how many bytes of the media the player has consumed."""
        if self.total <= 0:
            return 0
        try:
            position_ms, length_ms = self.metrics.get_position()
        except Exception:  # noqa: BLE001
            position_ms = length_ms = 0
        if length_ms > 0:
            ratio = max(0.0, min(1.0, position_ms / length_ms))
            return int(self.total * ratio)
        # duration not known yet (startup) -> fall back to the playable frontier
        return self.cache.contiguous_bytes()

    def _maybe_reset_cursor(self) -> None:
        """If the player jumped far ahead (seek), resume reading near there."""
        played = self._played_bytes()
        if played > self._cursor + self.RESET_THRESHOLD:
            self._cursor = played

    # ------------------------------------------------------------------ workers

    def _worker(self) -> None:
        while not self._stop_event.is_set():
            with self._cond:
                self._maybe_reset_cursor()
                cursor = self._cursor
                if cursor >= self.total or cursor < 0:
                    self._cond.wait(0.5)
                    continue
                ahead = cursor - self._played_bytes()
                if ahead >= self.keep_ahead:
                    self._cond.wait(0.5)
                    continue
                self._cursor = cursor + self.CHUNK
                self._cond.notify_all()
            if self._stop_event.is_set():
                break
            end = min(cursor + self.CHUNK, self.total)
            try:
                self.fetcher.get_span(cursor, end, cancelled=self._stop_event.is_set)
            except Exception as exc:  # noqa: BLE001
                self.log(f"پیش‌خوانی داده با خطا مواجه شد: {exc}", "warning")
                if not self._stop_event.wait(1.0):
                    continue

    def run(self) -> None:
        workers = [
            threading.Thread(target=self._worker, name=f"read-ahead-{i}", daemon=True)
            for i in range(self.workers)
        ]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join()

    def stop(self) -> None:
        self._stop_event.set()
        with self._cond:
            self._cond.notify_all()
