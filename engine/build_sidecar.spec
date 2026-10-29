# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the TaoYongStudio engine sidecar.

    pyinstaller --noconfirm engine/build_sidecar.spec

Output: engine/dist/taoyong-engine/taoyong-engine.exe
The Tauri shell prefers this executable over the system Python when it is present.
"""
import os

ROOT = os.path.abspath(SPECPATH)
ENTRY = os.path.join(ROOT, "build_sidecar_entry.py")

a = Analysis(
    [ENTRY],
    pathex=[ROOT],
    binaries=[],
    datas=[],
    hiddenimports=[
        "PIL",
        "PIL.Image",
        "PIL.ImageDraw",
        "PIL.ImageFont",
        "PIL.ImageTk",
        "numpy",
        "requests",
        "edge_tts",
        "uharfbuzz",
        "freetype",
        "imageio_ffmpeg",
        "googleapiclient",
        "googleapiclient.discovery",
        "google_auth_oauthlib",
        "google.oauth2.credentials",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "matplotlib",
        "pytest",
        "IPython",
        "notebook",
        "pandas",
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="taoyong-engine",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="taoyong-engine",
)
