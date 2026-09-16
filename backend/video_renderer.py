import os
import time
import random
import subprocess
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Optional
from .config import find_ffmpeg, find_ffprobe, TEMP_DIR, OUTPUT_DIR, BASE_DIR, DATA_DIR, load_settings

# Modern transition pool for random mixing (YouTube/TikTok creator style)
TRANSITION_POOL = ["smoothleft", "smoothright", "zoomin", "fade", "fadefast", "circlecrop", "dissolve"]


def _pick_transition(idx: int, mode: str) -> str:
    """Returns transition type for scene boundary idx based on mode."""
    if mode == "random":
        return TRANSITION_POOL[idx % len(TRANSITION_POOL)]
    return mode


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

    out_dir = Path(settings.get("output_dir", str(OUTPUT_DIR)))
    out_dir.mkdir(parents=True, exist_ok=True)
    final_output_path = out_dir / output_filename

    fps = int(custom_options.get("fps", 30))
    use_gpu = bool(settings.get("gpu_acceleration", True))
    
    # Options for visual FX and audio
    enable_motion = bool(custom_options.get("enable_motion", True))
    enable_vignette = bool(custom_options.get("enable_vignette", False))
    color_grade = custom_options.get("color_grade", "clean")
    transition = custom_options.get("transition", "none").lower().strip()
    mute_stock_audio = bool(custom_options.get("mute_stock_audio", True))
    bgm_track = custom_options.get("bgm_track", settings.get("default_bgm", "cinematic_ambient"))
    bgm_volume = float(custom_options.get("bgm_volume", 0.10)) # default 10%

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
            valid_clips.append((sc.get("id", len(valid_clips)), fpath, dur))
        else:
            print(f"[Renderer] Warning: Clip missing for scene {sc.get('id')}")

    if not valid_clips:
        raise ValueError("No valid video clips found to render.")

    render_session_id = f"render_{int(time.time())}"
    seg_dir = TEMP_DIR / render_session_id
    seg_dir.mkdir(parents=True, exist_ok=True)

    # Modern transition settings (supports 'random' for mixed transitions)
    has_transition = (
        (transition in ("smoothleft", "smoothright", "zoomin", "fade", "fadefast", "circlecrop", "dissolve", "random"))
        and len(valid_clips) > 1
    )
    trans_dur = 0.25 if transition == "fadefast" else 0.35

    print(f"[Renderer] Normalizing {len(valid_clips)} clips in parallel across multi-worker threads (Transition: {transition})...")
    if progress_callback:
        progress_callback("normalizing", 10, f"Normalizing {len(valid_clips)} scene clips in parallel...")

    # ==================== STAGE 1: PARALLEL SEGMENT NORMALIZATION (16:9 FULL HD) ====================
    seg_files = [None] * len(valid_clips)
    num_workers = min(8, max(2, (os.cpu_count() or 4)))

    def normalize_clip(item_idx, sc_id, fpath, dur):
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

        # OPTIMIZATION: Skip heavy re-encoding if clip was already pre-processed
        # by trim_and_fit_clip (filename starts with 'sc_'). Only apply motion/FX
        # if those features are actually enabled, otherwise just re-trim duration.
        fname = Path(fpath).name
        is_pretrimmed = fname.startswith("sc_")
        needs_fx = enable_motion or enable_vignette or color_grade != "clean"

        if is_pretrimmed and not needs_fx and not has_transition:
            # Fast path: clip is already 1920x1080@30fps, just re-mux to .ts with stream copy
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
                return (item_idx, seg_out)
            except subprocess.CalledProcessError:
                pass  # Fall through to full re-encode

        # Build filter pipeline:
        if enable_motion:
            if item_idx % 2 == 0:
                vf_scale = f"scale=2048:1152:force_original_aspect_ratio=increase,crop=1920:1080:(in_w-out_w)/2+(in_w-out_w)/4*sin(2*PI*t/{max(0.5, dur)}):(in_h-out_h)/2+(in_h-out_h)/4*cos(2*PI*t/{max(0.5, dur)})"
            else:
                vf_scale = f"scale=2048:1152:force_original_aspect_ratio=increase,crop=1920:1080:(in_w-out_w)*(t/{max(0.5, dur)}):(in_h-out_h)/2"
        else:
            vf_scale = "scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080"

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
            "-t", f"{clip_target_dur:.2f}",
            "-vf", vf,
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-crf", "18",
            "-pix_fmt", "yuv420p",
            "-an",  # Strip stock video audio completely to avoid noise
            "-threads", "2",
            str(seg_out)
        ]
        try:
            subprocess.run(cmd, capture_output=True, check=True)
            return (item_idx, seg_out)
        except subprocess.CalledProcessError as e:
            print(f"[Renderer] Normalization failed for scene {sc_id}: {e.stderr.decode('utf-8', errors='ignore')}")
            # Fallback: create solid color test clip for this duration
            fb_cmd = [
                ffmpeg_exe, "-y",
                "-f", "lavfi",
                "-i", f"color=c=0x111726:s=1920x1080:d={clip_target_dur:.2f}:r={fps}",
                "-c:v", "libx264",
                "-preset", "ultrafast",
                "-pix_fmt", "yuv420p",
                "-an",
                str(seg_out)
            ]
            subprocess.run(fb_cmd, capture_output=True, check=True)
            return (item_idx, seg_out)

    with ThreadPoolExecutor(max_workers=num_workers) as executor:
        futures = {
            executor.submit(normalize_clip, i, sc_id, fpath, dur): i
            for i, (sc_id, fpath, dur) in enumerate(valid_clips)
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
        print(f"[Renderer] Applying modern '{transition}' transitions across {len(valid_clips)} clips via FFmpeg xfade...")
        if progress_callback:
            progress_callback("concatenating", 60, f"Applying modern '{transition}' transitions...")

        # 2-PASS APPROACH for large scene counts (>15 clips):
        # Split into batches, render each batch with xfade, then concat batches.
        # This prevents massive single-command filtergraphs that exhaust RAM.
        BATCH_SIZE = 15
        if len(valid_clips) > BATCH_SIZE:
            batch_outputs = _render_xfade_batches(
                ffmpeg_exe, seg_files, valid_clips, transition, trans_dur, seg_dir, BATCH_SIZE
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
                ffmpeg_exe, seg_files, valid_clips, transition, trans_dur, stitched_video
            )

    else:
        print("[Renderer] Concatenating normalized segments via stream copy...")
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
    print("[Renderer] Burning CapCut kinetic subtitles and mixing audio...")
    if progress_callback:
        progress_callback("burning_subtitles", 75, "Burning CapCut kinetic captions & mastering audio...")

    # Choose encoder: check for hardware NVENC
    encoder = "libx264"
    encoder_args = ["-preset", "ultrafast", "-crf", "20", "-pix_fmt", "yuv420p"]


    if use_gpu and _check_nvenc_available(ffmpeg_exe):
        encoder = "h264_nvenc"
        encoder_args = ["-preset", "p4", "-cq", "22", "-pix_fmt", "yuv420p"]

    # Check for Background Music (BGM)
    resolved_bgm_path = _resolve_bgm_path(bgm_track)
    has_bgm = bool(resolved_bgm_path and os.path.exists(resolved_bgm_path))

    # Construct FFmpeg inputs
    # Input 0: Stitched video
    # Input 1: Voiceover audio (guaranteed mapped)
    final_cmd = [
        ffmpeg_exe, "-y",
        "-i", str(stitched_video),
        "-i", str(resolved_audio_path)
    ]

    if has_bgm:
        # Input 2: Background music
        final_cmd.extend(["-i", str(resolved_bgm_path)])
        print(f"[Renderer] Mixing BGM track: {resolved_bgm_path} at volume {bgm_volume:.2f}")

    # Build filter_complex for Video (ASS Subtitles) + Audio (Voiceover + BGM mix)
    filter_complex_parts = []
    
    # 1. Video Filter: ASS subtitles if present
    if ass_subtitle_path and os.path.exists(ass_subtitle_path):
        escaped_ass = str(Path(ass_subtitle_path).resolve()).replace("\\", "/").replace(":", "\\:")
        filter_complex_parts.append(f"[0:v]ass='{escaped_ass}'[vout]")
        video_map_label = "[vout]"
    else:
        video_map_label = "0:v:0"

    # 2. Audio Filter: Mix voiceover (100%) + BGM (10%)
    if has_bgm:
        # Loop BGM seamlessly, duck to bgm_volume (10%), mix with voiceover
        audio_filter = (
            f"[1:a]volume=1.0[vo];"
            f"[2:a]aloop=loop=-1:size=2e+09,volume={bgm_volume:.2f}[bgm];"
            f"[vo][bgm]amix=inputs=2:duration=first:dropout_transition=2[aout]"
        )
        filter_complex_parts.append(audio_filter)
        audio_map_label = "[aout]"
    else:
        # Simple voiceover stream mapping
        audio_map_label = "1:a:0"

    if filter_complex_parts:
        final_cmd.extend(["-filter_complex", ";".join(filter_complex_parts)])
        final_cmd.extend(["-map", video_map_label, "-map", audio_map_label])
    else:
        final_cmd.extend(["-map", "0:v:0", "-map", "1:a:0"])

    final_cmd.extend([
        "-c:v", encoder,
        *encoder_args,
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        str(final_output_path)
    ])

    try:
        subprocess.run(final_cmd, capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as e:
        print(f"[Renderer] Render with {encoder} failed: {e.stderr}. Retrying with CPU libx264...")
        # Fallback to CPU libx264
        cpu_cmd = [
            ffmpeg_exe, "-y",
            "-i", str(stitched_video),
            "-i", str(resolved_audio_path)
        ]
        if has_bgm:
            cpu_cmd.extend(["-i", str(resolved_bgm_path)])
        if filter_complex_parts:
            cpu_cmd.extend(["-filter_complex", ";".join(filter_complex_parts)])
            cpu_cmd.extend(["-map", video_map_label, "-map", audio_map_label])
        else:
            cpu_cmd.extend(["-map", "0:v:0", "-map", "1:a:0"])

        cpu_cmd.extend([
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-crf", "20",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", "192k",
            "-shortest",
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


def _check_nvenc_available(ffmpeg_exe: str) -> bool:
    """Quickly probes if NVIDIA NVENC is operational on this system."""
    try:
        test_cmd = [
            ffmpeg_exe, "-f", "lavfi", "-i", "nullsrc=s=64x64:d=0.1",
            "-c:v", "h264_nvenc", "-f", "null", "-"
        ]
        res = subprocess.run(test_cmd, capture_output=True)
        return res.returncode == 0
    except Exception:
        return False


def _render_xfade_single(ffmpeg_exe, seg_files, valid_clips, transition, trans_dur, output_path):
    """Single-pass xfade for <=15 clips. Supports 'random' transition mode."""
    xfade_cmd = [ffmpeg_exe, "-y"]
    for seg in seg_files:
        xfade_cmd.extend(["-i", str(seg)])

    filter_chains = []
    cum_offset = 0.0
    for i in range(len(valid_clips) - 1):
        dur_i = valid_clips[i][2]
        cum_offset += dur_i
        trans_offset = max(0.01, cum_offset - (trans_dur / 2.0))

        # Pick transition type (random or fixed)
        trans_type = _pick_transition(i, transition)

        in_label = "[0:v]" if i == 0 else f"[v{i}]"
        next_label = f"[{i+1}:v]"
        out_label = f"[v{i+1}]"

        filter_chains.append(
            f"{in_label}{next_label}xfade=transition={trans_type}:duration={trans_dur:.2f}:offset={trans_offset:.2f}{out_label}"
        )

    final_filter = ";".join(filter_chains)
    last_out = f"[v{len(valid_clips)-1}]"

    xfade_cmd.extend([
        "-filter_complex", final_filter,
        "-map", last_out,
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-crf", "18",
        "-pix_fmt", "yuv420p",
        "-an",
        str(output_path)
    ])
    subprocess.run(xfade_cmd, capture_output=True, check=True)


def _render_xfade_batches(ffmpeg_exe, seg_files, valid_clips, transition, trans_dur, seg_dir, batch_size=15):
    """
    2-pass xfade for large scene counts (>15 clips).
    Splits clips into batches, renders each batch with xfade transitions,
    then returns list of batch output files for final concatenation.
    This prevents massive filtergraphs that exhaust RAM on weaker machines.
    """
    batch_outputs = []
    total = len(valid_clips)

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
            trans_offset = max(0.01, cum_offset - (trans_dur / 2.0))

            trans_type = _pick_transition(batch_start + i, transition)

            in_label = "[0:v]" if i == 0 else f"[v{i}]"
            next_label = f"[{i+1}:v]"
            out_label = f"[v{i+1}]"

            filter_chains.append(
                f"{in_label}{next_label}xfade=transition={trans_type}:duration={trans_dur:.2f}:offset={trans_offset:.2f}{out_label}"
            )

        final_filter = ";".join(filter_chains)
        last_out = f"[v{len(batch_clips)-1}]"

        xfade_cmd.extend([
            "-filter_complex", final_filter,
            "-map", last_out,
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-crf", "18",
            "-pix_fmt", "yuv420p",
            "-an",
            str(batch_out)
        ])

        try:
            subprocess.run(xfade_cmd, capture_output=True, check=True)
            batch_outputs.append(batch_out)
            print(f"[Renderer] Batch {batch_start}-{batch_end} rendered with xfade transitions")
        except subprocess.CalledProcessError as e:
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
