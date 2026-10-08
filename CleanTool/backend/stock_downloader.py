import os
import re
import json
import time
import random
import hashlib
import requests
import subprocess
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Optional, Set
from .config import CACHE_DIR, TEMP_DIR, DATA_DIR, find_ffmpeg, find_ffprobe, load_settings

VIDEO_CACHE_DIR = CACHE_DIR / "stock_videos"
VIDEO_CACHE_DIR.mkdir(parents=True, exist_ok=True)


import threading

HISTORY_FILE = DATA_DIR / "stock_usage_history.json"
_HISTORY_LOCK = threading.Lock()
_trim_slots = min(6, max(2, (os.cpu_count() or 4) // 2))
_TRIM_SEMAPHORE = threading.Semaphore(_trim_slots)  # Auto-scales trimming threads based on CPU cores (2 to 6)
_CLIP_PROBE_CACHE: Dict[str, float] = {}
_PROBE_LOCK = threading.Lock()


def _get_recently_used_video_ids(days: int = 14) -> Dict[str, float]:
    """Returns mapping of video_id -> timestamp used within the last `days` days across all projects."""
    with _HISTORY_LOCK:
        if not HISTORY_FILE.exists():
            return {}
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            cutoff = time.time() - (days * 86400)
            return {str(k): float(v) for k, v in data.items() if isinstance(v, (int, float)) and v > cutoff}
        except Exception:
            return {}


def _record_used_video_id(video_id: Any):
    """Records that a video_id has been selected in a project to prevent cross-project repetition."""
    if not video_id:
        return
    with _HISTORY_LOCK:
        try:
            data = {}
            if HISTORY_FILE.exists():
                try:
                    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                        data = json.load(f)
                except Exception:
                    data = {}
            data[str(video_id)] = time.time()
            cutoff = time.time() - (30 * 86400)
            data = {str(k): float(v) for k, v in data.items() if isinstance(v, (int, float)) and v > cutoff}
            with open(HISTORY_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f)
        except Exception as e:
            print(f"[StockDownloader] Notice recording used video id: {e}")


def trim_and_fit_clip(
    raw_path: str,
    target_dur: float,
    scene_id: int,
    target_resolution: str = "1080p",
    aspect_ratio: str = "16:9"
) -> str:
    """
    Intelligently crops and trims a downloaded stock video to the EXACT scene duration in parallel background threads.
    - Strips all excess video beyond sentence duration so clips never spill into next sentences.
    - If clip is shorter than sentence, applies seamless looping (-stream_loop -1).
    - Enforces target resolution (1080p Full HD, 4K UHD, 8K UHD) with 16:9 Landscape or 9:16 Vertical Shorts.
    - Uses hardware GPU encoder (QSV / NVENC / AMF) when available for 5x-10x pre-scaling speed.
    - Strips native audio (-an) to prevent ambient noise clash.
    """
    if not raw_path or not os.path.exists(raw_path):
        return raw_path

    ffmpeg_exe = find_ffmpeg()
    target_dur = max(0.5, round(float(target_dur), 2))
    res_str = str(target_resolution or "1080p").lower().strip()
    is_vertical = str(aspect_ratio or "").lower().strip() in ("9:16", "vertical", "portrait", "shorts", "tiktok")

    if is_vertical:
        if res_str == "8k":
            w, h = 4320, 7680
        elif res_str == "4k":
            w, h = 2160, 3840
        else:
            w, h = 1080, 1920
    else:
        if res_str == "8k":
            w, h = 7680, 4320
        elif res_str == "4k":
            w, h = 3840, 2160
        else:
            w, h = 1920, 1080

    raw_key = str(raw_path)
    with _PROBE_LOCK:
        cached_dur = _CLIP_PROBE_CACHE.get(raw_key)

    if cached_dur is not None:
        probe_dur = cached_dur
    else:
        probe_dur = 0.0
        ffprobe_exe = find_ffprobe()
        try:
            p_cmd = [ffprobe_exe, "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", raw_key]
            res = subprocess.run(p_cmd, capture_output=True, text=True, check=True)
            probe_dur = float(res.stdout.strip())
        except Exception:
            probe_dur = 0.0
        with _PROBE_LOCK:
            _CLIP_PROBE_CACHE[raw_key] = probe_dur

    scene_clip_dir = CACHE_DIR / "scene_clips"
    scene_clip_dir.mkdir(parents=True, exist_ok=True)

    path_hash = hashlib.md5(f"{raw_path}_{target_dur}_{res_str}_{w}x{h}".encode("utf-8")).hexdigest()[:8]
    out_name = f"sc_{scene_id:04d}_{res_str}_{path_hash}.mp4"
    out_path = scene_clip_dir / out_name

    if out_path.exists() and out_path.stat().st_size > 1000:
        return str(out_path)

    # Content-Aware Action Window Selection:
    start_offset = 0.0
    if probe_dur >= (target_dur + 2.0):
        headroom = probe_dur - target_dur
        candidate_offset = round(headroom * 0.40, 2)
        start_offset = max(1.5, min(candidate_offset, round(headroom - 0.4, 2)))

    # Detect fastest encoder with safe thread count for background tasks
    encoder = "libx264"
    encoder_args = ["-preset", "ultrafast", "-crf", "18", "-pix_fmt", "yuv420p", "-threads", "2"]
    try:
        from .video_renderer import get_best_video_encoder
        encoder, encoder_args = get_best_video_encoder(ffmpeg_exe, use_gpu=True)
        # If CPU encoder, cap threads to 2 so parallel tasks don't starve OS
        if encoder == "libx264" and "-threads" in encoder_args:
            idx = encoder_args.index("-threads")
            if idx + 1 < len(encoder_args):
                encoder_args[idx + 1] = "2"
    except Exception:
        pass

    cmd = [ffmpeg_exe, "-y"]
    if probe_dur > 0 and probe_dur < (target_dur + start_offset):
        cmd.extend(["-stream_loop", "-1"])
        start_offset = 0.0

    if start_offset > 0:
        cmd.extend(["-ss", f"{start_offset:.2f}"])

    scale_filter = f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},setsar=1,fps=30"
    trim_dur = target_dur + 1.0  # 1.0s headroom for smooth zero-re-encode transitions
    cmd.extend([
        "-i", str(raw_path),
        "-t", f"{trim_dur:.2f}",
        "-vf", scale_filter,
        "-c:v", encoder,
        *encoder_args,
        "-an",
        "-dn",
        str(out_path)
    ])
    
    # Throttle concurrent FFmpeg trimming based on dynamic semaphore
    with _TRIM_SEMAPHORE:
        try:
            subprocess.run(cmd, capture_output=True, check=True)
            return str(out_path)
        except Exception:
            # Fallback to 2-threaded CPU libx264
            try:
                cpu_cmd = [
                    ffmpeg_exe, "-y",
                    "-i", str(raw_path),
                    "-t", f"{trim_dur:.2f}",
                    "-vf", scale_filter,
                    "-c:v", "libx264",
                    "-preset", "ultrafast",
                    "-crf", "18",
                    "-pix_fmt", "yuv420p",
                    "-threads", "2",
                    "-an",
                    "-dn",
                    str(out_path)
                ]
                subprocess.run(cpu_cmd, capture_output=True, check=True)
                return str(out_path)
            except Exception as e2:
                print(f"[StockDownloader] Notice: trimming raw clip failed: {e2}, falling back to raw path")
                return raw_path


class ApiKeyPool:
    """
    Thread-safe round-robin API key pool with automatic rate-limit (429) cooldown.
    Distributes scene queries across multiple accounts so limits are never exceeded.
    """
    def __init__(self, keys: List[str], provider_name: str = "Pexels"):
        self.keys = [str(k).strip() for k in keys if k and str(k).strip()]
        self.provider_name = provider_name
        self.index = 0
        self.lock = threading.Lock()
        self.cooldowns: Dict[str, float] = {}
        self._exhausted_logged: bool = False

    def has_keys(self) -> bool:
        return len(self.keys) > 0

    def has_active_keys(self) -> bool:
        """Returns True if there is at least one active, non-cooldown key available right now."""
        with self.lock:
            if not self.keys:
                return False
            now = time.time()
            return any(self.cooldowns.get(k, 0.0) <= now for k in self.keys)

    def get_candidate_keys(self) -> List[str]:
        """
        Returns ordered candidate keys prioritizing active non-cooldown keys.
        If ALL keys are in cooldown, returns empty list immediately so the engine fails over to secondary providers!
        """
        with self.lock:
            if not self.keys:
                return []
            now = time.time()
            active = [k for k in self.keys if self.cooldowns.get(k, 0.0) <= now]
            if active:
                self._exhausted_logged = False
                start_idx = self.index % len(active)
                ordered_active = active[start_idx:] + active[:start_idx]
                self.index = (self.index + 1) % len(active)
                return ordered_active
            else:
                # All keys in cooldown!
                if not self._exhausted_logged:
                    self._exhausted_logged = True
                    wait_s = int(min(self.cooldowns.values()) - now) if self.cooldowns else 300
                    print(f"[StockDownloader] [INFO] All {len(self.keys)} {self.provider_name} account keys are cooling down from rate limits (~{max(1, wait_s)}s left). Fast-failing over to backup providers...")
                return []

    def mark_rate_limited(self, key: str, cooldown_seconds: int = 300):
        with self.lock:
            k_mask = f"...{key[-6:]}" if len(key) >= 6 else key
            self.cooldowns[key] = time.time() + cooldown_seconds
            now = time.time()
            active_left = sum(1 for k in self.keys if self.cooldowns.get(k, 0.0) <= now)
            if active_left > 0:
                print(f"[StockDownloader] [WARNING] {self.provider_name} Key {k_mask} hit rate limit (429). Cooldown {cooldown_seconds}s. Load-balancing to remaining {active_left} active key(s)...")
            else:
                print(f"[StockDownloader] [WARNING] {self.provider_name} Key {k_mask} hit rate limit (429). All account keys now in cooldown ({cooldown_seconds}s). Cascading to Pixabay and fallback providers...")


from urllib3.util import Retry
from requests.adapters import HTTPAdapter
import time

# Create high-performance persistent session with connection pooling
SESSION = requests.Session()
retries = Retry(total=2, backoff_factor=0.5, status_forcelist=[500, 502, 503, 504], raise_on_status=False)
adapter = HTTPAdapter(pool_connections=64, pool_maxsize=64, max_retries=retries)
SESSION.mount("https://", adapter)
SESSION.mount("http://", adapter)


def download_scenes_concurrently(scenes: List[Dict[str, Any]], progress_callback=None, target_resolution: str = "1080p", niche: str = "", pipeline: str = "Main", aspect_ratio: str = "16:9", generation_mode: str = "niche") -> List[Dict[str, Any]]:
    """
    Downloads stock videos for all scenes in parallel using a ThreadPoolExecutor.
    Load-balances queries across multiple API keys (Pexels, Pixabay, etc.).
    Includes visual diversity tracking to prevent adjacent scenes from getting identical clips.
    Pre-scales each clip to target resolution and aspect ratio using hardware GPU encoding.
    """
    settings = load_settings()
    configured_workers = int(settings.get("workers", 8))

    # Initialize shared key pools for this batch of scenes
    p_keys = settings.get("pexels_api_keys") or ([settings.get("pexels_api_key")] if settings.get("pexels_api_key") else [])
    pb_keys = settings.get("pixabay_api_keys") or ([settings.get("pixabay_api_key")] if settings.get("pixabay_api_key") else [])
    pexels_pool = ApiKeyPool(p_keys, "Pexels")
    pixabay_pool = ApiKeyPool(pb_keys, "Pixabay")

    total_keys = len(p_keys) + len(pb_keys)
    num_workers = max(configured_workers, min(16, max(4, total_keys * 2)))

    print(f"[StockDownloader] Launching parallel download for {len(scenes)} scenes across {num_workers} workers (Resolution: {target_resolution}, Aspect: {aspect_ratio}, Niche: '{niche}', Generation Mode: '{generation_mode}', Pipeline: '{pipeline}', Pexels Accounts: {len(p_keys)}, Pixabay Accounts: {len(pb_keys)})...")

    completed_scenes = [None] * len(scenes)
    completed_count = 0
    lock = threading.Lock()
    # Visual diversity: track video IDs used in the current video to guarantee zero repetition
    used_video_ids: Set[str] = set()
    global_past_used = _get_recently_used_video_ids(days=14)

    def process_scene(scene_item):
        nonlocal completed_count
        scene_idx = scene_item["id"]
        scene_niche = scene_item.get("niche") or niche
        scene_gen_mode = scene_item.get("generation_mode") or generation_mode or "niche"
        tags = scene_item.get("search_tags", ["cinematic inspiring"])
        selected_tag = scene_item.get("selected_tag") or tags[0]
        duration = float(scene_item.get("duration", 4.0))
        scene_aspect = scene_item.get("aspect_ratio") or aspect_ratio or "16:9"

        clip_data = None
        # Try selected tag first, then other candidate tags
        sentence_text = scene_item.get("text", "")
        search_candidates = [selected_tag] + [t for t in tags if t != selected_tag]
        for candidate in search_candidates:
            clip_data = find_and_download_stock_video(
                candidate,
                min_duration=duration,
                sentence_context=sentence_text,
                target_resolution=target_resolution,
                pexels_pool=pexels_pool,
                pixabay_pool=pixabay_pool,
                niche=scene_niche,
                pipeline=pipeline,
                active_batch_ids=used_video_ids,
                past_used_ids=global_past_used,
                generation_mode=scene_gen_mode
            )
            if clip_data:
                vid_id = clip_data.get("video_id")
                with lock:
                    if vid_id and str(vid_id) in used_video_ids and len(search_candidates) > 1:
                        continue  # Try next tag for visual variety
                    if vid_id:
                        used_video_ids.add(str(vid_id))
                break

        # If external APIs returned nothing, try niche-specific guaranteed space queries before offline canvas
        if not clip_data:
            scene_niche_clean = str(scene_niche or "").lower()
            if scene_gen_mode != "voiceover" and any(k in scene_niche_clean for k in ("space", "sci-fi", "cosmos", "astronomy")):
                for fallback_q in ["deep space galaxy nebula", "astronaut walking planet surface", "hubble telescope cosmos 4k"]:
                    clip_data = find_and_download_stock_video(
                        fallback_q,
                        min_duration=duration,
                        sentence_context=sentence_text,
                        target_resolution=target_resolution,
                        pexels_pool=pexels_pool,
                        pixabay_pool=pixabay_pool,
                        niche=scene_niche,
                        pipeline=pipeline,
                        active_batch_ids=used_video_ids,
                        past_used_ids=global_past_used,
                        generation_mode=scene_gen_mode
                    )
                    if clip_data:
                        vid_id = clip_data.get("video_id")
                        with lock:
                            if vid_id:
                                used_video_ids.add(str(vid_id))
                        break

        # If external APIs returned nothing (e.g. API rate limit hit in long-form videos),
        # intelligently reuse one of the real downloaded clips from this project rather than showing blank/gradients!
        if not clip_data:
            with lock:
                successful_real_clips = [
                    sc["video_clip"] for sc in completed_scenes
                    if sc and sc.get("video_clip") and not sc.get("video_clip", {}).get("is_fallback") and sc.get("video_clip", {}).get("raw_file_path")
                ]
            if successful_real_clips:
                base_clip = successful_real_clips[scene_idx % len(successful_real_clips)]
                clip_data = dict(base_clip)
                clip_data["video_id"] = f"{base_clip.get('video_id')}_reuse_{scene_idx}"
                clip_data["file_path"] = base_clip["raw_file_path"]
                clip_data["is_fallback"] = False
                clip_data["is_reused"] = True
            else:
                clip_data = get_fallback_stock_video(scene_idx, selected_tag, duration)

        # Intelligently trim the clip to the exact sentence duration (stripping excess video)
        if clip_data and clip_data.get("file_path"):
            trimmed_path = trim_and_fit_clip(
                clip_data["file_path"],
                duration,
                scene_idx,
                target_resolution=target_resolution,
                aspect_ratio=scene_aspect
            )
            clip_data["raw_file_path"] = clip_data["file_path"]
            clip_data["file_path"] = trimmed_path
            clip_data["duration"] = duration

        scene_item["video_clip"] = clip_data
        scene_item["fallback_used"] = bool(clip_data and clip_data.get("is_fallback"))
        scene_item["status"] = "ready"

        with lock:
            if 0 <= scene_idx < len(completed_scenes):
                completed_scenes[scene_idx] = scene_item
            completed_count += 1
            current_done = completed_count

        if progress_callback:
            try:
                progress_callback(current_done, len(scenes), scene_item)
            except Exception as e:
                print(f"[StockDownloader] Callback error: {e}")

        return scene_item

    with ThreadPoolExecutor(max_workers=num_workers) as executor:
        future_to_scene = {executor.submit(process_scene, sc): item_idx for item_idx, sc in enumerate(scenes)}
        for future in as_completed(future_to_scene):
            item_idx = future_to_scene[future]
            try:
                res = future.result()
                completed_scenes[item_idx] = res
            except Exception as e:
                sc_id = scenes[item_idx].get("id", item_idx)
                print(f"[StockDownloader] Error processing scene {sc_id}: {e}")
                fallback = get_fallback_stock_video(sc_id, "cinematic", float(scenes[item_idx].get("duration", 4.0)))
                scenes[item_idx]["video_clip"] = fallback
                scenes[item_idx]["fallback_used"] = True
                scenes[item_idx]["status"] = "ready"
                completed_scenes[item_idx] = scenes[item_idx]

    return completed_scenes


def _simplify_stock_query(q: str) -> Optional[str]:
    """Extracts core 2 salient words from a multi-word query if initial search fails."""
    clean = re.sub(r'[#,\-_\./]', ' ', q).strip().lower()
    words = [w for w in clean.split() if w not in ("cinematic", "dramatic", "4k", "hd", "footage", "video", "ultra", "scene", "shot", "view", "majestic", "dense")]
    if len(words) >= 3:
        return " ".join(words[:2])
    return None


def _score_candidate(
    duration: float, 
    width: int, 
    height: int, 
    target_dur: float, 
    query_words: List[str], 
    metadata_text: str, 
    target_resolution: str = "1080p",
    niche: str = "",
    pipeline: str = "",
    video_id: Any = None,
    active_batch_ids: Optional[Set[str]] = None,
    past_used_ids: Optional[Dict[str, float]] = None,
    generation_mode: str = "niche"
) -> float:
    """Ranks candidate video clips based on resolution, duration headroom, keyword match, and niche relevance."""
    score = 0.0

    # 0. Anti-Repetition Diversity Penalty (Intra-video & Cross-project)
    if video_id is not None:
        vid_str = str(video_id)
        if active_batch_ids and vid_str in active_batch_ids:
            score -= 1000.0  # Absolute veto: already used in current video!
        elif past_used_ids and vid_str in past_used_ids:
            score -= 75.0   # Soft penalty: prioritize never-before-seen footage across projects
    res_str = str(target_resolution or "1080p").lower().strip()

    # 1. Orientation & Resolution (40-45 pts)
    if res_str in ("4k", "8k"):
        if width >= 3840 and height >= 2160:
            score += 45.0
        elif width >= 2560 and width > height:
            score += 35.0
        elif width >= 1920 and width > height:
            score += 25.0
        elif width >= 1280 and width > height:
            score += 15.0
        elif width > 0 and width < height:
            score -= 60.0
    else:
        if width >= 1920 and height == 1080:
            score += 40.0
        elif width >= 1280 and width > height:
            score += 25.0
        elif width > 0 and width < height:
            score -= 60.0  # Penalize vertical clips in 16:9 widescreen mode

    # 2. Duration Headroom Fit (30 pts)
    if target_dur <= duration <= (target_dur * 3.5):
        score += 30.0
    elif (target_dur * 3.5) < duration <= 35.0:
        score += 15.0
    elif duration > 35.0:
        score += 5.0
    elif duration < target_dur:
        score += 0.0

    # 3. Keyword / Semantic Overlap (up to 50 pts)
    meta_lower = metadata_text.lower()
    matched = sum(1 for w in query_words if len(w) >= 3 and w in meta_lower)
    score += min(50.0, matched * 15.0)

    # 4. NICHE-SPECIFIC RELEVANCE BONUS & CLASH PENALTIES
    # Only enforce strict niche penalties and channel universe dominance when generation_mode is 'niche'
    is_niche_mode = (str(generation_mode or "niche").lower() != "voiceover")
    niche_clean = str(niche or "").lower() if is_niche_mode else ""
    all_query_text = " ".join(query_words).lower()

    is_motivation_niche = any(k in niche_clean for k in ("motivation", "stoic", "discipline", "mindset", "success", "psychology", "growth"))
    is_space_niche = any(k in niche_clean for k in ("space", "sci-fi", "cosmos", "astronomy")) or (is_niche_mode and any(k in all_query_text for k in ("outer space", "deep space", "galaxy", "astronaut", "nebula", "solar system", "cosmos")))

    if is_motivation_niche:
        mot_positives = {
            "run", "running", "runner", "gym", "workout", "fitness", "training", "athlete", "athletic",
            "mountain", "climbing", "summit", "peak", "sunrise", "dawn", "silhouette", "focused",
            "study", "desk", "writing", "skyscraper", "city", "skyline", "office", "businessman",
            "victory", "celebration", "determination", "grit", "boxing", "boxer", "crossfit", "sweat"
        }
        if any(w in meta_lower for w in mot_positives):
            score += 45.0

        # Strict veto clashes for motivation: NEVER allow space, galaxy, astronauts, recipes, etc.
        mot_clashes = {
            "space", "galaxy", "planet", "astronaut", "nasa", "orbit", "satellite", "nebula",
            "cosmos", "solar system", "alien", "spaceship", "ufo", "recipe", "cooking",
            "baking", "wedding", "bride", "groom", "makeup", "cosmetics", "cartoon",
            "puppy", "kitten", "cat", "dog", "baby", "infant", "toddler"
        }
        if any(c in meta_lower for c in mot_clashes):
            score -= 250.0

    elif is_space_niche:
        space_positives = {"space", "galaxy", "planet", "stars", "star", "astronomy", "cosmos", "astronaut", "nasa", "orbit", "satellite", "telescope", "spacecraft", "solar", "moon", "mars", "nebula", "universe", "alien", "sci-fi"}
        if any(w in meta_lower for w in space_positives):
            score += 50.0

        # NEVER allow sports, swimming, beach, kitchen, makeup, or civilian lifestyle clips for space!
        space_clashes = {
            "swim", "swimming", "swimmer", "olympic", "olympics", "beach", "pool", "kitchen", "cooking", "recipe",
            "baking", "wedding", "bride", "groom", "makeup", "cosmetics", "fashion", "dress", "dance", "dancing",
            "soccer", "football", "baseball", "tennis", "puppy", "kitten", "cat", "dog", "barbecue", "party", "lake",
            "ocean beach", "playground", "children", "child", "kids", "bedroom", "sleeping", "bed", "alarm clock",
            "wallet", "dollar", "cash", "money", "office", "cubicle", "hospital", "patient", "classroom", "school",
            "traffic jam", "supermarket", "grocery"
        }
        if any(c in meta_lower for c in space_clashes):
            score -= 250.0

    elif any(k in niche_clean for k in ("military", "war", "defense")) or any(k in all_query_text for k in ("missile", "war", "tank", "bomb", "soldier", "radar", "fighter", "battlefield", "airforce", "navy")):
        mil_positives = {"military", "soldier", "army", "tank", "missile", "war", "weapon", "fighter", "aircraft", "radar", "navy", "combat", "explosion", "battlefield", "artillery", "troops", "infantry"}
        if any(w in meta_lower for w in mil_positives):
            score += 40.0
        mil_clashes = {
            "boxing", "boxer", "punching bag", "punching", "punch", "mma", "ufc", "karate", "taekwondo",
            "martial art", "sparring", "ring", "gloves", "kickboxing", "jiu jitsu", "wrestling",
            "gym", "workout", "fitness", "bodybuilding", "crossfit", "barbell", "dumbbell", "biceps",
            "swimming", "swimmer", "beach", "pool", "resort", "cocktail", "yoga", "pilates",
            "snail", "mollusk", "flower", "garden", "kitten", "puppy", "butterfly",
            "makeup", "fashion", "dress", "party", "wedding", "bride", "groom",
            "baking", "cooking", "kitchen", "dance", "dancing", "ballet",
            "soccer", "football", "baseball", "tennis", "basketball", "volleyball",
            "motivation", "motivational", "self help", "lifestyle"
        }
        if any(c in meta_lower for c in mil_clashes):
            score -= 200.0

    elif any(k in niche_clean for k in ("wildlife", "animal", "predator", "ocean")):
        wild_positives = {"lion", "tiger", "eagle", "shark", "whale", "elephant", "wolf", "bear",
                          "leopard", "cheetah", "crocodile", "snake", "gorilla", "panther", "jaguar",
                          "predator", "prey", "wildlife", "safari", "savannah", "ocean", "coral",
                          "dolphin", "orca", "hawk", "falcon", "penguin", "underwater"}
        if any(w in meta_lower for w in wild_positives):
            score += 45.0
        wild_clashes = {
            "boxing", "boxer", "gym", "workout", "fitness", "office", "boardroom", "computer",
            "keyboard", "desk", "meeting", "stocks", "trading", "makeup", "fashion",
            "cooking", "kitchen", "party", "wedding", "ballet", "dance"
        }
        if any(c in meta_lower for c in wild_clashes):
            score -= 200.0

    elif any(k in niche_clean for k in ("history", "empire", "ancient")) or any(k in all_query_text for k in ("ancient", "rome", "egypt", "pyramid", "castle", "medieval", "knight", "colosseum", "pharaoh", "empire", "ruins", "viking", "ottoman")):
        hist_positives = {"ancient", "ruins", "roman", "egypt", "pyramid", "castle", "medieval", "knight", "colosseum", "temple", "pharaoh", "emperor", "empire", "archaeology", "artifact", "warrior", "gladiator", "viking", "dynasty", "samurai", "fortress", "tomb"}
        if any(w in meta_lower for w in hist_positives):
            score += 40.0
        hist_clashes = {
            "laptop", "computer", "keyboard", "smartphone", "cell phone", "modern car", "highway traffic",
            "skyscraper", "gym workout", "fitness", "modern fashion", "sneakers", "office cubicle", "boardroom",
            "airplane cockpit", "neon city", "cyber", "hacker"
        }
        if any(c in meta_lower for c in hist_clashes):
            score -= 200.0

    elif any(k in niche_clean for k in ("crime", "mystery", "noir")) or any(k in all_query_text for k in ("detective", "crime", "police", "siren", "handcuffs", "prison", "jail", "courtroom", "judge", "heist", "robbery", "forensic", "murder")):
        crime_positives = {"police", "detective", "crime", "siren", "handcuffs", "prison", "jail", "court", "courtroom", "judge", "forensic", "investigation", "alley", "surveillance", "robbery", "murder", "noir", "inmate", "gavel", "heist"}
        if any(w in meta_lower for w in crime_positives):
            score += 40.0
        crime_clashes = {
            "beach party", "pool", "swim", "wedding", "bride", "groom", "birthday", "party",
            "happy kids", "children playing", "picnic", "cooking", "recipe", "cartoon", "dancing", "cheerleader"
        }
        if any(c in meta_lower for c in crime_clashes):
            score -= 180.0

    elif any(k in niche_clean for k in ("horror", "paranormal")) or any(k in all_query_text for k in ("horror", "haunted", "ghost", "creepy", "graveyard", "cemetery", "witch", "vampire", "monster", "nightmare", "eerie", "fog")):
        horror_positives = {"horror", "haunted", "ghost", "creepy", "eerie", "graveyard", "cemetery", "full moon", "shadows", "abandoned", "witch", "monster", "mist", "gothic", "darkness", "tombstone", "nightmare"}
        if any(w in meta_lower for w in horror_positives):
            score += 40.0
        horror_clashes = {
            "sunny beach", "smiling", "birthday", "wedding", "workout", "gym", "cooking food", "recipe",
            "cute puppy", "kitten", "playground", "bright sunlight", "swimming pool", "dance party"
        }
        if any(c in meta_lower for c in horror_clashes):
            score -= 200.0

    elif any(k in niche_clean for k in ("science", "engineering", "brain", "medical")) or any(k in all_query_text for k in ("dna", "genetics", "microscope", "bacteria", "cells", "surgery", "surgeon", "laboratory", "virus", "brain", "medical")):
        sci_positives = {"science", "medical", "doctor", "hospital", "surgery", "dna", "laboratory", "cells", "microscope", "virus", "research", "patient", "biology", "chemist", "quantum", "neural", "neurons", "brain", "anatomy"}
        if any(w in meta_lower for w in sci_positives):
            score += 40.0
        sci_clashes = {
            "beach party", "nightclub", "fashion runway", "soccer match", "football game", "barbecue",
            "grill", "cartoon toys", "wedding dance", "cocktail bar"
        }
        if any(c in meta_lower for c in sci_clashes):
            score -= 160.0

    elif any(k in niche_clean for k in ("automotive", "supercar", "car", "racing")) or any(k in all_query_text for k in ("supercar", "ferrari", "lamborghini", "formula 1", "racing", "drift", "engine", "sports car", "speedometer")):
        auto_positives = {"supercar", "sports car", "racing", "drift", "track", "formula 1", "speed", "engine", "cockpit", "ferrari", "lamborghini", "highway", "acceleration", "hypercar", "speedometer", "motorcycle"}
        if any(w in meta_lower for w in auto_positives):
            score += 40.0
        auto_clashes = {
            "kitchen", "cooking", "bedroom", "sleeping", "makeup", "farm animals", "cows", "gardening",
            "baby nursery", "ballet dance", "swimming pool"
        }
        if any(c in meta_lower for c in auto_clashes):
            score -= 180.0

    elif any(k in niche_clean for k in ("finance", "wealth", "business", "money")):
        fin_positives = {"money", "finance", "stock", "market", "trading", "crypto", "business", "office", "charts", "economy"}
        if any(w in meta_lower for w in fin_positives):
            score += 35.0
        fin_clashes = {"beach party", "pool", "swim", "gaming", "esports", "cartoon", "toys", "farm animals", "mud"}
        if any(c in meta_lower for c in fin_clashes):
            score -= 120.0

    elif any(k in niche_clean for k in ("fitness", "health", "workout")):
        fit_positives = {"gym", "fitness", "workout", "athlete", "training", "exercise", "muscle", "running"}
        if any(w in meta_lower for w in fit_positives):
            score += 35.0
        fit_clashes = {"junk food", "burger", "couch", "sleeping", "smoking", "office desk"}
        if any(c in meta_lower for c in fit_clashes):
            score -= 100.0

    elif any(k in niche_clean for k in ("nature", "wildlife", "animal")):
        nat_positives = {"forest", "mountain", "ocean", "river", "wildlife", "animal", "landscape", "nature", "trees"}
        if any(w in meta_lower for w in nat_positives):
            score += 35.0
        nat_clashes = {"office", "cubicle", "keyboard", "computer", "traffic jam"}
        if any(c in meta_lower for c in nat_clashes):
            score -= 100.0

    # 5. PIPELINE AESTHETIC BOOST (Nature & Scenery vs Cinematic Film)
    pipe_clean = str(pipeline or "").lower().strip()
    if pipe_clean == "nature":
        nature_keywords = {"nature", "landscape", "drone", "aerial", "mountain", "forest", "ocean", "river", "sunset", "clouds", "waterfall", "wildlife", "greenery", "scenery"}
        if any(w in meta_lower for w in nature_keywords):
            score += 35.0
    elif pipe_clean == "cinematic":
        cinematic_keywords = {"cinematic", "dramatic", "film", "dark", "moody", "atmospheric", "silhouette", "slow motion", "lens", "shadow", "35mm"}
        if any(w in meta_lower for w in cinematic_keywords):
            score += 35.0

    return score


def find_and_download_stock_video(
    query: str,
    min_duration: float = 3.0,
    sentence_context: str = "",
    target_resolution: str = "1080p",
    pexels_pool: Optional[ApiKeyPool] = None,
    pixabay_pool: Optional[ApiKeyPool] = None,
    allow_simplify: bool = True,
    niche: str = "",
    pipeline: str = "Main",
    active_batch_ids: Optional[Set[str]] = None,
    past_used_ids: Optional[Dict[str, float]] = None,
    generation_mode: str = "niche"
) -> Optional[Dict[str, Any]]:
    """
    Cascading Fallback Provider Architecture with Multi-Account Pools:
    1. Enriches search query based on selected Pipeline (Main vs Nature & Scenery vs Cinematic Film).
    2. Queries primary provider (Pexels) across configured account keys. If candidates match, returns immediately!
    3. Only if all Pexels keys fail or rate-limit, cascades to Pixabay multi-account pool.
    4. If Pixabay fails, cascades to free archives (Coverr / NASA / Wikimedia).
    5. If no results and query has >= 3 words, retries with simplified 2-word salient query.
    """
    settings = load_settings()
    provider_pref = settings.get("video_provider", "all")

    if pexels_pool is None:
        p_keys = settings.get("pexels_api_keys") or ([settings.get("pexels_api_key")] if settings.get("pexels_api_key") else [])
        pexels_pool = ApiKeyPool(p_keys, "Pexels")

    if pixabay_pool is None:
        pb_keys = settings.get("pixabay_api_keys") or ([settings.get("pixabay_api_key")] if settings.get("pixabay_api_key") else [])
        pixabay_pool = ApiKeyPool(pb_keys, "Pixabay")

    coverr_key = settings.get("coverr_api_key", "").strip()
    videvo_key = settings.get("videvo_api_key", "").strip()
    nasa_enabled = bool(settings.get("nasa_api_key") or settings.get("nasa_enabled", True))
    wiki_enabled = bool(settings.get("wikimedia_video_enabled", False))
    webhook_url = settings.get("custom_stock_webhook", "").strip()

    # Enrich query with pipeline aesthetic bias
    effective_query = query
    p_lower = str(pipeline or "Main").lower().strip()
    if p_lower == "nature":
        nature_markers = ("nature", "landscape", "scenery", "forest", "mountain", "ocean", "river", "drone", "waterfall", "wildlife", "sunset")
        if not any(k in query.lower() for k in nature_markers):
            effective_query = f"{query} nature landscape"
    elif p_lower == "cinematic":
        cinematic_markers = ("cinematic", "film", "dramatic", "moody", "35mm", "slow motion")
        if not any(k in query.lower() for k in cinematic_markers):
            effective_query = f"{query} cinematic"

    # Priority 1: Pexels (best quality)
    if (provider_pref in ("all", "pexels")) and pexels_pool.has_active_keys():
        clip = _search_pexels(effective_query, pexels_pool, min_duration, sentence_context, target_resolution=target_resolution, niche=niche, pipeline=pipeline, active_batch_ids=active_batch_ids, past_used_ids=past_used_ids, generation_mode=generation_mode)
        if clip:
            return clip

    # Priority 2: Pixabay (fast secondary fallback)
    if (provider_pref in ("all", "pixabay")) and pixabay_pool.has_active_keys():
        clip = _search_pixabay(effective_query, pixabay_pool, min_duration, sentence_context, target_resolution=target_resolution, niche=niche, pipeline=pipeline, active_batch_ids=active_batch_ids, past_used_ids=past_used_ids, generation_mode=generation_mode)
        if clip:
            return clip

    # Priority 3: Coverr (free clips)
    if (provider_pref in ("all", "coverr")) and coverr_key:
        clip = _search_coverr(effective_query, coverr_key, min_duration)
        if clip:
            return clip

    # Priority 4: Videvo
    if (provider_pref in ("all", "videvo")) and videvo_key:
        clip = _search_videvo(effective_query, videvo_key, min_duration)
        if clip:
            return clip

    # Priority 5: NASA Open Video (ONLY for Space & Astronomy niche or query)
    is_space_query = (any(k in str(niche).lower() for k in ("space", "sci-fi", "cosmos", "astronomy")) if generation_mode != "voiceover" else False) or any(k in effective_query.lower() for k in ("outer space", "deep space", "galaxy", "astronaut", "nebula"))
    if (provider_pref in ("all", "nasa")) and nasa_enabled and is_space_query:
        clip = _search_nasa(effective_query, min_duration)
        if clip:
            return clip

    # Priority 6: Wikimedia Commons
    if (provider_pref in ("all", "wikimedia")) and wiki_enabled:
        clip = _search_wikimedia(effective_query, min_duration)
        if clip:
            return clip

    # Priority 7: Webhook Proxy
    if webhook_url:
        clip = _search_custom_webhook(effective_query, webhook_url, settings.get("rapidapi_stock_key", ""), min_duration)
        if clip:
            return clip

    # Fallback retry: If multi-word query failed on all providers, try simplified 2-word query
    if allow_simplify:
        simple_q = _simplify_stock_query(query)
        if simple_q and simple_q.lower() != query.lower():
            simplified_clip = find_and_download_stock_video(
                simple_q,
                min_duration=min_duration,
                sentence_context=sentence_context,
                target_resolution=target_resolution,
                pexels_pool=pexels_pool,
                pixabay_pool=pixabay_pool,
                allow_simplify=False,
                niche=niche,
                pipeline=pipeline,
                active_batch_ids=active_batch_ids,
                past_used_ids=past_used_ids,
                generation_mode=generation_mode
            )
            if simplified_clip:
                return simplified_clip

    return None


def _search_pexels(
    query: str,
    pool: ApiKeyPool,
    min_duration: float,
    sentence_context: str = "",
    target_resolution: str = "1080p",
    niche: str = "",
    pipeline: str = "",
    active_batch_ids: Optional[Set[str]] = None,
    past_used_ids: Optional[Dict[str, float]] = None,
    generation_mode: str = "niche"
) -> Optional[Dict[str, Any]]:
    clean_query = re.sub(r'#', '', query).strip()
    candidate_keys = pool.get_candidate_keys()
    if not candidate_keys:
        return None

    if past_used_ids is None:
        past_used_ids = _get_recently_used_video_ids(days=14)

    query_tokens = re.findall(r'\b[a-zA-Z]{3,}\b', (clean_query + " " + sentence_context).lower())

    for api_key in candidate_keys:
        url = f"https://api.pexels.com/videos/search?query={requests.utils.quote(clean_query)}&orientation=landscape&size=large&per_page=20"
        headers = {"Authorization": api_key, "User-Agent": "VideoGen/1.0"}
        try:
            r = SESSION.get(url, headers=headers, timeout=7)
            if r.status_code == 429:
                pool.mark_rate_limited(api_key, 300)
                continue  # Retry immediately with next account key in pool!
            if r.status_code != 200:
                continue
            data = r.json()
            videos = data.get("videos", [])
            if not videos:
                return None  # Legitimate 0 results, no need to burn other keys

            # Candidate Scoring & Ranking across results
            scored = []
            for vid in videos:
                vfiles = vid.get("video_files", [])
                best_file = None
                for vf in vfiles:
                    w = vf.get("width") or 0
                    h = vf.get("height") or 0
                    link = vf.get("link")
                    if link and w >= 1280 and (w > h):
                        if target_resolution in ("4k", "8k"):
                            if w >= 3840 and h >= 2160:
                                best_file = vf
                                break
                            if best_file is None or w > (best_file.get("width") or 0):
                                best_file = vf
                        else:
                            if w == 1920 and h == 1080:
                                best_file = vf
                                break
                            if best_file is None or w > (best_file.get("width") or 0):
                                best_file = vf

                if best_file and best_file.get("link"):
                    vid_dur = float(vid.get("duration", min_duration))
                    url_slug = vid.get("url", "")
                    meta_text = f"{url_slug} {' '.join(vid.get('tags', []))}"
                    score = _score_candidate(
                        duration=vid_dur,
                        width=best_file.get("width", 1920),
                        height=best_file.get("height", 1080),
                        target_dur=min_duration,
                        query_words=query_tokens,
                        metadata_text=meta_text,
                        target_resolution=target_resolution,
                        niche=niche,
                        pipeline=pipeline,
                        video_id=vid.get("id"),
                        active_batch_ids=active_batch_ids,
                        past_used_ids=past_used_ids,
                        generation_mode=generation_mode
                    )
                    scored.append((score, vid, best_file))

            if not scored:
                continue

            scored.sort(key=lambda x: x[0], reverse=True)

            # Smart Dynamic Candidate Selection (Anti-Monopoly):
            # Prefer top candidates with positive score that haven't been used in active batch
            valid_candidates = [c for c in scored if c[0] > 0 and (not active_batch_ids or str(c[1]['id']) not in active_batch_ids)]
            if not valid_candidates:
                valid_candidates = [c for c in scored if c[0] > -500]
            if not valid_candidates:
                valid_candidates = scored

            # Pool top tier within 15 points of best score (up to top 4)
            best_score = valid_candidates[0][0]
            top_tier = [c for c in valid_candidates if (best_score - c[0]) <= 15.0][:4]
            selected_choice = random.choice(top_tier) if top_tier else valid_candidates[0]

            score, vid, best_file = selected_choice
            download_url = best_file["link"]
            local_path = _download_file_cached(download_url, f"pexels_{vid['id']}.mp4")
            if local_path and os.path.exists(local_path):
                vid_str = str(vid["id"])
                _record_used_video_id(vid_str)
                if active_batch_ids is not None:
                    active_batch_ids.add(vid_str)
                return {
                    "provider": "pexels",
                    "video_id": vid["id"],
                    "query": clean_query,
                    "file_path": str(local_path),
                    "thumbnail_url": vid.get("image", ""),
                    "duration": float(vid.get("duration", min_duration)),
                    "width": best_file.get("width", 1920),
                    "height": best_file.get("height", 1080),
                    "is_fallback": False
                }
        except Exception as e:
            print(f"[StockDownloader] Pexels error for '{clean_query}': {e}")
            continue

    return None


def _search_pixabay(
    query: str,
    pool: ApiKeyPool,
    min_duration: float,
    sentence_context: str = "",
    target_resolution: str = "1080p",
    niche: str = "",
    pipeline: str = "",
    active_batch_ids: Optional[Set[str]] = None,
    past_used_ids: Optional[Dict[str, float]] = None,
    generation_mode: str = "niche"
) -> Optional[Dict[str, Any]]:
    clean_query = re.sub(r'#', '', query).strip()
    candidate_keys = pool.get_candidate_keys()
    if not candidate_keys:
        return None

    if past_used_ids is None:
        past_used_ids = _get_recently_used_video_ids(days=14)

    query_tokens = re.findall(r'\b[a-zA-Z]{3,}\b', (clean_query + " " + sentence_context).lower())

    for api_key in candidate_keys:
        url = f"https://pixabay.com/api/videos/?key={api_key}&q={requests.utils.quote(clean_query)}&video_type=film&orientation=horizontal&per_page=20"
        headers = {"User-Agent": "VideoGen/1.0"}
        try:
            r = SESSION.get(url, headers=headers, timeout=7)
            if r.status_code == 429:
                pool.mark_rate_limited(api_key, 300)
                continue  # Retry with next Pixabay key in pool!
            if r.status_code != 200:
                continue
            data = r.json()
            hits = data.get("hits", [])
            if not hits:
                return None

            scored = []
            for h in hits:
                vid_files = h.get("videos", {})
                if target_resolution in ("4k", "8k"):
                    selected = vid_files.get("large") or vid_files.get("medium")
                else:
                    selected = vid_files.get("large") or vid_files.get("medium")
                if not selected or not selected.get("url"):
                    continue
                w = selected.get("width") or 0
                h_val = selected.get("height") or 0
                if h_val > w and w > 0:
                    continue  # Skip vertical clips
                vid_dur = float(h.get("duration", min_duration))
                tags_text = h.get("tags", "")
                score = _score_candidate(
                    duration=vid_dur,
                    width=w,
                    height=h_val,
                    target_dur=min_duration,
                    query_words=query_tokens,
                    metadata_text=tags_text,
                    target_resolution=target_resolution,
                    niche=niche,
                    pipeline=pipeline,
                    video_id=h.get("id"),
                    active_batch_ids=active_batch_ids,
                    past_used_ids=past_used_ids,
                    generation_mode=generation_mode
                )
                scored.append((score, h, selected))

            if not scored:
                continue

            scored.sort(key=lambda x: x[0], reverse=True)

            valid_candidates = [c for c in scored if c[0] > 0 and (not active_batch_ids or str(c[1]['id']) not in active_batch_ids)]
            if not valid_candidates:
                valid_candidates = [c for c in scored if c[0] > -500]
            if not valid_candidates:
                valid_candidates = scored

            best_score = valid_candidates[0][0]
            top_tier = [c for c in valid_candidates if (best_score - c[0]) <= 15.0][:4]
            selected_choice = random.choice(top_tier) if top_tier else valid_candidates[0]

            score, h, selected = selected_choice
            dl_url = selected["url"]
            local_path = _download_file_cached(dl_url, f"pixabay_{h['id']}.mp4")
            if local_path and os.path.exists(local_path):
                vid_str = str(h["id"])
                _record_used_video_id(vid_str)
                if active_batch_ids is not None:
                    active_batch_ids.add(vid_str)
                return {
                    "provider": "pixabay",
                    "video_id": h["id"],
                    "query": clean_query,
                    "file_path": str(local_path),
                    "thumbnail_url": h.get("picture_id", ""),
                    "duration": float(h.get("duration", min_duration)),
                    "width": selected.get("width", 1920),
                    "height": selected.get("height", 1080),
                    "is_fallback": False
                }
        except Exception as e:
            print(f"[StockDownloader] Pixabay error for '{clean_query}': {e}")
            continue

    return None


def _search_coverr(query: str, api_key: str, min_duration: float) -> Optional[Dict[str, Any]]:
    clean_query = re.sub(r'#', '', query).strip()
    url = f"https://api.coverr.co/videos?query={requests.utils.quote(clean_query)}&urls=mp4"
    headers = {"Authorization": f"Bearer {api_key}", "User-Agent": "VideoGen/1.0"}
    try:
        r = SESSION.get(url, headers=headers, timeout=8)
        if r.status_code == 200:
            hits = r.json().get("hits", [])
            for h in hits:
                urls = h.get("urls", {})
                dl_url = urls.get("mp4") or urls.get("mp4_download")
                w = h.get("width") or 1920
                h_val = h.get("height") or 1080
                if h_val > w:
                    continue  # Ensure landscape only
                if dl_url:
                    local_path = _download_file_cached(dl_url, f"coverr_{h.get('id', 'vid')}.mp4")
                    if local_path and os.path.exists(local_path):
                        return {
                            "provider": "coverr",
                            "video_id": h.get("id"),
                            "query": clean_query,
                            "file_path": str(local_path),
                            "thumbnail_url": h.get("thumbnail", ""),
                            "duration": float(h.get("duration", min_duration)),
                            "width": 1920,
                            "height": 1080
                        }
    except Exception as e:
        print(f"[StockDownloader] Coverr error for '{clean_query}': {e}")
    return None


def _search_videvo(query: str, api_key: str, min_duration: float) -> Optional[Dict[str, Any]]:
    clean_query = re.sub(r'#', '', query).strip()
    url = f"https://api.videvo.net/v1/videos?q={requests.utils.quote(clean_query)}&api_key={api_key}"
    headers = {"User-Agent": "VideoGen/1.0"}
    try:
        r = SESSION.get(url, headers=headers, timeout=8)
        if r.status_code == 200:
            items = r.json().get("data", [])
            for item in items:
                dl_url = item.get("download_url") or item.get("preview_url")
                if dl_url:
                    local_path = _download_file_cached(dl_url, f"videvo_{item.get('id')}.mp4")
                    if local_path and os.path.exists(local_path):
                        return {
                            "provider": "videvo",
                            "video_id": item.get("id"),
                            "query": clean_query,
                            "file_path": str(local_path),
                            "thumbnail_url": item.get("thumbnail_url", ""),
                            "duration": float(item.get("duration", min_duration)),
                            "width": 1920,
                            "height": 1080
                        }
    except Exception as e:
        print(f"[StockDownloader] Videvo error for '{clean_query}': {e}")
    return None


def _search_nasa(query: str, min_duration: float) -> Optional[Dict[str, Any]]:
    """Searches NASA Image & Video Library (Public domain free space/earth/nature)."""
    clean_query = re.sub(r'#', '', query).strip()
    url = f"https://images-api.nasa.gov/search?q={requests.utils.quote(clean_query)}&media_type=video"
    try:
        r = SESSION.get(url, timeout=8)
        if r.status_code == 200:
            items = r.json().get("collection", {}).get("items", [])
            for item in items[:5]:
                manifest_url = item.get("href")
                if manifest_url:
                    m_resp = SESSION.get(manifest_url, timeout=5)
                    if m_resp.status_code == 200:
                        urls = m_resp.json()
                        # Pick MP4 video
                        mp4_urls = [u for u in urls if isinstance(u, str) and u.lower().endswith(".mp4") and "preview" not in u.lower()]
                        if mp4_urls:
                            chosen_url = mp4_urls[0]
                            nasa_id = item.get("data", [{}])[0].get("nasa_id", "nasa")
                            local_path = _download_file_cached(chosen_url, f"nasa_{nasa_id}.mp4")
                            if local_path and os.path.exists(local_path):
                                return {
                                    "provider": "nasa",
                                    "video_id": nasa_id,
                                    "query": clean_query,
                                    "file_path": str(local_path),
                                    "thumbnail_url": item.get("links", [{}])[0].get("href", ""),
                                    "duration": min_duration,
                                    "width": 1920,
                                    "height": 1080
                                }
    except Exception as e:
        print(f"[StockDownloader] NASA video search error: {e}")
    return None


def _search_wikimedia(query: str, min_duration: float) -> Optional[Dict[str, Any]]:
    """Searches Wikimedia Commons open video database."""
    clean_query = re.sub(r'#', '', query).strip()
    url = f"https://commons.wikimedia.org/w/api.php?action=query&generator=search&gsrsearch={requests.utils.quote(clean_query)}+filetype:video&prop=imageinfo&iiprop=url|size|mime&format=json"
    headers = {"User-Agent": "VideoGen/1.0 (Educational open stock generator)"}
    try:
        r = SESSION.get(url, headers=headers, timeout=8)
        if r.status_code == 200:
            pages = r.json().get("query", {}).get("pages", {})
            for pid, pdata in pages.items():
                iinfo = pdata.get("imageinfo", [{}])[0]
                v_url = iinfo.get("url")
                if v_url and (v_url.lower().endswith(".mp4") or v_url.lower().endswith(".webm")):
                    local_path = _download_file_cached(v_url, f"wiki_{pid}.mp4")
                    if local_path and os.path.exists(local_path):
                        return {
                            "provider": "wikimedia",
                            "video_id": pid,
                            "query": clean_query,
                            "file_path": str(local_path),
                            "thumbnail_url": "",
                            "duration": min_duration,
                            "width": iinfo.get("width", 1920),
                            "height": iinfo.get("height", 1080)
                        }
    except Exception as e:
        print(f"[StockDownloader] Wikimedia video search error: {e}")
    return None


def _search_custom_webhook(query: str, webhook_url: str, api_key: str, min_duration: float) -> Optional[Dict[str, Any]]:
    """Queries user custom stock video API or RapidAPI stock endpoint."""
    headers = {"User-Agent": "VideoGen/1.0"}
    if api_key:
        headers["X-API-Key"] = api_key
        headers["Authorization"] = f"Bearer {api_key}"
    try:
        r = SESSION.post(webhook_url, json={"query": query, "min_duration": min_duration}, headers=headers, timeout=8)
        if r.status_code == 200:
            data = r.json()
            dl_url = data.get("download_url") or data.get("video_url")
            if dl_url:
                local_path = _download_file_cached(dl_url, f"custom_{int(time.time())}.mp4")
                if local_path and os.path.exists(local_path):
                    return {
                        "provider": "custom_webhook",
                        "video_id": data.get("id", "custom"),
                        "query": query,
                        "file_path": str(local_path),
                        "thumbnail_url": data.get("thumbnail_url", ""),
                        "duration": float(data.get("duration", min_duration)),
                        "width": data.get("width", 1920),
                        "height": data.get("height", 1080)
                    }
    except Exception as e:
        print(f"[StockDownloader] Custom webhook search error: {e}")
    return None


def search_alternative_clips(query: str, limit: int = 8) -> List[Dict[str, Any]]:
    """Returns candidate video clips for a search query so user can pick an alternative in UI."""
    settings = load_settings()
    p_keys = settings.get("pexels_api_keys") or ([settings.get("pexels_api_key")] if settings.get("pexels_api_key") else [])
    pb_keys = settings.get("pixabay_api_keys") or ([settings.get("pixabay_api_key")] if settings.get("pixabay_api_key") else [])
    clean_query = re.sub(r'#', '', query).strip()
    results = []

    # 1. Pexels alternative search across keys
    for p_key in p_keys:
        if not p_key:
            continue
        try:
            url = f"https://api.pexels.com/videos/search?query={requests.utils.quote(clean_query)}&orientation=landscape&size=large&per_page={limit}"
            r = SESSION.get(url, headers={"Authorization": p_key}, timeout=8)
            if r.status_code == 200:
                for vid in r.json().get("videos", []):
                    vfiles = vid.get("video_files", [])
                    best = next((f for f in vfiles if (f.get("width") or 0) >= 1280 and (f.get("width", 0) > (f.get("height") or 0))), None)
                    if best and best.get("link"):
                        results.append({
                            "provider": "pexels",
                            "id": vid["id"],
                            "download_url": best["link"],
                            "thumbnail_url": vid.get("image", ""),
                            "duration": vid.get("duration", 5),
                            "width": best.get("width", 1920),
                            "height": best.get("height", 1080)
                        })
                if results:
                    break
        except Exception as e:
            print(f"[StockDownloader] Alternative search Pexels error: {e}")

    # 2. Pixabay alternative search
    if len(results) < limit:
        for pb_key in pb_keys:
            if not pb_key:
                continue
            try:
                url = f"https://pixabay.com/api/videos/?key={pb_key}&q={requests.utils.quote(clean_query)}&video_type=film&per_page={limit}"
                r = SESSION.get(url, timeout=8)
                if r.status_code == 200:
                    for h in r.json().get("hits", []):
                        vids = h.get("videos", {})
                        chosen = vids.get("large") or vids.get("medium")
                        if chosen and chosen.get("url"):
                            results.append({
                                "provider": "pixabay",
                                "id": h["id"],
                                "download_url": chosen["url"],
                                "thumbnail_url": f"https://i.vimeocdn.com/video/{h.get('picture_id')}_640x360.jpg",
                                "duration": h.get("duration", 5),
                                "width": chosen.get("width", 1920),
                                "height": chosen.get("height", 1080)
                            })
                    if results:
                        break
            except Exception as e:
                print(f"[StockDownloader] Alternative search Pixabay error: {e}")

    return results


def _download_file_cached(url: str, filename: str) -> Path:
    """Downloads a file if not already in local cache with 1MB high-speed streaming chunks."""
    url_hash = hashlib.md5(url.encode('utf-8')).hexdigest()[:10]
    out_path = VIDEO_CACHE_DIR / f"{url_hash}_{filename}"
    if out_path.exists() and out_path.stat().st_size > 10000:
        return out_path

    try:
        with SESSION.get(url, stream=True, timeout=30) as r:
            r.raise_for_status()
            with open(out_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=1048576):  # 1MB buffer for max throughput
                    if chunk:
                        f.write(chunk)
        return out_path
    except Exception as e:
        print(f"[StockDownloader] Download error for {url}: {e}")
        if out_path.exists():
            out_path.unlink()
        return None


def get_fallback_stock_video(scene_idx: int, query: str, duration: float) -> Dict[str, Any]:
    """
    Generates a crisp, cinematic 1080p 16:9 motion background with gradient lighting and motion
    using FFmpeg filter lavfi. Guarantees that the app always has 100% playable Full HD clips
    regardless of external network/API limits.
    """
    ffmpeg_exe = find_ffmpeg()
    target_duration = max(3.0, duration + 0.5)
    fallback_file = VIDEO_CACHE_DIR / f"cinematic_scene_{scene_idx % 8}.mp4"

    # Color themes matching cinematic stock moods
    palettes = [
        ("0x111625", "0x1a2639", "0x2d4059"),  # Dark moody blue
        ("0x1a120b", "0x3c2a21", "0xd5cea3"),  # Warm amber cinematic
        ("0x0d1b2a", "0x1b263b", "0x415a77"),  # Midnight navy
        ("0x1f1d36", "0x3f3351", "0x864879"),  # Moody purple dusk
        ("0x181818", "0x282828", "0x404040"),  # High contrast monochrome
        ("0x0f2027", "0x203a43", "0x2c5364"),  # Nordic dark teal
        ("0x2c3e50", "0x34495e", "0x7f8c8d"),  # Corporate clean slate
        ("0x141e30", "0x243b55", "0x141e30"),  # Deep ocean blue
    ]
    c1, c2, c3 = palettes[scene_idx % len(palettes)]

    if not fallback_file.exists() or fallback_file.stat().st_size < 5000:
        # Create a dynamic animated 1080p video with subtle pan/zoom effect using testsrc/gradients
        cmd = [
            ffmpeg_exe, "-y",
            "-f", "lavfi",
            "-i", f"gradients=s=1920x1080:c0={c1}:c1={c2}:c2={c3}:x0=w*0.5:y0=h*0.5:radius=900:speed=0.01:d={target_duration}",
            "-vf", "format=yuv420p,boxblur=8:1",
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-t", str(target_duration),
            "-r", "30",
            str(fallback_file)
        ]
        try:
            subprocess.run(cmd, capture_output=True, check=True)
        except Exception as e:
            # Even simpler fallback if gradients filter not supported in certain builds
            cmd_simple = [
                ffmpeg_exe, "-y",
                "-f", "lavfi",
                "-i", f"color=c={c1}:s=1920x1080:d={target_duration}:r=30",
                "-c:v", "libx264", "-preset", "ultrafast",
                str(fallback_file)
            ]
            subprocess.run(cmd_simple, capture_output=True)

    return {
        "provider": "studio_cinematic",
        "video_id": f"scene_{scene_idx}",
        "query": query,
        "file_path": str(fallback_file),
        "web_url": f"/media/cache/stock_videos/{fallback_file.name}",
        "thumbnail_url": "",
        "duration": target_duration,
        "width": 1920,
        "height": 1080,
        "is_fallback": True
    }
