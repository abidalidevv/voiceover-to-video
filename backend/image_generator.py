import os
import re
import hashlib
import requests
import subprocess
from pathlib import Path
from typing import List, Optional
from PIL import Image

from .config import CACHE_DIR, TEMP_DIR, find_ffmpeg, load_settings

IMAGE_CACHE_DIR = CACHE_DIR / "scene_images"
IMAGE_CACHE_DIR.mkdir(parents=True, exist_ok=True)

SCENE_CLIP_DIR = CACHE_DIR / "scene_clips"
SCENE_CLIP_DIR.mkdir(parents=True, exist_ok=True)


def _enrich_image_prompt(raw_text: str, tags: Optional[List[str]] = None, niche: str = "General") -> str:
    """Enriches raw voiceover sentence or search tags into an Ultra HD cinematic image prompt."""
    base_text = ""
    if tags and len(tags) > 0:
        base_text = ", ".join(tags[:3])
    elif raw_text:
        # Clean transcript words
        clean = re.sub(r'[^a-zA-Z0-9\s]', ' ', raw_text).strip()
        words = [w for w in clean.split() if len(w) >= 3 and w.lower() not in (
            "this", "that", "with", "from", "have", "been", "were", "what", "here", "there", "they", "your"
        )]
        base_text = " ".join(words[:6]) if words else raw_text

    niche_qualifier = ""
    niche_lower = str(niche).lower()
    if "war" in niche_lower or "military" in niche_lower or any(w in base_text.lower() for w in ["missile", "war", "military", "tank", "soldier", "rocket", "strike", "attack"]):
        niche_qualifier = "military defense, dramatic war atmosphere, tactical battlefield, explosion smoke, volumetric lighting"
    elif "tech" in niche_lower or "ai" in niche_lower:
        niche_qualifier = "futuristic cyberpunk aesthetic, glowing neon data, high tech 8k"
    elif "nature" in niche_lower or "wildlife" in niche_lower:
        niche_qualifier = "national geographic photography, majestic natural lighting, atmospheric depth"
    elif "history" in niche_lower or "empire" in niche_lower:
        niche_qualifier = "historical epic cinematography, antique grand architecture, golden hour"
    else:
        niche_qualifier = "cinematic film still, 35mm photograph, dramatic composition"

    prompt = f"{base_text}, {niche_qualifier}, photorealistic 8k resolution, cinematic lighting, masterpiece, wide angle 16:9, highly detailed, no text, no watermark, no blur"
    return prompt.strip()


def generate_scene_image(
    prompt: str,
    scene_id: int = 0,
    tags: Optional[List[str]] = None,
    niche: str = "General",
    target_resolution: str = "1080p"
) -> Path:
    """
    Generates an Ultra HD 16:9 cinematic image for a scene.
    1. Tries Google Nano Banana / Gemini Image API if quota is active.
    2. Automatically cascades to Pollinations Flux 16:9 (fast, free, photorealistic 1920x1080).
    Saves to image cache and returns Path.
    """
    settings = load_settings()
    gemini_key = settings.get("gemini_api_key", "").strip()
    gemini_keys = settings.get("gemini_api_keys") or ([gemini_key] if gemini_key else [])

    enriched_prompt = _enrich_image_prompt(prompt, tags=tags, niche=niche)
    prompt_hash = hashlib.md5(f"{enriched_prompt}_{target_resolution}".encode("utf-8")).hexdigest()[:10]
    out_filename = f"sc_{scene_id:04d}_{prompt_hash}.jpg"
    out_path = IMAGE_CACHE_DIR / out_filename

    # Cache hit check
    if out_path.exists() and out_path.stat().st_size > 5000:
        return out_path

    # Resolution dimensions
    res_str = str(target_resolution or "1080p").lower().strip()
    if res_str in ("4k", "8k"):
        w, h = 1920, 1080  # AI generation native 1080p, upscaled to 4K during FFmpeg assembly
    else:
        w, h = 1920, 1080

    # Priority 1: Google Imagen 3 API if key is available
    image_bytes = None
    if gemini_keys:
        for g_key in gemini_keys:
            if not g_key:
                continue
            for model_id in ["imagen-3.0-generate-002", "imagen-3.0-generate-001"]:
                try:
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_id}:predict?key={g_key}"
                    payload = {
                        "instances": [{"prompt": enriched_prompt}],
                        "parameters": {"aspectRatio": "16:9", "sampleCount": 1}
                    }
                    res = requests.post(url, json=payload, timeout=20)
                    if res.status_code == 200:
                        data = res.json()
                        preds = data.get("predictions", [])
                        if preds and "bytesBase64Encoded" in preds[0]:
                            import base64
                            image_bytes = base64.b64decode(preds[0]["bytesBase64Encoded"])
                            print(f"[ImageGenerator] Successfully generated Ultra HD 16:9 image via Google {model_id} for Scene #{scene_id+1}")
                            break
                except Exception:
                    continue
            if image_bytes:
                break

    # Priority 2: High-Performance Pollinations Flux 16:9 Generator (Fast, Free, Ultra HD 16:9)
    if not image_bytes:
        try:
            print(f"[ImageGenerator] Generating Ultra HD 16:9 AI Image for Scene #{scene_id+1}: '{enriched_prompt[:60]}...'")
            poll_url = f"https://image.pollinations.ai/prompt/{requests.utils.quote(enriched_prompt)}?width={w}&height={h}&nologo=true&model=flux"
            r = requests.get(poll_url, timeout=30)
            if r.status_code == 200 and len(r.content) > 5000:
                image_bytes = r.content
        except Exception as e:
            print(f"[ImageGenerator] Notice: Pollinations request notice: {e}")

    # Fallback to local high-contrast canvas if network fails
    if not image_bytes:
        img = Image.new("RGB", (w, h), color=(18, 24, 38))
        img.save(out_path, format="JPEG", quality=95)
        return out_path

    # Save to disk and verify with PIL
    with open(out_path, "wb") as f:
        f.write(image_bytes)

    try:
        with Image.open(out_path) as test_img:
            test_img.verify()
    except Exception:
        # Repair image
        img = Image.new("RGB", (w, h), color=(20, 25, 40))
        img.save(out_path, format="JPEG", quality=95)

    return out_path


def convert_image_to_scene_clip(
    image_path: str,
    duration: float,
    scene_id: int,
    target_resolution: str = "1080p",
    motion: bool = True
) -> str:
    """
    Renders an Ultra HD 16:9 image into an MP4 video clip matching the EXACT voiceover sentence duration.
    Applies subtle cinematic Ken Burns zoom/pan motion so images blend seamlessly into video timeline.
    """
    if not image_path or not os.path.exists(image_path):
        return ""

    ffmpeg_exe = find_ffmpeg()
    target_dur = max(0.5, round(float(duration), 2))
    res_str = str(target_resolution or "1080p").lower().strip()
    if res_str == "8k":
        w, h = 7680, 4320
    elif res_str == "4k":
        w, h = 3840, 2160
    else:
        w, h = 1920, 1080

    path_hash = hashlib.md5(f"{image_path}_{target_dur}_{res_str}_{motion}".encode("utf-8")).hexdigest()[:8]
    out_name = f"sc_{scene_id:04d}_ai_{path_hash}.mp4"
    out_path = SCENE_CLIP_DIR / out_name

    if out_path.exists() and out_path.stat().st_size > 1000:
        return str(out_path)

    fps = 30
    total_frames = max(15, int(target_dur * fps))

    # Ken Burns subtle cinematic zoom-in motion
    if motion:
        vf_filter = (
            f"zoompan=z='min(zoom+0.0012,1.15)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
            f"d={total_frames}:s={w}x{h}:fps={fps},setsar=1"
        )
    else:
        vf_filter = f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},setsar=1,fps={fps}"

    cmd = [
        ffmpeg_exe, "-y",
        "-loop", "1",
        "-i", str(image_path),
        "-t", f"{target_dur:.2f}",
        "-vf", vf_filter,
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-crf", "18",
        "-pix_fmt", "yuv420p",
        "-threads", "0",
        "-an",
        str(out_path)
    ]

    try:
        subprocess.run(cmd, capture_output=True, check=True)
        return str(out_path)
    except Exception as e:
        print(f"[ImageGenerator] Notice: Ken Burns motion failed: {e}. Retrying static 16:9 loop...")
        simple_cmd = [
            ffmpeg_exe, "-y",
            "-loop", "1",
            "-i", str(image_path),
            "-t", f"{target_dur:.2f}",
            "-vf", f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},setsar=1,fps={fps}",
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-crf", "18",
            "-pix_fmt", "yuv420p",
            "-an",
            str(out_path)
        ]
        try:
            subprocess.run(simple_cmd, capture_output=True, check=True)
            return str(out_path)
        except Exception as e2:
            print(f"[ImageGenerator] Error converting image to video: {e2}")
            return str(image_path)
