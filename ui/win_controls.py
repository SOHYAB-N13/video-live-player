"""Native Windows window control helpers for the custom title bar and fullscreen.

The WebView runs inside a frameless WinForms window. This module drives the
host window with plain ctypes calls so the HTML front-end can:

* move the window (drag from the custom title bar),
* minimize / maximize / restore / close,
* enter a *real* OS-level fullscreen (the window covers the whole monitor,
  hiding the taskbar).

The window stays *truly* borderless (no ``WS_THICKFRAME``), so the client
area always equals the window rectangle: maximize fills the work area with no
margins and no border / white line is ever drawn. Edge resizing is provided
through a ``WM_NCHITTEST`` subclass hook instead of the invisible frame.

Everything degrades gracefully to no-ops if the native handle is unavailable.
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes
from typing import Optional

import webview

USER32 = ctypes.windll.user32

# Window styles ----------------------------------------------------------------
GWL_STYLE = -16
WS_THICKFRAME = 0x00040000
WS_MINIMIZEBOX = 0x00020000
WS_MAXIMIZEBOX = 0x00010000

# Messages ----------------------------------------------------------------------
WM_NCCALCSIZE = 0x0083
WM_NCHITTEST = 0x0084

# NCHITTEST results --------------------------------------------------------------
HTNOWHERE = 0
HTCLIENT = 1
HTLEFT = 10
HTRIGHT = 11
HTTOP = 12
HTTOPLEFT = 13
HTTOPRIGHT = 14
HTBOTTOM = 15
HTBOTTOMLEFT = 16
HTBOTTOMRIGHT = 17

# ShowWindow --------------------------------------------------------------------
SW_MINIMIZE = 6

# SetWindowPos ------------------------------------------------------------------
HWND_TOPMOST = wintypes.HWND(-1)
HWND_NOTOPMOST = wintypes.HWND(-2)
SWP_NOACTIVATE = 0x0010
SWP_FRAMECHANGED = 0x0020
SWP_NOSIZE = 0x0001
SWP_NOZORDER = 0x0004
SWP_SHOWWINDOW = 0x0040

# RedrawWindow ------------------------------------------------------------------
RDW_INVALIDATE = 0x0001
RDW_ALLCHILDREN = 0x0080
RDW_UPDATENOW = 0x0100

MONITOR_DEFAULTTONEAREST = 2

RESIZE_MARGIN = 8  #: px hot zone at the window edges that resizes the window

# DWM ---------------------------------------------------------------------------
DWMNCRP_DISABLED = 1
DWMNCRP_ENABLED = 2
DWMWA_NCRENDERING_POLICY = 2
DWMWA_WINDOW_CORNER_PREFERENCE = 33
DWMWCP_DEFAULT = 0
DWMWCP_DONOTROUND = 1


class RECT(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long),
    ]

    @property
    def width(self) -> int:
        return self.right - self.left

    @property
    def height(self) -> int:
        return self.bottom - self.top


class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


class MONITORINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", ctypes.c_uint),
        ("rcMonitor", RECT),
        ("rcWork", RECT),
        ("dwFlags", ctypes.c_uint),
    ]


class MARGINS(ctypes.Structure):
    _fields_ = [
        ("cxLeftWidth", ctypes.c_int),
        ("cxRightWidth", ctypes.c_int),
        ("cyTopHeight", ctypes.c_int),
        ("cyBottomHeight", ctypes.c_int),
    ]


# Subclassing -------------------------------------------------------------------
SUBCLASSPROC = ctypes.WINFUNCTYPE(
    ctypes.c_ssize_t,
    wintypes.HWND,
    wintypes.UINT,
    wintypes.WPARAM,
    wintypes.LPARAM,
    ctypes.c_size_t,  # UINT_PTR
    ctypes.c_size_t,  # DWORD_PTR / ULONG_PTR
)


def _to_intptr(handle: object) -> int:
    """Convert a pythonnet System.IntPtr (or plain int) to a Python int."""
    try:
        if hasattr(handle, "ToInt64"):
            return int(handle.ToInt64())
        return int(handle)
    except Exception:  # noqa: BLE001
        return int(str(handle))


# Declare prototypes so 64-bit handles are passed correctly.
USER32.SetWindowPos.argtypes = [
    wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_uint
]
USER32.SetWindowPos.restype = wintypes.BOOL
USER32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(RECT)]
USER32.GetWindowRect.restype = wintypes.BOOL
USER32.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(RECT)]
USER32.GetClientRect.restype = wintypes.BOOL
USER32.GetCursorPos.argtypes = [ctypes.POINTER(POINT)]
USER32.GetCursorPos.restype = wintypes.BOOL
USER32.MonitorFromWindow.argtypes = [wintypes.HWND, ctypes.c_uint]
USER32.MonitorFromWindow.restype = wintypes.HMONITOR
USER32.GetMonitorInfoW.argtypes = [wintypes.HMONITOR, ctypes.POINTER(MONITORINFO)]
USER32.GetMonitorInfoW.restype = wintypes.BOOL
USER32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
USER32.ShowWindow.restype = wintypes.BOOL
USER32.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
USER32.GetWindowLongPtrW.restype = ctypes.c_ssize_t
USER32.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t]
USER32.SetWindowLongPtrW.restype = ctypes.c_ssize_t
USER32.SetForegroundWindow.argtypes = [wintypes.HWND]
USER32.SetForegroundWindow.restype = wintypes.BOOL
USER32.RedrawWindow.argtypes = [wintypes.HWND, ctypes.POINTER(RECT), wintypes.HANDLE, ctypes.c_uint]
USER32.RedrawWindow.restype = wintypes.BOOL

DWMAPI = ctypes.windll.dwmapi
DWMAPI.DwmSetWindowAttribute.argtypes = [wintypes.HWND, ctypes.c_uint, ctypes.c_void_p, ctypes.c_uint]
DWMAPI.DwmSetWindowAttribute.restype = ctypes.c_long  # HRESULT


class WindowControls:
    """Bindings to the host window for the custom title bar and fullscreen."""

    def __init__(self) -> None:
        self._window: Optional[webview.Window] = None
        self._hwnd: Optional[int] = None
        self._fullscreen = False
        self._maximized = False
        self._fs_normal_rect: Optional[RECT] = None
        self._max_normal_rect: Optional[RECT] = None
        self._bound = False
        self._dragging = False
        self._grab_dx = 0
        self._grab_dy = 0
        self._subclass_proc: Optional[SUBCLASSPROC] = None

    # ------------------------------------------------------------------ lifecycle

    def bind(self) -> bool:
        """Attach to the live pywebview window (call after the GUI is running)."""
        for _ in range(50):
            try:
                if not webview.windows:
                    continue
                window = webview.windows[0]
                native = getattr(window, "native", None)
                handle = getattr(native, "Handle", None)
                if handle is not None:
                    self._window = window
                    self._hwnd = _to_intptr(handle)
                    self._enable_borderless_window()
                    self._run_on_ui_thread(self._install_borderless_hook)
                    self._bound = True
                    return True
            except Exception:  # noqa: BLE001
                pass
            import time

            time.sleep(0.1)
        return False

    @property
    def available(self) -> bool:
        return self._bound and self._hwnd is not None

    # ------------------------------------------------------------------ threading

    def _run_on_ui_thread(self, func) -> None:
        """Run ``func`` on the thread that owns the window (WinForms UI thread).

        Some window operations (window subclassing in particular) must be
        issued from the window's owning thread; this marshals the call through
        ``BeginInvoke`` when needed and falls back to calling directly.
        """
        try:
            form = self._window.native
            if bool(getattr(form, "InvokeRequired", False)):
                try:
                    import clr  # noqa: F401

                    from System import Action

                    form.BeginInvoke(Action(func))
                    return
                except Exception:  # noqa: BLE001
                    pass
            func()
        except Exception:  # noqa: BLE001
            try:
                func()
            except Exception:  # noqa: BLE001
                pass

    # ------------------------------------------------------------------ styling

    def _enable_borderless_window(self) -> None:
        """Keep the window truly borderless: no resize frame, no white line."""
        try:
            style = int(USER32.GetWindowLongPtrW(self._hwnd, GWL_STYLE))
            style |= WS_MINIMIZEBOX | WS_MAXIMIZEBOX
            style &= ~WS_THICKFRAME
            USER32.SetWindowLongPtrW(self._hwnd, GWL_STYLE, style)
            USER32.SetWindowPos(self._hwnd, None, 0, 0, 0, 0, SWP_NOSIZE | SWP_NOZORDER | SWP_SHOWWINDOW)
        except Exception:  # noqa: BLE001
            pass

    def _install_borderless_hook(self) -> None:
        """Intercept edge hit-testing (resize) and keep the client area full."""
        try:
            comctl32 = ctypes.windll.comctl32
            comctl32.SetWindowSubclass.argtypes = [
                wintypes.HWND, SUBCLASSPROC, ctypes.c_uint, ctypes.c_size_t
            ]
            comctl32.SetWindowSubclass.restype = wintypes.BOOL
            comctl32.DefSubclassProc.argtypes = [
                wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM
            ]
            comctl32.DefSubclassProc.restype = ctypes.c_ssize_t

            @SUBCLASSPROC
            def _proc(hwnd, msg, wparam, lparam, _uid, _refdata):
                if msg == WM_NCCALCSIZE:
                    return 0  # client area == window rect (no border)
                if msg == WM_NCHITTEST:
                    return WindowControls._hit_test(hwnd, lparam)
                return comctl32.DefSubclassProc(hwnd, msg, wparam, lparam)

            self._subclass_proc = _proc  # keep a reference so it is not GC'd
            comctl32.SetWindowSubclass(self._hwnd, _proc, 1, 0)
        except Exception:  # noqa: BLE001
            pass

    @staticmethod
    def _hit_test(hwnd: int, lparam: int) -> int:
        """Return the resize zone under the cursor (WM_NCHITTEST handling)."""
        try:
            rect = RECT()
            USER32.GetWindowRect(hwnd, ctypes.byref(rect))
            x = (int(lparam) & 0xFFFF) - rect.left
            y = ((int(lparam) >> 16) & 0xFFFF) - rect.top
            width = rect.width
            height = rect.height
            if x < 0 or y < 0 or x >= width or y >= height:
                return HTNOWHERE
            margin = RESIZE_MARGIN
            left = x <= margin
            right = x >= width - margin - 1
            top = y <= margin
            bottom = y >= height - margin - 1
            if top and left:
                return HTTOPLEFT
            if top and right:
                return HTTOPRIGHT
            if bottom and left:
                return HTBOTTOMLEFT
            if bottom and right:
                return HTBOTTOMRIGHT
            if left:
                return HTLEFT
            if right:
                return HTRIGHT
            if top:
                return HTTOP
            if bottom:
                return HTBOTTOM
            return HTCLIENT
        except Exception:  # noqa: BLE001
            return HTCLIENT

    def _repaint(self) -> None:
        """Force a clean repaint of the window and its children."""
        try:
            USER32.RedrawWindow(self._hwnd, None, None, RDW_INVALIDATE | RDW_ALLCHILDREN | RDW_UPDATENOW)
        except Exception:  # noqa: BLE001
            pass

    def _set_dwm_frame(self, enabled: bool) -> None:
        """Enable/disable the DWM glass frame that can show as a thin line.

        pywebview extends the DWM frame 1px into the client area to render the
        window shadow. On a dark fullscreen / maximized window that 1px glass
        edge appears as a thin white line, so it is removed while the window
        covers the whole screen and restored afterwards.
        """
        try:
            margins = MARGINS(1, 1, 1, 1) if enabled else MARGINS(0, 0, 0, 0)
            # No argtypes here: like pywebview itself, pass the struct by reference.
            DWMAPI.DwmExtendFrameIntoClientArea(self._hwnd, ctypes.byref(margins))
            policy = DWMNCRP_ENABLED if enabled else DWMNCRP_DISABLED
            value = ctypes.c_int(policy)
            DWMAPI.DwmSetWindowAttribute(
                self._hwnd, DWMWA_NCRENDERING_POLICY, ctypes.byref(value), ctypes.sizeof(value)
            )
            corner = DWMWCP_DEFAULT if enabled else DWMWCP_DONOTROUND
            value2 = ctypes.c_int(corner)
            DWMAPI.DwmSetWindowAttribute(
                self._hwnd, DWMWA_WINDOW_CORNER_PREFERENCE, ctypes.byref(value2), ctypes.sizeof(value2)
            )
        except Exception:  # noqa: BLE001
            pass

    # ------------------------------------------------------------------ actions

    def minimize(self) -> None:
        if self.available:
            USER32.ShowWindow(self._hwnd, SW_MINIMIZE)

    def toggle_maximize(self) -> None:
        if not self.available:
            return
        if self.is_maximized():
            self.restore()
        else:
            self.maximize()

    def maximize(self) -> None:
        """Fill the monitor's work area exactly (no margins, no border)."""
        if not self.available:
            return
        try:
            normal = RECT()
            USER32.GetWindowRect(self._hwnd, ctypes.byref(normal))
            self._max_normal_rect = normal
            work = self._work_area()
            USER32.SetWindowPos(
                self._hwnd,
                None,
                work.left,
                work.top,
                work.width,
                work.height,
                SWP_NOZORDER | SWP_FRAMECHANGED,
            )
            self._maximized = True
            self._set_dwm_frame(False)
            self._repaint()
        except Exception:  # noqa: BLE001
            pass

    def restore(self) -> None:
        """Return the window to the size/position it had before maximizing."""
        if not self.available:
            return
        try:
            normal = self._max_normal_rect or RECT()
            USER32.SetWindowPos(
                self._hwnd,
                None,
                normal.left,
                normal.top,
                normal.width,
                normal.height,
                SWP_NOZORDER | SWP_FRAMECHANGED,
            )
            self._maximized = False
            self._set_dwm_frame(True)
            self._repaint()
        except Exception:  # noqa: BLE001
            pass

    def _work_area(self) -> RECT:
        monitor = USER32.MonitorFromWindow(self._hwnd, MONITOR_DEFAULTTONEAREST)
        info = MONITORINFO()
        info.cbSize = ctypes.sizeof(MONITORINFO)
        USER32.GetMonitorInfoW(monitor, ctypes.byref(info))
        return info.rcWork

    def close(self) -> None:
        try:
            if self._window is not None:
                self._window.destroy()
        except Exception:  # noqa: BLE001
            pass

    def toggle_fullscreen(self) -> None:
        if not self.available:
            return
        try:
            if self._fullscreen:
                self._exit_fullscreen()
            else:
                self._enter_fullscreen()
            self._fullscreen = not self._fullscreen
        except Exception:  # noqa: BLE001
            pass

    def _enter_fullscreen(self) -> None:
        normal = RECT()
        USER32.GetWindowRect(self._hwnd, ctypes.byref(normal))
        self._fs_normal_rect = normal
        monitor = USER32.MonitorFromWindow(self._hwnd, MONITOR_DEFAULTTONEAREST)
        info = MONITORINFO()
        info.cbSize = ctypes.sizeof(MONITORINFO)
        USER32.GetMonitorInfoW(monitor, ctypes.byref(info))
        bounds = info.rcMonitor
        USER32.SetWindowPos(
            self._hwnd,
            HWND_TOPMOST,
            bounds.left,
            bounds.top,
            bounds.width,
            bounds.height,
            SWP_NOACTIVATE | SWP_FRAMECHANGED,
        )
        USER32.SetForegroundWindow(self._hwnd)
        self._set_dwm_frame(False)
        self._repaint()

    def _exit_fullscreen(self) -> None:
        normal = self._fs_normal_rect or RECT()
        USER32.SetWindowPos(
            self._hwnd,
            HWND_NOTOPMOST,
            normal.left,
            normal.top,
            normal.width,
            normal.height,
            SWP_NOACTIVATE | SWP_FRAMECHANGED,
        )
        USER32.SetForegroundWindow(self._hwnd)
        self._set_dwm_frame(True)
        self._repaint()

    def start_drag(self) -> None:
        """Begin a manual window drag from the custom title bar.

        Records the grab offset (cursor position relative to the window's
        top-left corner) so that later ``drag_to`` calls keep the cursor at
        the same spot inside the window while moving it. This is more
        reliable inside WebView2 than the classic ``WM_NCLBUTTONDOWN`` trick.
        """
        if not self.available:
            return
        try:
            point = POINT()
            if not USER32.GetCursorPos(ctypes.byref(point)):
                return
            rect = RECT()
            USER32.GetWindowRect(self._hwnd, ctypes.byref(rect))
            self._grab_dx = point.x - rect.left
            self._grab_dy = point.y - rect.top
            self._dragging = True
        except Exception:  # noqa: BLE001
            self._dragging = False

    def drag_to(self, x: int, y: int) -> None:
        """Move the window so the cursor ends up at the given screen point."""
        if not self._dragging or not self.available:
            return
        try:
            USER32.SetWindowPos(
                self._hwnd,
                None,
                int(x) - self._grab_dx,
                int(y) - self._grab_dy,
                0,
                0,
                SWP_NOSIZE | SWP_NOZORDER,
            )
        except Exception:  # noqa: BLE001
            pass

    def end_drag(self) -> None:
        self._dragging = False

    # ------------------------------------------------------------------ state

    def is_maximized(self) -> bool:
        if not self.available or not self._maximized:
            return False
        try:
            rect = RECT()
            USER32.GetWindowRect(self._hwnd, ctypes.byref(rect))
            work = self._work_area()
            return (
                rect.left == work.left
                and rect.top == work.top
                and rect.right == work.right
                and rect.bottom == work.bottom
            )
        except Exception:  # noqa: BLE001
            return self._maximized

    def is_fullscreen(self) -> bool:
        return self._fullscreen
