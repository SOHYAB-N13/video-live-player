"""HTTP client used to probe and fetch data from the remote media server."""

from __future__ import annotations

import re
import time
from typing import Callable, Iterator, Optional
from urllib.parse import urlparse

from .datatypes import MediaInfo

try:  # graceful detection - the caller reports a friendly error if missing
    import requests  # type: ignore
except ImportError:  # pragma: no cover
    requests = None  # type: ignore[assignment]

try:  # silence InsecureRequestWarning when --insecure is used
    import urllib3

    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
except Exception:  # noqa: BLE001
    pass

DEFAULT_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) MediaStreamer/1.0"
CHUNK = 64 * 1024  #: Size of streamed chunks in bytes.


class RangeNotSupported(Exception):
    """Raised when the server ignores Range requests (always answers 200)."""


class RemoteStreamError(Exception):
    """Raised when the remote media cannot be fetched after all retries."""


def _parse_length(headers) -> Optional[int]:
    content_length = headers.get("Content-Length")
    if content_length and content_length.isdigit():
        return int(content_length)
    content_range = headers.get("Content-Range")
    if content_range and "/" in content_range:
        total = content_range.rsplit("/", 1)[-1].strip()
        if total.isdigit():
            return int(total)
    return None


def _parse_filename(headers, url: str) -> str:
    from urllib.parse import unquote

    disposition = headers.get("Content-Disposition") or ""
    match = re.search(r"filename\*?=(?:UTF-8\'\')?\"?([^\";]+)\"?", disposition, re.IGNORECASE)
    if match:
        name = match.group(1).strip().strip('"')
        if name:
            return unquote(name)
    path = urlparse(url).path
    base = path.rsplit("/", 1)[-1] if path else ""
    return base or "media"


class RemoteStream:
    """Robust HTTP client for a single direct media URL."""

    def __init__(
        self,
        url: str,
        insecure: bool = False,
        timeout: tuple[float, float] = (5.0, 30.0),
        retries: int = 3,
        backoff: float = 1.0,
        log: Optional[Callable[[str, str], None]] = None,
    ) -> None:
        if requests is None:
            raise RemoteStreamError("کتابخانه requests نصب نیست.")
        self.url = url
        self.insecure = insecure
        self.timeout = timeout
        self.retries = max(1, retries)
        self.backoff = backoff
        self._log = log or (lambda msg, level="info": None)
        self.session = requests.Session()
        self.session.headers["User-Agent"] = DEFAULT_USER_AGENT
        self.session.verify = not insecure
        self.media_info: Optional[MediaInfo] = None

    # ------------------------------------------------------------------ probe

    def probe(self) -> MediaInfo:
        """Inspect headers to learn length, type, range support and filename."""
        length: Optional[int] = None
        content_type: Optional[str] = None
        filename: str = "media"
        accepts_ranges = False
        ok = False
        encoding = None

        # 1) Prefer HEAD when available.
        try:
            resp = self.session.head(self.url, timeout=self.timeout, allow_redirects=True)
            ok = 200 <= resp.status_code < 300
            if ok:
                length = _parse_length(resp.headers)
                content_type = resp.headers.get("Content-Type")
                accepts_ranges = resp.headers.get("Accept-Ranges", "").lower() == "bytes"
                filename = _parse_filename(resp.headers, self.url)
                encoding = resp.headers.get("Content-Encoding")
            resp.close()
        except requests.RequestException:
            pass

        # 2) Fallback / confirmation: GET with a one-byte range.
        if not ok or length is None or not accepts_ranges:
            try:
                resp = self.session.get(
                    self.url,
                    headers={"Range": "bytes=0-0"},
                    stream=True,
                    timeout=self.timeout,
                    allow_redirects=True,
                )
                if resp.status_code in (200, 206):
                    ok = True
                    if resp.status_code == 206:
                        accepts_ranges = True
                    content_range = resp.headers.get("Content-Range")
                    if content_range and "/" in content_range:
                        total = content_range.rsplit("/", 1)[-1].strip()
                        if total.isdigit():
                            length = int(total)
                    if length is None:
                        length = _parse_length(resp.headers)
                    content_type = content_type or resp.headers.get("Content-Type")
                    filename = _parse_filename(resp.headers, self.url) or filename
                    encoding = encoding or resp.headers.get("Content-Encoding")
                resp.close()
            except requests.RequestException:
                ok = False

        if not ok:
            raise RemoteStreamError("امکان اتصال به سرور وجود ندارد یا لینک معتبر نیست.")

        # Random access needs a known length and no transfer/content encoding.
        if length is None or not accepts_ranges or encoding:
            accepts_ranges = False

        self.media_info = MediaInfo(
            url=self.url,
            content_length=length,
            content_type=content_type,
            filename=filename,
            accepts_ranges=accepts_ranges,
        )
        return self.media_info

    # ------------------------------------------------------------------ fetching

    def iter_range(
        self,
        start: int,
        end: int,
        on_bytes: Optional[Callable[[int], None]] = None,
        cancelled: Optional[Callable[[], bool]] = None,
    ) -> Iterator[bytes]:
        """Yield bytes for the inclusive range ``[start, end]``.

        Uses HTTP Range requests and retries transient connection failures by
        resuming from the last successfully delivered byte.
        """
        if self.media_info is None:
            self.probe()
        pos = start
        while pos <= end:
            for attempt in range(self.retries):
                if cancelled is not None and cancelled():
                    return
                resp = None
                try:
                    resp = self.session.get(
                        self.url,
                        headers={"Range": f"bytes={pos}-{end}"},
                        stream=True,
                        timeout=self.timeout,
                        allow_redirects=True,
                    )
                    code = resp.status_code
                    if code == 416:
                        if self.media_info.content_length is not None and pos >= self.media_info.content_length:
                            return
                        raise RemoteStreamError(f"بازه درخواستی نامعتبر است ({pos}-{end}).")
                    if code == 200 and pos > 0:
                        raise RangeNotSupported()
                    if code not in (200, 206):
                        raise RemoteStreamError(f"خطای سرور: HTTP {code}")
                    for chunk in resp.iter_content(chunk_size=CHUNK):
                        if not chunk:
                            continue
                        if cancelled is not None and cancelled():
                            return
                        pos += len(chunk)
                        yield chunk
                        if on_bytes is not None:
                            on_bytes(len(chunk))
                        if pos > end:
                            return
                    return
                except RangeNotSupported:
                    raise
                except RemoteStreamError:
                    raise
                except requests.RequestException as exc:
                    if attempt + 1 < self.retries and not (cancelled is not None and cancelled()):
                        time.sleep(self.backoff * (attempt + 1))
                        continue
                    raise RemoteStreamError(f"اتصال در حین دریافت داده قطع شد: {exc}") from exc
                finally:
                    if resp is not None:
                        resp.close()

    def iter_stream(
        self,
        on_bytes: Optional[Callable[[int], None]] = None,
        cancelled: Optional[Callable[[], bool]] = None,
    ) -> Iterator[bytes]:
        """Sequential full GET, used when the server does not support ranges."""
        for attempt in range(self.retries):
            resp = None
            try:
                resp = self.session.get(self.url, stream=True, timeout=self.timeout, allow_redirects=True)
                code = resp.status_code
                if 200 <= code < 300:
                    for chunk in resp.iter_content(chunk_size=CHUNK):
                        if not chunk:
                            continue
                        if cancelled is not None and cancelled():
                            return
                        yield chunk
                        if on_bytes is not None:
                            on_bytes(len(chunk))
                    return
                raise RemoteStreamError(f"خطای سرور: HTTP {code}")
            except RemoteStreamError:
                raise
            except requests.RequestException as exc:
                if attempt + 1 < self.retries and not (cancelled is not None and cancelled()):
                    time.sleep(self.backoff * (attempt + 1))
                    continue
                raise RemoteStreamError(f"دریافت جریان داده با شکست مواجه شد: {exc}") from exc
            finally:
                if resp is not None:
                    resp.close()

    # ------------------------------------------------------------------ teardown

    def close(self) -> None:
        try:
            self.session.close()
        except Exception:  # noqa: BLE001
            pass
