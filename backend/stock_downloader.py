import os
import re
import hashlib
import requests
import subprocess
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Optional
from .config import CACHE_DIR, TEMP_DIR, find_ffmpeg, find_ffprobe, load_settings

VIDEO_CACHE_DIR = CACHE_DIR / "stock_videos"
VIDEO_CACHE_DIR.mkdir(parents=True, exist_ok=True)


import threading


def trim_and_fit_clip(raw_path: str, target_dur: float, scene_id: int) -> str:
    """
    Intelligently crops and trims a downloaded stock video to the EXACT scene duration.
    - Strips all excess video beyond the sentence duration so clips never spill into next sentences.
    - If the clip is shorter than the sentence, applies seamless looping (-stream_loop -1).
    - Enforces clean 1920x1080 16:9 Full HD center-crop, 30fps, setsar=1.
    - Strips native audio (-an) to prevent ambient noise clash.
    """
    if not raw_path or not os.path.exists(raw_path):
        return raw_path

    ffmpeg_exe = find_ffmpeg()
    target_dur = max(0.5, round(float(target_dur), 2))
    
    probe_dur = 0.0
    ffprobe_exe = find_ffprobe()
    try:
        p_cmd = [ffprobe_exe, "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(raw_path)]
        res = subprocess.run(p_cmd, capture_output=True, text=True, check=True)
        probe_dur = float(res.stdout.strip())
    except Exception:
        probe_dur = 0.0

    scene_clip_dir = CACHE_DIR / "scene_clips"
    scene_clip_dir.mkdir(parents=True, exist_ok=True)
    
    path_hash = hashlib.md5(f"{raw_path}_{target_dur}".encode("utf-8")).hexdigest()[:8]
    out_name = f"sc_{scene_id:04d}_{path_hash}.mp4"
    out_path = scene_clip_dir / out_name

    if out_path.exists() and out_path.stat().st_size > 1000:
        return str(out_path)

    # Content-Aware Action Window Selection:
    # Stock footage typically starts with 1-2s camera prep or stabilizer shake.
    # The primary planned action and subject motion occurs in the middle 35% to 70% of the footage.
    start_offset = 0.0
    if probe_dur >= (target_dur + 2.0):
        headroom = probe_dur - target_dur
        # Center in the golden action zone (~40% through available headroom)
        candidate_offset = round(headroom * 0.40, 2)
        start_offset = max(1.5, min(candidate_offset, round(headroom - 0.4, 2)))

    cmd = [ffmpeg_exe, "-y"]
    if probe_dur > 0 and probe_dur < (target_dur + start_offset):
        cmd.extend(["-stream_loop", "-1"])
        start_offset = 0.0

    if start_offset > 0:
        cmd.extend(["-ss", f"{start_offset:.2f}"])

    cmd.extend([
        "-i", str(raw_path),
        "-t", f"{target_dur:.2f}",
        "-vf", "scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,setsar=1,fps=30",
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-crf", "18",
        "-pix_fmt", "yuv420p",
        "-an",
        str(out_path)
    ])
    try:
        subprocess.run(cmd, capture_output=True, check=True)
        return str(out_path)
    except Exception as e:
        print(f"[StockDownloader] Notice: trimming raw clip failed: {e}, falling back to raw path")
        return raw_path


def download_scenes_concurrently(scenes: List[Dict[str, Any]], progress_callback=None) -> List[Dict[str, Any]]:
    """
    Downloads stock videos for all scenes in parallel using a ThreadPoolExecutor.
    Includes visual diversity tracking to prevent adjacent scenes from getting identical clips.
    """
    settings = load_settings()
    num_workers = int(settings.get("workers", 6))
    
    print(f"[StockDownloader] Launching parallel download for {len(scenes)} scenes across {num_workers} workers...")

    completed_scenes = [None] * len(scenes)
    completed_count = 0
    lock = threading.Lock()
    # Visual diversity: track recently used video IDs to prevent adjacent repetition
    used_video_ids = set()

    def process_scene(scene_item):
        nonlocal completed_count
        scene_idx = scene_item["id"]
        tags = scene_item.get("search_tags", ["cinematic inspiring"])
        selected_tag = scene_item.get("selected_tag") or tags[0]
        duration = float(scene_item.get("duration", 4.0))

        clip_data = None
        # Try selected tag first, then other candidate tags
        sentence_text = scene_item.get("text", "")
        search_candidates = [selected_tag] + [t for t in tags if t != selected_tag]
        for candidate in search_candidates:
            clip_data = find_and_download_stock_video(candidate, min_duration=duration, sentence_context=sentence_text)
            if clip_data:
                vid_id = clip_data.get("video_id")
                # Visual diversity check: if this video was already used recently,
                # try the next tag to force a different visual
                with lock:
                    if vid_id and vid_id in used_video_ids and len(search_candidates) > 1:
                        continue  # Try next tag for visual variety
                    if vid_id:
                        used_video_ids.add(vid_id)
                break

        # If external APIs returned nothing (e.g. no key or rate limited), generate offline fallback
        if not clip_data:
            clip_data = get_fallback_stock_video(scene_idx, selected_tag, duration)

        # Intelligently trim the clip to the exact sentence duration (stripping excess video)
        if clip_data and clip_data.get("file_path"):
            trimmed_path = trim_and_fit_clip(clip_data["file_path"], duration, scene_idx)
            clip_data["raw_file_path"] = clip_data["file_path"]
            clip_data["file_path"] = trimmed_path
            clip_data["duration"] = duration

        scene_item["video_clip"] = clip_data
        scene_item["fallback_used"] = bool(clip_data and clip_data.get("is_fallback"))
        scene_item["status"] = "ready"

        with lock:
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


from urllib3.util import Retry
from requests.adapters import HTTPAdapter

# Create persistent session with connection pooling and 429 rate limit backoff
SESSION = requests.Session()
retries = Retry(total=2, backoff_factor=0.8, status_forcelist=[429, 500, 502, 503, 504], raise_on_status=False)
adapter = HTTPAdapter(pool_connections=32, pool_maxsize=32, max_retries=retries)
SESSION.mount("https://", adapter)
SESSION.mount("http://", adapter)


def _score_candidate(duration: float, width: int, height: int, target_dur: float, query_words: List[str], metadata_text: str) -> float:
    """Ranks candidate video clips based on resolution, duration headroom, and keyword match."""
    score = 0.0
    # 1. Orientation & Resolution (40 pts)
    if width >= 1920 and height == 1080:
        score += 40.0
    elif width >= 1280 and width > height:
        score += 25.0
    elif width > 0 and width < height:
        score -= 60.0  # Penalize vertical clips in 16:9 widescreen mode

    # 2. Duration Headroom Fit (30 pts)
    # Sweet spot: clip is 1.5x - 3.5x target_dur so action window trimming captures the peak movement
    if target_dur <= duration <= (target_dur * 3.5):
        score += 30.0
    elif (target_dur * 3.5) < duration <= 35.0:
        score += 15.0
    elif duration > 35.0:
        score += 5.0
    elif duration < target_dur:
        score += 0.0  # Shorter than sentence requires looping

    # 3. Keyword / Semantic Overlap (30 pts)
    meta_lower = metadata_text.lower()
    matched = sum(1 for w in query_words if len(w) >= 3 and w in meta_lower)
    score += min(30.0, matched * 10.0)

    return score


def find_and_download_stock_video(query: str, min_duration: float = 3.0, sentence_context: str = "") -> Optional[Dict[str, Any]]:
    """
    Cascading Fallback Provider Architecture:
    1. Queries primary provider (Pexels). If candidates match, returns immediately!
    2. Only if primary returns 0 results or encounters a 429 rate limit, cascades to Pixabay.
    3. If Pixabay fails, cascades to free archives (Coverr / NASA / Wikimedia).
    Eliminates uncontrolled API fan-out, stops blocking threads, and preserves API quotas.
    """
    settings = load_settings()
    provider_pref = settings.get("video_provider", "all")
    
    pexels_key = settings.get("pexels_api_key", "").strip()
    pixabay_key = settings.get("pixabay_api_key", "").strip()
    coverr_key = settings.get("coverr_api_key", "").strip()
    videvo_key = settings.get("videvo_api_key", "").strip()
    nasa_enabled = bool(settings.get("nasa_api_key") or settings.get("nasa_enabled", True))
    wiki_enabled = bool(settings.get("wikimedia_video_enabled", False))
    webhook_url = settings.get("custom_stock_webhook", "").strip()

    # Priority 1: Pexels (best quality)
    if (provider_pref in ("all", "pexels")) and pexels_key:
        clip = _search_pexels(query, pexels_key, min_duration, sentence_context)
        if clip:
            return clip

    # Priority 2: Pixabay (fast secondary fallback)
    if (provider_pref in ("all", "pixabay")) and pixabay_key:
        clip = _search_pixabay(query, pixabay_key, min_duration, sentence_context)
        if clip:
            return clip

    # Priority 3: Coverr (free clips)
    if (provider_pref in ("all", "coverr")) and coverr_key:
        clip = _search_coverr(query, coverr_key, min_duration)
        if clip:
            return clip

    # Priority 4: Videvo
    if (provider_pref in ("all", "videvo")) and videvo_key:
        clip = _search_videvo(query, videvo_key, min_duration)
        if clip:
            return clip

    # Priority 5: NASA Open Video
    if (provider_pref in ("all", "nasa")) and nasa_enabled:
        clip = _search_nasa(query, min_duration)
        if clip:
            return clip

    # Priority 6: Wikimedia Commons
    if (provider_pref in ("all", "wikimedia")) and wiki_enabled:
        clip = _search_wikimedia(query, min_duration)
        if clip:
            return clip

    # Priority 7: Webhook Proxy
    if webhook_url:
        clip = _search_custom_webhook(query, webhook_url, settings.get("rapidapi_stock_key", ""), min_duration)
        if clip:
            return clip

    return None


def _search_pexels(query: str, api_key: str, min_duration: float, sentence_context: str = "") -> Optional[Dict[str, Any]]:
    clean_query = re.sub(r'#', '', query).strip()
    url = f"https://api.pexels.com/videos/search?query={requests.utils.quote(clean_query)}&orientation=landscape&size=large&per_page=15"
    headers = {"Authorization": api_key, "User-Agent": "VideoGen/1.0"}
    try:
        r = SESSION.get(url, headers=headers, timeout=7)
        if r.status_code == 429:
            print(f"[StockDownloader] ⚠️ Pexels API rate limit (429) hit for '{clean_query}'. Gracefully cascading to Pixabay...")
            return None
        if r.status_code != 200:
            return None
        data = r.json()
        videos = data.get("videos", [])
        if not videos:
            return None

        query_tokens = re.findall(r'\b[a-zA-Z]{3,}\b', (clean_query + " " + sentence_context).lower())

        # Candidate Scoring & Ranking across all 15 results
        scored = []
        for vid in videos:
            vfiles = vid.get("video_files", [])
            best_file = None
            for vf in vfiles:
                w = vf.get("width") or 0
                h = vf.get("height") or 0
                link = vf.get("link")
                if link and w >= 1280 and (w > h):
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
                    metadata_text=meta_text
                )
                scored.append((score, vid, best_file))

        scored.sort(key=lambda x: x[0], reverse=True)

        for score, vid, best_file in scored:
            download_url = best_file["link"]
            local_path = _download_file_cached(download_url, f"pexels_{vid['id']}.mp4")
            if local_path and os.path.exists(local_path):
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
    return None


def _search_pixabay(query: str, api_key: str, min_duration: float, sentence_context: str = "") -> Optional[Dict[str, Any]]:
    clean_query = re.sub(r'#', '', query).strip()
    url = f"https://pixabay.com/api/videos/?key={api_key}&q={requests.utils.quote(clean_query)}&video_type=film&orientation=horizontal&per_page=15"
    headers = {"User-Agent": "VideoGen/1.0"}
    try:
        r = SESSION.get(url, headers=headers, timeout=7)
        if r.status_code == 429:
            print(f"[StockDownloader] ⚠️ Pixabay API rate limit (429) hit for '{clean_query}'. Cascading to backup provider...")
            return None
        if r.status_code != 200:
            return None
        data = r.json()
        hits = data.get("hits", [])
        if not hits:
            return None

        query_tokens = re.findall(r'\b[a-zA-Z]{3,}\b', (clean_query + " " + sentence_context).lower())

        scored = []
        for h in hits:
            vid_files = h.get("videos", {})
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
                metadata_text=tags_text
            )
            scored.append((score, h, selected))

        scored.sort(key=lambda x: x[0], reverse=True)

        for score, h, selected in scored:
            dl_url = selected["url"]
            local_path = _download_file_cached(dl_url, f"pixabay_{h['id']}.mp4")
            if local_path and os.path.exists(local_path):
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
    return None
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
    pexels_key = settings.get("pexels_api_key", "").strip()
    pixabay_key = settings.get("pixabay_api_key", "").strip()
    clean_query = re.sub(r'#', '', query).strip()
    results = []

    if pexels_key:
        try:
            url = f"https://api.pexels.com/videos/search?query={requests.utils.quote(clean_query)}&orientation=landscape&size=large&per_page={limit}"
            r = requests.get(url, headers={"Authorization": pexels_key}, timeout=10)
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
        except Exception as e:
            print(f"[StockDownloader] Alternative search Pexels error: {e}")

    if pixabay_key and len(results) < limit:
        try:
            url = f"https://pixabay.com/api/videos/?key={pixabay_key}&q={requests.utils.quote(clean_query)}&video_type=film&per_page={limit}"
            r = requests.get(url, timeout=10)
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
        except Exception as e:
            print(f"[StockDownloader] Alternative search Pixabay error: {e}")

    return results


def _download_file_cached(url: str, filename: str) -> Path:
    """Downloads a file if not already in local cache."""
    # Hash the URL to avoid collision
    url_hash = hashlib.md5(url.encode('utf-8')).hexdigest()[:10]
    out_path = VIDEO_CACHE_DIR / f"{url_hash}_{filename}"
    if out_path.exists() and out_path.stat().st_size > 10000:
        return out_path

    try:
        with SESSION.get(url, stream=True, timeout=30) as r:
            r.raise_for_status()
            with open(out_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=262144):
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
        "thumbnail_url": "",
        "duration": target_duration,
        "width": 1920,
        "height": 1080
    }
