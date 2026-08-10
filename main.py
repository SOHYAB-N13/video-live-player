#!/usr/bin/env python3
"""Entry point for the live video streamer application.

Run with::

    python main.py

The user interface is a modern dark HTML/CSS/JavaScript dashboard rendered in
a WebView (Microsoft Edge WebView2). JavaScript talks to the Python backend
only through the pywebview API bridge.

Optional arguments:

    --url <link>      Play a direct media link on startup.
    --cache <mb>      Max RAM buffer in MiB (default 256).
    --keep-ahead <mb> Max lead in no-range mode in MiB (default 64).
    --insecure        Ignore HTTPS certificate errors.
    --debug           Keep the WebView development console enabled.
"""

from __future__ import annotations

import argparse

from core.controller import StreamController
from core.events import EventBus
from ui.bridge import StreamBridge
from ui.webview_app import launch

MIB = 1024 * 1024


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="پخش آنلاین ویدیو از لینک مستقیم")
    parser.add_argument("--url", help="لینک مستقیم ویدیو (http/https)")
    parser.add_argument("--cache", type=int, default=256, help="حداکثر بافر در RAM به مگابایت (پیش‌فرض: 256)")
    parser.add_argument("--keep-ahead", type=int, default=64, help="حد فاصله دریافت در حالت بدون Range به مگابایت (پیش‌فرض: 64)")
    parser.add_argument("--workers", type=int, default=3, help="تعداد اتصال‌های موازی برای سرعت دانلود بیشتر (پیش‌فرض: 3)")
    parser.add_argument("--insecure", action="store_true", help="نادیده گرفتن خطای گواهی HTTPS")
    parser.add_argument("--debug", action="store_true", help="فعال‌سازی کنسول توسعه WebView")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    bus = EventBus()
    controller = StreamController(
        bus,
        cache_capacity=args.cache * MIB,
        keep_ahead=args.keep_ahead * MIB,
        insecure=args.insecure,
        download_workers=args.workers,
    )
    bridge = StreamBridge(controller, bus)
    launch(bridge, initial_url=args.url or "", debug=args.debug)


if __name__ == "__main__":
    main()
