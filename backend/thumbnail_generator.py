import os
import re
import time
import shutil
import random
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance

from .config import find_ffmpeg, DATA_DIR, OUTPUT_DIR, TEMP_DIR, load_settings

THUMBNAILS_DIR = DATA_DIR / "thumbnails"
THUMBNAILS_DIR.mkdir(parents=True, exist_ok=True)


def _get_font(font_name: str, size: int) -> ImageFont.FreeTypeFont:
    """Safely loads a Windows font or falls back gracefully."""
    font_candidates = [
        f"C:/Windows/Fonts/{font_name}.ttf",
        f"C:/Windows/Fonts/{font_name}",
        f"{font_name}.ttf",
        font_name,
        "C:/Windows/Fonts/impact.ttf",
        "C:/Windows/Fonts/ariblk.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/seguibl.ttf",
        "arial.ttf",
    ]
    for c in font_candidates:
        try:
            return ImageFont.truetype(c, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _fit_font(font_name: str, initial_size: int, text: str, max_width: int = 1140) -> ImageFont.FreeTypeFont:
    """Dynamically scales font size down until text fits within max_width."""
    if not text:
        return _get_font(font_name, initial_size)
    size = initial_size
    while size >= 32:
        f = _get_font(font_name, size)
        try:
            bbox = f.getbbox(text)
            w = bbox[2] - bbox[0]
            if w <= max_width:
                return f
        except Exception:
            return f
        size -= 4
    return _get_font(font_name, 32)


def extract_hook_text(project: Dict[str, Any], custom_headline: Optional[str] = None) -> Tuple[str, str]:
    """
    Extracts a punchy, clickbait 2-line headline suitable for YouTube thumbnails.
    Line 1: High-energy hook (e.g. "STOP DOING THIS!")
    Line 2: Curiosity kicker (e.g. "BEFORE IT'S TOO LATE")
    """
    if custom_headline and custom_headline.strip():
        words = custom_headline.strip().split()
        if len(words) <= 3:
            return custom_headline.strip().upper(), ""
        mid = len(words) // 2
        return " ".join(words[:mid]).upper(), " ".join(words[mid:]).upper()

    name = project.get("name", "").strip()
    niche = project.get("niche", "General").lower()
    scenes = project.get("scenes", [])
    first_text = ""
    for sc in scenes:
        txt = sc.get("text", "").strip()
        if txt and len(txt) > 8:
            first_text = txt
            break

    # Clean text
    clean_speech = re.sub(r'[^a-zA-Z0-9\s]', ' ', first_text).strip()
    speech_words = [w for w in clean_speech.split() if len(w) > 2]

    # Smart Niche Clickbait Hooks
    niche_hooks = {
        "motivation": ("NEVER GIVE UP", "THE UNSTOPPABLE MINDSET"),
        "nature": ("INCREDIBLE DISCOVERY", "NATURE'S SECRET"),
        "tech": ("AI CHANGED EVERYTHING", "YOU WON'T BELIEVE THIS"),
        "finance": ("HOW TO GET RICH", "DON'T MISS THIS"),
        "luxury": ("LIVING THE DREAM", "INSIDE BILLIONAIRE LIFE"),
        "fitness": ("TRANSFORM TODAY", "NO MORE EXCUSES"),
        "stoic": ("THE STOIC SECRET", "SILENCE YOUR WEAKNESS"),
        "crime": ("THE DARK TRUTH", "NEVER SOLVED"),
        "science": ("SCIENCE EXPLAINED", "HOW IT REALLY WORKS"),
    }

    for k, (h1, h2) in niche_hooks.items():
        if k in niche:
            return h1, h2

    if speech_words and len(speech_words) >= 4:
        return " ".join(speech_words[:3]).upper(), " ".join(speech_words[3:6]).upper()

    if name:
        name_words = name.replace("_", " ").split()
        if len(name_words) >= 4:
            return " ".join(name_words[:2]).upper(), " ".join(name_words[2:5]).upper()
        return name.upper(), "MUST WATCH NOW"

    return "THE SECRET REVEALED", "DON'T IGNORE THIS"


def _extract_frame_from_video(video_path: str, output_image_path: str) -> bool:
    """Extracts a high quality frame from a video clip with boundary fallback for short clips."""
    if not video_path or not os.path.exists(video_path):
        return False
    ffmpeg_exe = find_ffmpeg()

    # Try 1.0s first, fallback to 0.2s or 0.0s for short scenes (< 1.5s)
    for ss_time in ["00:00:01.000", "00:00:00.200", "00:00:00.000"]:
        cmd = [
            ffmpeg_exe, "-y",
            "-ss", ss_time,
            "-i", str(video_path),
            "-vframes", "1",
            "-q:v", "2",
            "-vf", "scale=1280:720:force_original_aspect_ratio=increase,crop=1280:720",
            str(output_image_path)
        ]
        try:
            res = subprocess.run(cmd, capture_output=True, timeout=8)
            if res.returncode == 0 and os.path.exists(output_image_path) and os.path.getsize(output_image_path) > 1000:
                return True
        except Exception:
            pass

    return False


def _fetch_stock_photo(query: str, settings: Dict[str, Any], output_path: str) -> bool:
    """Fetches high-res stock photo from Pexels or Pixabay using multi-account keys."""
    import requests
    clean_q = re.sub(r'[^a-zA-Z0-9\s]', ' ', query).strip()

    # 1. Try Pexels Photo API across keys
    p_keys = settings.get("pexels_api_keys") or ([settings.get("pexels_api_key")] if settings.get("pexels_api_key") else [])
    for p_key in p_keys:
        if not p_key:
            continue
        try:
            url = f"https://api.pexels.com/v1/search?query={requests.utils.quote(clean_q)}&orientation=landscape&per_page=3"
            r = requests.get(url, headers={"Authorization": p_key}, timeout=5)
            if r.status_code == 200:
                data = r.json()
                photos = data.get("photos", [])
                if photos:
                    img_url = photos[0]["src"].get("large2x") or photos[0]["src"].get("large")
                    if img_url:
                        dl = requests.get(img_url, timeout=7)
                        if dl.status_code == 200:
                            with open(output_path, "wb") as f:
                                f.write(dl.content)
                            return True
        except Exception:
            pass

    # 2. Try Pixabay Photo API across keys
    pb_keys = settings.get("pixabay_api_keys") or ([settings.get("pixabay_api_key")] if settings.get("pixabay_api_key") else [])
    for pb_key in pb_keys:
        if not pb_key:
            continue
        try:
            url = f"https://pixabay.com/api/?key={pb_key}&q={requests.utils.quote(clean_q)}&image_type=photo&orientation=horizontal&per_page=3"
            r = requests.get(url, timeout=5)
            if r.status_code == 200:
                data = r.json()
                hits = data.get("hits", [])
                if hits:
                    img_url = hits[0].get("largeImageURL") or hits[0].get("webformatURL")
                    if img_url:
                        dl = requests.get(img_url, timeout=7)
                        if dl.status_code == 200:
                            with open(output_path, "wb") as f:
                                f.write(dl.content)
                            return True
        except Exception:
            pass

    return False


def _generate_gradient_background(w: int = 1280, h: int = 720, style: str = "viral") -> Image.Image:
    """Creates a high-contrast artistic background if no images are available."""
    img = Image.new("RGB", (w, h), color="#0c101d")
    draw = ImageDraw.Draw(img)

    if style == "viral":
        # Deep blue-black with vibrant magenta/orange spotlight
        for y in range(h):
            ratio = y / h
            r = int(12 + ratio * 20)
            g = int(16 + ratio * 15)
            b = int(32 + ratio * 45)
            draw.line([(0, y), (w, y)], fill=(r, g, b))
        # Add energetic glow orb on right side
        glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        gdraw = ImageDraw.Draw(glow)
        gdraw.ellipse([w * 0.55, -h * 0.2, w * 1.2, h * 1.1], fill=(255, 60, 0, 70))
        gdraw.ellipse([w * 0.65, h * 0.1, w * 1.1, h * 0.9], fill=(255, 220, 0, 50))
        glow = glow.filter(ImageFilter.GaussianBlur(80))
        img.paste(glow, (0, 0), glow)
    elif style == "modern":
        # Cyber dark violet / midnight blue with radiant neon cyan & magenta laser spotlight
        for y in range(h):
            ratio = y / h
            r = int(15 + ratio * 30)
            g = int(8 + ratio * 15)
            b = int(35 + ratio * 55)
            draw.line([(0, y), (w, y)], fill=(r, g, b))
        glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        gdraw = ImageDraw.Draw(glow)
        gdraw.ellipse([w * 0.6, -h * 0.1, w * 1.15, h * 0.8], fill=(189, 0, 255, 60))
        gdraw.ellipse([w * 0.2, h * 0.4, w * 0.8, h * 1.1], fill=(0, 245, 255, 45))
        glow = glow.filter(ImageFilter.GaussianBlur(90))
        img.paste(glow, (0, 0), glow)
    else:
        # Cinematic dark teal / obsidian vignette
        for y in range(h):
            ratio = y / h
            r = int(6 + ratio * 8)
            g = int(18 + ratio * 22)
            b = int(28 + ratio * 32)
            draw.line([(0, y), (w, y)], fill=(r, g, b))
        glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        gdraw = ImageDraw.Draw(glow)
        gdraw.ellipse([w * 0.4, h * 0.2, w * 0.9, h * 0.8], fill=(0, 240, 255, 45))
        glow = glow.filter(ImageFilter.GaussianBlur(100))
        img.paste(glow, (0, 0), glow)

    return img


def _draw_text_with_effects(
    draw: ImageDraw.ImageDraw,
    xy: Tuple[int, int],
    text: str,
    font: ImageFont.FreeTypeFont,
    fill_color: str,
    stroke_color: str = "#000000",
    stroke_width: int = 8,
    shadow_offset: Tuple[int, int] = (6, 8),
    shadow_color: str = "#000000",
    glow_color: Optional[Tuple[int, int, int, int]] = None,
    glow_radius: int = 14,
    target_img: Optional[Image.Image] = None
):
    """
    Draws text with:
    1. Volumetric neon rim glow (via Gaussian blur on an RGBA layer if target_img & glow_color provided).
    2. Deep multi-pass drop shadow for 3D depth pop.
    3. Heavy outer stroke + vibrant foreground fill for 100% crisp YouTube readability.
    """
    x, y = xy

    # 1. Volumetric Neon Rim Glow
    if glow_color and target_img is not None:
        try:
            glow_layer = Image.new("RGBA", target_img.size, (0, 0, 0, 0))
            gdraw = ImageDraw.Draw(glow_layer)
            gdraw.text((x, y), text, font=font, fill=glow_color, stroke_width=stroke_width + 12, stroke_fill=glow_color)
            blurred_glow = glow_layer.filter(ImageFilter.GaussianBlur(glow_radius))
            target_img.paste(blurred_glow, (0, 0), blurred_glow)
        except Exception:
            pass

    sx, sy = shadow_offset
    # 2. Multi-tier drop shadow for 3D volumetric pop
    if shadow_offset != (0, 0):
        draw.text((x + sx, y + sy), text, font=font, fill=shadow_color, stroke_width=stroke_width + 4, stroke_fill=shadow_color)
        draw.text((x + max(1, sx // 2), y + max(1, sy // 2)), text, font=font, fill=shadow_color, stroke_width=stroke_width + 1, stroke_fill=shadow_color)

    # 3. Outer stroke + Vibrant fill
    draw.text((x, y), text, font=font, fill=fill_color, stroke_width=stroke_width, stroke_fill=stroke_color)


def create_style_1_viral_punch(
    base_image: Image.Image,
    line1: str,
    line2: str,
    niche: str = ""
) -> Image.Image:
    """
    STYLE 1: Viral Punch (Alex Hormozi / MrBeast Style)
    - Contrast and saturation boosted
    - Dark lateral gradient on left
    - Electric Yellow + Pure White text with golden ambient glow
    - Heavy 8px black stroke and 3D shadow
    - Viral Warning Badge ("🚨 MUST WATCH" or "🔥 100% PROVEN")
    """
    thumb = base_image.copy().resize((1280, 720), Image.Resampling.LANCZOS)
    
    # 1. Color & Contrast Boost
    enhancer = ImageEnhance.Contrast(thumb)
    thumb = enhancer.enhance(1.25)
    enhancer = ImageEnhance.Color(thumb)
    thumb = enhancer.enhance(1.20)

    # 2. Gradient Overlay on Left Side for Text Readability
    overlay = Image.new("RGBA", (1280, 720), (0, 0, 0, 0))
    odraw = ImageDraw.Draw(overlay)
    for x in range(880):
        alpha = int(225 * (1.0 - (x / 880.0) ** 1.3))
        odraw.line([(x, 0), (x, 720)], fill=(4, 6, 12, alpha))
    thumb.paste(overlay, (0, 0), overlay)

    draw = ImageDraw.Draw(thumb)

    # 3. Viral Pill Badge in Top Left
    badge_font = _get_font("impact", 28)
    badge_text = "MUST WATCH"
    if "tech" in niche.lower() or "ai" in niche.lower():
        badge_text = "MIND BLOWING"
    elif "finance" in niche.lower():
        badge_text = "FINANCIAL FREEDOM"
    elif "motivation" in niche.lower():
        badge_text = "100% PROVEN"

    bx, by = 60, 55
    bb = badge_font.getbbox(badge_text)
    bw, bh = (bb[2] - bb[0]) + 36, 52
    draw.rounded_rectangle([bx, by, bx + bw, by + bh], radius=10, fill="#E60026", outline="#FFE600", width=3)
    draw.text((bx + 18, by + 8), badge_text, font=badge_font, fill="#FFFFFF", stroke_width=2, stroke_fill="#000000")

    # 4. Main Headline Lines (Auto-scaled so text never cuts off)
    font_main_1 = _fit_font("impact", 94, line1, max_width=1120) if line1 else _get_font("impact", 94)
    font_main_2 = _fit_font("impact", 94, line2, max_width=1120) if line2 else _get_font("impact", 94)
    y_cursor = 145

    # Line 1: Electric Yellow with Gold Rim Glow
    if line1:
        _draw_text_with_effects(
            draw=draw,
            xy=(60, y_cursor),
            text=line1,
            font=font_main_1,
            fill_color="#FFE600",
            stroke_color="#000000",
            stroke_width=8,
            shadow_offset=(8, 10),
            shadow_color="#000000",
            glow_color=(255, 200, 0, 140),
            glow_radius=16,
            target_img=thumb
        )
        draw = ImageDraw.Draw(thumb)
        bbox1 = font_main_1.getbbox(line1)
        h1 = (bbox1[3] - bbox1[1]) if bbox1 else 90
        y_cursor += max(100, h1 + 25)

    # Line 2: Pure White
    if line2:
        _draw_text_with_effects(
            draw=draw,
            xy=(60, y_cursor),
            text=line2,
            font=font_main_2,
            fill_color="#FFFFFF",
            stroke_color="#000000",
            stroke_width=8,
            shadow_offset=(8, 10),
            shadow_color="#000000",
            glow_color=(255, 255, 255, 90),
            glow_radius=12,
            target_img=thumb
        )
        draw = ImageDraw.Draw(thumb)

    # 5. Bottom Callout Tagline
    tag_font = _get_font("ariblk", 28)
    tag_text = "WATCH BEFORE DELETED!"
    tb = tag_font.getbbox(tag_text)
    tw = (tb[2] - tb[0]) + 40
    draw.rounded_rectangle([60, 600, 60 + tw, 655], radius=8, fill="#FFE600", outline="#000000", width=2)
    draw.text((80, 610), tag_text, font=tag_font, fill="#000000")

    return thumb.convert("RGB")


def create_style_2_cinematic_mystery(
    base_image: Image.Image,
    line1: str,
    line2: str,
    niche: str = ""
) -> Image.Image:
    """
    STYLE 2: Cinematic Mystery (Magnates Media / James Jani / Vox Style)
    - Moody cinematic color balance & deep vignette
    - Gold / Cyan typography with volumetric cyan rim glow
    - Minimal luxury framing
    - Intriguing curiosity gap hook
    """
    thumb = base_image.copy().resize((1280, 720), Image.Resampling.LANCZOS)
    
    # 1. Moody Grading: slightly desaturate & darken with cold teal vignette
    enhancer = ImageEnhance.Contrast(thumb)
    thumb = enhancer.enhance(1.35)
    enhancer = ImageEnhance.Brightness(thumb)
    thumb = enhancer.enhance(0.85)

    # Dark Vignette Frame
    vignette = Image.new("RGBA", (1280, 720), (0, 0, 0, 0))
    vdraw = ImageDraw.Draw(vignette)
    for i in range(120):
        alpha = int(255 * (1.0 - (i / 120.0)))
        vdraw.rectangle([i, i, 1280 - i, 720 - i], outline=(2, 6, 14, alpha), width=2)
    
    # Dark bottom scrim for typography
    for y in range(330, 720):
        ratio = (y - 330) / 390.0
        alpha = int(245 * ratio)
        vdraw.line([(0, y), (1280, y)], fill=(3, 7, 16, alpha))

    thumb.paste(vignette, (0, 0), vignette)
    draw = ImageDraw.Draw(thumb)

    # 2. Sleek Border Framing (Luxury Creator Look)
    draw.rectangle([24, 24, 1256, 696], outline="#FFD700", width=2)

    # 3. Category Label in Gold
    cat_font = _get_font("ariblk", 24)
    cat_text = "• SPECIAL REPORT •"
    if "mystery" in niche.lower() or "crime" in niche.lower():
        cat_text = "• CLASSIFIED ARCHIVE •"
    elif "finance" in niche.lower() or "wealth" in niche.lower():
        cat_text = "• THE WEALTH BLUEPRINT •"
    elif "tech" in niche.lower() or "ai" in niche.lower():
        cat_text = "• THE INSIDE INVESTIGATION •"
    
    draw.text((60, 385), cat_text, font=cat_font, fill="#FFD700", stroke_width=1, stroke_fill="#000000")

    # 4. Cinematic Headline
    font_gold_1 = _fit_font("ariblk", 74, line1, max_width=1120) if line1 else _get_font("ariblk", 74)
    font_gold_2 = _fit_font("ariblk", 74, line2, max_width=1120) if line2 else _get_font("ariblk", 74)

    y_pos = 430
    if line1:
        _draw_text_with_effects(
            draw=draw,
            xy=(60, y_pos),
            text=line1,
            font=font_gold_1,
            fill_color="#00F0FF",
            stroke_color="#05101A",
            stroke_width=6,
            shadow_offset=(5, 6),
            shadow_color="#000000",
            glow_color=(0, 240, 255, 150),
            glow_radius=16,
            target_img=thumb
        )
        draw = ImageDraw.Draw(thumb)
        b1 = font_gold_1.getbbox(line1)
        h1 = (b1[3] - b1[1]) if b1 else 70
        y_pos += max(80, h1 + 18)
    
    if line2:
        _draw_text_with_effects(
            draw=draw,
            xy=(60, y_pos),
            text=line2,
            font=font_gold_2,
            fill_color="#FFFFFF",
            stroke_color="#05101A",
            stroke_width=6,
            shadow_offset=(5, 6),
            shadow_color="#000000",
            glow_color=(255, 215, 0, 90),
            glow_radius=10,
            target_img=thumb
        )
        draw = ImageDraw.Draw(thumb)

    # 5. Glowing Accent Bar
    draw.line([(60, 630), (540, 630)], fill="#FFD700", width=4)
    draw.text((60, 642), "THE UNTOLD STORY • HIGH FIDELITY DOCUMENTARY", font=_get_font("arialbd", 20), fill="#A0B0C0")

    return thumb.convert("RGB")


def create_style_3_modern_tech(
    base_image: Image.Image,
    line1: str,
    line2: str,
    niche: str = ""
) -> Image.Image:
    """
    STYLE 3: Modern Tech / Neon Visionary (MKBHD / Kurzgesagt Style)
    - Cyber neon aesthetic with deep purple & cyan ambient glow
    - Sleek glassmorphism backdrop container card behind typography
    - Electric Cyan (#00F5FF) + Radiant Magenta (#FF007A) / White text
    - Tech telemetry footer ("4K ULTRA HD • HIGH RETENTION")
    - Futuristic badge ("⚡ EXCLUSIVE BREAKTHROUGH")
    """
    thumb = base_image.copy().resize((1280, 720), Image.Resampling.LANCZOS)

    # 1. Vibrant Cyber Color Grade
    enhancer = ImageEnhance.Contrast(thumb)
    thumb = enhancer.enhance(1.22)
    enhancer = ImageEnhance.Color(thumb)
    thumb = enhancer.enhance(1.15)

    # 2. Glassmorphic Card Container on Bottom/Left for Typography
    card = Image.new("RGBA", (1280, 720), (0, 0, 0, 0))
    cdraw = ImageDraw.Draw(card)

    card_x0, card_y0 = 40, 290
    card_x1, card_y1 = 1240, 680
    # Semi-transparent dark glass fill
    cdraw.rounded_rectangle([card_x0, card_y0, card_x1, card_y1], radius=24, fill=(10, 14, 28, 205), outline=(0, 245, 255, 120), width=2)

    # Top highlight line for glassmorphic shine
    cdraw.line([(card_x0 + 24, card_y0 + 2), (card_x1 - 24, card_y0 + 2)], fill=(255, 255, 255, 140), width=2)
    thumb.paste(card, (0, 0), card)

    draw = ImageDraw.Draw(thumb)

    # 3. Futuristic Pill Badge
    badge_font = _get_font("seguibl", 22)
    badge_text = "⚡ EXCLUSIVE BREAKTHROUGH"
    if "ai" in niche.lower() or "tech" in niche.lower():
        badge_text = "⚡ NEXT-GEN AI EXCLUSIVE"
    elif "finance" in niche.lower():
        badge_text = "📈 MARKET SHOCKWAVE"
    elif "motivation" in niche.lower():
        badge_text = "🔥 MASTERCLASS PROTOCOL"

    bx, by = 70, 315
    bb = badge_font.getbbox(badge_text)
    bw, bh = (bb[2] - bb[0]) + 30, 42
    draw.rounded_rectangle([bx, by, bx + bw, by + bh], radius=8, fill="#6200EA", outline="#00F5FF", width=2)
    draw.text((bx + 15, by + 8), badge_text, font=badge_font, fill="#00F5FF")

    # 4. Modern Bold Headline
    font_tech_1 = _fit_font("ariblk", 76, line1, max_width=1100) if line1 else _get_font("ariblk", 76)
    font_tech_2 = _fit_font("ariblk", 76, line2, max_width=1100) if line2 else _get_font("ariblk", 76)

    y_pos = 370
    if line1:
        _draw_text_with_effects(
            draw=draw,
            xy=(70, y_pos),
            text=line1,
            font=font_tech_1,
            fill_color="#00F5FF",
            stroke_color="#050B14",
            stroke_width=6,
            shadow_offset=(6, 7),
            shadow_color="#000000",
            glow_color=(0, 245, 255, 170),
            glow_radius=18,
            target_img=thumb
        )
        draw = ImageDraw.Draw(thumb)
        b1 = font_tech_1.getbbox(line1)
        h1 = (b1[3] - b1[1]) if b1 else 72
        y_pos += max(82, h1 + 16)

    if line2:
        _draw_text_with_effects(
            draw=draw,
            xy=(70, y_pos),
            text=line2,
            font=font_tech_2,
            fill_color="#FFFFFF",
            stroke_color="#050B14",
            stroke_width=6,
            shadow_offset=(6, 7),
            shadow_color="#000000",
            glow_color=(189, 0, 255, 140),
            glow_radius=14,
            target_img=thumb
        )
        draw = ImageDraw.Draw(thumb)

    # 5. Glowing Telemetry Bar
    tele_font = _get_font("arialbd", 18)
    tele_text = "4K ULTRA HD  |  VERIFIED ANALYSIS  |  HIGH RETENTION"
    draw.line([(70, 638), (480, 638)], fill="#00F5FF", width=3)
    draw.text((70, 646), tele_text, font=tele_font, fill="#94A3B8")

    return thumb.convert("RGB")


def generate_youtube_thumbnails(
    project: Dict[str, Any],
    custom_headline: Optional[str] = None,
    target_dir: Optional[Path] = None,
    bundle_prefix: Optional[str] = None
) -> Dict[str, Any]:
    """
    Generates 3 distinct high-CTR YouTube thumbnails for the project:
    - Style 1: Viral Punch (Alex Hormozi / MrBeast)
    - Style 2: Cinematic Mystery (Vox / Magnates Media)
    - Style 3: Modern Tech / Neon Visionary (MKBHD / Kurzgesagt)

    Uses matching bundle_prefix (e.g. A938_20260923_224510_ProjectName) so the user can easily
    match the video and thumbnails in the output folder.
    """
    settings = load_settings()
    conf_thumb = str(settings.get("thumbnail_output_dir", "")).strip()
    thumb_default = Path(conf_thumb) if conf_thumb else THUMBNAILS_DIR
    out_dir = target_dir or thumb_default
    out_dir.mkdir(parents=True, exist_ok=True)

    proj_id = project.get("id", f"proj_{int(time.time())}")
    proj_name = project.get("name", "YouTube_Video")
    safe_name = re.sub(r'[^a-zA-Z0-9_-]', '_', proj_name)
    niche = project.get("niche", "General")

    # Match bundle prefix with video file
    prefix = bundle_prefix or project.get("bundle_prefix")
    if not prefix:
        letters = "ABCDEFGHJKLMNPQRSTUVWXYZ"
        code = f"{random.choice(letters)}{random.randint(100, 999)}"
        ts = time.strftime("%Y%m%d_%H%M%S")
        prefix = f"{code}_{ts}_{safe_name[:25].strip('_')}"
        project["bundle_prefix"] = prefix

    line1, line2 = extract_hook_text(project, custom_headline)

    # 1. Acquire Base Image
    base_img = None
    temp_frame_path = str(TEMP_DIR / f"thumb_frame_{proj_id}_{int(time.time())}.jpg")

    # A. Try Rendered Video first
    rendered_vid = project.get("rendered_video", {})
    vid_file = rendered_vid.get("file_path") if rendered_vid else None
    if vid_file and os.path.exists(vid_file):
        if _extract_frame_from_video(vid_file, temp_frame_path):
            try:
                base_img = Image.open(temp_frame_path).convert("RGB")
            except Exception:
                pass

    # B. Try Scene 0 clip if rendered video frame failed
    if base_img is None:
        scenes = project.get("scenes", [])
        if scenes:
            clip = scenes[0].get("video_clip", {})
            fpath = clip.get("file_path") or clip.get("raw_file_path")
            if fpath and os.path.exists(fpath):
                if _extract_frame_from_video(fpath, temp_frame_path):
                    try:
                        base_img = Image.open(temp_frame_path).convert("RGB")
                    except Exception:
                        pass

    # C. Try Stock Photo API
    if base_img is None:
        search_query = niche
        if scenes and scenes[0].get("search_tags"):
            search_query = scenes[0]["search_tags"][0]
        if _fetch_stock_photo(search_query, settings, temp_frame_path):
            try:
                base_img = Image.open(temp_frame_path).convert("RGB")
            except Exception:
                pass

    # D. Fallback: Gradient backgrounds
    if base_img is None:
        base_img_1 = _generate_gradient_background(1280, 720, style="viral")
        base_img_2 = _generate_gradient_background(1280, 720, style="cinematic")
        base_img_3 = _generate_gradient_background(1280, 720, style="modern")
    else:
        base_img_1 = base_img.copy()
        base_img_2 = base_img.copy()
        base_img_3 = base_img.copy()

    # Clean up temp frame
    if os.path.exists(temp_frame_path):
        try:
            os.remove(temp_frame_path)
        except Exception:
            pass

    # 2. Render all 3 Distinct Styles
    thumb1 = create_style_1_viral_punch(base_img_1, line1, line2, niche=niche)
    thumb2 = create_style_2_cinematic_mystery(base_img_2, line1, line2, niche=niche)
    thumb3 = create_style_3_modern_tech(base_img_3, line1, line2, niche=niche)

    # 3. Save to data/thumbnails/ with matching prefix and legacy filenames
    t1_filename = f"{prefix}_Thumb_Viral_Style1.jpg"
    t2_filename = f"{prefix}_Thumb_Cinematic_Style2.jpg"
    t3_filename = f"{prefix}_Thumb_ModernTech_Style3.jpg"
    t1_path = out_dir / t1_filename
    t2_path = out_dir / t2_filename
    t3_path = out_dir / t3_filename

    thumb1.save(str(t1_path), "JPEG", quality=95)
    thumb2.save(str(t2_path), "JPEG", quality=95)
    thumb3.save(str(t3_path), "JPEG", quality=95)

    # Also save legacy files for backward compatibility
    try:
        thumb1.save(str(out_dir / f"{proj_id}_thumb_1_viral.jpg"), "JPEG", quality=92)
        thumb2.save(str(out_dir / f"{proj_id}_thumb_2_cinematic.jpg"), "JPEG", quality=92)
        thumb3.save(str(out_dir / f"{proj_id}_thumb_3_modern.jpg"), "JPEG", quality=92)
    except Exception:
        pass

    # 4. ALSO copy all 3 directly into the video output directory!
    try:
        conf_out = str(settings.get("output_dir", "")).strip()
        dest_dir = Path(conf_out) if conf_out else OUTPUT_DIR
        dest_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(t1_path, dest_dir / t1_filename)
        shutil.copy2(t2_path, dest_dir / t2_filename)
        shutil.copy2(t3_path, dest_dir / t3_filename)
    except Exception as e:
        print(f"[ThumbnailGenerator] Notice copying thumbnails to video output dir: {e}")

    # Web URLs
    url1 = f"/media/thumbnails/{t1_filename}"
    url2 = f"/media/thumbnails/{t2_filename}"
    url3 = f"/media/thumbnails/{t3_filename}"

    return {
        "thumb1_url": url1,
        "thumb2_url": url2,
        "thumb3_url": url3,
        "thumb1_path": str(t1_path),
        "thumb2_path": str(t2_path),
        "thumb3_path": str(t3_path),
        "headline_line1": line1,
        "headline_line2": line2,
        "bundle_prefix": prefix,
        "generated_at": time.strftime("%b %d, %Y %I:%M %p")
    }
