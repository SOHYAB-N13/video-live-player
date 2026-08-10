"""WebView application launcher.

Builds a single self-contained HTML document from the ``ui/web`` assets and
starts the pywebview window (Microsoft Edge WebView2 on Windows). The
:class:`ui.bridge.StreamBridge` object is attached as ``js_api`` so that
JavaScript can call into the Python backend through ``pywebview.api``.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import webview

from ui.bridge import StreamBridge

WINDOW_TITLE = "Live Video Streamer"
WINDOW_SIZE = (1040, 760)
WINDOW_MIN_SIZE = (860, 560)
BACKGROUND = "#06060a"


def _assets_dir() -> Path:
    """Locate the ``ui/web`` assets in development and frozen (PyInstaller) runs."""
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        candidates = []
        if meipass:
            candidates.append(Path(meipass) / "ui" / "web")
        candidates.append(Path(sys.executable).resolve().parent / "ui" / "web")
        for candidate in candidates:
            if (candidate / "index.html").exists():
                return candidate
        return candidates[0]
    return Path(__file__).resolve().parent / "web"


ASSETS_DIR = _assets_dir()


def load_html(initial_url: str = "") -> str:
    """Read the HTML/CSS/JS assets and inline them into one document.

    ``utf-8-sig`` strips a leading UTF-8 byte-order mark if one is present.
    A BOM inside the inline ``<style>`` block would otherwise sit at a
    non-zero offset and Chromium would drop the first CSS rule (the ``:root``
    custom-property block), which made every ``var(--...)`` color resolve to
    black. Reading with ``utf-8-sig`` makes the loader immune to that.
    """
    html = (ASSETS_DIR / "index.html").read_text(encoding="utf-8-sig")
    css = (ASSETS_DIR / "styles.css").read_text(encoding="utf-8-sig")
    js = (ASSETS_DIR / "app.js").read_text(encoding="utf-8-sig")
    js = js.replace("__INITIAL_URL__", json.dumps(initial_url or ""))
    html = html.replace("/*__STYLES__*/", css)
    html = html.replace("//__SCRIPT__", js)
    return html


def launch(bridge: StreamBridge, initial_url: str = "", debug: bool = False) -> None:
    """Create the WebView window and run the GUI message loop (main thread).

    The window is frameless: the default OS title bar is removed and replaced
    by the app's custom HTML title bar (see ``ui/web``). ``easy_drag`` is
    disabled so window dragging is handled exclusively by the custom title
    bar through the native window bridge.
    """
    html = load_html(initial_url)
    webview.create_window(
        WINDOW_TITLE,
        html=html,
        js_api=bridge,
        width=WINDOW_SIZE[0],
        height=WINDOW_SIZE[1],
        min_size=WINDOW_MIN_SIZE,
        background_color=BACKGROUND,
        frameless=True,
        shadow=True,
        easy_drag=False,
        resizable=True,
    )
    webview.start(func=bridge.on_gui_started, debug=debug)
