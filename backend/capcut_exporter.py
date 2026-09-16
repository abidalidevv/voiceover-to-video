import os
import json
import time
import uuid
import shutil
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional
from .config import DATA_DIR, load_settings


def get_capcut_drafts_dir() -> Path:
    """Returns the default or user-configured CapCut PC drafts directory."""
    settings = load_settings()
    custom_dir = settings.get("capcut_drafts_dir")
    if custom_dir and Path(custom_dir).exists():
        return Path(custom_dir)

    # Standard Windows CapCut PC location
    local_appdata = os.environ.get("LOCALAPPDATA", "")
    if local_appdata:
        standard_path = Path(local_appdata) / "CapCut" / "User Data" / "Projects" / "com.lveditor.draft"
        try:
            standard_path.mkdir(parents=True, exist_ok=True)
            return standard_path
        except Exception:
            pass

    # Fallback to internal data directory
    fallback = DATA_DIR / "capcut_drafts"
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback


def find_capcut_executable() -> Optional[str]:
    """Finds CapCut.exe on the Windows system."""
    settings = load_settings()
    custom_exe = settings.get("capcut_exe_path")
    if custom_exe and Path(custom_exe).exists():
        return custom_exe

    # Check which
    which_path = shutil.which("CapCut.exe") or shutil.which("CapCut")
    if which_path:
        return which_path

    # Check local appdata apps
    local_appdata = os.environ.get("LOCALAPPDATA", "")
    if local_appdata:
        capcut_apps = Path(local_appdata) / "CapCut" / "Apps"
        if capcut_apps.exists():
            # Find version folder with CapCut.exe
            for p in sorted(capcut_apps.glob("*/CapCut.exe"), reverse=True):
                if p.exists():
                    return str(p)

    # Common Program Files paths
    common_locations = [
        Path("C:/Program Files/CapCut/CapCut.exe"),
        Path("C:/Program Files (x86)/CapCut/CapCut.exe"),
        Path(local_appdata) / "CapCut" / "CapCut.exe",
    ]
    for loc in common_locations:
        if loc.exists():
            return str(loc)

    return None


def export_project_to_capcut(project_data: Dict[str, Any], custom_options: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Creates a full CapCut PC project folder containing draft_content.json and draft_meta_info.json.
    Places video clips, voiceover audio, and subtitle texts onto the timeline.
    """
    drafts_root = get_capcut_drafts_dir()
    project_title = project_data.get("name", "VideoGen_Project")
    # Clean project folder name
    safe_name = "".join([c if c.isalnum() or c in " _-" else "_" for c in project_title]).strip()
    folder_name = f"{safe_name}_{int(time.time())}"
    project_dir = drafts_root / folder_name
    project_dir.mkdir(parents=True, exist_ok=True)

    scenes = project_data.get("scenes", [])
    audio_path = project_data.get("audio_path") or ""
    total_duration_sec = float(project_data.get("duration", 30.0))
    total_duration_us = int(total_duration_sec * 1_000_000)

    # CapCut Materials lists
    materials_videos = []
    materials_audios = []
    materials_texts = []
    materials_speeds = []

    # Default speed object
    speed_id = str(uuid.uuid4()).upper()
    materials_speeds.append({
        "curve_speed": None,
        "id": speed_id,
        "mode": 0,
        "speed": 1.0,
        "type": "speed"
    })

    # 1. Voiceover Audio Material & Track
    audio_material_id = str(uuid.uuid4()).upper()
    audio_abs_path = str(Path(audio_path).resolve()) if audio_path else ""
    materials_audios.append({
        "app_id": 0,
        "category_id": "",
        "category_name": "",
        "check_flag": 1,
        "duration": total_duration_us,
        "extra_info": "",
        "file_Path": audio_abs_path,
        "id": audio_material_id,
        "intensifies_audio_path": "",
        "is_ai_clone_tone": False,
        "is_text_edit": False,
        "music_id": str(uuid.uuid4()).upper(),
        "name": Path(audio_path).name if audio_path else "voiceover.mp3",
        "path": audio_abs_path,
        "source_platform": 0,
        "team_id": "",
        "type": "extract_music",
        "video_id": ""
    })

    audio_segment = {
        "caption_info": None,
        "clip": None,
        "common_keyframes": [],
        "enable_adjust": True,
        "enable_color_curves": True,
        "enable_color_match_adjust": False,
        "enable_color_wheels": True,
        "enable_lut": True,
        "enable_smart_color_adjust": False,
        "extra_material_refs": [speed_id],
        "group_id": "",
        "hdr_settings": None,
        "id": str(uuid.uuid4()).upper(),
        "intensifies_audio": None,
        "is_placeholder": False,
        "is_tone_modify": False,
        "keyframe_refs": [],
        "last_nonzero_volume": 1.0,
        "material_id": audio_material_id,
        "render_index": 0,
        "responsive_layout": {"enable": False},
        "reverse": False,
        "source_timerange": {"duration": total_duration_us, "start": 0},
        "speed": 1.0,
        "target_timerange": {"duration": total_duration_us, "start": 0},
        "template_id": "",
        "track_attribute": 0,
        "track_render_index": 0,
        "visible": True,
        "volume": 1.0
    }

    # 2. Video Clips Materials & Track
    video_segments = []
    current_timeline_us = 0

    for sc in scenes:
        clip = sc.get("video_clip", {})
        clip_path = clip.get("file_path") if clip else None
        sc_dur_sec = float(sc.get("duration", 4.0))
        sc_dur_us = int(sc_dur_sec * 1_000_000)

        if clip_path and Path(clip_path).exists():
            v_abs_path = str(Path(clip_path).resolve())
            v_mat_id = str(uuid.uuid4()).upper()

            materials_videos.append({
                "aigc_type": "none",
                "audio_fade": None,
                "category_id": "",
                "category_name": "",
                "check_flag": 63487,
                "crop": {"lower_left_x": 0.0, "lower_left_y": 1.0, "lower_right_x": 1.0, "lower_right_y": 1.0, "upper_left_x": 0.0, "upper_left_y": 0.0, "upper_right_x": 1.0, "upper_right_y": 0.0},
                "crop_ratio": "free",
                "crop_scale": 1.0,
                "duration": sc_dur_us + 1_000_000,
                "extra_info": "",
                "file_Path": v_abs_path,
                "height": 1080,
                "id": v_mat_id,
                "material_name": Path(clip_path).name,
                "path": v_abs_path,
                "type": "video",
                "width": 1920
            })

            v_seg = {
                "cartoon": False,
                "clip": {"alpha": 1.0, "flip": {"horizontal": False, "vertical": False}, "rotation": 0.0, "scale": {"x": 1.0, "y": 1.0}, "transform": {"x": 0.0, "y": 0.0}},
                "common_keyframes": [],
                "enable_adjust": True,
                "enable_color_curves": True,
                "enable_color_match_adjust": False,
                "enable_color_wheels": True,
                "enable_lut": True,
                "enable_smart_color_adjust": False,
                "extra_material_refs": [speed_id],
                "group_id": "",
                "hdr_settings": None,
                "id": str(uuid.uuid4()).upper(),
                "intensifies_audio": None,
                "is_placeholder": False,
                "is_tone_modify": False,
                "keyframe_refs": [],
                "last_nonzero_volume": 1.0,
                "material_id": v_mat_id,
                "render_index": 0,
                "responsive_layout": {"enable": False},
                "reverse": False,
                "source_timerange": {"duration": sc_dur_us, "start": 0},
                "speed": 1.0,
                "target_timerange": {"duration": sc_dur_us, "start": current_timeline_us},
                "template_id": "",
                "track_attribute": 0,
                "track_render_index": 0,
                "visible": True,
                "volume": 0.0  # Stock B-roll muted so voiceover is clear
            }
            video_segments.append(v_seg)

        current_timeline_us += sc_dur_us

    # 3. Subtitle / Text Track & Materials
    text_segments = []
    font_name = (custom_options.get("font_name") if custom_options else None) or "Montserrat"
    font_size = (custom_options.get("font_size") if custom_options else None) or 24
    primary_color = (custom_options.get("primary_color") if custom_options else None) or "#FFFFFF"
    highlight_color = (custom_options.get("highlight_color") if custom_options else None) or "#FFE010"

    for sc in scenes:
        words = sc.get("words", [])
        if words:
            # Group into small readable phrases
            for i in range(0, len(words), 4):
                phrase_words = words[i:i+4]
                t_start = int(float(phrase_words[0]["start"]) * 1_000_000)
                t_end = int(float(phrase_words[-1]["end"]) * 1_000_000)
                phrase_dur = max(300_000, t_end - t_start)
                phrase_text = " ".join([w.get("word", "") for w in phrase_words]).strip().upper()

                t_mat_id = str(uuid.uuid4()).upper()
                text_content_obj = {
                    "styles": [
                        {
                            "fill": {"alpha": 1.0, "content": {"render_type": "solid", "solid": {"color": [1.0, 1.0, 1.0]}}},
                            "font": {"id": "", "path": "", "title": font_name},
                            "range": [0, len(phrase_text)],
                            "size": float(font_size) / 2.5
                        }
                    ],
                    "text": phrase_text
                }

                materials_texts.append({
                    "alignment": 1,
                    "background_alpha": 1.0,
                    "background_color": "",
                    "background_height": 0.14,
                    "background_horizontal_offset": 0.0,
                    "background_round_radius": 0.0,
                    "background_style": 0,
                    "background_vertical_offset": 0.0,
                    "background_width": 0.14,
                    "bold_width": 0.0,
                    "border_color": "#000000",
                    "border_width": 0.08,
                    "check_flag": 7,
                    "content": json.dumps(text_content_obj, ensure_ascii=False),
                    "font_category_id": "",
                    "font_category_name": "",
                    "font_id": "",
                    "font_name": font_name,
                    "font_path": "",
                    "font_resource_id": "",
                    "font_size": float(font_size) / 2.5,
                    "font_source_platform": 0,
                    "font_team_id": "",
                    "font_title": font_name,
                    "font_url": "",
                    "fonts": [],
                    "has_shadow": True,
                    "id": t_mat_id,
                    "initial_scale": 1.0,
                    "inner_padding": 0.0,
                    "is_rich_text": False,
                    "italic_degree": 0,
                    "ktv_color": "",
                    "language": "",
                    "layer_weight": 1,
                    "letter_spacing": 0.0,
                    "line_feed": 1,
                    "line_spacing": 0.02,
                    "name": "",
                    "original_size": [],
                    "preset_category": "",
                    "preset_category_id": "",
                    "preset_has_set_marker": False,
                    "preset_id": "",
                    "preset_index": 0,
                    "preset_name": "",
                    "recognize_type": 0,
                    "shadow_alpha": 0.8,
                    "shadow_angle": -45.0,
                    "shadow_color": "#000000",
                    "shadow_distance": 8.0,
                    "shadow_point": {"x": 5.0, "y": -5.0},
                    "shadow_smoothing": 1.0,
                    "shape_clip_x": False,
                    "shape_clip_y": False,
                    "style_name": "",
                    "sub_type": 0,
                    "text_alpha": 1.0,
                    "text_color": primary_color,
                    "text_size": 30,
                    "text_to_audio_ids": [],
                    "typesetting": 0,
                    "underline": False,
                    "use_effect_default_color": False,
                    "words": {"has_shadow": False, "text_color": ""}
                })

                text_segments.append({
                    "caption_info": None,
                    "clip": {"alpha": 1.0, "flip": {"horizontal": False, "vertical": False}, "rotation": 0.0, "scale": {"x": 1.0, "y": 1.0}, "transform": {"x": 0.0, "y": -0.65}},
                    "common_keyframes": [],
                    "enable_adjust": True,
                    "enable_color_curves": True,
                    "enable_color_match_adjust": False,
                    "enable_color_wheels": True,
                    "enable_lut": True,
                    "enable_smart_color_adjust": False,
                    "extra_material_refs": [],
                    "group_id": "",
                    "hdr_settings": None,
                    "id": str(uuid.uuid4()).upper(),
                    "intensifies_audio": None,
                    "is_placeholder": False,
                    "is_tone_modify": False,
                    "keyframe_refs": [],
                    "last_nonzero_volume": 1.0,
                    "material_id": t_mat_id,
                    "render_index": 0,
                    "responsive_layout": {"enable": False},
                    "reverse": False,
                    "source_timerange": None,
                    "speed": 1.0,
                    "target_timerange": {"duration": phrase_dur, "start": t_start},
                    "template_id": "",
                    "track_attribute": 0,
                    "track_render_index": 0,
                    "visible": True,
                    "volume": 1.0
                })
        else:
            # Whole scene fallback
            t_start = int(float(sc.get("start", 0)) * 1_000_000)
            t_dur = int(float(sc.get("duration", 4.0)) * 1_000_000)
            raw_text = sc.get("text", "").strip().upper()
            if raw_text:
                t_mat_id = str(uuid.uuid4()).upper()
                materials_texts.append({
                    "id": t_mat_id,
                    "font_title": font_name,
                    "font_name": font_name,
                    "text_color": primary_color,
                    "content": json.dumps({"styles": [], "text": raw_text}),
                    "font_size": 24.0,
                    "border_color": "#000000",
                    "border_width": 0.08
                })
                text_segments.append({
                    "id": str(uuid.uuid4()).upper(),
                    "material_id": t_mat_id,
                    "target_timerange": {"duration": t_dur, "start": t_start},
                    "clip": {"transform": {"x": 0.0, "y": -0.65}},
                    "visible": True
                })

    # Assemble tracks
    tracks = [
        # Track 0: Video clips
        {
            "attribute": 0,
            "flag": 0,
            "id": str(uuid.uuid4()).upper(),
            "is_default_name": True,
            "name": "Video Track",
            "segments": video_segments,
            "type": "video"
        },
        # Track 1: Subtitle Text Track
        {
            "attribute": 0,
            "flag": 0,
            "id": str(uuid.uuid4()).upper(),
            "is_default_name": True,
            "name": "Subtitles",
            "segments": text_segments,
            "type": "text"
        },
        # Track 2: Voiceover Audio Track
        {
            "attribute": 0,
            "flag": 0,
            "id": str(uuid.uuid4()).upper(),
            "is_default_name": True,
            "name": "Voiceover Audio",
            "segments": [audio_segment],
            "type": "audio"
        }
    ]

    # Full draft_content.json structure
    draft_content = {
        "canvas_config": {
            "height": 1080,
            "ratio": "original",
            "width": 1920
        },
        "color_space": 0,
        "config": {
            "adjust_max_index": 1,
            "attachment_info": [],
            "combination_max_index": 1,
            "export_range": None,
            "extract_audio_last_index": 1,
            "lyrics_recognition_id": "",
            "lyrics_sync": True,
            "lyrics_taskinfo": [],
            "maintrack_adsorb": True,
            "material_save_mode": 0,
            "original_sound_last_index": 1,
            "record_audio_last_index": 1,
            "sticker_max_index": 1,
            "subtitle_keywords_config": None,
            "subtitle_recognition_id": "",
            "subtitle_sync": True,
            "subtitle_taskinfo": [],
            "system_font_list": [],
            "video_mute": False,
            "zoom_info_params": None
        },
        "cover": None,
        "create_time": int(time.time() * 1_000_000),
        "duration": max(total_duration_us, current_timeline_us),
        "extra_info": None,
        "fps": 30.0,
        "free_render_index_mode_on": False,
        "group_container": None,
        "id": str(uuid.uuid4()).upper(),
        "keyframe_graph_list": [],
        "keyframes": {"adjusts": [], "audios": [], "effects": [], "filters": [], "handwrites": [], "stickers": [], "texts": [], "videos": []},
        "last_modified_platform": {"app_id": 3704, "app_source": "ea", "app_version": "3.5.0", "device_id": "windows", "hard_disk_id": "", "mac_address": "", "os": "windows", "os_version": "10.0.19045"},
        "materials": {
            "audio_balances": [],
            "audio_effects": [],
            "audio_fades": [],
            "audio_track_indexes": [],
            "audios": materials_audios,
            "beats": [],
            "canvases": [],
            "chromas": [],
            "color_curves": [],
            "drafts": [],
            "effects": [],
            "flowers": [],
            "green_screens": [],
            "handwrites": [],
            "hsl": [],
            "images": [],
            "log_color_wheels": [],
            "loudnesses": [],
            "manual_deformations": [],
            "masks": [],
            "material_animations": [],
            "material_colors": [],
            "placeholders": [],
            "plugin_effects": [],
            "primary_color_wheels": [],
            "realtime_denoises": [],
            "shapes": [],
            "smart_crops": [],
            "sound_channel_mappings": [],
            "speeds": materials_speeds,
            "stickers": [],
            "tail_leaders": [],
            "text_templates": [],
            "texts": materials_texts,
            "time_marks": [],
            "transitions": [],
            "video_effects": [],
            "video_track_indexes": [],
            "videos": materials_videos,
            "vocal_beautifys": [],
            "vocal_separations": []
        },
        "mutable_config": None,
        "name": folder_name,
        "new_version": "100.0.0",
        "relationships": [],
        "render_index_mode": "default",
        "retouch_cover": None,
        "source": "default",
        "static_cover_image_path": "",
        "tracks": tracks,
        "update_time": int(time.time() * 1_000_000),
        "version": 360000
    }

    # Full draft_meta_info.json structure
    draft_meta_info = {
        "draft_cloud_capcut_id": "",
        "draft_cloud_last_action_download": False,
        "draft_cloud_materials": [],
        "draft_cloud_purchase_info": [],
        "draft_cloud_template_id": "",
        "draft_cloud_tutorial_info": "",
        "draft_cloud_videocut_purchase_info": [],
        "draft_cover": "",
        "draft_fold_path": str(project_dir.resolve()),
        "draft_id": str(uuid.uuid4()).upper(),
        "draft_is_ai_shorts": False,
        "draft_is_invisible": False,
        "draft_materials": [],
        "draft_materials_copied_info": [],
        "draft_name": folder_name,
        "draft_new_version": "",
        "draft_removable": False,
        "draft_root_path": str(drafts_root.resolve()),
        "draft_segment_extra_info": [],
        "draft_timeline_materials_size_": 0,
        "tm_draft_cloud_completed": "",
        "tm_draft_cloud_modified": 0,
        "tm_draft_create": int(time.time() * 1_000_000),
        "tm_draft_modified": int(time.time() * 1_000_000),
        "tm_draft_removed": 0,
        "tm_duration": max(total_duration_us, current_timeline_us)
    }

    # Write files
    content_file = project_dir / "draft_content.json"
    meta_file = project_dir / "draft_meta_info.json"

    with open(content_file, "w", encoding="utf-8") as f:
        json.dump(draft_content, f, indent=2, ensure_ascii=False)

    with open(meta_file, "w", encoding="utf-8") as f:
        json.dump(draft_meta_info, f, indent=2, ensure_ascii=False)

    # Launch CapCut if installed
    capcut_exe = find_capcut_executable()
    launched = False
    if capcut_exe:
        try:
            subprocess.Popen([capcut_exe])
            launched = True
        except Exception as e:
            print(f"[CapCutExporter] Error launching CapCut.exe: {e}")

    # Open folder in Windows Explorer
    try:
        os.startfile(str(project_dir.resolve()))
    except Exception:
        subprocess.Popen(f'explorer "{project_dir.resolve()}"', shell=True)

    return {
        "status": "success",
        "folder_name": folder_name,
        "project_dir": str(project_dir.resolve()),
        "capcut_exe": capcut_exe,
        "launched": launched,
        "scenes_count": len(video_segments),
        "subtitles_count": len(text_segments)
    }
