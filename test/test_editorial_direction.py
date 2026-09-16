import sys
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.scene_analyzer import (
    analyze_script_editorial_direction,
    build_scenes
)

class TestEditorialDirection(unittest.TestCase):

    def test_safe_defaults_when_empty_or_no_keys(self):
        # When transcript is empty
        res = analyze_script_editorial_direction("", niche="Tech", groq_key="", openai_key="")
        self.assertEqual(res["energy"], "medium")
        self.assertEqual(res["pacing_multiplier"], 1.0)
        self.assertIsNone(res["climax_scene_index"])
        self.assertEqual(res["tone"], "neutral")

        # When no API keys exist
        res2 = analyze_script_editorial_direction(
            "This is a test script with some words.",
            niche="Tech",
            groq_key="",
            openai_key=""
        )
        self.assertEqual(res2["energy"], "medium")
        self.assertEqual(res2["pacing_multiplier"], 1.0)
        self.assertIsNone(res2["climax_scene_index"])
        self.assertEqual(res2["tone"], "neutral")

    @patch("backend.scene_analyzer.requests.post")
    def test_successful_groq_llm_parsing(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{
                "message": {
                    "content": '{"energy": "high", "pacing_multiplier": 0.85, "climax_scene_index": 1, "tone": "urgent action"}'
                }
            }]
        }
        mock_post.return_value = mock_resp

        transcript = "First sentence here. Second emphatic climax sentence! Third wrap up sentence."
        res = analyze_script_editorial_direction(transcript, niche="Fitness", groq_key="gsk_dummy_test_key")

        self.assertEqual(res["energy"], "high")
        self.assertAlmostEqual(res["pacing_multiplier"], 0.85)
        self.assertEqual(res["climax_scene_index"], 1)
        self.assertEqual(res["tone"], "urgent action")

    @patch("backend.scene_analyzer.requests.post")
    def test_clamping_and_normalization(self, mock_post):
        # LLM returns out-of-bound multiplier (e.g. 2.5) and unknown energy
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{
                "message": {
                    "content": '```json\n{"energy": "super_crazy", "pacing_multiplier": 2.5, "climax_scene_index": 0, "tone": "intense"}\n```'
                }
            }]
        }
        mock_post.return_value = mock_resp

        res = analyze_script_editorial_direction("Sentence test.", niche="General", groq_key="gsk_key")
        self.assertEqual(res["energy"], "medium")  # normalized unknown energy to medium
        self.assertAlmostEqual(res["pacing_multiplier"], 1.3)  # clamped to max 1.3
        self.assertEqual(res["climax_scene_index"], 0)

    @patch("backend.scene_analyzer.requests.post")
    def test_resilience_to_malformed_json_and_network_errors(self, mock_post):
        # 1. Invalid JSON string
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{
                "message": {
                    "content": "Sorry, I cannot process this request."
                }
            }]
        }
        mock_post.return_value = mock_resp

        res = analyze_script_editorial_direction("Some script text.", niche="General", groq_key="gsk_key")
        self.assertEqual(res["energy"], "medium")
        self.assertEqual(res["pacing_multiplier"], 1.0)
        self.assertIsNone(res["climax_scene_index"])
        self.assertEqual(res["tone"], "neutral")

        # 2. Network exception
        mock_post.side_effect = Exception("Connection refused / timeout")
        res_err = analyze_script_editorial_direction("Some script text.", niche="General", groq_key="gsk_key")
        self.assertEqual(res_err["energy"], "medium")
        self.assertEqual(res_err["pacing_multiplier"], 1.0)
        self.assertIsNone(res_err["climax_scene_index"])
        self.assertEqual(res_err["tone"], "neutral")

    def test_build_scenes_backward_compatibility(self):
        transcription = {
            "duration": 12.0,
            "segments": [
                {"start": 0.0, "end": 4.0, "text": "First test sentence.", "words": [
                    {"word": "First", "start": 0.0, "end": 1.0},
                    {"word": "test", "start": 1.0, "end": 2.5},
                    {"word": "sentence.", "start": 2.5, "end": 4.0}
                ]},
                {"start": 4.0, "end": 8.0, "text": "Second test sentence.", "words": [
                    {"word": "Second", "start": 4.0, "end": 5.0},
                    {"word": "test", "start": 5.0, "end": 6.5},
                    {"word": "sentence.", "start": 6.5, "end": 8.0}
                ]},
                {"start": 8.0, "end": 12.0, "text": "Third test sentence.", "words": [
                    {"word": "Third", "start": 8.0, "end": 9.0},
                    {"word": "test", "start": 9.0, "end": 10.5},
                    {"word": "sentence.", "start": 10.5, "end": 12.0}
                ]}
            ]
        }

        # Calling without editorial_direction
        scenes = build_scenes(transcription, niche="General")
        self.assertTrue(len(scenes) >= 3)
        for sc in scenes:
            self.assertIn("is_climax", sc)
            self.assertFalse(sc["is_climax"])

    def test_build_scenes_with_climax_and_pacing(self):
        transcription = {
            "duration": 12.0,
            "segments": [
                {"start": 0.0, "end": 4.0, "text": "Sentence one starts now.", "words": [
                    {"word": "Sentence", "start": 0.0, "end": 1.0},
                    {"word": "one", "start": 1.0, "end": 2.0},
                    {"word": "starts", "start": 2.0, "end": 3.0},
                    {"word": "now.", "start": 3.0, "end": 4.0}
                ]},
                {"start": 4.0, "end": 8.0, "text": "This is the absolute climax!", "words": [
                    {"word": "This", "start": 4.0, "end": 5.0},
                    {"word": "is", "start": 5.0, "end": 5.8},
                    {"word": "the", "start": 5.8, "end": 6.2},
                    {"word": "absolute", "start": 6.2, "end": 7.0},
                    {"word": "climax!", "start": 7.0, "end": 8.0}
                ]},
                {"start": 8.0, "end": 12.0, "text": "And the conclusion follows.", "words": [
                    {"word": "And", "start": 8.0, "end": 9.0},
                    {"word": "the", "start": 9.0, "end": 9.8},
                    {"word": "conclusion", "start": 9.8, "end": 11.0},
                    {"word": "follows.", "start": 11.0, "end": 12.0}
                ]}
            ]
        }

        editorial = {
            "energy": "high",
            "pacing_multiplier": 0.8,
            "climax_scene_index": 1,
            "tone": "exciting"
        }

        # Template max duration = 3.0, pacing multiplier = 0.8 -> effective cap = 2.4s
        scenes = build_scenes(
            transcription,
            niche="General",
            editorial_direction=editorial,
            max_scene_duration=3.0
        )

        self.assertTrue(len(scenes) >= 3)

        # Climax index 1 should be marked is_climax=True
        self.assertTrue(scenes[1]["is_climax"])
        self.assertFalse(scenes[0]["is_climax"])
        self.assertFalse(scenes[2]["is_climax"])

        # All scene durations should be capped at 3.0 * 0.8 = 2.4s
        for sc in scenes:
            self.assertLessEqual(sc["duration"], 2.41)

if __name__ == "__main__":
    unittest.main()
