"""StreamController drives a single streaming session and exposes statistics."""

from __future__ import annotations

import threading
from typing import Optional

from .cache import BlockCache
from .datatypes import StatsCollector, StatsSnapshot, StreamStatus, html5_playable
from .events import EventBus
from .player import Player
from .proxy import LocalProxy
from .remote import RemoteStream, RemoteStreamError

MIB = 1024 * 1024
DEFAULT_CACHE = 256 * MIB  #: Default RAM budget for the streaming buffer.
DEFAULT_KEEP_AHEAD = 64 * MIB  #: Default max lead in no-range fallback mode.
PREFETCH_FIRST = 2 * MIB  #: Bytes warmed before the player connects.

#: Status values the WebView may push back for HTML5 playback.
UI_STATUS_MAP = {
    "connecting": StreamStatus.CONNECTING,
    "buffering": StreamStatus.BUFFERING,
    "playing": StreamStatus.PLAYING,
    "paused": StreamStatus.PAUSED,
    "ended": StreamStatus.STOPPED,
    "error": StreamStatus.ERROR,
}


class StreamController:
    """High-level facade used by the WebView bridge.

    Only one session runs at a time; starting a new one stops the previous.
    The UI only ever calls the public methods below and reads snapshots.
    """

    def __init__(
        self,
        bus: EventBus,
        cache_capacity: int = DEFAULT_CACHE,
        keep_ahead: int = DEFAULT_KEEP_AHEAD,
        insecure: bool = False,
        prefer_html5: bool = True,
        download_workers: int = 3,
    ) -> None:
        self.bus = bus
        self.cache_capacity = max(cache_capacity, 32 * MIB)
        self.keep_ahead = max(keep_ahead, 8 * MIB)
        self.insecure = insecure
        self.prefer_html5 = prefer_html5
        self.download_workers = max(1, int(download_workers))
        self._lock = threading.Lock()
        self._session: Optional[_Session] = None

    # ------------------------------------------------------------------ control

    def start(self, url: object, hwnd: object = None) -> None:
        url_text = str(url or "").strip()
        if not url_text:
            self.bus.emit("log", "لینک ویدیو را وارد کنید.", "warning")
            return
        if not url_text.lower().startswith(("http://", "https://")):
            self.bus.emit("log", "فقط لینک‌های http:// یا https:// پشتیبانی می‌شوند.", "error")
            return
        self.stop()
        session = _Session(
            self.bus,
            url_text,
            hwnd,
            self.cache_capacity,
            self.keep_ahead,
            self.insecure,
            self.prefer_html5,
            self.download_workers,
        )
        with self._lock:
            self._session = session
        session.start()

    def stop(self) -> None:
        with self._lock:
            session = self._session
        if session is not None:
            session.stop()

    def current_session(self) -> Optional["_Session"]:
        with self._lock:
            return self._session

    def toggle_pause(self) -> None:
        with self._lock:
            session = self._session
        if session is not None:
            session.toggle_pause()

    def seek(self, ms: int) -> None:
        with self._lock:
            session = self._session
        if session is not None:
            session.seek(ms)

    def set_volume(self, volume: int) -> None:
        with self._lock:
            session = self._session
        if session is not None:
            session.set_volume(volume)

    # ------------------------------------------------------------------ stats

    def snapshot(self) -> StatsSnapshot:
        with self._lock:
            session = self._session
        if session is not None:
            return session.snapshot()
        return StatsSnapshot(
            status=StreamStatus.IDLE,
            bytes_fetched=0,
            bytes_total=None,
            cache_bytes=0,
            cache_capacity=self.cache_capacity,
            speed_bps=0.0,
            position_ms=0,
            length_ms=0,
        )

    def close(self) -> None:
        self.stop()


class _Session:
    """Owns the resources of one playback: remote, cache, proxy, player.

    A session runs in one of two playback modes:

    * ``html5`` - the WebView's ``<video>`` element streams directly from the
      loopback proxy (fast start, native seeking, no extra window);
    * ``vlc`` - the bundled VLC player decodes formats the browser cannot
      (MKV, AVI, ...) and shows its own window.
    """

    def __init__(
        self,
        bus: EventBus,
        url: str,
        hwnd: object,
        cache_capacity: int,
        keep_ahead: int,
        insecure: bool,
        prefer_html5: bool,
        download_workers: int = 3,
    ) -> None:
        self.bus = bus
        self.url = url
        self.hwnd = hwnd
        self.cache_capacity = cache_capacity
        self.keep_ahead = keep_ahead
        self.insecure = insecure
        self.prefer_html5 = prefer_html5
        self.download_workers = max(1, int(download_workers))
        self._stop = threading.Event()
        self._done = threading.Event()
        self._ready = threading.Event()
        self.status = StreamStatus.IDLE
        self.mode = "vlc"
        self.content_type: object = None
        self.content_length: object = None
        self.filename: str = ""
        self.error_message: Optional[str] = None
        self.metrics = StatsCollector(cache_capacity)
        self.remote: Optional[RemoteStream] = None
        self.cache: Optional[BlockCache] = None
        self.proxy: Optional[LocalProxy] = None
        self.player: Optional[Player] = None

    # ------------------------------------------------------------------ lifecycle

    def start(self) -> None:
        threading.Thread(target=self._run, name="session", daemon=True).start()

    def _run(self) -> None:
        try:
            self._set_status(StreamStatus.PROBING)
            self.remote = RemoteStream(self.url, insecure=self.insecure, log=self._emit_log)
            info = self.remote.probe()
            self._emit_log(f"اتصال برقرار شد: {info.filename or info.url}", "info")
            self.metrics.bytes_total = info.content_length
            self.content_type = info.content_type
            self.content_length = info.content_length
            self.filename = info.filename
            if self._stop.is_set():
                return

            self.cache = BlockCache(self.cache_capacity, info.content_length)
            self.proxy = LocalProxy(
                cache=self.cache,
                remote=self.remote,
                metrics=self.metrics,
                bus=self.bus,
                total=info.content_length,
                content_type=info.content_type,
                range_mode=info.accepts_ranges,
                keep_ahead=self.keep_ahead,
                download_workers=self.download_workers,
                log=self._emit_log,
            )
            self.proxy.start()
            self.proxy.prefetch(PREFETCH_FIRST)
            self.proxy.prefetch_mp4_moov()
            if self._stop.is_set():
                return

            self.mode = "html5" if (self.prefer_html5 and html5_playable(info.content_type)) else "vlc"
            if self.mode == "vlc":
                self.player = Player(log=self._emit_log)
                self._set_status(StreamStatus.CONNECTING)
                self._emit_log("در حال شروع پخش در VLC...", "info")
                self.player.play(self.proxy.base_url(), self.hwnd)
            else:
                self._set_status(StreamStatus.CONNECTING)
                self._emit_log("جریان برای پخش درون‌برنامه‌ای آماده است.", "info")
            self._ready.set()
            self._monitor()
        except RemoteStreamError as exc:
            self.error_message = str(exc)
            self._set_status(StreamStatus.ERROR)
            self._emit_log(f"خطا: {exc}", "error")
        except RuntimeError as exc:
            self.error_message = str(exc)
            self._set_status(StreamStatus.ERROR)
            self._emit_log(f"خطا: {exc}", "error")
        except Exception as exc:  # noqa: BLE001 - never crash the app
            self.error_message = str(exc)
            self._set_status(StreamStatus.ERROR)
            self._emit_log(f"خطای غیرمنتظره: {exc}", "error")
        finally:
            self._ready.set()
            self._cleanup()
            self._done.set()

    def _monitor(self) -> None:
        last = None
        while not self._stop.is_set():
            player = self.player
            if player is not None:
                state = player.state_name()
                if state and state != last:
                    last = state
                    self._emit_log(f"وضعیت پخش‌کننده: {state}", "debug")
                self.metrics.set_position(player.get_time_ms(), player.get_length_ms())
                self._apply_player_state(state)
            if self.cache is not None:
                self.metrics.set_cache_bytes(self.cache.resident_bytes())
            self._stop.wait(0.35)

    def _apply_player_state(self, state: object) -> None:
        if state == "Ended":
            self._set_status(StreamStatus.STOPPED)
            self._emit_log("پخش به پایان رسید.", "info")
            self._stop.set()
        elif state == "Error":
            self._set_status(StreamStatus.ERROR)
            self._emit_log("پخش‌کننده با خطا مواجه شد؛ لینک را دوباره تلاش کنید.", "error")
        elif state == "Buffering":
            self._set_status(StreamStatus.BUFFERING)
        elif state == "Playing":
            self._set_status(StreamStatus.PLAYING)
        elif state == "Paused":
            self._set_status(StreamStatus.PAUSED)
        elif state == "Stopped":
            self._set_status(StreamStatus.STOPPED)

    # ------------------------------------------------------------------ bridge API

    def wait_ready(self, timeout: float = 25.0) -> bool:
        """Block until the session is ready or has failed; return success."""
        self._ready.wait(timeout)
        return self.error_message is None and self.proxy is not None

    def stream_info(self) -> Optional[dict]:
        """Serializable description of the ready stream for the WebView."""
        if self.proxy is None:
            return None
        return {
            "mode": self.mode,
            "url": self.proxy.base_url() if self.mode == "html5" else None,
            "content_type": self.content_type,
            "content_length": self.content_length,
            "filename": self.filename,
        }

    def start_vlc_fallback(self) -> None:
        """Switch an html5-mode session over to the VLC player (browser reject)."""
        if self._stop.is_set() or self.proxy is None:
            return
        if self.player is not None:
            return
        try:
            self.mode = "vlc"
            self.player = Player(log=self._emit_log)
            self._set_status(StreamStatus.CONNECTING)
            self._emit_log("پخش به VLC واگذار شد.", "warning")
            self.player.play(self.proxy.base_url(), self.hwnd)
        except Exception as exc:  # noqa: BLE001
            self._set_status(StreamStatus.ERROR)
            self._emit_log(f"خطا در راه‌اندازی VLC: {exc}", "error")

    def set_ui_status(self, value: object) -> None:
        """Apply a status reported by the WebView (HTML5 playback mode)."""
        status = UI_STATUS_MAP.get(str(value))
        if status is None:
            return
        self._set_status(status)
        if status == StreamStatus.STOPPED:
            self._emit_log("پخش به پایان رسید.", "info")

    def set_ui_position(self, position_ms: object, length_ms: object) -> None:
        try:
            self.metrics.set_position(int(position_ms), int(length_ms))
        except (TypeError, ValueError):
            pass

    # ------------------------------------------------------------------ control

    def stop(self) -> None:
        self._stop.set()
        player = self.player
        if player is not None:
            player.stop()
        self._done.wait(timeout=3.0)

    def toggle_pause(self) -> None:
        player = self.player
        if player is None:
            return
        if player.is_playing():
            player.set_pause(True)
        else:
            player.set_pause(False)

    def seek(self, ms: int) -> None:
        player = self.player
        if player is not None:
            player.set_time_ms(ms)

    def set_volume(self, volume: int) -> None:
        player = self.player
        if player is not None:
            player.set_volume(volume)

    def set_fullscreen(self, enabled: bool) -> None:
        """Mirror the app's fullscreen to VLC when playing in VLC mode."""
        if self.mode != "vlc":
            return
        player = self.player
        if player is not None:
            player.set_fullscreen(bool(enabled))

    def snapshot(self) -> StatsSnapshot:
        return self.metrics.snapshot()

    # ------------------------------------------------------------------ internals

    def _cleanup(self) -> None:
        if self.proxy is not None:
            try:
                self.proxy.close()
            except Exception:  # noqa: BLE001
                pass
        if self.player is not None:
            try:
                self.player.release()
            except Exception:  # noqa: BLE001
                pass
        if self.remote is not None:
            try:
                self.remote.close()
            except Exception:  # noqa: BLE001
                pass
        if self.cache is not None:
            try:
                self.cache.clear()
            except Exception:  # noqa: BLE001
                pass
        self._set_status(StreamStatus.STOPPED)

    def _set_status(self, status: StreamStatus) -> None:
        self.status = status
        self.metrics.status = status
        self.bus.emit("status", status)

    def _emit_log(self, message: str, level: str = "info") -> None:
        self.bus.emit("log", message, level)
