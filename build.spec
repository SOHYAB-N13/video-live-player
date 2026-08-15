# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller build specification for the Live Video Player.

Build with::

    python -m PyInstaller build.spec --noconfirm --clean

Produces a self-contained ``dist/LiveVideoPlayer/`` folder. The WebView2
runtime DLLs shipped by pywebview and the pythonnet (.NET) runtime are picked
up by the hooks bundled inside the ``webview`` and ``pythonnet`` packages.
"""

from PyInstaller.utils.hooks import collect_data_files

block_cipher = None

# Inline the front-end assets so the frozen app finds them next to the code.
datas = [("ui/web", "ui/web")]

# The pywebview hooks already gather `webview/js` and `webview/lib`; adding
# them explicitly is harmless and guards against hook ordering differences.
datas += collect_data_files("webview", subdir="js")
datas += collect_data_files("webview", subdir="lib")

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=[
        # pywebview picks the GUI backend at runtime; make the Windows
        # backend (and its ctypes helper) visible to the static analysis.
        "webview.platforms.winforms",
        "webview.platforms.win32",
        "clr",
        "vlc",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter"],
    noarchive=False,
    block_cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="LiveVideoPlayer",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon="app.ico",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="LiveVideoPlayer",
)
