import sys
import os
import json
import shutil
from pathlib import Path

# Determine if running in a frozen bundle (PyInstaller) or raw Python script
if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).resolve().parent
    BUNDLE_DIR = Path(getattr(sys, "_MEIPASS", str(BASE_DIR)))
else:
    BASE_DIR = Path(__file__).resolve().parent.parent
    BUNDLE_DIR = BASE_DIR

DATA_DIR = BASE_DIR / "data"
SETTINGS_FILE = DATA_DIR / "settings.json"
CACHE_DIR = DATA_DIR / "cache"
OUTPUT_DIR = DATA_DIR / "output"
TEMP_DIR = DATA_DIR / "temp"
SFX_DIR = DATA_DIR / "sfx"
BIN_DIR = BASE_DIR / "bin"

# Resolve Frontend directory (checks bundle directory first, then root folder)
FRONTEND_DIR = BUNDLE_DIR / "frontend"
if not FRONTEND_DIR.exists():
    FRONTEND_DIR = BASE_DIR / "frontend"

for d in [DATA_DIR, CACHE_DIR, OUTPUT_DIR, TEMP_DIR, SFX_DIR, BIN_DIR]:
    d.mkdir(parents=True, exist_ok=True)


def list_sfx_files() -> list:
    """Lists available sound effect audio files in data/sfx/."""
    if not SFX_DIR.exists():
        return []
    return [f.name for f in SFX_DIR.glob("*.*") if f.suffix.lower() in (".mp3", ".wav", ".aac", ".ogg")]


DEFAULT_SETTINGS = {
    # Stock Video APIs (10+ Providers & Endpoints)
    "pexels_api_key": "",
    "pixabay_api_key": "",
    "coverr_api_key": "",
    "mixkit_api_key": "",
    "videvo_api_key": "",
    "wikimedia_video_enabled": False,
    "internet_archive_enabled": True,
    "nasa_api_key": "",
    "freepik_api_key": "",
    "rapidapi_stock_key": "",
    "custom_stock_webhook": "",
    
    # AI & Transcription APIs
    "groq_api_key": "",
    "openai_api_key": "",
    "gemini_api_key": "",
    "elevenlabs_api_key": "",

    # Performance & Concurrency Settings (GPU / CPU Tuner)
    "workers": 8,                     # 2 to 32 worker threads
    "hardware_encoder": "auto",       # "auto", "nvenc", "amf", "qsv", "cpu"
    "video_provider": "all",          # "all", "pexels", "pixabay", "coverr", etc.
    "resolution": "1920x1080",
    "fps": 30,
    "output_dir": str(OUTPUT_DIR),
    "default_caption_preset": "capcut_yellow",
    "gpu_acceleration": True
}


def find_ffmpeg() -> str:
    """Find the path to ffmpeg executable with portable priority."""
    # 1. Check local portable bin directories
    candidates = [
        BIN_DIR / "ffmpeg.exe",
        BUNDLE_DIR / "bin" / "ffmpeg.exe",
        BUNDLE_DIR / "ffmpeg.exe",
        DATA_DIR / "bin" / "ffmpeg.exe",
        BASE_DIR / "ffmpeg.exe"
    ]
    for c in candidates:
        if c.exists():
            return str(c)

    # 2. Check system PATH
    found = shutil.which("ffmpeg")
    if found:
        return found

    # 3. Common windows winget / local paths
    common_paths = [
        Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Links" / "ffmpeg.exe",
        Path(os.environ.get("ProgramFiles", "")) / "ffmpeg" / "bin" / "ffmpeg.exe",
        Path(os.environ.get("ProgramFiles(x86)", "")) / "ffmpeg" / "bin" / "ffmpeg.exe",
    ]
    for p in common_paths:
        if p.exists():
            return str(p)
    return "ffmpeg"


def find_ffprobe() -> str:
    """Find the path to ffprobe executable with portable priority."""
    candidates = [
        BIN_DIR / "ffprobe.exe",
        BUNDLE_DIR / "bin" / "ffprobe.exe",
        BUNDLE_DIR / "ffprobe.exe",
        DATA_DIR / "bin" / "ffprobe.exe",
        BASE_DIR / "ffprobe.exe"
    ]
    for c in candidates:
        if c.exists():
            return str(c)

    found = shutil.which("ffprobe")
    if found:
        return found

    common_paths = [
        Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Links" / "ffprobe.exe",
        Path(os.environ.get("ProgramFiles", "")) / "ffmpeg" / "bin" / "ffprobe.exe",
        Path(os.environ.get("ProgramFiles(x86)", "")) / "ffmpeg" / "bin" / "ffprobe.exe",
    ]
    for p in common_paths:
        if p.exists():
            return str(p)
    return "ffprobe"


def load_settings() -> dict:
    if SETTINGS_FILE.exists():
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                merged = {**DEFAULT_SETTINGS, **data}
                return merged
        except Exception:
            pass
    return DEFAULT_SETTINGS.copy()


def save_settings(new_settings: dict) -> dict:
    current = load_settings()
    current.update(new_settings)
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(current, f, indent=2)
    return current
