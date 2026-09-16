import os
import json
import shutil
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
SETTINGS_FILE = DATA_DIR / "settings.json"
CACHE_DIR = DATA_DIR / "cache"
OUTPUT_DIR = DATA_DIR / "output"
TEMP_DIR = DATA_DIR / "temp"
SFX_DIR = DATA_DIR / "sfx"

for d in [DATA_DIR, CACHE_DIR, OUTPUT_DIR, TEMP_DIR, SFX_DIR]:
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
    """Find the path to ffmpeg executable."""
    found = shutil.which("ffmpeg")
    if found:
        return found
    # Common windows winget / local paths
    common_paths = [
        Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Links" / "ffmpeg.exe",
        Path(os.environ.get("ProgramFiles", "")) / "ffmpeg" / "bin" / "ffmpeg.exe",
    ]
    for p in common_paths:
        if p.exists():
            return str(p)
    return "ffmpeg"


def find_ffprobe() -> str:
    """Find the path to ffprobe executable."""
    found = shutil.which("ffprobe")
    if found:
        return found
    common_paths = [
        Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Links" / "ffprobe.exe",
        Path(os.environ.get("ProgramFiles", "")) / "ffmpeg" / "bin" / "ffprobe.exe",
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
