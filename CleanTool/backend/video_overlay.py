"""
Video Overlay Engine — Overlay a secondary video/image layer on top of the main video.
Supports position presets (corners, center), opacity control (0-100%), and auto-scaling.
Integrates into the FFmpeg filter_complex chain in video_renderer.py.
"""

import os
from pathlib import Path
from typing import Optional, Tuple

from .config import DATA_DIR, BASE_DIR


OVERLAY_DIR = DATA_DIR / "assets" / "overlays"
OVERLAY_DIR.mkdir(parents=True, exist_ok=True)

# Position presets: maps friendly name → FFmpeg overlay coordinates
# W = main video width, H = main video height, w = overlay width, h = overlay height
POSITION_PRESETS = {
    "top_left":     "overlay=10:10",
    "top_right":    "overlay=W-w-10:10",
    "bottom_left":  "overlay=10:H-h-10",
    "bottom_right": "overlay=W-w-10:H-h-10",
    "center":       "overlay=(W-w)/2:(H-h)/2",
}


def resolve_overlay_path(path_or_key: Optional[str]) -> Optional[str]:
    """
    Resolves an overlay video/image file path.
    Accepts absolute path, relative path, or filename in the overlays directory.
    Returns None if overlay is disabled or file not found.
    """
    if not path_or_key or path_or_key in ("none", "off", "None", ""):
        return None

    p = Path(path_or_key)

    # 1. Absolute path
    if p.is_absolute() and p.exists():
        return str(p.resolve())

    # 2. Check in data/assets/overlays/
    overlay_path = OVERLAY_DIR / path_or_key
    if overlay_path.exists():
        return str(overlay_path.resolve())

    # 3. Check with common extensions
    for ext in (".mp4", ".mov", ".webm", ".png", ".jpg", ".gif"):
        candidate = OVERLAY_DIR / f"{path_or_key}{ext}"
        if candidate.exists():
            return str(candidate.resolve())

    # 4. Check relative to BASE_DIR
    if (BASE_DIR / path_or_key).exists():
        return str((BASE_DIR / path_or_key).resolve())

    return None


def get_overlay_scale_filter(
    overlay_input_label: str,
    target_w: int,
    target_h: int,
    scale_percent: float = 20.0
) -> Tuple[str, str]:
    """
    Returns FFmpeg filter string to scale overlay to a percentage of the main frame width
    while maintaining aspect ratio, plus the output label.
    
    Args:
        overlay_input_label: FFmpeg stream label (e.g. "[3:v]")
        target_w: Main video width (e.g. 1920)
        target_h: Main video height (e.g. 1080)
        scale_percent: Overlay width as % of main frame (default 20% = ~384px on 1080p)
    
    Returns:
        Tuple of (filter_string, output_label)
    """
    overlay_w = int(target_w * (scale_percent / 100.0))
    # -1 preserves aspect ratio
    output_label = "[ovr_scaled]"
    filter_str = f"{overlay_input_label}scale={overlay_w}:-1{output_label}"
    return filter_str, output_label


def build_overlay_filter(
    overlay_input_idx: int,
    video_input_label: str,
    position: str = "bottom_right",
    opacity: float = 0.30,
    target_w: int = 1920,
    target_h: int = 1080,
    scale_percent: float = 20.0,
    is_video_overlay: bool = True
) -> Tuple[str, str]:
    """
    Builds a complete FFmpeg filter_complex string for video/image overlay with opacity.
    
    Args:
        overlay_input_idx: FFmpeg input index for the overlay file (e.g. 3 for 4th input)
        video_input_label: Current video stream label (e.g. "[0:v]" or "[vout]")
        position: Position preset name or "custom_X_Y" format
        opacity: 0.0 (invisible) to 1.0 (fully opaque)
        target_w: Main video width
        target_h: Main video height
        scale_percent: Overlay scale as % of main frame width
        is_video_overlay: True if overlay is video, False if static image
    
    Returns:
        Tuple of (filter_complex_string, output_video_label)
    """
    opacity = max(0.0, min(1.0, float(opacity)))
    
    # Determine overlay position
    position_key = str(position).lower().strip()
    if position_key.startswith("custom_"):
        # Custom X,Y position: "custom_100_200"
        parts = position_key.replace("custom_", "").split("_")
        try:
            x, y = int(parts[0]), int(parts[1])
            overlay_pos = f"overlay={x}:{y}"
        except (ValueError, IndexError):
            overlay_pos = POSITION_PRESETS.get("bottom_right", "overlay=W-w-10:H-h-10")
    else:
        overlay_pos = POSITION_PRESETS.get(position_key, POSITION_PRESETS["bottom_right"])
    
    # Calculate overlay dimensions
    overlay_w = int(target_w * (scale_percent / 100.0))
    
    # Build filter chain:
    # 1. Scale overlay to target size
    # 2. Apply opacity via colorchannelmixer (alpha channel)
    # 3. Overlay onto main video at specified position
    
    ovr_input = f"[{overlay_input_idx}:v]"
    
    filter_parts = []
    
    # Scale + format to RGBA (needed for opacity) + apply opacity
    if opacity < 1.0:
        filter_parts.append(
            f"{ovr_input}scale={overlay_w}:-1,format=rgba,"
            f"colorchannelmixer=aa={opacity:.2f}[ovr_ready]"
        )
    else:
        filter_parts.append(
            f"{ovr_input}scale={overlay_w}:-1,format=rgba[ovr_ready]"
        )
    
    # If video overlay needs looping to match main video duration
    if is_video_overlay:
        # Use shortest=1 so overlay stops when main video ends
        filter_parts.append(
            f"{video_input_label}[ovr_ready]{overlay_pos}:shortest=1[vovr]"
        )
    else:
        filter_parts.append(
            f"{video_input_label}[ovr_ready]{overlay_pos}[vovr]"
        )
    
    output_label = "[vovr]"
    filter_string = ";".join(filter_parts)
    
    return filter_string, output_label


def list_overlay_files() -> list:
    """Lists all available overlay files in the overlays directory."""
    if not OVERLAY_DIR.exists():
        return []
    
    valid_exts = {".mp4", ".mov", ".webm", ".avi", ".png", ".jpg", ".jpeg", ".gif", ".webp"}
    files = []
    for f in sorted(OVERLAY_DIR.iterdir()):
        if f.suffix.lower() in valid_exts:
            files.append({
                "name": f.stem,
                "filename": f.name,
                "path": str(f.resolve()),
                "type": "video" if f.suffix.lower() in (".mp4", ".mov", ".webm", ".avi") else "image",
                "size_kb": round(f.stat().st_size / 1024, 1)
            })
    return files
