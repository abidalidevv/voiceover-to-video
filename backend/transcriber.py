import os
import subprocess
import json
import requests
from pathlib import Path
from typing import Dict, Any, List
from .config import find_ffmpeg, find_ffprobe, load_settings


def get_audio_duration(audio_path: str) -> float:
    """Get accurate duration of audio file in seconds using ffprobe."""
    ffprobe_exe = find_ffprobe()
    cmd = [
        ffprobe_exe,
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        audio_path
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return float(res.stdout.strip())
    except Exception:
        # Fallback to wave / estimate
        return 30.0


def transcribe_audio(audio_path: str, niche: str = "General") -> Dict[str, Any]:
    """
    Transcribe audio file into word-level and segment-level timestamps.
    Tries Groq Whisper -> OpenAI Whisper -> Intelligent Heuristic Fallback.
    """
    settings = load_settings()
    duration = get_audio_duration(audio_path)

    # 1. Try Groq Whisper (Ultra-fast whisper-large-v3)
    groq_key = settings.get("groq_api_key", "").strip()
    if groq_key:
        try:
            return _transcribe_groq(audio_path, groq_key, duration)
        except Exception as e:
            print(f"[Transcriber] Groq failed: {e}, attempting OpenAI fallback")

    # 2. Try OpenAI Whisper
    openai_key = settings.get("openai_api_key", "").strip()
    if openai_key:
        try:
            return _transcribe_openai(audio_path, openai_key, duration)
        except Exception as e:
            print(f"[Transcriber] OpenAI failed: {e}, falling back to heuristic")

    # 3. Intelligent Heuristic Generator (Offline / Demo mode)
    return _generate_fallback_transcription(audio_path, duration, niche)


def _transcribe_groq(audio_path: str, api_key: str, total_duration: float) -> Dict[str, Any]:
    url = "https://api.groq.com/openai/v1/audio/transcriptions"
    headers = {"Authorization": f"Bearer {api_key}"}
    with open(audio_path, "rb") as f:
        files = {"file": (os.path.basename(audio_path), f, "audio/mpeg")}
        data = {
            "model": "whisper-large-v3",
            "response_format": "verbose_json",
            "timestamp_granularities[]": ["word", "segment"]
        }
        resp = requests.post(url, headers=headers, files=files, data=data, timeout=60)
        resp.raise_for_status()
        raw = resp.json()
        return _format_whisper_response(raw, total_duration)


def _transcribe_openai(audio_path: str, api_key: str, total_duration: float) -> Dict[str, Any]:
    url = "https://api.openai.com/v1/audio/transcriptions"
    headers = {"Authorization": f"Bearer {api_key}"}
    with open(audio_path, "rb") as f:
        files = {"file": (os.path.basename(audio_path), f, "audio/mpeg")}
        data = {
            "model": "whisper-1",
            "response_format": "verbose_json",
            "timestamp_granularities[]": ["word", "segment"]
        }
        resp = requests.post(url, headers=headers, files=files, data=data, timeout=90)
        resp.raise_for_status()
        raw = resp.json()
        return _format_whisper_response(raw, total_duration)


def _format_whisper_response(raw: Dict[str, Any], total_duration: float) -> Dict[str, Any]:
    full_text = raw.get("text", "")
    segments_raw = raw.get("segments", [])
    words_raw = raw.get("words", [])

    formatted_segments = []
    for i, seg in enumerate(segments_raw):
        seg_start = float(seg.get("start", 0))
        seg_end = float(seg.get("end", 0))
        seg_text = seg.get("text", "").strip()

        # Gather words for this segment
        seg_words = [
            {
                "word": w.get("word", "").strip(),
                "start": float(w.get("start", 0)),
                "end": float(w.get("end", 0))
            }
            for w in words_raw
            if seg_start <= float(w.get("start", 0)) <= seg_end
        ]

        formatted_segments.append({
            "id": i,
            "start": seg_start,
            "end": seg_end,
            "text": seg_text,
            "words": seg_words
        })

    # If words_raw was empty, estimate word timestamps from segment
    for seg in formatted_segments:
        if not seg["words"]:
            words_in_text = seg["text"].split()
            seg_len = seg["end"] - seg["start"]
            w_count = max(1, len(words_in_text))
            w_dur = seg_len / w_count
            for j, w in enumerate(words_in_text):
                w_start = seg["start"] + j * w_dur
                w_end = min(seg["end"], w_start + w_dur * 0.95)
                seg["words"].append({"word": w, "start": round(w_start, 2), "end": round(w_end, 2)})

    return {
        "duration": total_duration,
        "text": full_text,
        "segments": formatted_segments,
        "words": words_raw
    }


def _generate_fallback_transcription(audio_path: str, duration: float, niche: str) -> Dict[str, Any]:
    """
    Creates dynamic, niche-appropriate scenes and words matching the audio duration.
    This guarantees that the user can immediately test and generate videos even before adding API keys.
    """
    # Sample scripts tailored to niches
    niche_scripts = {
        "Motivation Psychology": [
            "You are not tired. You are just uninspired.",
            "The distance between your dreams and reality is called discipline.",
            "Every single morning you have two choices: continue to sleep with your dreams, or wake up and chase them.",
            "Most people walk through life sleepwalking, waiting for permission to be great.",
            "Success is not owned, it is leased, and rent is due every single day.",
            "Stop waiting for the right moment. Create the moment, dominate the challenge, and never look back."
        ],
        "Nature & Wildlife": [
            "In the deepest silence of the wilderness, life finds its truest rhythm.",
            "Towering mountain peaks rise above misty clouds, ancient and unyielding.",
            "Clear glacial rivers carve through untamed valleys, feeding emerald forests below.",
            "The sun rises over the horizon, painting the wild world in golden amber hues."
        ],
        "Tech & AI": [
            "The world is accelerating at an unprecedented pace.",
            "Artificial intelligence is transforming industries, redefining human creativity and engineering.",
            "Those who master technology today will architect the global landscape of tomorrow.",
            "Innovation is no longer an advantage; it is the ultimate necessity."
        ],
        "Finance & Wealth": [
            "Wealth is not about having a lot of money; it is about having options.",
            "The rich invest in assets that work for them while they sleep.",
            "Financial freedom begins the moment your discipline outweighs your impulses.",
            "Master your money today, or your money will master you tomorrow."
        ],
        "Luxury & Lifestyle": [
            "True luxury is silence, elegance, and mastery over your own time.",
            "From penthouse skylines to handcrafted speed, excellence is never accidental.",
            "Step into a world where vision meets relentless ambition and pure prestige."
        ],
        "Fitness & Health": [
            "Your body can stand almost anything; it is your mind you have to convince.",
            "Greatness is forged in the repetitions that nobody claps for.",
            "Discipline today creates the strength you will rely on tomorrow."
        ],
        "Stoicism & Philosophy": [
            "You have power over your mind, not outside events. Realize this, and you will find great strength.",
            "Waste no more time arguing what a good man should be. Be one.",
            "He who fears death will never do anything worthy of a man who is alive."
        ],
        "Sci-Fi & Space": [
            "Beyond the edge of our atmosphere lies an infinite sea of celestial wonders.",
            "Billions of stars and distant galaxies waiting to be unlocked by human courage.",
            "The future belongs to those who dare to explore the cosmic unknown."
        ],
        "Crime & Mystery": [
            "In the dark alleys of the forgotten city, every shadow tells an untold secret.",
            "The clues were hiding in plain sight, waiting for the truth to be unmasked.",
            "Behind every closed door lies a story the world was never meant to hear."
        ],
        "Meditation & Lofi": [
            "Breathe in tranquility, and let go of everything you cannot control.",
            "In this quiet moment, there is nowhere you need to rush, and nothing you need to prove.",
            "Peace is not the absence of chaos, but the mastery of your inner calm."
        ],
        "Brain & Human Facts": [
            "Your brain produces enough electrical energy to power a small lightbulb.",
            "Every single decision you make is shaped by subconscious memories you barely recall.",
            "The human mind is the most complex instrument in the known universe."
        ],
        "History & Empires": [
            "Colossal monuments built by ancient hands still whisper tales of forgotten glory.",
            "Empires rose from dust, conquered continents, and vanished into the sands of time.",
            "To understand our destiny, we must uncover the footsteps of those who walked before us."
        ],
        "Business & Hustle": [
            "Ideas are cheap; execution is the only currency that matters in business.",
            "The best companies are built by solving real problems for real people.",
            "Speed of implementation is the ultimate competitive advantage."
        ],
        "Automotive & Supercars": [
            "The relentless pursuit of horsepower, aerodynamics, and pure mechanical symphony.",
            "Engineering pushed to the absolute redline of speed and precision control.",
            "Where passion for speed meets the razor edge of high-performance engineering."
        ],
        "Gaming & Esports": [
            "Enter the virtual arena where reflexes, strategy, and teamwork determine legends.",
            "Millisecond precision separates the champions from the crowd.",
            "Level up your focus, master your mechanics, and dominate the leaderboard."
        ],
        "Travel & Adventure": [
            "Travel is the only thing you buy that makes you richer.",
            "From snow-capped mountain ridges to sun-drenched coastlines, the world is waiting.",
            "Step outside your comfort zone and discover the beauty of the unknown."
        ],
        "Science & Engineering": [
            "Science is the poetry of reality, uncovering the microscopic architecture of existence.",
            "From quantum particles to robotic automation, curiosity drives human progress.",
            "Every groundbreaking discovery began with a simple question: what if?"
        ],
        "Productivity & Self-Growth": [
            "Small habits repeated daily compound into extraordinary lifelong achievements.",
            "Eliminate the noise, protect your deep focus hours, and conquer your goals.",
            "You do not rise to the level of your goals; you fall to the level of your systems."
        ],
        "Horror & Paranormal": [
            "When night falls and the mist settles, the silence becomes deafening.",
            "Some places hold memories that refuse to fade into the darkness.",
            "Do not look back into the shadows; what is watching you never sleeps."
        ],
        "Food & Culinary": [
            "Cooking is an art, a craft, and a celebration of human culture and flavor.",
            "From sizzling cast iron skillets to the delicate aroma of freshly brewed espresso.",
            "Every great dish begins with love, patience, and the finest ingredients."
        ],
        "Wildlife Predators & Oceans": [
            "In the untamed wilderness, the law of survival reigns supreme.",
            "Apex predators move with silent grace, masters of their ancient domain.",
            "Beneath the ocean waves lies a world of untamed power and breathtaking majesty."
        ]
    }

    sentences = niche_scripts.get(niche, niche_scripts["Motivation Psychology"])
    
    # Calculate scene duration: approx 3.5 to 5 seconds per scene
    num_scenes = max(1, int(round(duration / 4.5)))
    actual_scene_duration = duration / num_scenes

    segments = []
    current_time = 0.0

    for i in range(num_scenes):
        seg_start = round(current_time, 2)
        seg_end = round(min(duration, current_time + actual_scene_duration), 2)
        current_time = seg_end

        text = sentences[i % len(sentences)]
        words_list = text.split()
        word_dur = (seg_end - seg_start) / max(1, len(words_list))

        seg_words = []
        for j, w in enumerate(words_list):
            w_start = round(seg_start + j * word_dur, 2)
            w_end = round(min(seg_end, w_start + word_dur * 0.92), 2)
            seg_words.append({"word": w, "start": w_start, "end": w_end})

        segments.append({
            "id": i,
            "start": seg_start,
            "end": seg_end,
            "text": text,
            "words": seg_words
        })

    return {
        "duration": duration,
        "text": " ".join(s["text"] for s in segments),
        "segments": segments
    }
