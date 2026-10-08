import os
import re
import hashlib
import requests
import subprocess
import base64
from pathlib import Path
from typing import List, Optional
from PIL import Image

from .config import CACHE_DIR, TEMP_DIR, find_ffmpeg, load_settings

IMAGE_CACHE_DIR = CACHE_DIR / "scene_images"
IMAGE_CACHE_DIR.mkdir(parents=True, exist_ok=True)

SCENE_CLIP_DIR = CACHE_DIR / "scene_clips"
SCENE_CLIP_DIR.mkdir(parents=True, exist_ok=True)

# Universal negative prompt — keeps images clean & cinematic
NEGATIVE_PROMPT = (
    "text, watermark, logo, caption, subtitle, banner, label, signature, "
    "blurry, low quality, bad anatomy, deformed, ugly, cartoon, anime, "
    "illustration, painting, drawing, sketch, 3d render, artificial, "
    "oversaturated, grain, noise, jpeg artifacts, ugly face, duplicate, "
    "multiple frames, collage, tiling"
)


def _enrich_image_prompt(raw_text: str, tags: Optional[List[str]] = None, niche: str = "General") -> str:
    """
    Builds a rich, cinematic image prompt from voiceover text or search tags.
    Optimized for Pollinations Flux & Gemini Imagen.
    """
    # Pick best base subject
    if tags and len(tags) > 0:
        base_text = ", ".join(tags[:4])
    elif raw_text:
        # Strip filler/stop words, keep meaningful nouns & verbs
        clean = re.sub(r'[^a-zA-Z0-9\s]', ' ', raw_text).strip()
        stop = {
            "this", "that", "with", "from", "have", "been", "were", "what",
            "here", "there", "they", "your", "will", "just", "when", "then",
            "than", "into", "also", "some", "about", "more", "very", "only",
            "like", "over", "after", "before", "their", "which"
        }
        words = [w for w in clean.split() if len(w) >= 3 and w.lower() not in stop]
        base_text = " ".join(words[:8]) if words else raw_text[:60]
    else:
        base_text = "cinematic dramatic scene"

    # Niche-specific visual style
    niche_lower = str(niche).lower()
    txt_lower = base_text.lower()

    military_kw = ["missile", "war", "military", "tank", "soldier", "rocket", "strike", "weapon", "navy", "army"]
    if "war" in niche_lower or "military" in niche_lower or any(w in txt_lower for w in military_kw):
        style = (
            "military documentary photography, dramatic war zone, tactical battlefield, "
            "volumetric light through smoke, cinematic lens flare, extreme wide angle"
        )
    elif "tech" in niche_lower or "ai" in niche_lower or "software" in niche_lower:
        style = (
            "futuristic tech aesthetic, dark studio background, glowing holographic UI, "
            "neon blue cyan accent light, professional corporate photography"
        )
    elif "motivat" in niche_lower or "success" in niche_lower or "mindset" in niche_lower or "productivity" in niche_lower:
        style = (
            "epic motivational cinematic scene, dramatic golden hour backlight, "
            "silhouette of determined person, powerful composition, cinematic anamorphic lens"
        )
    elif "finance" in niche_lower or "money" in niche_lower or "invest" in niche_lower or "crypto" in niche_lower:
        style = (
            "luxury finance photography, polished dark background, golden bokeh, "
            "professional business aesthetic, dramatic studio lighting"
        )
    elif "health" in niche_lower or "fitness" in niche_lower or "gym" in niche_lower:
        style = (
            "athletic sports photography, dynamic movement blur, gym/outdoor setting, "
            "strong directional rim lighting, energetic composition"
        )
    elif "nature" in niche_lower or "wildlife" in niche_lower or "environment" in niche_lower:
        style = (
            "National Geographic photography, majestic natural landscape, "
            "atmospheric depth of field, golden hour magic, ultra wide angle"
        )
    elif "history" in niche_lower or "empire" in niche_lower or "ancient" in niche_lower:
        style = (
            "historical epic cinematography, grand ancient architecture, "
            "golden hour warm light, dramatic moody atmosphere, film grain"
        )
    elif "food" in niche_lower or "cook" in niche_lower or "recipe" in niche_lower:
        style = (
            "professional food photography, macro lens, beautiful bokeh background, "
            "studio lighting, rich vibrant colors, editorial magazine quality"
        )
    elif "travel" in niche_lower or "adventure" in niche_lower or "explore" in niche_lower:
        style = (
            "travel photography, stunning landmark, breathtaking wide angle vista, "
            "vibrant atmosphere, cinematic sky, golden hour"
        )
    else:
        style = (
            "cinematic film still, 35mm anamorphic lens, dramatic lighting, "
            "award-winning photography, deep shadows, rich contrast"
        )

    prompt = (
        f"{base_text}, {style}, "
        f"photorealistic 8K resolution, masterpiece, highly detailed, "
        f"sharp focus, no text, no watermark"
    )
    return prompt.strip()


def generate_scene_image(
    prompt: str,
    scene_id: int = 0,
    tags: Optional[List[str]] = None,
    niche: str = "General",
    target_resolution: str = "1080p",
    aspect_ratio: str = "16:9"
) -> Path:
    """
    Generates an Ultra HD cinematic image for a scene.

    Priority chain (all FREE):
      1. Google Gemini 2.0 Flash (free tier image generation via generateContent)
      2. Google Imagen 3.0 (if Gemini key has access — usually paid but worth trying)
      3. Pollinations Flux (best free model — enhanced prompt, negative prompt, safe mode)
      4. Pollinations Turbo (fast fallback)
      5. Dark canvas placeholder (last resort — never crashes render)
    """
    settings = load_settings()
    gemini_key = settings.get("gemini_api_key", "").strip()
    gemini_keys = settings.get("gemini_api_keys") or ([gemini_key] if gemini_key else [])

    is_vertical = str(aspect_ratio).strip().lower() in ("9:16", "vertical", "portrait", "shorts", "tiktok")
    w, h = (1080, 1920) if is_vertical else (1920, 1080)
    aspect_tag = "vertical 9:16 portrait" if is_vertical else "wide angle 16:9 landscape"

    enriched = _enrich_image_prompt(prompt, tags=tags, niche=niche)
    # Correct the aspect in enriched prompt
    if is_vertical:
        enriched = enriched.replace("wide angle 16:9", "vertical 9:16 portrait composition")
    else:
        enriched = enriched.replace("vertical 9:16 portrait", "wide angle 16:9")

    prompt_hash = hashlib.md5(f"{enriched}_{w}x{h}".encode("utf-8")).hexdigest()[:10]
    out_filename = f"sc_{scene_id:04d}_{prompt_hash}.jpg"
    out_path = IMAGE_CACHE_DIR / out_filename

    if out_path.exists() and out_path.stat().st_size > 5000:
        return out_path

    image_bytes = None

    # ── Priority 1: Pollinations Turbo (100% Free, No Key Required, 2-4s Generation) ──
    neg_encoded = requests.utils.quote(NEGATIVE_PROMPT)
    prompt_encoded = requests.utils.quote(enriched)

    for model, timeout_s in [("turbo", 12), ("flux", 15)]:
        if image_bytes:
            break
        try:
            print(f"[ImageGenerator] Generating {w}x{h} via Pollinations/{model} for Scene #{scene_id+1}: '{enriched[:50]}...'")
            poll_url = (
                f"https://image.pollinations.ai/prompt/{prompt_encoded}"
                f"?width={w}&height={h}"
                f"&model={model}"
                f"&nologo=true"
                f"&enhance=true"
                f"&safe=true"
                f"&negative={neg_encoded}"
                f"&seed={abs(hash(enriched)) % 99999}"
            )
            r = requests.get(poll_url, timeout=timeout_s)
            if r.status_code == 200 and len(r.content) > 5000:
                image_bytes = r.content
                print(f"[ImageGenerator] [OK] Pollinations/{model} successfully generated Scene #{scene_id+1}")
                break
        except Exception as e:
            print(f"[ImageGenerator] Pollinations/{model} notice: {e}")

    # ── Priority 2: Google Gemini / Imagen (Quick 4s safe probe if key configured) ──
    if gemini_keys and not image_bytes:
        full_prompt = (
            f"Generate a photorealistic Ultra HD {aspect_tag} cinematic photograph of: {enriched}. "
            f"No text, no watermarks, no captions. Professional photography only."
        )
        for g_key in gemini_keys[:1]:  # Test first key with fast 4s timeout
            if not g_key or image_bytes:
                break
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-exp:generateContent?key={g_key}"
                payload = {
                    "contents": [{"parts": [{"text": full_prompt}]}],
                    "generationConfig": {"responseModalities": ["IMAGE", "TEXT"]}
                }
                res = requests.post(url, json=payload, timeout=4)
                if res.status_code == 200:
                    data = res.json()
                    for cand in data.get("candidates", []):
                        for p_item in cand.get("content", {}).get("parts", []):
                            if "inlineData" in p_item and p_item["inlineData"].get("data"):
                                image_bytes = base64.b64decode(p_item["inlineData"]["data"])
                                print(f"[ImageGenerator] [OK] Gemini generated Scene #{scene_id+1}")
                                break
                        if image_bytes:
                            break
            except Exception:
                pass

    # ── Priority 3: Pixabay & Pexels 4K Stock Photo Fallback (0.4s Instant & High-Res) ──
    if not image_bytes:
        search_query = tags[0] if tags and len(tags) > 0 else (prompt[:40] if prompt else "cinematic nature")
        clean_q = re.sub(r'[^a-zA-Z0-9\s]', ' ', search_query).strip()

        # Try Pixabay Photos
        pb_key = settings.get("pixabay_api_key", "").strip()
        if pb_key and not image_bytes:
            try:
                orient = "vertical" if is_vertical else "horizontal"
                pb_url = f"https://pixabay.com/api/?key={pb_key}&q={requests.utils.quote(clean_q)}&image_type=photo&orientation={orient}&per_page=3"
                pb_res = requests.get(pb_url, timeout=4)
                if pb_res.status_code == 200:
                    hits = pb_res.json().get("hits", [])
                    if hits:
                        img_url = hits[0].get("largeImageURL") or hits[0].get("webformatURL")
                        if img_url:
                            img_r = requests.get(img_url, timeout=6)
                            if img_r.status_code == 200 and len(img_r.content) > 5000:
                                image_bytes = img_r.content
                                print(f"[ImageGenerator] [OK] Pixabay 4K Stock Photo retrieved for Scene #{scene_id+1}")
            except Exception as e:
                print(f"[ImageGenerator] Pixabay photo fallback notice: {e}")

        # Try Pexels Photos
        px_key = settings.get("pexels_api_key", "").strip()
        if px_key and not image_bytes:
            try:
                px_orient = "portrait" if is_vertical else "landscape"
                px_url = f"https://api.pexels.com/v1/search?query={requests.utils.quote(clean_q)}&orientation={px_orient}&per_page=3"
                px_res = requests.get(px_url, headers={"Authorization": px_key}, timeout=4)
                if px_res.status_code == 200:
                    photos = px_res.json().get("photos", [])
                    if photos:
                        src = photos[0].get("src", {})
                        p_img_url = src.get("large2x") or src.get("large") or src.get("original")
                        if p_img_url:
                            img_r = requests.get(p_img_url, timeout=6)
                            if img_r.status_code == 200 and len(img_r.content) > 5000:
                                image_bytes = img_r.content
                                print(f"[ImageGenerator] [OK] Pexels 4K Stock Photo retrieved for Scene #{scene_id+1}")
            except Exception as e:
                print(f"[ImageGenerator] Pexels photo fallback notice: {e}")

    # ── Priority 4: Dark branded canvas placeholder (last resort — never crashes) ──
    if not image_bytes:
        print(f"[ImageGenerator] [Notice] All online image sources timed out for Scene #{scene_id+1} — creating canvas")
        img = Image.new("RGB", (w, h), color=(12, 18, 32))
        from PIL import ImageDraw
        draw = ImageDraw.Draw(img)
        for i in range(0, h, 4):
            alpha = int(255 * (i / h) * 0.3)
            draw.line([(0, i), (w, i)], fill=(20 + alpha // 10, 30 + alpha // 8, 60 + alpha // 5))
        img.save(out_path, format="JPEG", quality=95)
        return out_path

    # ── Save & verify ──
    with open(out_path, "wb") as f:
        f.write(image_bytes)

    try:
        with Image.open(out_path) as test_img:
            test_img.verify()
    except Exception:
        img = Image.new("RGB", (w, h), color=(12, 18, 32))
        img.save(out_path, format="JPEG", quality=95)

    return out_path


# ════════════════════════════════════════════════════════════
#  Image → Scene Video Clip (Ken Burns zoom motion)
# ════════════════════════════════════════════════════════════

def convert_image_to_scene_clip(
    image_path: str,
    duration: float,
    scene_id: int,
    target_resolution: str = "1080p",
    motion: bool = True,
    aspect_ratio: str = "16:9"
) -> str:
    """
    Renders an Ultra HD image into an MP4 video clip matching the EXACT voiceover duration.
    Applies subtle cinematic Ken Burns zoom/pan motion.
    Supports 16:9 Landscape and 9:16 Vertical Shorts.
    """
    if not image_path or not os.path.exists(image_path):
        return ""

    ffmpeg_exe = find_ffmpeg()
    target_dur = max(0.5, round(float(duration), 2))
    is_vertical = str(aspect_ratio).strip().lower() in ("9:16", "vertical", "portrait", "shorts", "tiktok")
    res_str = str(target_resolution or "1080p").lower().strip()

    if is_vertical:
        if res_str == "8k":
            w, h = 4320, 7680
        elif res_str == "4k":
            w, h = 2160, 3840
        else:
            w, h = 1080, 1920
    else:
        if res_str == "8k":
            w, h = 7680, 4320
        elif res_str == "4k":
            w, h = 3840, 2160
        else:
            w, h = 1920, 1080

    path_hash = hashlib.md5(f"{image_path}_{target_dur}_{w}x{h}_{motion}".encode("utf-8")).hexdigest()[:8]
    out_name = f"sc_{scene_id:04d}_ai_{path_hash}.mp4"
    out_path = SCENE_CLIP_DIR / out_name

    if out_path.exists() and out_path.stat().st_size > 1000:
        return str(out_path)

    fps = 30
    total_frames = max(15, int(target_dur * fps))

    # Ken Burns: subtle cinematic zoom-in
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
        print(f"[ImageGenerator] Ken Burns failed: {e} — retrying static")
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
