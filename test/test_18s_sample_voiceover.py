import os
import sys
import json
import time
import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from backend.config import DATA_DIR, SFX_DIR, find_ffmpeg
from backend.scene_analyzer import (
    _apply_callouts_prioritization,
    _match_emphasis_words_with_timestamps
)
from backend.subtitle_generator import generate_ass_subtitles
from backend.video_renderer import render_final_video
from backend.templates import get_template

def run_18s_sample_voiceover_test():
    print("=" * 70)
    print("RUNNING 18-SECOND SAMPLE VOICEOVER TEST WITH ALL 3 EDITING EFFECTS")
    print("=" * 70)

    ffmpeg = find_ffmpeg()
    temp_dir = DATA_DIR / "temp" / "test_18s_sample"
    temp_dir.mkdir(parents=True, exist_ok=True)

    # 1. Create an 18-second synthetic voiceover audio with tones indicating speech segments
    audio_path = temp_dir / "sample_voiceover_18s.mp3"
    print(f"\n[1] Generating 18.0s synthetic voiceover at: {audio_path}")
    # 4 distinct segments (4.5s each)
    subprocess.run([
        ffmpeg, "-y",
        "-f", "lavfi", "-i", "sine=frequency=320:duration=18.0",
        "-af", "volume=0.8",
        "-c:a", "libmp3lame", "-b:a", "192k",
        str(audio_path)
    ], capture_output=True, check=True)

    # 2. Create 4 video clips (4.5s each)
    clip_colors = ["navy", "darkgreen", "maroon", "indigo"]
    clip_paths = []
    for i, color in enumerate(clip_colors):
        cp = temp_dir / f"clip_{i}_{color}.mp4"
        print(f"[2.{i+1}] Creating sample clip: {cp.name} (4.5s, 1920x1080)")
        subprocess.run([
            ffmpeg, "-y",
            "-f", "lavfi", "-i", f"color=c={color}:s=1920x1080:d=4.5:r=30",
            "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
            str(cp)
        ], capture_output=True, check=True)
        clip_paths.append(str(cp))

    # 3. Construct 4 scenes spanning the 18 seconds (4.5s each)
    # Scene 0: 0.0 - 4.5s (intro)
    # Scene 1: 4.5 - 9.0s (statistic, callout candidate)
    # Scene 2: 9.0 - 13.5s (climax scene with emphasis punch zoom in the middle at rel_start 2.0s)
    # Scene 3: 13.5 - 18.0s (conclusion)
    scenes = [
        {
            "id": 0,
            "scene_number": 1,
            "start": 0.0,
            "end": 4.5,
            "duration": 4.5,
            "text": "Every single entrepreneur wants to build something extraordinary.",
            "raw_callout_text": "START EXTRAORDINARY",
            "emphasis_word": "extraordinary",
            "is_climax": False,
            "words": [
                {"word": "Every", "start": 0.2, "end": 0.6},
                {"word": "single", "start": 0.7, "end": 1.1},
                {"word": "entrepreneur", "start": 1.2, "end": 2.0},
                {"word": "wants", "start": 2.1, "end": 2.5},
                {"word": "something", "start": 2.6, "end": 3.2},
                {"word": "extraordinary.", "start": 3.3, "end": 4.3}  # 4.3 is 0.2s from 4.5 -> will skip boundary
            ],
            "video_clip": {"file_path": clip_paths[0]}
        },
        {
            "id": 1,
            "scene_number": 2,
            "start": 4.5,
            "end": 9.0,
            "duration": 4.5,
            "text": "Yet over 90 percent of startups fail within the first two years.",
            "raw_callout_text": "90% OF STARTUPS FAIL",
            "emphasis_word": "fail",
            "is_climax": False,
            "words": [
                {"word": "Yet", "start": 4.7, "end": 5.0},
                {"word": "over", "start": 5.1, "end": 5.4},
                {"word": "90", "start": 5.5, "end": 5.9},
                {"word": "percent", "start": 6.0, "end": 6.5},
                {"word": "of", "start": 6.6, "end": 6.8},
                {"word": "startups", "start": 6.9, "end": 7.4},
                {"word": "fail", "start": 7.5, "end": 8.0},
                {"word": "early.", "start": 8.1, "end": 8.6}
            ],
            "video_clip": {"file_path": clip_paths[1]}
        },
        {
            "id": 2,
            "scene_number": 3,
            "start": 9.0,
            "end": 13.5,
            "duration": 4.5,
            "text": "The one critical truth you need to understand is relentless execution.",
            "raw_callout_text": "CRITICAL TRUTH: EXECUTE",
            "emphasis_word": "relentless",
            "is_climax": True,  # Climax scene
            "words": [
                {"word": "The", "start": 9.2, "end": 9.4},
                {"word": "one", "start": 9.5, "end": 9.7},
                {"word": "critical", "start": 9.8, "end": 10.3},
                {"word": "truth", "start": 10.4, "end": 10.9},
                {"word": "you", "start": 11.0, "end": 11.2},
                # 'relentless' word at 11.3 - 12.0. Relative to scene start (9.0): rel_start = 2.3s, rel_end = 3.0s.
                # Distance to scene start: 2.3s >= 0.3s. Distance to scene end: 4.5 - 3.0 = 1.5s >= 0.3s.
                # Boundary check passes cleanly!
                {"word": "relentless", "start": 11.3, "end": 12.0},
                {"word": "execution.", "start": 12.1, "end": 13.0}
            ],
            "video_clip": {"file_path": clip_paths[2]}
        },
        {
            "id": 3,
            "scene_number": 4,
            "start": 13.5,
            "end": 18.0,
            "duration": 4.5,
            "text": "Master this today and your results will compound forever.",
            "raw_callout_text": None,
            "emphasis_word": "forever",
            "is_climax": False,
            "words": [
                {"word": "Master", "start": 13.7, "end": 14.1},
                {"word": "this", "start": 14.2, "end": 14.5},
                {"word": "today", "start": 14.6, "end": 15.2},
                {"word": "and", "start": 15.3, "end": 15.5},
                {"word": "compound", "start": 15.6, "end": 16.5},
                {"word": "forever.", "start": 16.6, "end": 17.5}
            ],
            "video_clip": {"file_path": clip_paths[3]}
        }
    ]

    # 4. Run Phase 1 rate-limiting and prioritization
    print("\n[3] Testing Callout Prioritization & Rate Limiting (4 scenes -> exactly 1 callout allowed)...")
    _apply_callouts_prioritization(scenes)
    callout_scenes = [sc for sc in scenes if sc.get("callout_text")]
    print(f"Total Callouts Allowed: {len(callout_scenes)}")
    for sc in callout_scenes:
        print(f"  -> Scene #{sc['scene_number']} (is_climax={sc.get('is_climax')}): \"{sc['callout_text']}\"")
    assert len(callout_scenes) == 1, f"Expected 1 callout for 4 scenes, got {len(callout_scenes)}"
    assert scenes[2]["callout_text"] == "CRITICAL TRUTH: EXECUTE", "Climax scene must be prioritized for callout!"

    # 5. Run Phase 3 emphasis zoom matching and boundary checks
    print("\n[4] Testing Emphasis Zoom Timestamp Matching & Boundary Conflict Guard...")
    _match_emphasis_words_with_timestamps(scenes)
    for sc in scenes:
        print(f"  -> Scene #{sc['scene_number']} word='{sc.get('emphasis_word')}': rel_start={sc.get('emphasis_rel_start')}, rel_end={sc.get('emphasis_rel_end')}, skip_zoom={sc.get('skip_emphasis_zoom')}")

    # Scene 2 should NOT skip punch zoom
    assert scenes[2]["skip_emphasis_zoom"] is False, "Scene 2 middle word should have punch zoom enabled"
    # Scene 0 should skip punch zoom because 'extraordinary' is within 0.2s of scene end (boundary conflict)
    assert scenes[0]["skip_emphasis_zoom"] is True, "Scene 0 word too close to boundary must be skipped"

    # 6. Generate ASS subtitles with Callout badge
    ass_path = temp_dir / "sample_18s_subtitles.ass"
    print(f"\n[5] Generating ASS subtitles with Callout badge: {ass_path}")
    generate_ass_subtitles(
        scenes=scenes,
        output_path=str(ass_path),
        preset_key="capcut_yellow",
        custom_options={
            "callouts_enabled": True,
            "callout_style": "badge_yellow"
        }
    )
    ass_content = ass_path.read_text(encoding="utf-8")
    assert "Style: Callout," in ass_content, "Callout style missing in ASS file"
    assert "CRITICAL TRUTH: EXECUTE" in ass_content, "Callout text missing in ASS file"
    print("✅ ASS Subtitles correctly injected Callout Style and Dialogue line!")

    # 7. Render full 18-second video with Phase 1, Phase 2, and Phase 3 active
    out_filename = "sample_voiceover_18s_rendered.mp4"
    print(f"\n[6] Rendering 18-second video with all 3 effects active...")
    print("  - Phase 1: Text Callout badge enabled")
    print("  - Phase 2: Sound Stings at scene boundaries (whoosh_soft.mp3, vol 0.40)")
    print("  - Phase 3: Emphasis Punch Zoom (1.15x intensity) on Scene 3 'relentless'")
    print("  - Transitions: smoothleft xfade across the 4 clips")
    print("  - BGM: cinematic_ambient.mp3 ducked")

    out_rendered = render_final_video(
        audio_path=str(audio_path),
        scenes=scenes,
        ass_subtitle_path=str(ass_path),
        output_filename=out_filename,
        custom_options={
            "fps": 30,
            "enable_motion": True,
            "transition": "smoothleft",
            "transition_mode": "fixed",
            "transition_duration": 0.30,
            "bgm_track": "cinematic_ambient.mp3",
            "bgm_volume": 0.10,
            "transition_sfx": "whoosh_soft.mp3",
            "transition_sfx_volume": 0.40,
            "emphasis_zoom_enabled": True,
            "emphasis_zoom_intensity": 1.15
        }
    )

    rendered_file = Path(out_rendered)
    print(f"\n[7] Verifying rendered file: {rendered_file}")
    assert rendered_file.exists(), "Rendered MP4 file must exist"
    size_mb = rendered_file.stat().st_size / (1024 * 1024)
    print(f"  -> File size: {size_mb:.2f} MB")
    assert size_mb > 0.5, "Rendered MP4 should be at least 0.5 MB"

    # Probe duration and streams
    probe_cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration:stream=codec_type,width,height",
        "-of", "json",
        str(rendered_file)
    ]
    probe_res = subprocess.run(probe_cmd, capture_output=True, text=True, check=True)
    info = json.loads(probe_res.stdout)
    duration = float(info["format"]["duration"])
    streams = info["streams"]
    v_streams = [s for s in streams if s["codec_type"] == "video"]
    a_streams = [s for s in streams if s["codec_type"] == "audio"]

    print(f"  -> Probed Duration: {duration:.2f}s (expected ~18.0s)")
    print(f"  -> Video Streams: {len(v_streams)} ({v_streams[0]['width']}x{v_streams[0]['height']})")
    print(f"  -> Audio Streams: {len(a_streams)}")

    assert abs(duration - 18.0) < 1.0, f"Expected duration close to 18.0s, got {duration:.2f}s"
    assert len(v_streams) == 1, "Must have exactly 1 video stream"
    assert len(a_streams) == 1, "Must have exactly 1 audio stream"
    assert v_streams[0]["width"] == 1920 and v_streams[0]["height"] == 1080

    print("\n" + "=" * 70)
    print("✅ 18-SECOND SAMPLE VOICEOVER TEST PASSED WITH 100% SUCCESS!")
    print("=" * 70)

if __name__ == "__main__":
    run_18s_sample_voiceover_test()
