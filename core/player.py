"""Wrapper around python-vlc providing embedded-window playback."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Callable, Optional


def _locate_bundled_vlc() -> None:
    """Point python-vlc at the VLC runtime bundled next to a frozen executable."""
    if not getattr(sys, "frozen", False):
        return
    base = Path(sys.executable).resolve().parent
    libvlc = base / "libvlc.dll"
    plugins = base / "plugins"
    if libvlc.exists():
        os.environ.setdefault("PYTHON_VLC_LIB_PATH", str(libvlc))
    if plugins.exists():
        os.environ.setdefault("VLC_PLUGIN_PATH", str(plugins))


class Player:
    """Thin, defensive wrapper around a ``vlc.MediaPlayer`` instance."""

    NETWORK_CACHING_MS = 800  #: Buffer kept by VLC for the local stream.

    def __init__(self, log: Optional[Callable[[str, str], None]] = None) -> None:
        self.log = log or (lambda msg, level="info": None)
        _locate_bundled_vlc()
        try:
            import vlc  # noqa: F401
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("کتابخانه python-vlc نصب نیست.") from exc
        self._vlc = vlc
        self._instance: Optional[object] = None
        self._player: Optional[object] = None
        self._init_media_player()

    def _init_media_player(self) -> None:
        try:
            self._instance = self._vlc.Instance(
                [
                    "--no-video-title-show",
                    "--quiet",
                    "--no-color",
                    "--no-keyboard-events",
                ]
            )
            self._player = self._instance.media_player_new()
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"VLC قابل اجرا نیست: {exc}") from exc

    # ------------------------------------------------------------------ playback

    def play(self, url: str, hwnd: object = None) -> None:
        if self._instance is None or self._player is None:
            raise RuntimeError("پخش‌کننده در دسترس نیست.")
        self.stop()
        media = self._instance.media_new(url)
        media.add_option(":http-reconnect")
        media.add_option(f":network-caching={self.NETWORK_CACHING_MS}")
        media.add_option(f":live-caching={self.NETWORK_CACHING_MS}")
        media.add_option(f":file-caching={self.NETWORK_CACHING_MS}")
        self._player.set_media(media)
        if hwnd is not None:
            try:
                self._player.set_hwnd(int(hwnd))
            except Exception as exc:  # noqa: BLE001 - fall back to VLC's own window
                self.log(f"اتصال پنجره ویدیو ناموفق بود: {exc}", "warning")
        self._player.play()

    def stop(self) -> None:
        if self._player is not None:
            try:
                self._player.stop()
            except Exception:  # noqa: BLE001
                pass

    def release(self) -> None:
        try:
            if self._player is not None:
                self._player.stop()
                self._player.release()
        except Exception:  # noqa: BLE001
            pass
        self._player = None
        if self._instance is not None:
            try:
                self._instance.release()
            except Exception:  # noqa: BLE001
                pass
        self._instance = None

    # ------------------------------------------------------------------ state

    def get_state(self) -> object:
        if self._player is None:
            return None
        try:
            return self._player.get_state()
        except Exception:  # noqa: BLE001
            return None

    def state_name(self) -> Optional[str]:
        state = self.get_state()
        if state is None:
            return None
        try:
            return self._vlc.State(state).name
        except Exception:  # noqa: BLE001
            return str(state)

    def is_playing(self) -> bool:
        if self._player is None:
            return False
        try:
            return self._player.is_playing() == 1
        except Exception:  # noqa: BLE001
            return False

    def get_time_ms(self) -> int:
        if self._player is None:
            return 0
        try:
            return max(0, int(self._player.get_time()))
        except Exception:  # noqa: BLE001
            return 0

    def get_length_ms(self) -> int:
        if self._player is None:
            return 0
        try:
            return max(0, int(self._player.get_length()))
        except Exception:  # noqa: BLE001
            return 0

    def set_time_ms(self, ms: int) -> None:
        if self._player is None:
            return
        try:
            self._player.set_time(int(ms))
        except Exception:  # noqa: BLE001
            pass

    def set_pause(self, pause: bool) -> None:
        if self._player is None:
            return
        try:
            self._player.set_pause(1 if pause else 0)
        except Exception:  # noqa: BLE001
            pass

    def set_volume(self, volume: int) -> None:
        if self._player is None:
            return
        try:
            self._player.audio_set_volume(max(0, min(100, int(volume))))
        except Exception:  # noqa: BLE001
            pass

    def set_fullscreen(self, enabled: bool) -> None:
        """Toggle the VLC window's own fullscreen (used in VLC playback mode)."""
        if self._player is None:
            return
        try:
            self._player.set_fullscreen(1 if enabled else 0)
        except Exception:  # noqa: BLE001
            pass
