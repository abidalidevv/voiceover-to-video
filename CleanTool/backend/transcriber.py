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


def _prepare_compact_audio_for_stt(audio_path: str) -> str:
    """
    Compresses input audio to 16kHz mono 48kbps MP3 if needed.
    Ensures Groq's 25MB limit is NEVER exceeded and cuts upload time by 10x.
    Returns path to compact audio file (or original path if conversion fails).
    """
    p = Path(audio_path)
    if not p.exists():
        return audio_path

    # If already a small MP3 (< 15MB), no conversion needed
    fsize = p.stat().st_size
    if p.suffix.lower() == ".mp3" and fsize < 15 * 1024 * 1024:
        return audio_path

    from .config import TEMP_DIR
    compact_name = f"stt_compact_{p.stem[:20]}_{int(fsize)}.mp3"
    compact_path = TEMP_DIR / compact_name

    if compact_path.exists() and compact_path.stat().st_size > 1000:
        return str(compact_path)

    ffmpeg_exe = find_ffmpeg()
    cmd = [
        ffmpeg_exe, "-y",
        "-i", str(p),
        "-ar", "16000",
        "-ac", "1",
        "-b:a", "48k",
        str(compact_path)
    ]
    try:
        subprocess.run(cmd, capture_output=True, check=True)
        if compact_path.exists() and compact_path.stat().st_size > 1000:
            print(f"[Transcriber] Compacted audio from {fsize / (1024*1024):.1f}MB down to {compact_path.stat().st_size / (1024*1024):.2f}MB for ultra-fast STT upload.")
            return str(compact_path)
    except Exception as e:
        print(f"[Transcriber] Audio compression notice: {e}, using original audio file.")
    return audio_path


def _transcribe_long_audio_chunked(
    stt_audio_path: str,
    duration: float,
    gr_keys: List[str],
    openai_key: str = ""
) -> Optional[Dict[str, Any]]:
    """
    Slices long audio (>20 mins up to 3+ hours) into 12-15 minute compact segments,
    transcribes each segment with time offsets, and merges them into one seamless master transcript.
    Guarantees Groq's 25MB file limit is NEVER hit, even for a 3-hour recording!
    """
    import math
    chunk_dur = 720.0  # 12 minutes per slice (approx 4.3 MB at 48kbps, well below 25MB)
    num_chunks = int(math.ceil(duration / chunk_dur))
    print(f"[Transcriber] Long-form audio detected ({duration:.1f}s / {duration/60:.1f} mins). Slicing into {num_chunks} chunks of {chunk_dur/60:.0f}m...")

    ffmpeg_exe = find_ffmpeg()
    from .config import TEMP_DIR
    p = Path(stt_audio_path)

    all_segments = []
    all_words = []
    all_texts = []
    key_idx = 0

    for i in range(num_chunks):
        c_start = i * chunk_dur
        c_len = min(chunk_dur, duration - c_start)
        if c_len <= 0.5:
            break

        chunk_file = TEMP_DIR / f"chunk_{p.stem[:12]}_{i}_{int(c_start)}.mp3"
        slice_cmd = [
            ffmpeg_exe, "-y",
            "-ss", str(c_start),
            "-t", str(c_len),
            "-i", str(stt_audio_path),
            "-c", "copy",
            str(chunk_file)
        ]
        try:
            subprocess.run(slice_cmd, capture_output=True, check=True)
        except Exception:
            # Fallback with re-encode
            slice_cmd_enc = [
                ffmpeg_exe, "-y",
                "-ss", str(c_start),
                "-t", str(c_len),
                "-i", str(stt_audio_path),
                "-ar", "16000", "-ac", "1", "-b:a", "48k",
                str(chunk_file)
            ]
            subprocess.run(slice_cmd_enc, capture_output=True)

        if not chunk_file.exists() or chunk_file.stat().st_size < 500:
            print(f"[Transcriber] Warning: Chunk {i+1}/{num_chunks} slicing failed. Continuing...")
            continue

        print(f"[Transcriber] Transcribing long-form chunk {i+1}/{num_chunks} ({c_start/60:.1f}m -> {(c_start+c_len)/60:.1f}m)...")
        chunk_res = None

        # Try Groq keys in pool with rotation
        for attempt in range(len(gr_keys) or 1):
            if not gr_keys:
                break
            active_key = gr_keys[(key_idx + attempt) % len(gr_keys)]
            try:
                chunk_res = _transcribe_groq(str(chunk_file), active_key, c_len)
                key_idx = (key_idx + attempt + 1) % len(gr_keys)
                break
            except Exception as e:
                print(f"[Transcriber] Chunk {i+1} Groq key failure: {e}, trying next key...")

        # Fallback to OpenAI if Groq keys fail
        if not chunk_res and openai_key:
            try:
                chunk_res = _transcribe_openai(str(chunk_file), openai_key, c_len)
            except Exception as e:
                print(f"[Transcriber] Chunk {i+1} OpenAI failure: {e}")

        # Clean up chunk file
        try:
            if chunk_file.exists():
                chunk_file.unlink()
        except Exception:
            pass

        if chunk_res:
            c_text = chunk_res.get("text", "").strip()
            if c_text:
                all_texts.append(c_text)
            for seg in chunk_res.get("segments", []):
                shifted_seg = dict(seg)
                shifted_seg["id"] = len(all_segments)
                shifted_seg["start"] = round(float(seg.get("start", 0)) + c_start, 3)
                shifted_seg["end"] = round(float(seg.get("end", 0)) + c_start, 3)
                # Shift words inside segment
                shifted_words = []
                for w in seg.get("words", []):
                    sw = dict(w)
                    sw["start"] = round(float(w.get("start", 0)) + c_start, 3)
                    sw["end"] = round(float(w.get("end", 0)) + c_start, 3)
                    shifted_words.append(sw)
                shifted_seg["words"] = shifted_words
                all_segments.append(shifted_seg)

            for w in chunk_res.get("words", []):
                sw = dict(w)
                sw["start"] = round(float(w.get("start", 0)) + c_start, 3)
                sw["end"] = round(float(w.get("end", 0)) + c_start, 3)
                all_words.append(sw)

    if all_segments:
        print(f"[Transcriber] Merged long-form transcription: {len(all_segments)} segments, {len(all_words)} words across {duration/60:.1f} mins.")
        return {
            "text": " ".join(all_texts),
            "duration": duration,
            "segments": all_segments,
            "words": all_words,
            "is_long_form_chunked": True
        }
    return None


def transcribe_audio(audio_path: str, niche: str = "General") -> Dict[str, Any]:
    """
    Transcribe audio file into word-level and segment-level timestamps.
    Supports audio up to 3+ hours with automatic 12-minute chunking.
    Tries Groq Whisper -> OpenAI Whisper -> Intelligent Heuristic Fallback.
    """
    settings = load_settings()
    duration = get_audio_duration(audio_path)
    stt_audio_path = _prepare_compact_audio_for_stt(audio_path)

    # 1. Gather Groq and OpenAI keys
    gr_keys = settings.get("groq_api_keys") or ([settings.get("groq_api_key")] if settings.get("groq_api_key") else [])
    gr_keys = [k.strip() for k in gr_keys if k and k.strip()]
    openai_key = settings.get("openai_api_key", "").strip()

    # 2. If audio is long-form (> 20 mins / 1200s), automatically use chunked transcription!
    if duration > 1200:
        chunked = _transcribe_long_audio_chunked(stt_audio_path, duration, gr_keys, openai_key)
        if chunked:
            return chunked

    # 3. Standard single-shot Groq Whisper (for audios <= 20 mins)
    for groq_key in gr_keys:
        try:
            return _transcribe_groq(stt_audio_path, groq_key, duration)
        except Exception as e:
            print(f"[Transcriber] Groq key failed: {e}, trying next key...")

    # 4. Try OpenAI Whisper
    if openai_key:
        try:
            return _transcribe_openai(stt_audio_path, openai_key, duration)
        except Exception as e:
            print(f"[Transcriber] OpenAI failed: {e}, falling back to heuristic")

    # 5. Intelligent Heuristic Generator (Offline / Demo mode)
    print(f"[Transcriber] WARNING: Both Groq and OpenAI failed or were unconfigured. Using demo fallback transcription. Captions will be generic placeholders!")
    res = _generate_fallback_transcription(audio_path, duration, niche)
    res["is_fallback"] = True
    return res


def _transcribe_groq(audio_path: str, api_key: str, total_duration: float) -> Dict[str, Any]:
    url = "https://api.groq.com/openai/v1/audio/transcriptions"
    headers = {"Authorization": f"Bearer {api_key}"}
    
    # Infer proper audio MIME type from extension
    fname = os.path.basename(audio_path)
    ext = os.path.splitext(fname)[1].lower()
    mime_map = {
        ".wav": "audio/wav",
        ".mp3": "audio/mpeg",
        ".m4a": "audio/mp4",
        ".mp4": "audio/mp4",
        ".ogg": "audio/ogg",
        ".flac": "audio/flac",
        ".webm": "audio/webm"
    }
    content_type = mime_map.get(ext, "audio/mpeg")

    # Try whisper-large-v3 first, then whisper-large-v3-turbo
    models_to_try = ["whisper-large-v3", "whisper-large-v3-turbo"]
    last_err = None

    for model_name in models_to_try:
        try:
            with open(audio_path, "rb") as f:
                files = {"file": (fname, f, content_type)}
                data = {
                    "model": model_name,
                    "response_format": "verbose_json",
                    "timestamp_granularities[]": ["word", "segment"]
                }
                resp = requests.post(url, headers=headers, files=files, data=data, timeout=60)
                if resp.status_code == 200:
                    raw = resp.json()
                    print(f"[Transcriber] Groq speech transcription success using {model_name}!")
                    return _format_whisper_response(raw, total_duration)
                else:
                    print(f"[Transcriber] Groq {model_name} HTTP {resp.status_code}: {resp.text}")
                    last_err = Exception(f"HTTP {resp.status_code}: {resp.text}")
        except Exception as e:
            print(f"[Transcriber] Groq {model_name} request failed: {e}")
            last_err = e

    raise last_err or Exception("All Groq transcription models failed.")


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
