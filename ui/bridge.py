"""WebView bridge: the JavaScript <-> Python API.

This class is passed to pywebview as ``js_api``. Every public method becomes
callable from JavaScript via ``pywebview.api.<method>(...)`` and its return
value is JSON-serialized back to the browser. All backend work stays in
Python; the UI is a pure HTML/CSS/JS consumer.
"""

from __future__ import annotations

import re
from collections import deque
from typing import Optional

from core.controller import StreamController
from core.datatypes import StreamStatus
from core.events import EventBus
from ui.win_controls import WindowControls

#: Log levels forwarded to the WebView (debug noise is dropped).
VISIBLE_LOG_LEVELS = frozenset({"info", "warning", "error"})

#: Persian -> English translation for backend log messages (used when the
#: UI language is English). Exact strings first, then regex patterns for the
#: messages that carry dynamic parts.
_LOG_EN: list[tuple[object, str]] = [
    ("لینک ویدیو را وارد کنید.", "Please enter a video link."),
    ("فقط لینک‌های http:// یا https:// پشتیبانی می‌شوند.", "Only http:// or https:// links are supported."),
    ("جریان برای پخش درون‌برنامه‌ای آماده است.", "Stream is ready for in-app playback."),
    ("در حال شروع پخش در VLC...", "Starting playback in VLC..."),
    ("در حال شروع پخش...", "Starting playback..."),
    ("پخش به پایان رسید.", "Playback finished."),
    ("پخش به VLC واگذار شد.", "Playback handed over to VLC."),
    (
        "پخش‌کننده با خطا مواجه شد؛ لینک را دوباره تلاش کنید.",
        "The player ran into an error; please try the link again.",
    ),
    ("امکان اتصال به سرور وجود ندارد یا لینک معتبر نیست.", "Could not connect to the server or the link is not valid."),
    ("کتابخانه python-vlc نصب نیست.", "The python-vlc library is not installed."),
    ("شروع جلسه ممکن نشد.", "Could not start the session."),
    ("اتصال برقرار نشد؛ لینک را بررسی کنید.", "Connection failed; check the link."),
    ("جریان آماده نشد.", "The stream is not ready."),
    ("جلسه فعالی وجود ندارد.", "There is no active session."),
    (re.compile(r"^اتصال برقرار شد: (.*)$"), r"Connected: \1"),
    (re.compile(r"^خطا: (.*)$"), r"Error: \1"),
    (re.compile(r"^خطای غیرمنتظره: (.*)$"), r"Unexpected error: \1"),
    (re.compile(r"^وضعیت پخش‌کننده: (.*)$"), r"Player state: \1"),
    (re.compile(r"^خطا در راه‌اندازی VLC: (.*)$"), r"Failed to start VLC: \1"),
    (re.compile(r"^بازه درخواستی نامعتبر است \((\d+)-(\d+)\)\.$"), r"Invalid requested range (\1-\2)."),
    (re.compile(r"^خطای سرور: HTTP (\d+)$"), r"Server error: HTTP \1"),
    (re.compile(r"^اتصال در حین دریافت داده قطع شد: (.*)$"), r"Connection interrupted while receiving data: \1"),
    (re.compile(r"^دریافت جریان داده با شکست مواجه شد: (.*)$"), r"Failed to receive the data stream: \1"),
    (re.compile(r"^دریافت داده ناموفق بود \((\d+)-(\d+)\): (.*)$"), r"Failed to fetch data (\1-\2): \3"),
    (re.compile(r"^پیش‌خوانی داده با خطا مواجه شد: (.*)$"), r"Read-ahead fetch failed: \1"),
    (re.compile(r"^دریافت جریان متوقف شد: (.*)$"), r"Stream reception stopped: \1"),
    (re.compile(r"^خطای داخلی پروکسی: (.*)$"), r"Internal proxy error: \1"),
    (re.compile(r"^خطا هنگام ارسال داده: (.*)$"), r"Error while sending data: \1"),
    (re.compile(r"^VLC قابل اجرا نیست: (.*)$"), r"VLC could not be started: \1"),
    (re.compile(r"^اتصال پنجره ویدیو ناموفق بود: (.*)$"), r"Failed to attach the video window: \1"),
]


def _translate_log(message: str) -> str:
    """Translate a known Persian backend message into English."""
    for pattern, replacement in _LOG_EN:
        if isinstance(pattern, re.Pattern):
            translated = pattern.sub(replacement, message)
            if translated != message:
                return translated
        elif message == pattern:
            return replacement
    return message


class StreamBridge:
    """Adapter exposed to JavaScript through the WebView API."""

    def __init__(self, controller: StreamController, bus: EventBus) -> None:
        self.controller = controller
        self.win = WindowControls()
        self.language = "en"
        self._logs: deque[dict[str, str]] = deque(maxlen=1000)
        bus.subscribe("log", self._on_log)

    def on_gui_started(self) -> None:
        """Attach to the host window once the pywebview GUI is running."""
        self.win.bind()

    # ------------------------------------------------------------------ window controls

    def window_minimize(self) -> dict:
        self.win.minimize()
        return {"ok": True}

    def window_toggle_maximize(self) -> dict:
        self.win.toggle_maximize()
        return {"ok": True}

    def window_close(self) -> dict:
        self.win.close()
        return {"ok": True}

    def window_toggle_fullscreen(self) -> dict:
        """Toggle OS-level fullscreen and mirror it to VLC when applicable."""
        target = not self.win.is_fullscreen()
        self.win.toggle_fullscreen()
        session = self.controller.current_session()
        if session is not None:
            session.set_fullscreen(target)
        return {"ok": True}

    def window_start_drag(self) -> dict:
        self.win.start_drag()
        return {"ok": True}

    def window_drag_to(self, x: object, y: object) -> dict:
        try:
            self.win.drag_to(int(float(x)), int(float(y)))
        except (TypeError, ValueError):
            pass
        return {"ok": True}

    def window_end_drag(self) -> dict:
        self.win.end_drag()
        return {"ok": True}

    # ------------------------------------------------------------------ backend events

    def _on_log(self, message: object, level: str = "info") -> None:
        if level not in VISIBLE_LOG_LEVELS:
            return
        text = str(message)
        if self.language == "en":
            text = _translate_log(text)
        self._logs.append({"level": level, "message": text})

    def set_language(self, lang: object) -> dict:
        """Record the UI language so backend log messages are translated."""
        self.language = "en" if str(lang or "").lower().startswith("en") else "fa"
        return {"ok": True}

    # ------------------------------------------------------------------ actions

    def play(self, url: object) -> dict:
        """Start a streaming session and wait until it is ready (or failed)."""
        self.controller.start(str(url or "").strip())
        session = self.controller.current_session()
        if session is None:
            return {"ok": False, "error": "شروع جلسه ممکن نشد."}
        ready = session.wait_ready(timeout=25.0)
        if not ready:
            return {
                "ok": False,
                "error": session.error_message or "اتصال برقرار نشد؛ لینک را بررسی کنید.",
            }
        info = session.stream_info()
        if info is None:
            return {"ok": False, "error": "جریان آماده نشد."}
        info["ok"] = True
        return info

    def play_with_vlc(self) -> dict:
        """Force the current html5 session to hand playback over to VLC."""
        session = self.controller.current_session()
        if session is None:
            return {"ok": False, "error": "جلسه فعالی وجود ندارد."}
        session.start_vlc_fallback()
        return {"ok": True, "mode": session.mode}

    def stop(self) -> dict:
        self.controller.stop()
        return {"ok": True}

    def toggle_pause(self) -> dict:
        self.controller.toggle_pause()
        return {"ok": True}

    def seek(self, ratio: object) -> dict:
        """Seek to a fraction (0.0-1.0) of the media length."""
        try:
            ratio = float(ratio)
        except (TypeError, ValueError):
            return {"ok": False}
        snapshot = self.controller.snapshot()
        if snapshot.length_ms > 0:
            self.controller.seek(int(ratio * snapshot.length_ms))
        return {"ok": True}

    def set_volume(self, value: object) -> dict:
        try:
            self.controller.set_volume(int(float(value)))
        except (TypeError, ValueError):
            return {"ok": False}
        return {"ok": True}

    # ------------------------------------------------------------------ reports from JS

    def report_status(self, value: object) -> dict:
        session = self.controller.current_session()
        if session is not None:
            session.set_ui_status(value)
        return {"ok": True}

    def report_position(self, position_ms: object, length_ms: object) -> dict:
        session = self.controller.current_session()
        if session is not None:
            session.set_ui_position(position_ms, length_ms)
        return {"ok": True}

    # ------------------------------------------------------------------ polling

    def snapshot(self) -> dict:
        """Current stats as a plain dict for the UI's polling loop."""
        snap = self.controller.snapshot()
        session = self.controller.current_session()
        mode = session.mode if session is not None else "vlc"
        return {
            "status": snap.status.value,
            "mode": mode,
            "bytes_fetched": snap.bytes_fetched,
            "bytes_total": snap.bytes_total,
            "cache_bytes": snap.cache_bytes,
            "cache_capacity": snap.cache_capacity,
            "speed_bps": snap.speed_bps,
            "position_ms": snap.position_ms,
            "length_ms": snap.length_ms,
            "win_fullscreen": self.win.is_fullscreen(),
            "win_maximized": self.win.is_maximized(),
        }

    def drain_logs(self) -> list[dict[str, str]]:
        """Return and clear queued log entries since the last call."""
        items = list(self._logs)
        self._logs.clear()
        return items
