"""Local HTTP server that feeds the embedded player from a remote media source.

The player never talks to the internet directly. It requests byte ranges
from this loopback server; the proxy serves them from the in-memory
:class:`core.cache.BlockCache` and fetches whatever is missing from the
remote media server using HTTP Range requests. When the remote server does
not support ranges, a sequential feeder streams the file through.

Only the loopback interface is bound and a random per-session token must be
present in the URL, so no other local process can probe the stream.
"""

from __future__ import annotations

import re
import secrets
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Optional

from .cache import BlockCache
from .datatypes import StatsCollector
from .events import EventBus
from .fetcher import RangeFetcher, ReadAhead, SequentialFeeder
from .remote import RemoteStream

SERVE_CHUNK = 256 * 1024  #: Chunk size streamed to the player at a time.
READ_AHEAD_START = 2 * 1024 * 1024  #: parallel read-ahead begins after the warm-up prefetch


class _ProxyHandler(BaseHTTPRequestHandler):
    """Serves ``/<token>/stream`` with HTTP Range support for the player."""

    protocol_version = "HTTP/1.1"
    server_version = "MediaStreamer/1.0"
    sys_version = ""
    proxy = None  # type: ignore[assignment]

    def log_message(self, _format: str, *_args: object) -> None:
        pass

    # ------------------------------------------------------------------ helpers

    def _resolve(self) -> bool:
        if _ProxyHandler.proxy is None:
            return False
        parts = self.path.split("?", 1)[0].strip("/").split("/")
        return len(parts) == 2 and parts[0] == _ProxyHandler.proxy.token and parts[1] == "stream"

    def _send_headers(self, status: int, start: int, end: int, length: object) -> None:
        total = _ProxyHandler.proxy.total
        self.send_response(status)
        self.send_header("Content-Type", _ProxyHandler.proxy.content_type or "application/octet-stream")
        self.send_header("Accept-Ranges", "bytes" if _ProxyHandler.proxy.range_mode else "none")
        if length is not None:
            self.send_header("Content-Length", str(length))
        if status == 206 and total is not None:
            self.send_header("Content-Range", f"bytes {start}-{end}/{total}")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")
        self.end_headers()

    def _bad(self, code: int, message: str) -> None:
        body = message.encode("utf-8", errors="replace")
        self.send_response(code)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.end_headers()
        try:
            self.wfile.write(body)
            self.wfile.flush()
        except OSError:
            pass

    # ------------------------------------------------------------------ verbs

    def do_HEAD(self) -> None:  # noqa: N802 (HTTP verb)
        if not self._resolve():
            self._bad(404, "Not Found")
            return
        total = _ProxyHandler.proxy.total
        if total is None:
            self._bad(400, "Length unknown")
            return
        self._send_headers(200, 0, total - 1, total)

    def do_GET(self) -> None:  # noqa: N802 (HTTP verb)
        if not self._resolve():
            self._bad(404, "Not Found")
            return
        try:
            self._serve()
        except Exception as exc:  # noqa: BLE001 - never kill the server
            _ProxyHandler.proxy.log(f"خطای داخلی پروکسی: {exc}", "error")
            try:
                self._bad(500, "Internal Error")
            except OSError:
                pass

    # ------------------------------------------------------------------ serving

    def _serve(self) -> None:
        proxy = _ProxyHandler.proxy
        total = proxy.total
        self._client_gone = threading.Event()

        start, end, status = 0, None, 200
        if total is not None:
            range_header = self.headers.get("Range")
            if range_header and proxy.range_mode:
                match = re.match(r"bytes=(\d*)-(\d*)", range_header)
                if match:
                    a, b = match.group(1), match.group(2)
                    if a == "" and b == "":
                        start, end = 0, total - 1
                    elif a == "":
                        count = int(b)
                        start, end = max(0, total - count), total - 1
                    else:
                        start = int(a)
                        end = min(int(b), total - 1) if b else total - 1
                    if start >= total or start > end:
                        self._bad(416, "Range Not Satisfiable")
                        return
                    status = 206
                else:
                    start, end = 0, total - 1
            else:
                start, end = 0, total - 1

        length = (end - start + 1) if end is not None else None
        self._send_headers(status, start, end or 0, length)

        try:
            if proxy.range_mode and total is not None:
                self._serve_range_progressively(start, end)
            else:
                self._serve_sequentially(start, end)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            self._client_gone.set()
        except OSError:
            self._client_gone.set()
        except Exception as exc:  # noqa: BLE001
            self._client_gone.set()
            proxy.log(f"خطا هنگام ارسال داده: {exc}", "error")

    def _serve_range_progressively(self, start: int, end: int) -> None:
        """Serve a byte range in bounded windows, fetching each on demand.

        The player (VLC or the HTML5 media element) may ask for an open-ended
        range such as ``bytes=0-``. Fetching that entire range up front would
        download the whole file, so instead we fetch and forward one window at
        a time. The socket's back-pressure naturally paces how fast we run
        ahead of the player, and when the player closes the connection we stop
        fetching almost immediately.
        """
        proxy = _ProxyHandler.proxy
        fetcher = proxy.fetcher
        pos = start
        while True:
            if self._client_gone.is_set():
                return
            if pos >= end + 1:
                return
            window_end = min(pos + SERVE_CHUNK, end + 1)
            data = fetcher.get_span(pos, window_end, self._client_gone.is_set)
            if data is None:
                return
            self.wfile.write(data)
            self.wfile.flush()
            pos = window_end

    def _serve_sequentially(self, start: int, end: object) -> None:
        """Stream through the sequential feeder, waiting as data arrives."""
        proxy = _ProxyHandler.proxy
        feeder = proxy.feeder
        pos = start
        while True:
            if self._client_gone.is_set():
                return
            want = pos + SERVE_CHUNK
            if end is not None:
                if pos >= int(end) + 1:
                    return
                want = min(want, int(end) + 1)
            avail = min(feeder.wait_until(want), want)
            if avail <= pos:
                if feeder.is_done():
                    return
                time.sleep(0.05)
                continue
            data = proxy.cache.read_span(pos, avail)
            if data is None:
                time.sleep(0.02)
                continue
            self.wfile.write(data)
            self.wfile.flush()
            pos = avail
            feeder.set_consumed(pos)
            if end is not None and pos >= int(end) + 1:
                return
            if feeder.is_done() and pos >= feeder.available():
                return


def _locate_moov_after_mdat(head: bytes) -> Optional[int]:
    """Return the byte offset of the moov box for a simple non-fragmented MP4.

    Handles the common layout ``ftyp [free|skip|wide]* mdat moov`` and returns
    the offset of ``moov`` (the box right after the single known-size ``mdat``
    box). Returns None when the layout is fragmented or cannot be determined,
    in which case no moov preloading is attempted.
    """
    off = 0
    while off + 8 <= len(head):
        size = int.from_bytes(head[off : off + 4], "big")
        btype = head[off + 4 : off + 8].decode("latin1", "replace")
        if size == 0:
            return None
        header = 8
        if size == 1:
            if off + 16 > len(head):
                return None
            size = int.from_bytes(head[off + 8 : off + 16], "big")
            header = 16
        if size < header:
            return None
        if btype in ("ftyp", "free", "skip", "wide"):
            off += size
            continue
        if btype == "moov":
            return None  # faststart - no tail preload needed
        if btype == "mdat":
            return off + size
        return None  # sidx / moof / unknown -> fragmented or complex
    return None


class LocalProxy:
    """Owns the loopback HTTP server together with the data-moving pieces."""

    def __init__(
        self,
        cache: BlockCache,
        remote: RemoteStream,
        metrics: StatsCollector,
        bus: EventBus,
        total: object,
        content_type: object,
        range_mode: bool,
        keep_ahead: int,
        download_workers: int = 3,
        log: object = None,
    ) -> None:
        self.cache = cache
        self.remote = remote
        self.metrics = metrics
        self.bus = bus
        self.total = total
        self.content_type = content_type
        self.range_mode = range_mode
        self.keep_ahead = keep_ahead
        self.download_workers = max(1, int(download_workers))
        self.log = log
        self.token = secrets.token_hex(8)
        self.feeder: Optional[SequentialFeeder] = None
        self.fetcher: Optional[RangeFetcher] = None
        self.read_ahead: Optional[ReadAhead] = None
        _ProxyHandler.proxy = self
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), _ProxyHandler)
        self.httpd.daemon_threads = True
        self.port = self.httpd.server_address[1]

    # ------------------------------------------------------------------ lifecycle

    def start(self) -> None:
        if not self.range_mode:
            self.feeder = SequentialFeeder(
                self.remote,
                self.cache,
                self.keep_ahead,
                self.metrics,
                self.bus,
                self.log,
            )
            self.feeder.start()
        else:
            self.fetcher = RangeFetcher(
                self.remote,
                self.cache,
                self.total,
                self.metrics,
                self.log,
            )
            self.read_ahead = ReadAhead(
                cache=self.cache,
                fetcher=self.fetcher,
                metrics=self.metrics,
                total=int(self.total) if self.total is not None else None,
                keep_ahead=self.keep_ahead,
                workers=self.download_workers,
                initial_cursor=min(READ_AHEAD_START, int(self.total)) if self.total is not None else READ_AHEAD_START,
                log=self.log,
            )
            self.read_ahead.start()
        threading.Thread(target=self.httpd.serve_forever, name="proxy-server", daemon=True).start()

    def base_url(self) -> str:
        """Loopback URL handed to the player."""
        return f"http://127.0.0.1:{self.port}/{self.token}/stream"

    def prefetch(self, amount: int) -> None:
        """Warm the cache with the first bytes so playback starts instantly."""
        if not self.range_mode or self.total is None:
            return
        target = min(int(amount), int(self.total))
        if target <= 0:
            return

        def _do() -> None:
            try:
                if self.fetcher is not None:
                    self.fetcher.get_span(0, target, cancelled=lambda: False)
            except Exception:  # noqa: BLE001
                pass

        threading.Thread(target=_do, name="prefetch", daemon=True).start()

    def prefetch_mp4_moov(self) -> None:
        """Warm the cache with the moov atom of a non-faststart MP4.

        The moov atom holds the movie metadata and playback cannot start
        until it is read. In files that are not "faststart" the moov box
        lives at the very end, right after the (single) mdat box. This parses
        the top-level boxes cheaply and, when the layout matches, preloads
        exactly that tail region so the player finds the metadata instantly
        instead of waiting for a slow tail fetch.
        """
        if not self.range_mode or self.total is None:
            return

        def _do() -> None:
            try:
                head = b"".join(
                    self.remote.iter_range(0, min(65535, int(self.total) - 1), cancelled=lambda: False)
                )
                moov_start = _locate_moov_after_mdat(head)
                if moov_start is None or moov_start >= int(self.total):
                    return
                if self.fetcher is not None:
                    self.fetcher.get_span(moov_start, int(self.total), cancelled=lambda: False)
            except Exception:  # noqa: BLE001
                pass

        threading.Thread(target=_do, name="moov-prefetch", daemon=True).start()

    def close(self) -> None:
        if self.read_ahead is not None:
            self.read_ahead.stop()
        if self.feeder is not None:
            self.feeder.stop()
        try:
            self.httpd.shutdown()
        except Exception:  # noqa: BLE001
            pass
        try:
            self.httpd.server_close()
        except Exception:  # noqa: BLE001
            pass

