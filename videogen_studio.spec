# -*- mode: python ; coding: utf-8 -*-

import sys
import os
from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

block_cipher = None

BASE_DIR = Path(os.path.abspath(".")).resolve()

# Collect all hidden imports for FastAPI, Uvicorn, and backend modules
hidden_imports = [
    "uvicorn",
    "uvicorn.logging",
    "uvicorn.loops",
    "uvicorn.loops.auto",
    "uvicorn.protocols",
    "uvicorn.protocols.http",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.http.h11_impl",
    "uvicorn.protocols.http.httptools_impl",
    "uvicorn.protocols.websockets",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan",
    "uvicorn.lifespan.on",
    "fastapi",
    "fastapi.staticfiles",
    "fastapi.middleware.cors",
    "fastapi.responses",
    "starlette",
    "starlette.staticfiles",
    "starlette.middleware.cors",
    "starlette.responses",
    "pydantic",
    "pydantic_core",
    "pydantic.deprecated.decorator",
    "httpx",
    "httpcore",
    "h11",
    "groq",
    "aiohttp",
    "aiofiles",
    "multipart",
    "python_multipart",
    "PIL",
    "PIL.Image",
    "backend",
    "backend.config",
    "backend.server",
    "backend.transcriber",
    "backend.scene_analyzer",
    "backend.stock_downloader",
    "backend.subtitle_generator",
    "backend.video_renderer",
    "backend.capcut_exporter",
    "backend.templates"
]

hidden_imports += collect_submodules("backend")
hidden_imports += collect_submodules("uvicorn")
hidden_imports += collect_submodules("starlette")
hidden_imports += collect_submodules("fastapi")

# Collect static web assets & clean data assets (excluding heavy user exports/cache)
datas = [
    (str(BASE_DIR / "frontend"), "frontend"),
]
if (BASE_DIR / "bin").exists():
    datas.append((str(BASE_DIR / "bin"), "bin"))
if (BASE_DIR / "data" / "sfx").exists():
    datas.append((str(BASE_DIR / "data" / "sfx"), "data/sfx"))
if (BASE_DIR / "data" / "assets").exists():
    datas.append((str(BASE_DIR / "data" / "assets"), "data/assets"))
if (BASE_DIR / "data" / "settings.json").exists():
    datas.append((str(BASE_DIR / "data" / "settings.json"), "data"))

a = Analysis(
    ["desktop_launcher.py"],
    pathex=[str(BASE_DIR)],
    binaries=[],
    datas=datas,
    hiddenimports=list(set(hidden_imports)),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "scipy", "notebook", "IPython", "torch", "torchvision"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="VideoGenStudio",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,  # Keep console so user can see diagnostic startup logs if desired
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="VideoGenStudio",
)
