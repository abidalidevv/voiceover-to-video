import os
import time
import random
import subprocess
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Optional
from .config import find_ffmpeg, find_ffprobe, TEMP_DIR, OUTPUT_DIR, BASE_DIR, DATA_DIR, load_settings
from .transcriber import get_audio_duration
from .video_overlay import resolve_overlay_path, build_overlay_filter

# Modern transition pool for random mixing (YouTube/TikTok creator style)
TRANSITION_POOL = ["smoothleft", "smoothright", "zoomin", "fade", "fadefast", "circlecrop", "dissolve"]


def _pick_transition(
    idx: int,
    mode: str = "fixed",
    fallback: str = "smoothleft",
    last_picked: Optional[str] = None
) -> str:
    """
    Returns transition type for scene boundary idx based on mode.
    - If mode is 'random', picks via random.choice(TRANSITION_POOL) ensuring no two
      consecutive scene boundaries ever use the same transition type.
    - If mode is 'fixed', returns the template's single fixed transition value (fallback).
    - If mode is a specific transition name (backward compatibility), returns that mode.
    """
    mode_str = str(mode or "fixed").lower().strip()

    if mode_str == "random":
        # Never pick the SAME transition twice in a row
        candidates = [t for t in TRANSITION_POOL if t != last_picked]
        if not candidates:
            candidates = TRANSITION_POOL
        return random.choice(candidates)

    if mode_str == "fixed":
        return fallback if fallback is not None else "smoothleft"

    # Direct transition name passed as mode (e.g. "smoothleft", "fade", "none")
    return mode_str


def _resolve_audio_path(path_str: str) -> str:
    """Ensures input voiceover audio is resolved to an absolute, existing path."""
    if not path_str:
        return ""
    p = Path(path_str)
    if p.is_absolute() and p.exists():
        return str(p.resolve())
    # Try relative to BASE_DIR
    if (BASE_DIR / path_str).exists():
        return str((BASE_DIR / path_str).resolve())
    # Try relative to DATA_DIR
    if (DATA_DIR / path_str).exists():
        return str((DATA_DIR / path_str).resolve())
    # Try in data/temp
    if (DATA_DIR / "temp" / p.name).exists():
        return str((DATA_DIR / "temp" / p.name).resolve())
    return str(p.resolve())


def _resolve_bgm_path(bgm_key_or_path: Optional[str]) -> Optional[str]:
    """Resolves built-in preset or custom uploaded BGM audio file."""
    if not bgm_key_or_path or bgm_key_or_path in ("none", "off", "None", ""):
        return None
    # Check if absolute path
    p = Path(bgm_key_or_path)
    if p.is_absolute() and p.exists():
        return str(p.resolve())
    # Check in data/assets/bgm
    preset_path = DATA_DIR / "assets" / "bgm" / f"{bgm_key_or_path}.mp3"
    if preset_path.exists():
        return str(preset_path.resolve())
    # Check without extension
    preset_path_direct = DATA_DIR / "assets" / "bgm" / bgm_key_or_path
    if preset_path_direct.exists():
        return str(preset_path_direct.resolve())
    # Check relative to BASE_DIR
    if (BASE_DIR / bgm_key_or_path).exists():
        return str((BASE_DIR / bgm_key_or_path).resolve())
    return None


def _resolve_sfx_path(sfx_key_or_path: Optional[str]) -> Optional[str]:
    """Resolves built-in preset or custom SFX audio file in data/sfx/."""
    if not sfx_key_or_path or sfx_key_or_path in ("none", "off", "None", ""):
        return None
    p = Path(sfx_key_or_path)
    if p.is_absolute() and p.exists():
        return str(p.resolve())
    # Check in data/sfx with .mp3 extension
    sfx_path = DATA_DIR / "sfx" / f"{sfx_key_or_path}.mp3"
    if sfx_path.exists():
        return str(sfx_path.resolve())
    # Check in data/sfx directly
    sfx_path_direct = DATA_DIR / "sfx" / sfx_key_or_path
    if sfx_path_direct.exists():
        return str(sfx_path_direct.resolve())
    # Check relative to BASE_DIR
    if (BASE_DIR / sfx_key_or_path).exists():
        return str((BASE_DIR / sfx_key_or_path).resolve())
    return None


def render_final_video(
    audio_path: str,
    scenes: List[Dict[str, Any]],
    ass_subtitle_path: Optional[str] = None,
    output_filename: Optional[str] = None,
    custom_options: Dict[str, Any] = None,
    progress_callback = None
) -> str:
    """
    High-Speed Parallel Segmented Video Renderer with 16:9 Fitting, Audio Muxing & BGM.
    1. Normalizes clips in parallel: enforces 16:9 1920x1080 (smart crop / blurred letterbox for portrait clips).
    2. Supports subtle Ken Burns motion, cinematic vignette, and film grain overlay.
    3. Mutes native stock audio by default (or reduces to 10% ambient level).
    4. Losslessly concatenates normalized video segments in < 1 second.
    5. Dual-channel audio mixer: Voiceover (100% volume) + Background Music (10% volume).
    6. Burns CapCut kinetic subtitles and outputs high quality YouTube Full HD 1080p.
    """
    ffmpeg_exe = find_ffmpeg()
    settings = load_settings()
    custom_options = custom_options or {}

    if not output_filename:
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        output_filename = f"VideoGen_{timestamp}.mp4"

    conf_out = str(settings.get("output_dir", "")).strip()
    out_dir = Path(conf_out) if conf_out else OUTPUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    final_output_path = out_dir / output_filename

    fps = int(custom_options.get("fps", 30))
    use_gpu = bool(settings.get("gpu_acceleration", True))
    
    # Master On/Off Toggles
    enable_polish = bool(custom_options.get("enable_polish", True))
    enable_bgm = bool(custom_options.get("enable_bgm", True))
    enable_sfx = bool(custom_options.get("enable_sfx", True))

    # Options for visual FX and audio
    enable_motion = bool(custom_options.get("enable_motion", False)) and enable_polish
    enable_vignette = bool(custom_options.get("enable_vignette", False)) and enable_polish
    color_grade = custom_options.get("color_grade", "clean") if enable_polish else "clean"
    transition = (custom_options.get("transition", "none").lower().strip()) if enable_polish else "none"
    transition_mode = custom_options.get("transition_mode", "fixed").lower().strip()
    if transition == "random":
        transition_mode = "random"

    mute_stock_audio = bool(custom_options.get("mute_stock_audio", True))
    bgm_track = custom_options.get("bgm_track", settings.get("default_bgm", "cinematic_ambient")) if enable_bgm else "none"
    bgm_volume = float(custom_options.get("bgm_volume", 0.10)) if enable_bgm else 0.0
    raw_sfx = custom_options.get("transition_sfx") or settings.get("default_transition_sfx") or "whoosh_soft"
    transition_sfx = raw_sfx if enable_sfx else "none"
    transition_sfx_volume = float(custom_options.get("transition_sfx_volume", 0.40)) if enable_sfx else 0.0
    emphasis_zoom_enabled = bool(custom_options.get("emphasis_zoom_enabled", False)) and enable_polish
    emphasis_zoom_intensity = float(custom_options.get("emphasis_zoom_intensity", 1.15))

    # Video Overlay options
    overlay_video_path = custom_options.get("overlay_video", None)
    overlay_opacity = float(custom_options.get("overlay_opacity", 0.30))
    overlay_position = str(custom_options.get("overlay_position", "bottom_right")).lower().strip()
    overlay_scale = float(custom_options.get("overlay_scale", 20.0))
    resolved_overlay_path = resolve_overlay_path(overlay_video_path)
    has_overlay = bool(resolved_overlay_path and os.path.exists(resolved_overlay_path))

    # Aspect Ratio Configuration (16:9 Landscape vs 9:16 Vertical Shorts/TikTok)
    aspect_ratio = str(custom_options.get("aspect_ratio", "")).strip().lower()
    if not aspect_ratio:
        video_style = str(custom_options.get("video_style", "")).lower()
        if "tiktok" in video_style or "shorts" in video_style or "hormozi" in video_style or "9:16" in video_style:
            aspect_ratio = "9:16"
        else:
            aspect_ratio = "16:9"

    is_vertical = aspect_ratio in ("9:16", "vertical", "portrait")

    # Resolution Configuration (1080p, 4K UHD, 8K UHD)
    target_res = str(custom_options.get("target_resolution", "1080p")).lower().strip()
    if is_vertical:
        if target_res == "8k":
            target_w, target_h = 4320, 7680
            motion_w1, motion_h1 = 4968, 8832
            motion_w2, motion_h2 = 4608, 8192
        elif target_res == "4k":
            target_w, target_h = 2160, 3840
            motion_w1, motion_h1 = 2484, 4416
            motion_w2, motion_h2 = 2304, 4096
        else: # 1080p vertical
            target_w, target_h = 1080, 1920
            motion_w1, motion_h1 = 1242, 2208
            motion_w2, motion_h2 = 1152, 2048
    else:
        if target_res == "8k":
            target_w, target_h = 7680, 4320
            motion_w1, motion_h1 = 8832, 4968
            motion_w2, motion_h2 = 8192, 4608
        elif target_res == "4k":
            target_w, target_h = 3840, 2160
            motion_w1, motion_h1 = 4416, 2484
            motion_w2, motion_h2 = 4096, 2304
        else: # 1080p landscape
            target_w, target_h = 1920, 1080
            motion_w1, motion_h1 = 2208, 1242
            motion_w2, motion_h2 = 2048, 1152

    # Detect fastest hardware or CPU encoder once
    preferred_encoder = custom_options.get("hardware_encoder") or settings.get("hardware_encoder", "auto")
    encoder, encoder_args = get_best_video_encoder(ffmpeg_exe, use_gpu=use_gpu, preferred=preferred_encoder)

    # Verify input voiceover audio
    resolved_audio_path = _resolve_audio_path(audio_path)
    if not os.path.exists(resolved_audio_path):
        print(f"[Renderer] Warning: Voiceover audio missing at {resolved_audio_path}. Trying fallback search...")
        temp_audios = list((DATA_DIR / "temp").glob("*.mp3"))
        if temp_audios:
            resolved_audio_path = str(temp_audios[0].resolve())
            print(f"[Renderer] Found fallback voiceover audio: {resolved_audio_path}")
        else:
            raise FileNotFoundError(f"Input voiceover audio not found at: {audio_path}")

    # Verify input video clips
    valid_clips = []
    for sc in scenes:
        clip = sc.get("video_clip", {})
        fpath = clip.get("file_path") if clip else None
        dur = float(sc.get("duration", 4.0))
        if fpath and os.path.exists(fpath):
            valid_clips.append((sc.get("id", len(valid_clips)), fpath, dur, sc))
        else:
            print(f"[Renderer] Warning: Clip missing for scene {sc.get('id')}")

    if not valid_clips:
        raise ValueError("No valid video clips found to render.")

    render_session_id = f"render_{int(time.time())}"
    seg_dir = TEMP_DIR / render_session_id
    seg_dir.mkdir(parents=True, exist_ok=True)

    # Modern transition settings (supports 'random' and 'fixed' modes)
    has_transition = (
        (transition_mode == "random" or transition in ("smoothleft", "smoothright", "zoomin", "fade", "fadefast", "circlecrop", "dissolve"))
        and len(valid_clips) > 1
        and not (transition_mode == "fixed" and transition in ("none", "", "off"))
    )
    trans_dur = float(custom_options.get("transition_duration", 0.25 if transition == "fadefast" else 0.30))

    print(f"[Renderer] Normalizing {len(valid_clips)} clips in parallel (Transition: {transition}, Mode: {transition_mode}, Encoder: {encoder})...")
    if progress_callback:
        progress_callback("normalizing", 10, f"Normalizing {len(valid_clips)} scene clips in parallel...")

    # ==================== STAGE 1: PARALLEL SEGMENT NORMALIZATION (16:9 FULL HD) ====================
    seg_files = [None] * len(valid_clips)
    # Concurrency tuned for maximum speed without hardware driver exhaustion
    if use_gpu and encoder != "libx264":
        num_workers = 2  # Hardware encoders (QSV / NVENC) perform best with 2 concurrent tasks
    else:
        num_workers = min(4, max(2, (os.cpu_count() or 4) // 2))

    def normalize_clip(item_idx, sc_id, fpath, dur, sc):
        # File extension
        seg_ext = "mp4" if has_transition else "ts"
        seg_out = seg_dir / f"seg_{item_idx:04d}.{seg_ext}"

        # If transition is enabled, add handle padding to preserve exact sentence duration
        clip_target_dur = dur
        if has_transition:
            if item_idx == 0 or item_idx == len(valid_clips) - 1:
                clip_target_dur = dur + (trans_dur / 2.0)
            else:
                clip_target_dur = dur + trans_dur

        # Emphasis punch zoom check
        has_punch_zoom = (
            emphasis_zoom_enabled
            and emphasis_zoom_intensity > 1.01
            and not sc.get("skip_emphasis_zoom", True)
            and sc.get("emphasis_rel_start") is not None
        )

        # OPTIMIZATION: Skip heavy re-encoding if clip was already pre-processed
        # by trim_and_fit_clip (filename starts with 'sc_'). Only apply motion/FX
        # if those features are actually enabled, otherwise just stream-copy duration in < 0.05s.
        fname = Path(fpath).name
        is_pretrimmed = fname.startswith("sc_")
        needs_fx = enable_motion or enable_vignette or color_grade != "clean" or has_punch_zoom

        if is_pretrimmed and not needs_fx:
            # Fast path: clip is already 1920x1080@30fps, just re-mux/copy in < 0.05 seconds
            cmd = [
                ffmpeg_exe, "-y",
                "-i", str(fpath),
                "-t", f"{clip_target_dur:.2f}",
                "-c", "copy",
                "-an",
                str(seg_out)
            ]
            try:
                subprocess.run(cmd, capture_output=True, check=True)
                if seg_out.exists() and seg_out.stat().st_size > 1000:
                    return (item_idx, seg_out)
            except subprocess.CalledProcessError:
                pass  # Fall through to full re-encode

        # Construct punch zoom expression if active
        zoom_term = ""
        if has_punch_zoom:
            t0 = float(sc["emphasis_rel_start"])
            t1 = round(t0 + 0.15, 2)
            t2 = round(t1 + 0.25, 2)
            t3 = round(t2 + 0.20, 2)
            dz = round(emphasis_zoom_intensity - 1.0, 3)
            zoom_term = f"if(between(t,{t0:.2f},{t1:.2f}),{dz:.3f}*(t-{t0:.2f})/0.15,if(between(t,{t1:.2f},{t2:.2f}),{dz:.3f},if(between(t,{t2:.2f},{t3:.2f}),{dz:.3f}*(1-(t-{t2:.2f})/0.20),0)))"

        # Build filter pipeline with high-speed linear expressions:
        if enable_motion:
            if has_punch_zoom:
                vf_scale = f"scale={motion_w1}:{motion_h1}:force_original_aspect_ratio=increase,crop=w='{target_w}/(1+{zoom_term})':h='{target_h}/(1+{zoom_term})':x='(in_w-out_w)/2':y='(in_h-out_h)/2',scale={target_w}:{target_h}"
            elif item_idx % 2 == 0:
                vf_scale = f"scale={motion_w2}:{motion_h2}:force_original_aspect_ratio=increase,crop={target_w}:{target_h}:'(in_w-out_w)*(t/{max(0.5, dur)})':'(in_h-out_h)/2'"
            else:
                vf_scale = f"scale={motion_w2}:{motion_h2}:force_original_aspect_ratio=increase,crop={target_w}:{target_h}:'(in_w-out_w)*(1-t/{max(0.5, dur)})':'(in_h-out_h)/2'"
        else:
            if has_punch_zoom:
                vf_scale = f"scale={motion_w1}:{motion_h1}:force_original_aspect_ratio=increase,crop=w='{target_w}/(1+{zoom_term})':h='{target_h}/(1+{zoom_term})':x='(in_w-out_w)/2':y='(in_h-out_h)/2',scale={target_w}:{target_h}"
            else:
                vf_scale = f"scale={target_w}:{target_h}:force_original_aspect_ratio=increase,crop={target_w}:{target_h}"

        vf_parts = [vf_scale, "setsar=1", f"fps={fps}"]
        
        if enable_vignette:
            vf_parts.append("vignette=PI/4")
            
        if color_grade == "teal_orange":
            vf_parts.append("eq=contrast=1.08:brightness=0.01:saturation=1.2,colorbalance=rs=0.08:gs=-0.04:bs=-0.08:rh=-0.06:bh=0.1")
        elif color_grade == "warm_film":
            vf_parts.append("colorbalance=rs=0.07:gs=0.02:bs=-0.06")
        elif color_grade == "vibrant":
            vf_parts.append("eq=contrast=1.06:saturation=1.2")

        vf = ",".join(vf_parts)

        cmd = [
            ffmpeg_exe, "-y",
            "-stream_loop", "-1",  # Seamlessly loop if shorter than duration
            "-i", str(fpath),
            "-t", f"{clip_target_dur:.3f}",
            "-vf", vf,
            "-r", str(fps),
            "-vsync", "cfr",
            "-c:v", encoder,
            *encoder_args,
            "-an",  # Strip stock video audio completely to avoid noise
            str(seg_out)
        ]
        try:
            subprocess.run(cmd, capture_output=True, check=True)
            return (item_idx, seg_out)
        except subprocess.CalledProcessError as e:
            # CPU fallback if hardware encoder throws for this specific clip
            try:
                cpu_cmd = [
                    ffmpeg_exe, "-y",
                    "-stream_loop", "-1",
                    "-i", str(fpath),
                    "-t", f"{clip_target_dur:.3f}",
                    "-vf", vf,
                    "-r", str(fps),
                    "-vsync", "cfr",
                    "-c:v", "libx264",
                    "-preset", "ultrafast",
                    "-crf", "20",
                    "-pix_fmt", "yuv420p",
                    "-threads", "2",
                    "-an",
                    str(seg_out)
                ]
                subprocess.run(cpu_cmd, capture_output=True, check=True)
                return (item_idx, seg_out)
            except Exception:
                pass
            print(f"[Renderer] Normalization failed for scene {sc_id}: {e.stderr.decode('utf-8', errors='ignore') if hasattr(e, 'stderr') and e.stderr else e}")
            # Fallback: create solid color test clip for this duration
            fb_cmd = [
                ffmpeg_exe, "-y",
                "-f", "lavfi",
                "-i", f"color=c=0x111726:s={target_w}x{target_h}:d={clip_target_dur:.3f}:r={fps}",
                "-c:v", "libx264",
                "-preset", "ultrafast",
                "-pix_fmt", "yuv420p",
                "-threads", "0",
                "-an",
                str(seg_out)
            ]
            subprocess.run(fb_cmd, capture_output=True, check=True)
            return (item_idx, seg_out)

    with ThreadPoolExecutor(max_workers=num_workers) as executor:
        futures = {
            executor.submit(normalize_clip, i, sc_id, fpath, dur, sc): i
            for i, (sc_id, fpath, dur, sc) in enumerate(valid_clips)
        }
        done_count = 0
        for fut in as_completed(futures):
            i, seg_path = fut.result()
            seg_files[i] = seg_path
            done_count += 1
            if progress_callback:
                pct = int(10 + (done_count / len(valid_clips)) * 45)
                progress_callback("normalizing", pct, f"Prepared clip {done_count}/{len(valid_clips)}...")

    # ==================== STAGE 2: MODERN TRANSITIONS OR LOSSLESS CONCAT ====================
    stitched_video = seg_dir / "stitched_raw.mp4"

    if has_transition:
        print(f"[Renderer] Applying modern '{transition}' transitions across {len(valid_clips)} clips via FFmpeg xfade (mode: {transition_mode})...")
        if progress_callback:
            progress_callback("concatenating", 60, f"Applying modern '{transition}' transitions...")

        # 2-PASS APPROACH for large scene counts (>15 clips):
        # Split into batches, render each batch with xfade, then concat batches.
        BATCH_SIZE = 15
        if len(valid_clips) > BATCH_SIZE:
            batch_outputs = _render_xfade_batches(
                ffmpeg_exe, seg_files, valid_clips, transition, trans_dur, seg_dir, BATCH_SIZE,
                transition_mode=transition_mode, encoder=encoder, encoder_args=encoder_args
            )
            # Concat batch outputs via stream copy
            batch_list = seg_dir / "batch_concat.txt"
            with open(batch_list, "w", encoding="utf-8") as bf:
                for bp in batch_outputs:
                    escaped = str(bp).replace("\\", "/")
                    bf.write(f"file '{escaped}'\n")
            batch_cat_cmd = [
                ffmpeg_exe, "-y",
                "-f", "concat", "-safe", "0",
                "-i", str(batch_list),
                "-c", "copy",
                str(stitched_video)
            ]
            subprocess.run(batch_cat_cmd, capture_output=True, check=True)
        else:
            # Single-pass xfade for small scene counts
            _render_xfade_single(
                ffmpeg_exe, seg_files, valid_clips, transition, trans_dur, stitched_video,
                transition_mode=transition_mode, encoder=encoder, encoder_args=encoder_args
            )

    else:
        print("[Renderer] Concatenating normalized segments via lossless stream copy...")
        if progress_callback:
            progress_callback("concatenating", 60, "Stitching video segments into timeline...")

        concat_list_file = seg_dir / "concat_list.txt"
        with open(concat_list_file, "w", encoding="utf-8") as f:
            for seg in seg_files:
                escaped = str(seg.resolve()).replace("\\", "/")
                f.write(f"file '{escaped}'\n")

        concat_cmd = [
            ffmpeg_exe, "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(concat_list_file),
            "-c", "copy",
            str(stitched_video)
        ]
        subprocess.run(concat_cmd, capture_output=True, check=True)

    # ==================== STAGE 3: AUDIO MIX & SUBTITLE BURN ====================
    print(f"[Renderer] Burning CapCut kinetic subtitles and mixing audio (Encoder: {encoder})...")
    if progress_callback:
        progress_callback("burning_subtitles", 75, "Burning CapCut kinetic captions & mastering audio...")

    # Check for Background Music (BGM)
    resolved_bgm_path = _resolve_bgm_path(bgm_track)
    has_bgm = bool(resolved_bgm_path and os.path.exists(resolved_bgm_path))

    # Check for Transition Sound Stings (SFX)
    resolved_sfx_path = _resolve_sfx_path(transition_sfx)
    has_sfx = bool(resolved_sfx_path and os.path.exists(resolved_sfx_path) and len(valid_clips) > 1)

    # Construct FFmpeg inputs
    # Input 0: Stitched video
    # Input 1: Voiceover audio (guaranteed mapped)
    final_cmd = [
        ffmpeg_exe, "-y",
        "-i", str(stitched_video),
        "-i", str(resolved_audio_path)
    ]

    # Track the next available FFmpeg input index (0=video, 1=audio)
    next_input_idx = 2
    overlay_in_idx = None
    sfx_in_idx = None

    # Add overlay video/image as input if enabled
    if has_overlay:
        overlay_in_idx = next_input_idx
        next_input_idx += 1
        final_cmd.extend(["-i", str(resolved_overlay_path)])
        print(f"[Renderer] Adding video overlay: {resolved_overlay_path} at opacity {overlay_opacity:.0%} ({overlay_position})")

    if has_bgm:
        final_cmd.extend(["-i", str(resolved_bgm_path)])
        print(f"[Renderer] Mixing BGM track: {resolved_bgm_path} at volume {bgm_volume:.2f}")
        bgm_in_idx = next_input_idx
        next_input_idx += 1
        if has_sfx:
            sfx_in_idx = next_input_idx
            next_input_idx += 1
            final_cmd.extend(["-i", str(resolved_sfx_path)])
            print(f"[Renderer] Mixing transition SFX: {resolved_sfx_path} at volume {transition_sfx_volume:.2f}")
    else:
        bgm_in_idx = None
        if has_sfx:
            sfx_in_idx = next_input_idx
            next_input_idx += 1
            final_cmd.extend(["-i", str(resolved_sfx_path)])
            print(f"[Renderer] Mixing transition SFX: {resolved_sfx_path} at volume {transition_sfx_volume:.2f}")

    # Build filter_complex for Video (Overlay + ASS Subtitles) + Audio (Voiceover + BGM + SFX mix)
    filter_complex_parts = []
    
    # 0. Video Filter: Overlay layer (applied FIRST so subtitles render on top)
    current_video_label = "[0:v]"
    if has_overlay and overlay_in_idx is not None:
        is_video_ovr = resolved_overlay_path.lower().endswith((".mp4", ".mov", ".webm", ".avi"))
        ovr_filter, ovr_label = build_overlay_filter(
            overlay_input_idx=overlay_in_idx,
            video_input_label=current_video_label,
            position=overlay_position,
            opacity=overlay_opacity,
            target_w=target_w,
            target_h=target_h,
            scale_percent=overlay_scale,
            is_video_overlay=is_video_ovr
        )
        filter_complex_parts.append(ovr_filter)
        current_video_label = ovr_label

    # 1. Video Filter: ASS subtitles if present
    if ass_subtitle_path and os.path.exists(ass_subtitle_path):
        escaped_ass = str(Path(ass_subtitle_path).resolve()).replace("\\", "/").replace(":", "\\:")
        filter_complex_parts.append(f"{current_video_label}ass='{escaped_ass}'[vout]")
        video_map_label = "[vout]"
    else:
        # If we had overlay filter, use its output label; otherwise raw stream
        if has_overlay:
            video_map_label = current_video_label
        else:
            video_map_label = "0:v:0"

    # 2. Audio Filter: Sound Stings (SFX) with adelay + Voiceover (100%) + BGM (ducked)
    transition_timestamps = []
    curr_t = 0.0
    for i in range(len(valid_clips) - 1):
        curr_t += float(valid_clips[i][2])
        transition_timestamps.append(round(curr_t, 2))

    if has_sfx and transition_timestamps and sfx_in_idx is not None:
        k_sfx = len(transition_timestamps)
        sfx_splits = "".join(f"[sfx_{k}]" for k in range(k_sfx))
        sfx_filter_lines = [f"[{sfx_in_idx}:a]asplit={k_sfx}{sfx_splits}"]
        for k, t_trans in enumerate(transition_timestamps):
            delay_ms = max(0, int(round(t_trans * 1000)))
            sfx_filter_lines.append(
                f"[sfx_{k}]adelay={delay_ms}|{delay_ms},volume={transition_sfx_volume:.2f}[sfx_d{k}]"
            )
        if k_sfx == 1:
            sfx_filter_lines.append("[sfx_d0]anull[sfx_all]")
        else:
            delayed_inputs = "".join(f"[sfx_d{k}]" for k in range(k_sfx))
            sfx_filter_lines.append(f"{delayed_inputs}amix=inputs={k_sfx}:dropout_transition=0:normalize=0[sfx_all]")

        filter_complex_parts.append(";".join(sfx_filter_lines))

    if has_bgm and has_sfx:
        audio_filter = (
            f"[1:a]volume=1.0[vo];"
            f"[{bgm_in_idx}:a]aloop=loop=-1:size=2e+09,volume={bgm_volume:.2f}[bgm];"
            f"[vo][bgm][sfx_all]amix=inputs=3:duration=first:dropout_transition=2,aresample=async=1[aout]"
        )
        filter_complex_parts.append(audio_filter)
        audio_map_label = "[aout]"
    elif has_bgm and not has_sfx:
        audio_filter = (
            f"[1:a]volume=1.0[vo];"
            f"[{bgm_in_idx}:a]aloop=loop=-1:size=2e+09,volume={bgm_volume:.2f}[bgm];"
            f"[vo][bgm]amix=inputs=2:duration=first:dropout_transition=2,aresample=async=1[aout]"
        )
        filter_complex_parts.append(audio_filter)
        audio_map_label = "[aout]"
    elif not has_bgm and has_sfx:
        audio_filter = (
            f"[1:a]volume=1.0[vo];"
            f"[vo][sfx_all]amix=inputs=2:duration=first:dropout_transition=2,aresample=async=1[aout]"
        )
        filter_complex_parts.append(audio_filter)
        audio_map_label = "[aout]"
    else:
        # Simple voiceover stream mapping
        audio_map_label = "1:a:0"

    # Calculate exact voiceover audio duration for precise audio/video sync
    try:
        audio_dur = get_audio_duration(resolved_audio_path)
    except Exception:
        audio_dur = sum(c[2] for c in valid_clips)

    if filter_complex_parts:
        final_cmd.extend(["-filter_complex", ";".join(filter_complex_parts)])
        final_cmd.extend(["-map", video_map_label, "-map", audio_map_label])
    else:
        final_cmd.extend(["-map", "0:v:0", "-map", "1:a:0", "-af", "aresample=async=1"])

    final_cmd.extend(["-t", f"{audio_dur:.3f}"])

    if video_map_label == "0:v:0":
        print("[Renderer] Subtitles disabled: Using ultra-fast lossless video stream copy (-c:v copy)!")
        final_cmd.extend([
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "192k",
            str(final_output_path)
        ])
    else:
        final_cmd.extend([
            "-c:v", encoder,
            *encoder_args,
            "-c:a", "aac",
            "-b:a", "192k",
            str(final_output_path)
        ])

    try:
        subprocess.run(final_cmd, capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as e:
        print(f"[Renderer] Render with {encoder} failed: {e.stderr}. Retrying with multi-threaded CPU libx264...")
        # Fallback to CPU libx264 with all cores
        cpu_cmd = [
            ffmpeg_exe, "-y",
            "-i", str(stitched_video),
            "-i", str(resolved_audio_path)
        ]
        if has_overlay:
            cpu_cmd.extend(["-i", str(resolved_overlay_path)])
        if has_bgm:
            cpu_cmd.extend(["-i", str(resolved_bgm_path)])
        if has_sfx:
            cpu_cmd.extend(["-i", str(resolved_sfx_path)])

        if filter_complex_parts:
            cpu_cmd.extend(["-filter_complex", ";".join(filter_complex_parts)])
            cpu_cmd.extend(["-map", video_map_label, "-map", audio_map_label])
        else:
            cpu_cmd.extend(["-map", "0:v:0", "-map", "1:a:0", "-af", "aresample=async=1"])

        cpu_cmd.extend(["-t", f"{audio_dur:.3f}"])

        if video_map_label == "0:v:0":
            cpu_cmd.extend([
                "-c:v", "copy",
                "-c:a", "aac",
                "-b:a", "192k",
                str(final_output_path)
            ])
        else:
            cpu_cmd.extend([
                "-c:v", "libx264",
                "-preset", "ultrafast",
                "-crf", "20",
                "-pix_fmt", "yuv420p",
                "-threads", "0",
                "-c:a", "aac",
                "-b:a", "192k",
                str(final_output_path)
            ])
        subprocess.run(cpu_cmd, capture_output=True, text=True, check=True)

    # Clean up temp segments
    try:
        import shutil
        shutil.rmtree(seg_dir, ignore_errors=True)
    except Exception:
        pass

    if progress_callback:
        progress_callback("completed", 100, "Render completed successfully!")

    print(f"[Renderer] High-speed render completed: {final_output_path}")
    return str(final_output_path)


_DETECTED_ENCODER_CACHE = {}

def get_best_video_encoder(ffmpeg_exe: str, use_gpu: bool = True, preferred: Optional[str] = None):
    """
    Detects and returns the optimal video encoder on Windows.
    Checks user setting ("auto", "nvenc", "qsv", "amf", "cpu") or preferred override.
    Probes in priority order:
    1. NVIDIA NVENC (h264_nvenc) - Ultra-fast GPU
    2. Intel QuickSync (h264_qsv) - Very fast iGPU/dGPU
    3. AMD AMF (h264_amf) - AMD Radeon GPU
    4. Windows MediaFoundation (h264_mf)
    5. Fallback: Highly optimized CPU libx264 using all CPU cores (-threads 0)
    """
    global _DETECTED_ENCODER_CACHE
    settings = load_settings()
    user_choice = (preferred or settings.get("hardware_encoder", "auto") or "auto").lower().strip()

    if not use_gpu or user_choice == "cpu":
        return ("libx264", ["-preset", "ultrafast", "-crf", "20", "-pix_fmt", "yuv420p", "-threads", "0"])

    cache_key = f"{user_choice}_{use_gpu}"
    if isinstance(_DETECTED_ENCODER_CACHE, dict) and cache_key in _DETECTED_ENCODER_CACHE:
        return _DETECTED_ENCODER_CACHE[cache_key]

    encoder_map = {
        "nvenc": ("h264_nvenc", ["-preset", "p4", "-tune", "hq", "-cq", "22", "-pix_fmt", "yuv420p"]),
        "qsv": ("h264_qsv", ["-preset", "veryfast", "-global_quality", "23", "-pix_fmt", "nv12"]),
        "amf": ("h264_amf", ["-usage", "transcoding", "-quality", "speed", "-rc", "cqp", "-qp_p", "23", "-pix_fmt", "yuv420p"]),
        "mf": ("h264_mf", ["-rate_control", "cbr", "-b:v", "8M", "-pix_fmt", "yuv420p"])
    }

    candidates = []
    # If user explicitly chose a specific GPU encoder, test that first
    if user_choice in encoder_map:
        candidates.append(encoder_map[user_choice])

    standard_order = [
        encoder_map["nvenc"],
        encoder_map["qsv"],
        encoder_map["amf"],
        encoder_map["mf"]
    ]
    for c in standard_order:
        if c not in candidates:
            candidates.append(c)

    for enc, args in candidates:
        try:
            test_cmd = [
                ffmpeg_exe, "-y", "-f", "lavfi", "-i", "nullsrc=s=64x64:d=0.1",
                "-c:v", enc, *args, "-f", "null", "-"
            ]
            res = subprocess.run(test_cmd, capture_output=True, timeout=5)
            if res.returncode == 0:
                print(f"[Renderer] Hardware Acceleration Active: '{enc}' (args: {args})")
                if not isinstance(_DETECTED_ENCODER_CACHE, dict):
                    _DETECTED_ENCODER_CACHE = {}
                _DETECTED_ENCODER_CACHE[cache_key] = (enc, args)
                return (enc, args)
        except Exception:
            pass

    print("[Renderer] Hardware acceleration not available or failed probe. Using multi-threaded CPU libx264 (-threads 0)")
    cpu_result = ("libx264", ["-preset", "ultrafast", "-crf", "20", "-pix_fmt", "yuv420p", "-threads", "0"])
    if not isinstance(_DETECTED_ENCODER_CACHE, dict):
        _DETECTED_ENCODER_CACHE = {}
    _DETECTED_ENCODER_CACHE[cache_key] = cpu_result
    return cpu_result


def _render_xfade_single(ffmpeg_exe, seg_files, valid_clips, transition, trans_dur, output_path, transition_mode="fixed", encoder="libx264", encoder_args=None):
    """Single-pass xfade for <=15 clips. Supports 'random' and 'fixed' transition modes."""
    if encoder_args is None:
        encoder_args = ["-preset", "ultrafast", "-crf", "18", "-pix_fmt", "yuv420p"]

    xfade_cmd = [ffmpeg_exe, "-y"]
    for seg in seg_files:
        xfade_cmd.extend(["-i", str(seg)])

    filter_chains = []
    cum_offset = 0.0
    last_picked = None
    for i in range(len(valid_clips) - 1):
        dur_i = valid_clips[i][2]
        cum_offset += dur_i

        # Safe adaptive transition duration: center transition at boundary
        eff_trans = min(trans_dur, max(0.08, dur_i * 0.35))
        trans_offset = max(0.01, round(cum_offset - (eff_trans / 2.0), 3))

        # Pick transition type (random or fixed) with no consecutive repeats
        trans_type = _pick_transition(i, mode=transition_mode, fallback=transition, last_picked=last_picked)
        last_picked = trans_type

        print(f"[Renderer] Scene boundary {i} -> {i+1}: transition '{trans_type}' (mode: {transition_mode}, offset: {trans_offset:.3f}s, duration: {eff_trans:.3f}s)")

        in_label = "[0:v]" if i == 0 else f"[v{i}]"
        next_label = f"[{i+1}:v]"
        out_label = f"[v{i+1}]"

        filter_chains.append(
            f"{in_label}{next_label}xfade=transition={trans_type}:duration={eff_trans:.3f}:offset={trans_offset:.3f}{out_label}"
        )

    final_filter = ";".join(filter_chains)
    last_out = f"[v{len(valid_clips)-1}]"

    xfade_cmd.extend([
        "-filter_complex", final_filter,
        "-map", last_out,
        "-c:v", encoder,
        *encoder_args,
        "-an",
        str(output_path)
    ])
    try:
        subprocess.run(xfade_cmd, capture_output=True, check=True)
    except subprocess.CalledProcessError:
        if encoder != "libx264":
            print(f"[Renderer] xfade with {encoder} failed, retrying with CPU libx264...")
            fallback_cmd = [
                ffmpeg_exe, "-y"
            ]
            for seg in seg_files:
                fallback_cmd.extend(["-i", str(seg)])
            fallback_cmd.extend([
                "-filter_complex", final_filter,
                "-map", last_out,
                "-c:v", "libx264",
                "-preset", "ultrafast",
                "-crf", "18",
                "-pix_fmt", "yuv420p",
                "-threads", "0",
                "-an",
                str(output_path)
            ])
            subprocess.run(fallback_cmd, capture_output=True, check=True)
        else:
            raise


def _render_xfade_batches(ffmpeg_exe, seg_files, valid_clips, transition, trans_dur, seg_dir, batch_size=15, transition_mode="fixed", encoder="libx264", encoder_args=None):
    """
    2-pass xfade for large scene counts (>15 clips).
    Splits clips into batches, renders each batch with xfade transitions,
    then returns list of batch output files for final concatenation.
    This prevents massive filtergraphs that exhaust RAM on weaker machines.
    """
    if encoder_args is None:
        encoder_args = ["-preset", "ultrafast", "-crf", "18", "-pix_fmt", "yuv420p"]

    batch_outputs = []
    total = len(valid_clips)
    last_picked = None

    for batch_start in range(0, total, batch_size):
        batch_end = min(batch_start + batch_size, total)
        batch_segs = seg_files[batch_start:batch_end]
        batch_clips = valid_clips[batch_start:batch_end]

        if len(batch_segs) == 1:
            batch_outputs.append(batch_segs[0])
            continue

        batch_out = seg_dir / f"batch_{batch_start:04d}.mp4"

        xfade_cmd = [ffmpeg_exe, "-y"]
        for seg in batch_segs:
            xfade_cmd.extend(["-i", str(seg)])

        filter_chains = []
        cum_offset = 0.0
        for i in range(len(batch_clips) - 1):
            dur_i = batch_clips[i][2]
            cum_offset += dur_i

            # Safe adaptive transition duration for batches: center transition at boundary
            eff_trans = min(trans_dur, max(0.08, dur_i * 0.35))
            trans_offset = max(0.01, round(cum_offset - (eff_trans / 2.0), 3))

            boundary_idx = batch_start + i
            trans_type = _pick_transition(boundary_idx, mode=transition_mode, fallback=transition, last_picked=last_picked)
            last_picked = trans_type

            print(f"[Renderer] Batch scene boundary {boundary_idx} -> {boundary_idx+1}: transition '{trans_type}' (mode: {transition_mode}, offset: {trans_offset:.3f}s, duration: {eff_trans:.3f}s)")

            in_label = "[0:v]" if i == 0 else f"[v{i}]"
            next_label = f"[{i+1}:v]"
            out_label = f"[v{i+1}]"

            filter_chains.append(
                f"{in_label}{next_label}xfade=transition={trans_type}:duration={eff_trans:.3f}:offset={trans_offset:.3f}{out_label}"
            )

        final_filter = ";".join(filter_chains)
        last_out = f"[v{len(batch_clips)-1}]"

        xfade_cmd.extend([
            "-filter_complex", final_filter,
            "-map", last_out,
            "-c:v", encoder,
            *encoder_args,
            "-an",
            str(batch_out)
        ])

        try:
            subprocess.run(xfade_cmd, capture_output=True, check=True)
            batch_outputs.append(batch_out)
            print(f"[Renderer] Batch {batch_start}-{batch_end} rendered with xfade transitions")
        except subprocess.CalledProcessError as e:
            if encoder != "libx264":
                print(f"[Renderer] Batch xfade with {encoder} failed, retrying with CPU libx264...")
                fallback_cmd = [ffmpeg_exe, "-y"]
                for seg in batch_segs:
                    fallback_cmd.extend(["-i", str(seg)])
                fallback_cmd.extend([
                    "-filter_complex", final_filter,
                    "-map", last_out,
                    "-c:v", "libx264",
                    "-preset", "ultrafast",
                    "-crf", "18",
                    "-pix_fmt", "yuv420p",
                    "-threads", "0",
                    "-an",
                    str(batch_out)
                ])
                try:
                    subprocess.run(fallback_cmd, capture_output=True, check=True)
                    batch_outputs.append(batch_out)
                    continue
                except Exception:
                    pass

            print(f"[Renderer] Batch xfade failed, falling back to concat for batch {batch_start}-{batch_end}")
            # Fallback: concat without transitions for this batch
            batch_list = seg_dir / f"batch_list_{batch_start}.txt"
            with open(batch_list, "w", encoding="utf-8") as bf:
                for seg in batch_segs:
                    escaped = str(seg).replace("\\", "/")
                    bf.write(f"file '{escaped}'\n")
            cat_cmd = [
                ffmpeg_exe, "-y",
                "-f", "concat", "-safe", "0",
                "-i", str(batch_list),
                "-c", "copy",
                str(batch_out)
            ]
            subprocess.run(cat_cmd, capture_output=True, check=True)
            batch_outputs.append(batch_out)

    return batch_outputs
