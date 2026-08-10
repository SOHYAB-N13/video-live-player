"""Thread-safe LRU byte-block cache used as the streaming buffer.

The cache is a random-access buffer made of fixed-size blocks stored in RAM.
It serves two purposes:

* *range mode* - blocks requested by the player are fetched from the remote
  server on demand and cached here;
* *stream mode* - a feeder thread stores sequential blocks and the proxy
  reads them back for the player.

Blocks are evicted with LRU so the resident set never exceeds the configured
capacity, which keeps memory usage predictable no matter how long the media
file is.
"""

from __future__ import annotations

import threading
from collections import OrderedDict
from typing import Optional

BLOCK_SIZE = 64 * 1024  #: Size of a cache block in bytes.


class BlockCache:
    """Random-access, thread-safe, capacity-bounded block cache."""

    def __init__(self, capacity_bytes: int, total_bytes: Optional[int] = None) -> None:
        self.capacity = max(int(capacity_bytes), BLOCK_SIZE * 2)
        self.total_bytes = total_bytes
        self._lock = threading.RLock()
        self._blocks: OrderedDict[int, bytes] = OrderedDict()
        self._pending: dict[int, bytearray] = {}
        self._resident = 0

    # ------------------------------------------------------------------ helpers

    @staticmethod
    def _first_block(offset: int) -> int:
        return offset // BLOCK_SIZE

    @staticmethod
    def _last_block(start: int, length: int) -> int:
        if length <= 0:
            return BlockCache._first_block(start)
        return (start + length - 1) // BLOCK_SIZE

    def block_span(self, start: int, end: int) -> tuple[int, int]:
        """Return inclusive ``(first, last)`` block indexes covering [start, end)."""
        return self._first_block(start), self._last_block(start, max(end - start, 1))

    # ------------------------------------------------------------------ writing

    def store_bytes(self, start: int, data: bytes) -> int:
        """Store raw bytes starting at ``start``, committing whole blocks.

        Data is buffered per block until a block is complete (reaches a block
        boundary or the end of the file) and only then committed. Returns the
        number of bytes that were committed to finished blocks; the remaining
        bytes stay in an internal pending buffer.

        Thread-safety: callers must guarantee a given byte range is never
        written by two threads at once (:class:`core.fetcher.RangeFetcher`
        deduplicates overlapping fetches and
        :class:`core.fetcher.SequentialFeeder` is a single writer).
        """
        total = self.total_bytes
        with self._lock:
            pos = 0
            committed = 0
            n = len(data)
            while pos < n:
                offset = start + pos
                idx = offset // BLOCK_SIZE
                block_start = idx * BLOCK_SIZE
                room = BLOCK_SIZE - (offset - block_start)
                piece = data[pos : pos + room]
                if not piece:
                    break
                buf = self._pending.get(idx)
                if buf is None:
                    buf = bytearray()
                    self._pending[idx] = buf
                buf.extend(piece)
                pos += len(piece)

                block_end_exclusive = min(block_start + BLOCK_SIZE, total) if total is not None else block_start + BLOCK_SIZE
                if len(buf) >= (block_end_exclusive - block_start):
                    block = bytes(buf[:BLOCK_SIZE])
                    del self._pending[idx]
                    old = self._blocks.get(idx)
                    if old is not None:
                        self._blocks.move_to_end(idx)
                        if len(old) != len(block):
                            self._resident += len(block) - len(old)
                            self._blocks[idx] = block
                    else:
                        self._blocks[idx] = block
                        self._resident += len(block)
                    committed += len(block)
            self._evict()
            return committed

    def _evict(self) -> None:
        while self._resident > self.capacity and self._blocks:
            _idx, data = self._blocks.popitem(last=False)
            self._resident -= len(data)

    def flush_pending(self) -> int:
        """Commit buffered partial blocks as-is; returns committed bytes.

        In no-range mode the total size may be unknown, so the final partial
        block never reaches the block boundary and would otherwise stay in
        the pending buffer forever, truncating the tail of the file.
        """
        with self._lock:
            committed = 0
            for idx in sorted(self._pending):
                buf = self._pending.pop(idx)
                if not buf:
                    continue
                block = bytes(buf[:BLOCK_SIZE])
                old = self._blocks.get(idx)
                if old is not None:
                    self._blocks.move_to_end(idx)
                    if len(old) != len(block):
                        self._resident += len(block) - len(old)
                        self._blocks[idx] = block
                else:
                    self._blocks[idx] = block
                    self._resident += len(block)
                committed += len(block)
            self._evict()
            return committed

    # ------------------------------------------------------------------ reading

    def read_span(self, start: int, end: int) -> Optional[bytes]:
        """Return bytes for ``[start, end)`` if every block is cached, else None."""
        if end <= start:
            return b""
        first, last = self.block_span(start, end)
        with self._lock:
            parts: list[bytes] = []
            for idx in range(first, last + 1):
                data = self._blocks.get(idx)
                if data is None:
                    return None
                self._blocks.move_to_end(idx)
                parts.append(data)
        joined = b"".join(parts)
        cut_start = start - first * BLOCK_SIZE
        cut_end = cut_start + (end - start)
        return joined[cut_start:cut_end]

    def has_block(self, idx: int) -> bool:
        with self._lock:
            return idx in self._blocks

    def contiguous_bytes(self) -> int:
        """Bytes playable in order from offset 0 (no gaps before this point)."""
        with self._lock:
            idx = 0
            while idx in self._blocks:
                idx += 1
            return idx * BLOCK_SIZE

    def resident_bytes(self) -> int:
        with self._lock:
            return self._resident

    def clear(self) -> None:
        with self._lock:
            self._blocks.clear()
            self._pending.clear()
            self._resident = 0
