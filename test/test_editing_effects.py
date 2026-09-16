import os
import sys
import unittest
import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from backend.config import DATA_DIR, SFX_DIR, list_sfx_files, find_ffmpeg
from backend.scene_analyzer import (
    _enhance_tags_with_ai,
    _apply_callouts_prioritization,
    _match_emphasis_words_with_timestamps,
    build_scenes
)
from backend.subtitle_generator import (
    generate_ass_subtitles,
    CALLOUT_STYLES
)
from backend.templates import EDITING_TEMPLATES, get_template
from backend.video_renderer import (
    _resolve_sfx_path,
    render_final_video
)


class TestPhase1TextCallouts(unittest.TestCase):

    def test_callout_styles_presets(self):
        self.assertIn("badge_yellow", CALLOUT_STYLES)
        self.assertIn("badge_cyan", CALLOUT_STYLES)
        self.assertIn("badge_dark", CALLOUT_STYLES)

        for key, style in CALLOUT_STYLES.items():
            self.assertEqual(style["alignment"], 8, f"Style {key} must be top center alignment 8")
            self.assertEqual(style["border_style"], 3, f"Style {key} must have border_style 3 (opaque card)")
            self.assertIn("primary_color", style)
            self.assertIn("outline_color", style)
            self.assertIn("back_color", style)

    def test_templates_have_callout_fields(self):
        for tmpl_id, tmpl in EDITING_TEMPLATES.items():
            self.assertIn("callouts_enabled", tmpl, f"Template {tmpl_id} missing 'callouts_enabled'")
            self.assertIn("callout_style", tmpl, f"Template {tmpl_id} missing 'callout_style'")
            self.assertIn(tmpl["callout_style"], CALLOUT_STYLES, f"Template {tmpl_id} has invalid callout_style")

    def test_callouts_prioritization_and_rate_limiting(self):
        # 8 scenes: max_callouts = 8 // 4 = 2
        scenes = [
            {"id": 0, "text": "Intro sentence.", "is_climax": False, "raw_callout_text": "INTRO POINT"},
            {"id": 1, "text": "Normal claim.", "is_climax": False, "raw_callout_text": "CLAIM ONE"},
            {"id": 2, "text": "Another point.", "is_climax": False, "raw_callout_text": "POINT TWO"},
            {"id": 3, "text": "Statistic line with 95% certainty.", "is_climax": False, "raw_callout_text": "95% OF PEOPLE"},
            {"id": 4, "text": "Middle filler.", "is_climax": False, "raw_callout_text": None},
            {"id": 5, "text": "Climax sentence!", "is_climax": True, "raw_callout_text": "CLIMAX TRUTH"},
            {"id": 6, "text": "Wrap up sentence.", "is_climax": False, "raw_callout_text": "FINAL STEP"},
            {"id": 7, "text": "Outro sentence.", "is_climax": False, "raw_callout_text": None},
        ]

        _apply_callouts_prioritization(scenes)

        callout_scenes = [sc for sc in scenes if sc.get("callout_text")]
        # Exactly 2 callouts should be allowed (8 // 4)
        self.assertEqual(len(callout_scenes), 2)

        # Climax scene (index 5) MUST be prioritized and have callout_text
        self.assertTrue(scenes[5]["callout_text"] == "CLIMAX TRUTH")

        # The other selected should be the 95% stat (index 3) due to numeric boost
        self.assertTrue(scenes[3]["callout_text"] == "95% OF PEOPLE")

    def test_ass_file_callout_injection(self):
        scenes = [
            {"id": 0, "start": 0.0, "end": 3.0, "text": "First scene.", "callout_text": None, "words": []},
            {"id": 1, "start": 3.0, "end": 7.0, "text": "Second scene.", "callout_text": "99% PROVEN SUCCESS", "words": []},
            {"id": 2, "start": 7.0, "end": 10.0, "text": "Third scene.", "callout_text": None, "words": []}
        ]

        out_ass = Path(__file__).parent / "test_callout_sample.ass"
        try:
            # 1. With callouts enabled
            generate_ass_subtitles(
                scenes=scenes,
                output_path=str(out_ass),
                preset_key="capcut_yellow",
                custom_options={
                    "callouts_enabled": True,
                    "callout_style": "badge_yellow"
                }
            )
            content = out_ass.read_text(encoding="utf-8")

            # Check style
            self.assertIn("Style: Callout,", content)
            self.assertIn(",8,60,60,", content)  # Alignment 8

            # Check dialogue line
            self.assertIn("Dialogue: 1,0:00:03.00,0:00:07.00,Callout,,0,0,0,,{\\fad(180,180)", content)
            self.assertIn("99% PROVEN SUCCESS", content)

            # 2. With callouts disabled
            generate_ass_subtitles(
                scenes=scenes,
                output_path=str(out_ass),
                preset_key="capcut_yellow",
                custom_options={
                    "callouts_enabled": False
                }
            )
            content_disabled = out_ass.read_text(encoding="utf-8")
            self.assertNotIn("Callout,,0,0,0,,", content_disabled)

        finally:
            if out_ass.exists():
                out_ass.unlink()


class TestPhase2SoundStings(unittest.TestCase):

    def test_sfx_directory_and_files_exist(self):
        self.assertTrue(SFX_DIR.exists(), "data/sfx directory must exist")
        files = list_sfx_files()
        self.assertGreaterEqual(len(files), 4, "Must have at least 4 sound effect files")
        self.assertIn("whoosh_soft.mp3", files)
        self.assertIn("pop_punch.mp3", files)
        self.assertIn("click_modern.mp3", files)
        self.assertIn("ding_bell.mp3", files)

    def test_resolve_sfx_path(self):
        # Resolves filename with extension
        resolved = _resolve_sfx_path("whoosh_soft.mp3")
        self.assertIsNotNone(resolved)
        self.assertTrue(Path(resolved).exists())

        # Resolves filename without extension
        resolved_no_ext = _resolve_sfx_path("whoosh_soft")
        self.assertIsNotNone(resolved_no_ext)
        self.assertTrue(Path(resolved_no_ext).exists())

        # Null / empty / "none" returns None
        self.assertIsNone(_resolve_sfx_path(None))
        self.assertIsNone(_resolve_sfx_path(""))
        self.assertIsNone(_resolve_sfx_path("none"))
        self.assertIsNone(_resolve_sfx_path("non_existent_sfx.mp3"))

    def test_templates_have_sfx_fields(self):
        for tmpl_id, tmpl in EDITING_TEMPLATES.items():
            self.assertIn("transition_sfx", tmpl, f"Template {tmpl_id} missing 'transition_sfx'")
            self.assertIn("transition_sfx_volume", tmpl, f"Template {tmpl_id} missing 'transition_sfx_volume'")
            sfx = tmpl["transition_sfx"]
            if sfx is not None:
                self.assertTrue(_resolve_sfx_path(sfx) is not None, f"SFX '{sfx}' in template {tmpl_id} cannot be resolved")
            vol = tmpl["transition_sfx_volume"]
            self.assertIsInstance(vol, (float, int))
            self.assertGreater(vol, 0.0)


class TestPhase3EmphasisZoom(unittest.TestCase):

    def test_templates_have_emphasis_zoom_fields(self):
        for tmpl_id, tmpl in EDITING_TEMPLATES.items():
            self.assertIn("emphasis_zoom_enabled", tmpl, f"Template {tmpl_id} missing 'emphasis_zoom_enabled'")
            self.assertIn("emphasis_zoom_intensity", tmpl, f"Template {tmpl_id} missing 'emphasis_zoom_intensity'")
            self.assertIsInstance(tmpl["emphasis_zoom_enabled"], bool)
            intensity = tmpl["emphasis_zoom_intensity"]
            self.assertIsInstance(intensity, (float, int))
            self.assertGreaterEqual(intensity, 1.0)

    def test_emphasis_word_matching_and_boundary_guard(self):
        # Scene 1: Emphasis word in middle (start: 1.5, end: 2.0 within a 4.0s scene) -> Should NOT skip
        # Scene 2: Emphasis word near start (start: 0.1, end: 0.4 within a 4.0s scene) -> Must SKIP (<0.3s)
        # Scene 3: Emphasis word near end (start: 3.8, end: 4.0 within a 4.0s scene) -> Must SKIP (<0.3s)
        # Scene 4: Emphasis word not matching any word -> Should skip
        scenes = [
            {
                "id": 0,
                "start": 10.0,
                "end": 14.0,
                "duration": 4.0,
                "emphasis_word": "million",
                "words": [
                    {"word": "He", "start": 10.2, "end": 10.5},
                    {"word": "made", "start": 10.6, "end": 11.0},
                    {"word": "one", "start": 11.1, "end": 11.4},
                    {"word": "million", "start": 11.5, "end": 12.0},  # rel_start = 1.5, rel_end = 2.0 (>=0.3 from 0 and 4.0)
                    {"word": "dollars.", "start": 12.1, "end": 13.5}
                ]
            },
            {
                "id": 1,
                "start": 20.0,
                "end": 24.0,
                "duration": 4.0,
                "emphasis_word": "never",
                "words": [
                    {"word": "Never", "start": 20.1, "end": 20.25}, # rel_start = 0.1 (< 0.3s from start)
                    {"word": "give", "start": 20.3, "end": 21.0},
                    {"word": "up.", "start": 21.1, "end": 22.0}
                ]
            },
            {
                "id": 2,
                "start": 30.0,
                "end": 34.0,
                "duration": 4.0,
                "emphasis_word": "stop",
                "words": [
                    {"word": "Do", "start": 30.5, "end": 31.0},
                    {"word": "not", "start": 31.1, "end": 32.0},
                    {"word": "stop!", "start": 33.8, "end": 33.95} # rel_end = 3.95 (4.0 - 3.95 = 0.05 < 0.3s from end)
                ]
            },
            {
                "id": 3,
                "start": 40.0,
                "end": 44.0,
                "duration": 4.0,
                "emphasis_word": "unmatched",
                "words": [
                    {"word": "Simple", "start": 40.5, "end": 41.5},
                    {"word": "words.", "start": 41.6, "end": 42.5}
                ]
            }
        ]

        _match_emphasis_words_with_timestamps(scenes)

        # Scene 0: middle word, valid punch zoom
        self.assertFalse(scenes[0]["skip_emphasis_zoom"], "Middle word should not skip emphasis zoom")
        self.assertEqual(scenes[0]["emphasis_rel_start"], 1.5)
        self.assertEqual(scenes[0]["emphasis_rel_end"], 2.0)

        # Scene 1: word too close to start (0.1s < 0.3s)
        self.assertTrue(scenes[1]["skip_emphasis_zoom"], "Word within 0.3s of start must skip zoom")

        # Scene 2: word too close to end (dur - 3.95 = 0.05s < 0.3s)
        self.assertTrue(scenes[2]["skip_emphasis_zoom"], "Word within 0.3s of end must skip zoom")

        # Scene 3: word not in transcript
        self.assertTrue(scenes[3]["skip_emphasis_zoom"], "Unmatched word must skip zoom")

    @patch("backend.scene_analyzer.requests.post")
    def test_single_llm_call_extracts_callout_and_emphasis(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{
                "message": {
                    "content": """[
                        {
                            "search_tags": ["entrepreneur luxury", "money wealth"],
                            "callout_text": "10X YOUR INCOME",
                            "emphasis_word": "income"
                        },
                        {
                            "search_tags": ["focus computer"],
                            "callout_text": null,
                            "emphasis_word": "best"
                        }
                    ]"""
                }
            }]
        }
        mock_post.return_value = mock_response

        scenes = [
            {"id": 0, "text": "Learn how to 10x your income today."},
            {"id": 1, "text": "This is the best productivity method."}
        ]

        result = _enhance_tags_with_ai(scenes, "Wealth", openai_key="fake_test_key")

        # Exactly 1 HTTP POST call made
        self.assertEqual(mock_post.call_count, 1)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["callout_text"], "10X YOUR INCOME")
        self.assertEqual(result[0]["emphasis_word"], "income")
        self.assertEqual(result[0]["search_tags"], ["entrepreneur luxury", "money wealth"])
        self.assertIsNone(result[1]["callout_text"])
        self.assertEqual(result[1]["emphasis_word"], "best")


class TestIntegratedRenderEffects(unittest.TestCase):
    """
    Renders a short test video with all 3 effects active:
    - Text callouts
    - Sound stings (SFX)
    - Emphasis punch zoom
    """

    def setUp(self):
        self.ffmpeg = find_ffmpeg()
        self.test_dir = Path(__file__).parent / "temp_render_test"
        self.test_dir.mkdir(parents=True, exist_ok=True)

        # 1. Create short synthetic voiceover audio (2.5 seconds)
        self.audio_path = self.test_dir / "voiceover.mp3"
        subprocess.run([
            self.ffmpeg, "-y",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=3.0",
            "-c:a", "libmp3lame",
            str(self.audio_path)
        ], capture_output=True, check=True)

        # 2. Create 2 short synthetic video clips (1.5s each)
        self.clip1_path = self.test_dir / "clip1.mp4"
        subprocess.run([
            self.ffmpeg, "-y",
            "-f", "lavfi", "-i", "color=c=blue:s=1920x1080:d=1.5:r=30",
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            str(self.clip1_path)
        ], capture_output=True, check=True)

        self.clip2_path = self.test_dir / "clip2.mp4"
        subprocess.run([
            self.ffmpeg, "-y",
            "-f", "lavfi", "-i", "color=c=red:s=1920x1080:d=1.5:r=30",
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            str(self.clip2_path)
        ], capture_output=True, check=True)

    def tearDown(self):
        import shutil
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_render_with_all_three_effects(self):
        scenes = [
            {
                "id": 0,
                "start": 0.0,
                "end": 1.5,
                "duration": 1.5,
                "text": "First scene with callout and punch zoom.",
                "callout_text": "CRITICAL INSIGHT",
                "emphasis_word": "insight",
                "emphasis_rel_start": 0.6,
                "emphasis_rel_end": 0.9,
                "skip_emphasis_zoom": False,
                "words": [
                    {"word": "First", "start": 0.1, "end": 0.3},
                    {"word": "insight", "start": 0.6, "end": 0.9}
                ],
                "video_clip": {"file_path": str(self.clip1_path)}
            },
            {
                "id": 1,
                "start": 1.5,
                "end": 3.0,
                "duration": 1.5,
                "text": "Second scene closing.",
                "callout_text": None,
                "emphasis_word": None,
                "skip_emphasis_zoom": True,
                "words": [
                    {"word": "Closing", "start": 1.7, "end": 2.2}
                ],
                "video_clip": {"file_path": str(self.clip2_path)}
            }
        ]

        # Generate ASS subtitles with Callout
        ass_path = self.test_dir / "subtitles.ass"
        generate_ass_subtitles(
            scenes=scenes,
            output_path=str(ass_path),
            preset_key="capcut_yellow",
            custom_options={
                "callouts_enabled": True,
                "callout_style": "badge_yellow"
            }
        )

        out_name = f"test_render_effects_{os.getpid()}.mp4"
        out_path = render_final_video(
            audio_path=str(self.audio_path),
            scenes=scenes,
            ass_subtitle_path=str(ass_path),
            output_filename=out_name,
            custom_options={
                "fps": 30,
                "enable_motion": True,
                "transition": "none",
                "bgm_track": None,
                "transition_sfx": "whoosh_soft.mp3",
                "transition_sfx_volume": 0.40,
                "emphasis_zoom_enabled": True,
                "emphasis_zoom_intensity": 1.15
            }
        )

        out_file = Path(out_path)
        self.assertTrue(out_file.exists(), "Rendered MP4 file must exist")
        self.assertGreater(out_file.stat().st_size, 10000, "Rendered MP4 file must be non-empty")

        # Probe streams with ffprobe
        probe_cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "stream=codec_type,width,height",
            "-of", "csv=p=0",
            str(out_file)
        ]
        probe_res = subprocess.run(probe_cmd, capture_output=True, text=True, check=True)
        self.assertIn("video", probe_res.stdout)
        self.assertIn("audio", probe_res.stdout)
        self.assertIn("1920", probe_res.stdout)
        self.assertIn("1080", probe_res.stdout)

        # Cleanup rendered file
        try:
            out_file.unlink()
        except Exception:
            pass


if __name__ == "__main__":
    unittest.main()
