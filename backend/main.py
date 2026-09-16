"""
VideoGen Studio — Backend Server
FastAPI application with all services for automated YouTube video generation.
"""
import os
import sys
import json
import uuid
import time
import sqlite3
import asyncio
import subprocess
import tempfile
import shutil
import re
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import aiohttp
import aiofiles
import httpx

# ─── App Setup ───────────────────────────────────────────────────────────────
app = FastAPI(title="VideoGen Studio", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
PROJECTS_DIR = DATA_DIR / "projects"
UPLOADS_DIR = DATA_DIR / "uploads"
CACHE_DIR = DATA_DIR / "cache"
EXPORTS_DIR = DATA_DIR / "exports"
DB_PATH = DATA_DIR / "videogen.db"
FRONTEND_DIR = BASE_DIR / "frontend"

for d in [DATA_DIR, PROJECTS_DIR, UPLOADS_DIR, CACHE_DIR, EXPORTS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# ─── WebSocket Manager ──────────────────────────────────────────────────────
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except:
                pass

manager = ConnectionManager()

# ─── Database ────────────────────────────────────────────────────────────────
def init_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS projects (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            niche TEXT,
            status TEXT DEFAULT 'created',
            audio_path TEXT,
            audio_duration REAL,
            transcript_json TEXT,
            scene_plan_json TEXT,
            composition_json TEXT,
            orientation TEXT DEFAULT '16:9',
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS stock_assets (
            id TEXT PRIMARY KEY,
            project_id TEXT,
            provider TEXT,
            provider_id TEXT,
            query TEXT,
            url TEXT,
            download_path TEXT,
            width INTEGER,
            height INTEGER,
            duration REAL,
            fps REAL,
            orientation TEXT,
            license_info TEXT,
            scene_index INTEGER,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (project_id) REFERENCES projects(id)
        );
        CREATE TABLE IF NOT EXISTS job_history (
            id TEXT PRIMARY KEY,
            project_id TEXT,
            action TEXT,
            status TEXT,
            details TEXT,
            started_at TEXT DEFAULT (datetime('now')),
            finished_at TEXT,
            FOREIGN KEY (project_id) REFERENCES projects(id)
        );
    """)
    conn.close()

init_db()

def get_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn

def get_setting(key: str, default: str = "") -> str:
    conn = get_db()
    row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    conn.close()
    return row["value"] if row else default

def set_setting(key: str, value: str):
    conn = get_db()
    conn.execute("INSERT OR REPLACE INTO settings (key, value, updated_at) VALUES (?, ?, datetime('now'))", (key, value))
    conn.commit()
    conn.close()

# ─── Models ──────────────────────────────────────────────────────────────────
class SettingsUpdate(BaseModel):
    groq_api_key: Optional[str] = None
    pexels_api_key: Optional[str] = None
    pixabay_api_key: Optional[str] = None

class ProjectCreate(BaseModel):
    name: str
    niche: str = ""
    orientation: str = "16:9"

class GenerateRequest(BaseModel):
    project_id: str
    orientation: str = "16:9"
    caption_style: Optional[dict] = None

# ─── FFmpeg Detection ────────────────────────────────────────────────────────
def detect_ffmpeg():
    """Detect FFmpeg installation and capabilities."""
    info = {"installed": False, "version": "not found", "path": "", "encoders": [], "hw_accel": []}
    try:
        result = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            info["installed"] = True
            first_line = result.stdout.split("\n")[0]
            info["version"] = first_line.strip()
            info["path"] = shutil.which("ffmpeg") or ""

        # Check encoders
        result2 = subprocess.run(["ffmpeg", "-encoders"], capture_output=True, text=True, timeout=10)
        if result2.returncode == 0:
            for enc in ["libx264", "libx265", "h264_nvenc", "hevc_nvenc", "h264_qsv", "h264_amf"]:
                if enc in result2.stdout:
                    info["encoders"].append(enc)
                    if "nvenc" in enc or "qsv" in enc or "amf" in enc:
                        info["hw_accel"].append(enc)
    except Exception as e:
        info["error"] = str(e)
    return info

def detect_ffprobe():
    """Detect ffprobe installation."""
    try:
        result = subprocess.run(["ffprobe", "-version"], capture_output=True, text=True, timeout=10)
        return result.returncode == 0
    except:
        return False

# ─── Stock Video Providers ───────────────────────────────────────────────────
class StockProvider:
    """Base class for stock video providers."""
    async def search(self, query: str, orientation: str = "landscape", per_page: int = 10) -> List[Dict]:
        raise NotImplementedError

class PexelsProvider(StockProvider):
    """Pexels API adapter."""
    BASE_URL = "https://api.pexels.com/videos/search"

    def __init__(self, api_key: str):
        self.api_key = api_key

    async def search(self, query: str, orientation: str = "landscape", per_page: int = 10) -> List[Dict]:
        headers = {"Authorization": self.api_key}
        params = {"query": query, "orientation": orientation, "per_page": per_page, "size": "large"}
        async with aiohttp.ClientSession() as session:
            for attempt in range(3):
                try:
                    async with session.get(self.BASE_URL, headers=headers, params=params, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            results = []
                            for video in data.get("videos", []):
                                # Get the best HD video file
                                best_file = None
                                for vf in video.get("video_files", []):
                                    if vf.get("quality") == "hd" or vf.get("height", 0) >= 720:
                                        if best_file is None or vf.get("height", 0) > best_file.get("height", 0):
                                            best_file = vf
                                if not best_file and video.get("video_files"):
                                    best_file = video["video_files"][0]
                                if best_file:
                                    results.append({
                                        "id": f"pexels_{video['id']}",
                                        "provider": "pexels",
                                        "provider_id": str(video["id"]),
                                        "url": best_file.get("link", ""),
                                        "width": best_file.get("width", 1920),
                                        "height": best_file.get("height", 1080),
                                        "duration": video.get("duration", 0),
                                        "fps": best_file.get("fps", 30),
                                        "orientation": orientation,
                                        "license_info": "Pexels License - Free for commercial use",
                                        "thumbnail": video.get("image", ""),
                                        "query": query
                                    })
                            return results
                        elif resp.status == 429:
                            await asyncio.sleep(2 ** attempt)
                            continue
                        else:
                            text = await resp.text()
                            return [{"error": f"Pexels API error {resp.status}: {text}"}]
                except asyncio.TimeoutError:
                    if attempt < 2:
                        await asyncio.sleep(2 ** attempt)
                    continue
                except Exception as e:
                    return [{"error": f"Pexels error: {str(e)}"}]
        return [{"error": "Pexels API: max retries exceeded"}]

class PixabayProvider(StockProvider):
    """Pixabay API adapter."""
    BASE_URL = "https://pixabay.com/api/videos/"

    def __init__(self, api_key: str):
        self.api_key = api_key

    async def search(self, query: str, orientation: str = "landscape", per_page: int = 10) -> List[Dict]:
        # Map orientation
        pix_orient = "horizontal" if orientation == "landscape" else "vertical"
        params = {
            "key": self.api_key,
            "q": query,
            "video_type": "film",
            "per_page": min(per_page, 200),
            "orientation": pix_orient,
            "safesearch": "true"
        }
        async with aiohttp.ClientSession() as session:
            for attempt in range(3):
                try:
                    async with session.get(self.BASE_URL, params=params, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            results = []
                            for hit in data.get("hits", []):
                                videos = hit.get("videos", {})
                                # Prefer large, then medium
                                vid = videos.get("large", videos.get("medium", videos.get("small", {})))
                                if vid and vid.get("url"):
                                    results.append({
                                        "id": f"pixabay_{hit['id']}",
                                        "provider": "pixabay",
                                        "provider_id": str(hit["id"]),
                                        "url": vid["url"],
                                        "width": vid.get("width", 1920),
                                        "height": vid.get("height", 1080),
                                        "duration": hit.get("duration", 0),
                                        "fps": 30,
                                        "orientation": orientation,
                                        "license_info": "Pixabay License - Free for commercial use",
                                        "thumbnail": f"https://i.vimeocdn.com/video/{hit.get('picture_id', '')}_640x360.jpg",
                                        "query": query
                                    })
                            return results
                        elif resp.status == 429:
                            await asyncio.sleep(2 ** attempt)
                            continue
                        else:
                            text = await resp.text()
                            return [{"error": f"Pixabay API error {resp.status}: {text}"}]
                except asyncio.TimeoutError:
                    if attempt < 2:
                        await asyncio.sleep(2 ** attempt)
                    continue
                except Exception as e:
                    return [{"error": f"Pixabay error: {str(e)}"}]
        return [{"error": "Pixabay API: max retries exceeded"}]

# ─── Groq Services ───────────────────────────────────────────────────────────
async def transcribe_audio_groq(audio_path: str, api_key: str) -> dict:
    """Transcribe audio using Groq's Whisper API with word-level timestamps."""
    url = "https://api.groq.com/openai/v1/audio/transcriptions"
    headers = {"Authorization": f"Bearer {api_key}"}

    async with aiohttp.ClientSession() as session:
        data = aiohttp.FormData()
        data.add_field("file", open(audio_path, "rb"), filename=os.path.basename(audio_path))
        data.add_field("model", "whisper-large-v3")
        data.add_field("response_format", "verbose_json")
        data.add_field("timestamp_granularities[]", "word")
        data.add_field("timestamp_granularities[]", "segment")

        async with session.post(url, headers=headers, data=data, timeout=aiohttp.ClientTimeout(total=120)) as resp:
            if resp.status == 200:
                result = await resp.json()
                return {
                    "success": True,
                    "text": result.get("text", ""),
                    "duration": result.get("duration", 0),
                    "language": result.get("language", ""),
                    "segments": result.get("segments", []),
                    "words": result.get("words", [])
                }
            else:
                error_text = await resp.text()
                return {"success": False, "error": f"Groq API error {resp.status}: {error_text}"}

async def generate_scene_plan(transcript: dict, niche: str, api_key: str) -> dict:
    """Use Groq LLM to generate high quality visual scene plan with search queries."""
    from groq import Groq

    client = Groq(api_key=api_key)
    duration = transcript.get("duration", 0)
    text = transcript.get("text", "")
    niche_str = niche or "educational"

    prompt = f"""You are a professional video editor AI.
Video Niche: {niche_str}
Total Duration: {duration:.1f} seconds
Narration:
{text[:2600]}

Generate 8 to 12 visual scenes covering the video from 0.0s to {duration:.1f}s.
For each scene provide:
- index: 0, 1, 2...
- start_time and end_time (contiguous across the {duration:.1f}s)
- text: brief summary
- search_queries: array of 2 concise visual search queries for stock video APIs (e.g. "scientist laboratory microscope", "happy group friends outdoors")
- mood: visual mood

Return ONLY valid JSON:
{{"scenes": [{{"index": 0, "start_time": 0.0, "end_time": 25.0, "text": "...", "search_queries": ["query 1", "query 2"], "mood": "inspiring"}}]}}"""

    raw = ""
    for model in ["qwen/qwen3.8-27b", "openai/gpt-oss-120b"]:
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=800
            )
            raw = resp.choices[0].message.content
            if raw:
                break
        except Exception:
            continue

    data = None
    if raw:
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(0))
            except Exception:
                pass

        if not data:
            last_brace = raw.rfind("}")
            if last_brace != -1:
                repaired = raw[:last_brace+1] + "\n]}"
                match2 = re.search(r'\{.*\}', repaired, re.DOTALL)
                if match2:
                    try:
                        data = json.loads(match2.group(0))
                    except Exception:
                        pass

    scenes = data.get("scenes", []) if data else []

    # If parsing failed, construct structured scenes deterministically
    if not scenes:
        step = 25.0
        num_scenes = max(int(duration // step), 1)
        for i in range(num_scenes):
            st = round(i * step, 1)
            et = round(min((i + 1) * step, duration), 1)
            scenes.append({
                "index": i,
                "start_time": st,
                "end_time": et,
                "text": text[i*100:(i+1)*100],
                "search_queries": [f"{niche_str} concept", "cinematic inspirational background"],
                "mood": "engaging"
            })

    # Ensure full coverage of audio duration
    if scenes and duration > 0:
        if scenes[-1]["end_time"] < duration:
            scenes.append({
                "index": len(scenes),
                "start_time": scenes[-1]["end_time"],
                "end_time": round(duration, 1),
                "text": "Conclusion",
                "search_queries": ["peaceful nature landscape sunset", f"{niche_str} motivation"],
                "mood": "concluding"
            })

    # Normalize indices
    for idx, sc in enumerate(scenes):
        sc["index"] = idx

    return {"success": True, "plan": {"scenes": scenes}}

# ─── Video Downloader ────────────────────────────────────────────────────────
async def download_video(url: str, save_path: str, timeout: int = 60) -> dict:
    """Download a video file with progress tracking."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=timeout)) as resp:
                if resp.status == 200:
                    total = int(resp.headers.get("Content-Length", 0))
                    downloaded = 0
                    async with aiofiles.open(save_path, "wb") as f:
                        async for chunk in resp.content.iter_chunked(8192):
                            await f.write(chunk)
                            downloaded += len(chunk)
                    return {"success": True, "path": save_path, "size": downloaded}
                else:
                    return {"success": False, "error": f"HTTP {resp.status}"}
    except Exception as e:
        return {"success": False, "error": str(e)}

# ─── Caption Engine (ASS) ───────────────────────────────────────────────────
def generate_ass_captions(words: list, style: dict = None, width: int = 1920, height: int = 1080) -> str:
    """Generate ASS subtitle file with word-by-word highlight animation."""
    if style is None:
        style = {}

    font_name = style.get("font", "Arial Black")
    font_size = style.get("size", 22)
    primary_color = style.get("color", "&H00FFFFFF")  # White
    active_color = style.get("active_color", "&H0000FFFF")  # Yellow
    outline_color = style.get("outline_color", "&H00000000")  # Black
    outline_width = style.get("outline", 3)
    shadow = style.get("shadow", 1)
    alignment = style.get("alignment", 2)  # Bottom center
    margin_v = style.get("margin_v", 60)

    ass_header = f"""[Script Info]
Title: VideoGen Captions
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font_name},{font_size},{primary_color},&H000000FF,{outline_color},&H80000000,-1,0,0,0,100,100,0,0,1,{outline_width},{shadow},{alignment},40,40,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    def format_time(seconds):
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        cs = int((seconds % 1) * 100)
        return f"{h}:{m:02d}:{s:02d}.{cs:02d}"

    events = []
    if not words:
        return ass_header

    # Group words into lines (max ~8 words per line for readability)
    lines = []
    current_line = []
    for w in words:
        current_line.append(w)
        word_text = w.get("word", w.get("text", ""))
        if len(current_line) >= 7 or word_text.rstrip().endswith(('.', '!', '?', ',')):
            lines.append(current_line)
            current_line = []
    if current_line:
        lines.append(current_line)

    for line_words in lines:
        if not line_words:
            continue
        line_start = line_words[0].get("start", 0)
        line_end = line_words[-1].get("end", line_start + 1)

        # Build karaoke line with word highlights
        parts = []
        for i, w in enumerate(line_words):
            word_text = w.get("word", w.get("text", "")).strip()
            if not word_text:
                continue
            w_start = w.get("start", line_start)
            w_dur = w.get("end", w_start + 0.3) - w_start
            dur_cs = max(int(w_dur * 100), 10)
            parts.append(f"{{\\kf{dur_cs}}}{word_text} ")

        text = "".join(parts).strip()
        start_str = format_time(line_start)
        end_str = format_time(line_end + 0.3)
        events.append(f"Dialogue: 0,{start_str},{end_str},Default,,0,0,0,,{text}")

    return ass_header + "\n".join(events)

# ─── FFmpeg Renderer ─────────────────────────────────────────────────────────
async def normalize_clip(input_path: str, output_path: str, width: int = 1920, height: int = 1080, fps: int = 30, duration: float = None) -> dict:
    """Normalize a video clip to consistent format and duration."""
    cmd = ["ffmpeg", "-y"]
    if duration and duration > 0:
        cmd.extend(["-stream_loop", "-1"])
    cmd.extend(["-i", input_path])
    if duration and duration > 0:
        cmd.extend(["-t", f"{duration:.2f}"])
    cmd.extend([
        "-vf", f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black,fps={fps}",
        "-c:v", "libx264", "-preset", "fast", "-crf", "18",
        "-an", "-pix_fmt", "yuv420p",
        output_path
    ])
    try:
        proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)
        if proc.returncode == 0:
            return {"success": True, "path": output_path}
        else:
            return {"success": False, "error": stderr.decode()[-500:]}
    except Exception as e:
        return {"success": False, "error": str(e)}

async def render_final_video(project_id: str, composition: dict, audio_path: str,
                               ass_path: str, output_path: str, orientation: str = "16:9") -> dict:
    """Render the final video with captions burned in."""
    if orientation == "16:9":
        w, h = 1920, 1080
    else:
        w, h = 1080, 1920

    clips = composition.get("clips", [])
    if not clips:
        return {"success": False, "error": "No clips in composition"}

    # Create concat file
    concat_path = str(CACHE_DIR / f"{project_id}_concat.txt")
    normalized_clips = []

    await manager.broadcast({"type": "progress", "project_id": project_id, "step": "normalizing", "progress": 0})

    for i, clip in enumerate(clips):
        clip_path = clip.get("path", "")
        if not os.path.exists(clip_path):
            continue
        clip_dur = clip.get("end_time", 0) - clip.get("start_time", 0)
        if clip_dur <= 0:
            clip_dur = clip.get("duration", 6.0)

        norm_path = str(CACHE_DIR / f"{project_id}_norm_{i}.mp4")
        result = await normalize_clip(clip_path, norm_path, w, h, duration=clip_dur)
        if result["success"]:
            normalized_clips.append(norm_path)
            progress = int((i + 1) / len(clips) * 50)
            await manager.broadcast({"type": "progress", "project_id": project_id, "step": "normalizing", "progress": progress})

    if not normalized_clips:
        return {"success": False, "error": "No clips could be normalized"}

    # Write concat file
    with open(concat_path, "w") as f:
        for cp in normalized_clips:
            cp_safe = cp.replace("\\", "/")
            f.write(f"file '{cp_safe}'\n")

    await manager.broadcast({"type": "progress", "project_id": project_id, "step": "rendering", "progress": 50})

    # Get audio duration
    probe_cmd = ["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", audio_path]
    try:
        proc = await asyncio.create_subprocess_exec(*probe_cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        stdout, _ = await proc.communicate()
        audio_duration = float(stdout.decode().strip())
    except:
        audio_duration = None

    # Build render command
    cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_path, "-i", audio_path]

    # Add caption filter if ASS file exists
    vf_filters = []
    if ass_path and os.path.exists(ass_path):
        ass_escaped = ass_path.replace("\\", "/").replace(":", "\\:")
        vf_filters.append(f"ass='{ass_escaped}'")

    if vf_filters:
        cmd.extend(["-vf", ",".join(vf_filters)])

    cmd.extend([
        "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-c:a", "aac", "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        "-shortest",
        "-movflags", "+faststart"
    ])

    if audio_duration:
        cmd.extend(["-t", str(audio_duration)])

    cmd.append(output_path)

    try:
        proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=600)

        await manager.broadcast({"type": "progress", "project_id": project_id, "step": "rendering", "progress": 90})

        if proc.returncode == 0:
            # Verify output
            verify_cmd = ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", "-show_streams", output_path]
            vproc = await asyncio.create_subprocess_exec(*verify_cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            vstdout, _ = await vproc.communicate()
            probe_info = json.loads(vstdout.decode()) if vproc.returncode == 0 else {}

            await manager.broadcast({"type": "progress", "project_id": project_id, "step": "complete", "progress": 100})

            return {
                "success": True,
                "path": output_path,
                "probe_info": probe_info
            }
        else:
            return {"success": False, "error": stderr.decode()[-1000:]}
    except asyncio.TimeoutError:
        return {"success": False, "error": "Render timed out (10 minutes)"}
    except Exception as e:
        return {"success": False, "error": str(e)}

# ─── API Routes ──────────────────────────────────────────────────────────────

# -- Static files
app.mount("/frontend", StaticFiles(directory=str(FRONTEND_DIR)), name="frontend")

@app.get("/")
async def root():
    return FileResponse(str(FRONTEND_DIR / "index.html"))

# -- WebSocket
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

# -- System Info
@app.get("/api/system")
async def system_info():
    ffmpeg = detect_ffmpeg()
    ffprobe = detect_ffprobe()
    return {
        "python_version": sys.version,
        "ffmpeg": ffmpeg,
        "ffprobe_available": ffprobe,
        "data_dir": str(DATA_DIR),
        "platform": sys.platform
    }

# -- Settings
@app.get("/api/settings")
async def get_settings():
    return {
        "groq_api_key": get_setting("groq_api_key"),
        "pexels_api_key": get_setting("pexels_api_key"),
        "pixabay_api_key": get_setting("pixabay_api_key"),
    }

@app.post("/api/settings")
async def update_settings(settings: SettingsUpdate):
    if settings.groq_api_key is not None:
        set_setting("groq_api_key", settings.groq_api_key)
    if settings.pexels_api_key is not None:
        set_setting("pexels_api_key", settings.pexels_api_key)
    if settings.pixabay_api_key is not None:
        set_setting("pixabay_api_key", settings.pixabay_api_key)
    return {"status": "saved"}

@app.post("/api/settings/test")
async def test_api_keys():
    """Test all configured API keys."""
    results = {}

    # Test Groq
    groq_key = get_setting("groq_api_key")
    if groq_key:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get("https://api.groq.com/openai/v1/models",
                                       headers={"Authorization": f"Bearer {groq_key}"},
                                       timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    results["groq"] = {"valid": resp.status == 200, "status": resp.status}
        except Exception as e:
            results["groq"] = {"valid": False, "error": str(e)}
    else:
        results["groq"] = {"valid": False, "error": "No key configured"}

    # Test Pexels
    pexels_key = get_setting("pexels_api_key")
    if pexels_key:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get("https://api.pexels.com/videos/search?query=test&per_page=1",
                                       headers={"Authorization": pexels_key},
                                       timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    results["pexels"] = {"valid": resp.status == 200, "status": resp.status}
        except Exception as e:
            results["pexels"] = {"valid": False, "error": str(e)}
    else:
        results["pexels"] = {"valid": False, "error": "No key configured"}

    # Test Pixabay
    pixabay_key = get_setting("pixabay_api_key")
    if pixabay_key:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"https://pixabay.com/api/videos/?key={pixabay_key}&q=test&per_page=3",
                                       timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    results["pixabay"] = {"valid": resp.status == 200, "status": resp.status}
        except Exception as e:
            results["pixabay"] = {"valid": False, "error": str(e)}
    else:
        results["pixabay"] = {"valid": False, "error": "No key configured"}

    return results

# -- Projects
@app.get("/api/projects")
async def list_projects():
    conn = get_db()
    rows = conn.execute("SELECT * FROM projects ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.post("/api/projects")
async def create_project(project: ProjectCreate):
    pid = str(uuid.uuid4())[:8]
    conn = get_db()
    conn.execute(
        "INSERT INTO projects (id, name, niche, orientation) VALUES (?, ?, ?, ?)",
        (pid, project.name, project.niche, project.orientation)
    )
    conn.commit()
    conn.close()
    proj_dir = PROJECTS_DIR / pid
    proj_dir.mkdir(exist_ok=True)
    return {"id": pid, "name": project.name}

@app.get("/api/projects/{project_id}")
async def get_project(project_id: str):
    conn = get_db()
    row = conn.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Project not found")
    return dict(row)

@app.delete("/api/projects/{project_id}")
async def delete_project(project_id: str):
    conn = get_db()
    conn.execute("DELETE FROM stock_assets WHERE project_id=?", (project_id,))
    conn.execute("DELETE FROM job_history WHERE project_id=?", (project_id,))
    conn.execute("DELETE FROM projects WHERE id=?", (project_id,))
    conn.commit()
    conn.close()
    proj_dir = PROJECTS_DIR / project_id
    if proj_dir.exists():
        shutil.rmtree(str(proj_dir), ignore_errors=True)
    return {"status": "deleted"}

# -- Audio Upload
@app.post("/api/projects/{project_id}/upload-audio")
async def upload_audio(project_id: str, file: UploadFile = File(...)):
    conn = get_db()
    row = conn.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Project not found")

    proj_dir = PROJECTS_DIR / project_id
    proj_dir.mkdir(exist_ok=True)
    audio_path = proj_dir / f"audio{Path(file.filename).suffix}"

    async with aiofiles.open(str(audio_path), "wb") as f:
        content = await file.read()
        await f.write(content)

    # Get duration via ffprobe
    duration = 0
    try:
        proc = await asyncio.create_subprocess_exec(
            "ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", str(audio_path),
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, _ = await proc.communicate()
        duration = float(stdout.decode().strip())
    except:
        pass

    conn.execute("UPDATE projects SET audio_path=?, audio_duration=?, updated_at=datetime('now') WHERE id=?",
                 (str(audio_path), duration, project_id))
    conn.commit()
    conn.close()

    return {"path": str(audio_path), "duration": duration, "filename": file.filename}

# -- Transcription
@app.post("/api/projects/{project_id}/transcribe")
async def transcribe_project(project_id: str):
    conn = get_db()
    row = conn.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Project not found")
    if not row["audio_path"]:
        conn.close()
        raise HTTPException(status_code=400, detail="No audio uploaded")

    groq_key = get_setting("groq_api_key")
    if not groq_key:
        conn.close()
        raise HTTPException(status_code=400, detail="Groq API key not configured")

    await manager.broadcast({"type": "status", "project_id": project_id, "step": "transcribing", "message": "Transcribing audio..."})

    # Log job
    job_id = str(uuid.uuid4())[:8]
    conn.execute("INSERT INTO job_history (id, project_id, action, status) VALUES (?, ?, 'transcribe', 'running')",
                 (job_id, project_id))
    conn.commit()

    result = await transcribe_audio_groq(row["audio_path"], groq_key)

    if result.get("success"):
        transcript_json = json.dumps(result)
        conn.execute("UPDATE projects SET transcript_json=?, status='transcribed', updated_at=datetime('now') WHERE id=?",
                     (transcript_json, project_id))
        conn.execute("UPDATE job_history SET status='completed', finished_at=datetime('now'), details=? WHERE id=?",
                     (f"Duration: {result.get('duration', 0):.1f}s, Words: {len(result.get('words', []))}", job_id))
        conn.commit()
        conn.close()
        await manager.broadcast({"type": "status", "project_id": project_id, "step": "transcribed", "message": "Transcription complete!"})
        return result
    else:
        conn.execute("UPDATE job_history SET status='failed', finished_at=datetime('now'), details=? WHERE id=?",
                     (result.get("error", "Unknown error"), job_id))
        conn.commit()
        conn.close()
        raise HTTPException(status_code=500, detail=result.get("error", "Transcription failed"))

# -- Scene Planning
@app.post("/api/projects/{project_id}/plan-scenes")
async def plan_scenes(project_id: str):
    conn = get_db()
    row = conn.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Project not found")
    if not row["transcript_json"]:
        conn.close()
        raise HTTPException(status_code=400, detail="Audio not transcribed yet")

    groq_key = get_setting("groq_api_key")
    if not groq_key:
        conn.close()
        raise HTTPException(status_code=400, detail="Groq API key not configured")

    await manager.broadcast({"type": "status", "project_id": project_id, "step": "planning", "message": "Planning scenes..."})

    transcript = json.loads(row["transcript_json"])
    niche = row["niche"] or "general"

    result = await generate_scene_plan(transcript, niche, groq_key)

    if result.get("success"):
        plan_json = json.dumps(result["plan"])
        conn.execute("UPDATE projects SET scene_plan_json=?, status='planned', updated_at=datetime('now') WHERE id=?",
                     (plan_json, project_id))
        conn.commit()
        conn.close()
        await manager.broadcast({"type": "status", "project_id": project_id, "step": "planned", "message": "Scene plan ready!"})
        return result["plan"]
    else:
        conn.close()
        raise HTTPException(status_code=500, detail=result.get("error", "Scene planning failed"))

# -- Stock Search & Fetch
@app.post("/api/projects/{project_id}/fetch-stock")
async def fetch_stock_footage(project_id: str):
    conn = get_db()
    row = conn.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Project not found")
    if not row["scene_plan_json"]:
        conn.close()
        raise HTTPException(status_code=400, detail="Scenes not planned yet")

    pexels_key = get_setting("pexels_api_key")
    pixabay_key = get_setting("pixabay_api_key")
    if not pexels_key and not pixabay_key:
        conn.close()
        raise HTTPException(status_code=400, detail="No stock API keys configured")

    orientation_map = {"16:9": "landscape", "9:16": "portrait"}
    orient = orientation_map.get(row["orientation"], "landscape")

    scene_plan = json.loads(row["scene_plan_json"])
    scenes = scene_plan.get("scenes", [])

    await manager.broadcast({"type": "status", "project_id": project_id, "step": "fetching", "message": "Fetching stock footage..."})

    providers = []
    if pexels_key:
        providers.append(PexelsProvider(pexels_key))
    if pixabay_key:
        providers.append(PixabayProvider(pixabay_key))

    proj_dir = PROJECTS_DIR / project_id / "clips"
    proj_dir.mkdir(parents=True, exist_ok=True)

    used_ids = set()
    composition_clips = []
    total_scenes = len(scenes)

    for scene_idx, scene in enumerate(scenes):
        queries = scene.get("search_queries", ["nature landscape"])
        best_asset = None

        for query in queries:
            if best_asset:
                break
            for provider in providers:
                results = await provider.search(query, orient, per_page=5)
                for asset in results:
                    if "error" in asset:
                        continue
                    if asset["id"] in used_ids:
                        continue
                    best_asset = asset
                    used_ids.add(asset["id"])
                    break
                if best_asset:
                    break

        # Fallback hierarchy: niche -> aesthetic generic
        if not best_asset:
            niche_val = row["niche"] or "cinematic"
            fallbacks = [
                f"{niche_val} background",
                f"{niche_val} footage",
                "inspirational cinematic landscape",
                "abstract motion background 4k"
            ]
            for fb_query in fallbacks:
                if best_asset:
                    break
                for provider in providers:
                    results = await provider.search(fb_query, orient, per_page=5)
                    for asset in results:
                        if "error" in asset or asset["id"] in used_ids:
                            continue
                        best_asset = asset
                        used_ids.add(asset["id"])
                        break
                    if best_asset:
                        break

        if best_asset and best_asset.get("url"):
            clip_filename = f"scene_{scene_idx}_{best_asset['provider']}_{best_asset['provider_id']}.mp4"
            clip_path = str(proj_dir / clip_filename)

            dl_result = await download_video(best_asset["url"], clip_path)
            if dl_result["success"]:
                # Save to DB
                conn.execute("""INSERT OR REPLACE INTO stock_assets 
                    (id, project_id, provider, provider_id, query, url, download_path, width, height, duration, fps, orientation, license_info, scene_index)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (best_asset["id"], project_id, best_asset["provider"], best_asset["provider_id"],
                     best_asset["query"], best_asset["url"], clip_path,
                     best_asset["width"], best_asset["height"], best_asset["duration"],
                     best_asset["fps"], best_asset["orientation"], best_asset["license_info"], scene_idx))

                composition_clips.append({
                    "scene_index": scene_idx,
                    "path": clip_path,
                    "start_time": scene.get("start_time", 0),
                    "end_time": scene.get("end_time", 0),
                    "asset_id": best_asset["id"],
                    "provider": best_asset["provider"],
                    "query": best_asset["query"],
                    "duration": best_asset["duration"]
                })

        progress = int((scene_idx + 1) / total_scenes * 100)
        await manager.broadcast({"type": "progress", "project_id": project_id, "step": "fetching", "progress": progress,
                                  "message": f"Scene {scene_idx + 1}/{total_scenes}"})

    # Save composition
    composition = {"clips": composition_clips, "orientation": row["orientation"]}
    conn.execute("UPDATE projects SET composition_json=?, status='footage_ready', updated_at=datetime('now') WHERE id=?",
                 (json.dumps(composition), project_id))
    conn.commit()
    conn.close()

    await manager.broadcast({"type": "status", "project_id": project_id, "step": "footage_ready",
                              "message": f"Downloaded {len(composition_clips)} clips!"})

    return {"clips_downloaded": len(composition_clips), "total_scenes": total_scenes, "composition": composition}

# -- Render Video
@app.post("/api/projects/{project_id}/render")
async def render_video(project_id: str, caption_style: dict = None):
    conn = get_db()
    row = conn.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Project not found")
    if not row["composition_json"]:
        conn.close()
        raise HTTPException(status_code=400, detail="No footage fetched yet")
    if not row["audio_path"]:
        conn.close()
        raise HTTPException(status_code=400, detail="No audio file")

    orientation = row["orientation"] or "16:9"
    w, h = (1920, 1080) if orientation == "16:9" else (1080, 1920)

    composition = json.loads(row["composition_json"])

    # Generate captions if transcript available
    ass_path = ""
    if row["transcript_json"]:
        transcript = json.loads(row["transcript_json"])
        words = transcript.get("words", [])
        if words:
            ass_content = generate_ass_captions(words, caption_style or {}, w, h)
            ass_path = str(PROJECTS_DIR / project_id / "captions.ass")
            with open(ass_path, "w", encoding="utf-8") as f:
                f.write(ass_content)

    # Render
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_filename = f"{row['name'].replace(' ', '_')}_{orientation.replace(':', 'x')}_{timestamp}.mp4"
    output_path = str(EXPORTS_DIR / output_filename)

    job_id = str(uuid.uuid4())[:8]
    conn.execute("INSERT INTO job_history (id, project_id, action, status) VALUES (?, ?, 'render', 'running')",
                 (job_id, project_id))
    conn.commit()
    audio_file_path = row["audio_path"]
    conn.close()

    await manager.broadcast({"type": "status", "project_id": project_id, "step": "rendering", "message": "Rendering video..."})

    result = await render_final_video(project_id, composition, audio_file_path, ass_path, output_path, orientation)

    conn2 = get_db()
    if result["success"]:
        conn2.execute("UPDATE projects SET status='rendered', updated_at=datetime('now') WHERE id=?", (project_id,))
        conn2.execute("UPDATE job_history SET status='completed', finished_at=datetime('now'), details=? WHERE id=?",
                     (f"Output: {output_filename}", job_id))
        conn2.commit()
        conn2.close()
        await manager.broadcast({"type": "status", "project_id": project_id, "step": "rendered", "message": "Video rendered!"})
        return {"success": True, "output_path": output_path, "filename": output_filename, "probe_info": result.get("probe_info", {})}
    else:
        conn2.execute("UPDATE job_history SET status='failed', finished_at=datetime('now'), details=? WHERE id=?",
                     (result.get("error", ""), job_id))
        conn2.commit()
        conn2.close()
        raise HTTPException(status_code=500, detail=result.get("error", "Render failed"))

# -- Full Pipeline (one-click)
@app.post("/api/projects/{project_id}/generate")
async def generate_full(project_id: str):
    """Run the full pipeline: transcribe → plan → fetch → render."""
    conn = get_db()
    row = conn.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Project not found")
    if not row["audio_path"]:
        conn.close()
        raise HTTPException(status_code=400, detail="Upload audio first")
    conn.close()

    steps_results = {}

    # Step 1: Transcribe
    try:
        await manager.broadcast({"type": "pipeline", "project_id": project_id, "step": 1, "total": 4, "name": "Transcription"})
        result = await transcribe_project(project_id)
        steps_results["transcription"] = "success"
    except HTTPException as e:
        return {"success": False, "failed_step": "transcription", "error": e.detail, "results": steps_results}

    # Step 2: Plan scenes
    try:
        await manager.broadcast({"type": "pipeline", "project_id": project_id, "step": 2, "total": 4, "name": "Scene Planning"})
        result = await plan_scenes(project_id)
        steps_results["scene_planning"] = "success"
    except HTTPException as e:
        return {"success": False, "failed_step": "scene_planning", "error": e.detail, "results": steps_results}

    # Step 3: Fetch stock
    try:
        await manager.broadcast({"type": "pipeline", "project_id": project_id, "step": 3, "total": 4, "name": "Stock Footage"})
        result = await fetch_stock_footage(project_id)
        steps_results["stock_footage"] = "success"
    except HTTPException as e:
        return {"success": False, "failed_step": "stock_footage", "error": e.detail, "results": steps_results}

    # Step 4: Render
    try:
        await manager.broadcast({"type": "pipeline", "project_id": project_id, "step": 4, "total": 4, "name": "Rendering"})
        result = await render_video(project_id)
        steps_results["render"] = "success"
    except HTTPException as e:
        return {"success": False, "failed_step": "render", "error": e.detail, "results": steps_results}

    return {"success": True, "results": steps_results, "render_output": result}

# -- Job History
@app.get("/api/jobs")
async def list_jobs():
    conn = get_db()
    rows = conn.execute("""
        SELECT j.*, p.name as project_name FROM job_history j
        LEFT JOIN projects p ON j.project_id = p.id
        ORDER BY j.started_at DESC LIMIT 50
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]

# -- Stock Search (standalone)
@app.get("/api/stock/search")
async def search_stock(query: str, provider: str = "all", orientation: str = "landscape"):
    results = []
    if provider in ("all", "pexels"):
        pexels_key = get_setting("pexels_api_key")
        if pexels_key:
            p = PexelsProvider(pexels_key)
            results.extend(await p.search(query, orientation))
    if provider in ("all", "pixabay"):
        pixabay_key = get_setting("pixabay_api_key")
        if pixabay_key:
            p = PixabayProvider(pixabay_key)
            results.extend(await p.search(query, orientation))
    return results

# -- Serve exported files
@app.get("/api/exports/{filename}")
async def serve_export(filename: str):
    path = EXPORTS_DIR / filename
    if path.exists():
        return FileResponse(str(path), media_type="video/mp4", filename=filename)
    raise HTTPException(status_code=404, detail="File not found")

# ─── Entry Point ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=9000, log_level="info")
