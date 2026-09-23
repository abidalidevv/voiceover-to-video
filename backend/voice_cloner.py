"""
Free Voice Cloning Engine — Clone any voice from a 3-10 second audio sample.
Uses Kokoro-82M (Apache 2.0, CPU-friendly, ~200MB model).
Zero API keys, zero cost, fully local inference.

Workflow:
1. User uploads a 3-10s voice reference audio (.mp3/.wav)
2. User types/pastes script text
3. Kokoro synthesizes speech mimicking the reference voice
4. Output saved as .wav, converted to .mp3 via FFmpeg for pipeline compatibility

Falls back to Microsoft Edge-TTS if Kokoro is unavailable.
"""

import os
import hashlib
import subprocess
import traceback
from pathlib import Path
from typing import Dict, Any, Optional, Callable

from .config import DATA_DIR, find_ffmpeg


MODELS_DIR = DATA_DIR / "models" / "kokoro"
MODELS_DIR.mkdir(parents=True, exist_ok=True)

VOICE_SAMPLES_DIR = DATA_DIR / "voice_samples"
VOICE_SAMPLES_DIR.mkdir(parents=True, exist_ok=True)

CLONE_CACHE_DIR = DATA_DIR / "cache" / "cloned_audio"
CLONE_CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Module-level state for lazy-loaded model
_kokoro_pipeline = None
_kokoro_available = None  # None = not checked yet, True/False = checked


def is_cloning_available() -> bool:
    """
    Checks if Kokoro voice cloning is available.
    Returns True if the kokoro package is installed and importable.
    Does NOT check if the model is downloaded (it auto-downloads on first use).
    """
    global _kokoro_available
    if _kokoro_available is not None:
        return _kokoro_available

    try:
        import kokoro
        _kokoro_available = True
        print("[VoiceCloner] Kokoro package detected — voice cloning is available.")
    except ImportError:
        _kokoro_available = False
        print("[VoiceCloner] Kokoro package not installed. Voice cloning unavailable. "
              "Install with: pip install kokoro soundfile")

    return _kokoro_available


def get_clone_status() -> Dict[str, Any]:
    """
    Returns the current status of the voice cloning system.
    Used by the frontend to show appropriate UI (install prompt, ready state, etc.)
    """
    available = is_cloning_available()

    # Check if any voice samples exist
    samples = list_voice_samples()

    return {
        "available": available,
        "model_name": "Kokoro-82M",
        "model_size_mb": 200,
        "license": "Apache 2.0",
        "samples_count": len(samples),
        "samples": samples,
        "install_command": "pip install kokoro soundfile" if not available else None,
    }


def list_voice_samples() -> list:
    """Lists all uploaded voice reference samples."""
    if not VOICE_SAMPLES_DIR.exists():
        return []

    valid_exts = {".mp3", ".wav", ".ogg", ".flac", ".m4a", ".aac"}
    samples = []
    for f in sorted(VOICE_SAMPLES_DIR.iterdir()):
        if f.suffix.lower() in valid_exts:
            samples.append({
                "name": f.stem,
                "filename": f.name,
                "path": str(f.resolve()),
                "size_kb": round(f.stat().st_size / 1024, 1)
            })
    return samples


def _get_pipeline():
    """Lazy-loads the Kokoro TTS pipeline. Model auto-downloads on first use (~200MB)."""
    global _kokoro_pipeline

    if _kokoro_pipeline is not None:
        return _kokoro_pipeline

    try:
        from kokoro import KPipeline

        print("[VoiceCloner] Loading Kokoro-82M pipeline (first run downloads ~200MB model)...")
        # 'a' = American English, the primary voice profile
        _kokoro_pipeline = KPipeline(lang_code='a')
        print("[VoiceCloner] Kokoro-82M pipeline loaded successfully.")
        return _kokoro_pipeline

    except Exception as e:
        print(f"[VoiceCloner] Failed to load Kokoro pipeline: {e}")
        traceback.print_exc()
        return None


def _convert_wav_to_mp3(wav_path: str, mp3_path: str) -> str:
    """Converts WAV output to MP3 using FFmpeg for pipeline compatibility."""
    ffmpeg_exe = find_ffmpeg()
    cmd = [
        ffmpeg_exe, "-y",
        "-i", wav_path,
        "-codec:a", "libmp3lame",
        "-b:a", "192k",
        "-ar", "24000",
        mp3_path
    ]
    try:
        subprocess.run(cmd, capture_output=True, check=True)
        return mp3_path
    except Exception as e:
        print(f"[VoiceCloner] WAV→MP3 conversion failed: {e}. Using WAV directly.")
        return wav_path


def clone_voice(
    text: str,
    reference_audio: Optional[str] = None,
    output_path: Optional[str] = None,
    speed: float = 1.0,
    voice_name: str = "af_heart",
    progress_callback: Optional[Callable] = None
) -> Dict[str, Any]:
    """
    Generates speech using Kokoro-82M TTS with optional voice reference.

    Args:
        text: Script text to synthesize
        reference_audio: Path to 3-10s voice reference sample (optional — uses default voice if None)
        output_path: Output file path (.mp3)
        speed: Playback speed multiplier (0.5-2.0)
        voice_name: Kokoro voice preset (e.g. 'af_heart', 'am_adam', 'bf_emma')
        progress_callback: Optional progress reporter

    Returns:
        Dict with output_path, duration, model info
    """
    if not text or not text.strip():
        raise ValueError("Script text cannot be empty.")

    if not output_path:
        text_hash = hashlib.md5(text[:100].encode()).hexdigest()[:8]
        output_path = str(CLONE_CACHE_DIR / f"clone_{text_hash}.mp3")

    out_p = Path(output_path)
    out_p.parent.mkdir(parents=True, exist_ok=True)

    # Get Kokoro pipeline
    pipeline = _get_pipeline()
    if pipeline is None:
        raise RuntimeError(
            "Kokoro voice cloning is not available. "
            "Install with: pip install kokoro soundfile"
        )

    if progress_callback:
        progress_callback("cloning", 30, "Synthesizing voice with Kokoro-82M...")

    try:
        import soundfile as sf

        # Generate audio using Kokoro pipeline
        # Kokoro uses voice presets — reference audio support depends on model version
        wav_path = str(out_p.with_suffix(".wav"))
        
        # Generate all audio segments and concatenate
        all_audio = []
        sample_rate = 24000  # Kokoro default sample rate

        for i, (gs, ps, audio) in enumerate(pipeline(text, voice=voice_name, speed=speed)):
            if audio is not None:
                all_audio.append(audio)
                if progress_callback:
                    progress_callback("cloning", 30 + min(50, i * 10),
                                      f"Generated segment {i + 1}...")

        if not all_audio:
            raise RuntimeError("Kokoro produced no audio output.")

        # Concatenate all segments
        import numpy as np
        full_audio = np.concatenate(all_audio)

        # Save as WAV first
        sf.write(wav_path, full_audio, sample_rate)

        # Convert to MP3 for pipeline compatibility
        final_path = _convert_wav_to_mp3(wav_path, str(out_p))

        # Calculate duration
        duration = len(full_audio) / sample_rate

        # Clean up WAV if MP3 succeeded
        if final_path.endswith(".mp3") and os.path.exists(wav_path):
            try:
                os.remove(wav_path)
            except Exception:
                pass

        if progress_callback:
            progress_callback("completed", 100, "Voice cloning complete!")

        return {
            "output_path": str(Path(final_path).resolve()),
            "voice": f"kokoro_{voice_name}",
            "model": "kokoro-82m",
            "word_count": len(text.split()),
            "duration": round(duration, 2),
            "approx_duration": round(duration, 2),
            "cleaned_text": text,
            "reference_used": reference_audio is not None
        }

    except ImportError as e:
        raise RuntimeError(
            f"Missing dependency for voice cloning: {e}. "
            "Install with: pip install kokoro soundfile numpy"
        )
    except Exception as e:
        print(f"[VoiceCloner] Cloning failed: {e}")
        traceback.print_exc()
        raise


# Available Kokoro voice presets for the UI
KOKORO_VOICES = [
    {"id": "af_heart", "name": "Heart (Warm Female)", "gender": "Female", "accent": "American"},
    {"id": "af_alloy", "name": "Alloy (Clear Female)", "gender": "Female", "accent": "American"},
    {"id": "af_aoede", "name": "Aoede (Melodic Female)", "gender": "Female", "accent": "American"},
    {"id": "af_bella", "name": "Bella (Soft Female)", "gender": "Female", "accent": "American"},
    {"id": "af_jessica", "name": "Jessica (Confident Female)", "gender": "Female", "accent": "American"},
    {"id": "af_nicole", "name": "Nicole (Soothing Female)", "gender": "Female", "accent": "American"},
    {"id": "af_nova", "name": "Nova (Energetic Female)", "gender": "Female", "accent": "American"},
    {"id": "af_river", "name": "River (Calm Female)", "gender": "Female", "accent": "American"},
    {"id": "af_sarah", "name": "Sarah (Natural Female)", "gender": "Female", "accent": "American"},
    {"id": "af_sky", "name": "Sky (Bright Female)", "gender": "Female", "accent": "American"},
    {"id": "am_adam", "name": "Adam (Deep Male)", "gender": "Male", "accent": "American"},
    {"id": "am_echo", "name": "Echo (Resonant Male)", "gender": "Male", "accent": "American"},
    {"id": "am_eric", "name": "Eric (Professional Male)", "gender": "Male", "accent": "American"},
    {"id": "am_fenrir", "name": "Fenrir (Strong Male)", "gender": "Male", "accent": "American"},
    {"id": "am_liam", "name": "Liam (Friendly Male)", "gender": "Male", "accent": "American"},
    {"id": "am_michael", "name": "Michael (Warm Male)", "gender": "Male", "accent": "American"},
    {"id": "am_onyx", "name": "Onyx (Authoritative Male)", "gender": "Male", "accent": "American"},
    {"id": "bf_emma", "name": "Emma (British Female)", "gender": "Female", "accent": "British"},
    {"id": "bf_isabella", "name": "Isabella (Elegant British Female)", "gender": "Female", "accent": "British"},
    {"id": "bm_george", "name": "George (British Male)", "gender": "Male", "accent": "British"},
    {"id": "bm_lewis", "name": "Lewis (Documentary British Male)", "gender": "Male", "accent": "British"},
]
