import os
import json
import time
import shutil
import threading
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from .config import (
    BASE_DIR, DATA_DIR, CACHE_DIR, OUTPUT_DIR, TEMP_DIR,
    load_settings, save_settings, find_ffmpeg
)
from .transcriber import transcribe_audio, get_audio_duration
from .scene_analyzer import build_scenes
from .stock_downloader import download_scenes_concurrently, search_alternative_clips
from .subtitle_generator import generate_ass_subtitles, PRESET_STYLES
from .video_renderer import render_final_video
from .capcut_exporter import export_project_to_capcut, find_capcut_executable, get_capcut_drafts_dir

app = FastAPI(title="VideoGen Studio API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory storage for active projects
ACTIVE_PROJECTS: Dict[str, Dict[str, Any]] = {}
PROJECTS_FILE = DATA_DIR / "projects_history.json"


def load_projects_history() -> List[Dict[str, Any]]:
    if PROJECTS_FILE.exists():
        try:
            with open(PROJECTS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return []


def save_project_to_history(proj: Dict[str, Any]):
    history = load_projects_history()
    # Update or prepend
    history = [p for p in history if p.get("id") != proj.get("id")]
    history.insert(0, proj)
    with open(PROJECTS_FILE, "w", encoding="utf-8") as f:
        json.dump(history[:50], f, indent=2)


def _to_media_url(file_path: Any) -> str:
    """Safely converts a disk path under DATA_DIR to a /media/... web URL."""
    if not file_path:
        return ""
    p = Path(file_path)
    try:
        rel = p.resolve().relative_to(DATA_DIR.resolve()).as_posix()
        return f"/media/{rel}"
    except Exception:
        return f"/media/cache/stock_videos/{p.name}"



# ======================== SETTINGS ENDPOINTS ========================

@app.get("/api/settings")
def get_settings():
    return load_settings()


@app.post("/api/settings")
def update_settings(payload: Dict[str, Any]):
    updated = save_settings(payload)
    return {"status": "success", "settings": updated}


@app.post("/api/test-apis")
def test_apis():
    import requests
    settings = load_settings()
    results = {}

    # 1. Test Pexels
    p_key = settings.get("pexels_api_key", "").strip()
    if p_key:
        try:
            r = requests.get(
                "https://api.pexels.com/videos/search?query=nature&per_page=1",
                headers={"Authorization": p_key},
                timeout=6
            )
            results["pexels"] = {"status": "ok" if r.status_code == 200 else "error", "code": r.status_code}
        except Exception as e:
            results["pexels"] = {"status": "error", "error": str(e)}
    else:
        results["pexels"] = {"status": "unconfigured"}

    # 2. Test Pixabay
    pix_key = settings.get("pixabay_api_key", "").strip()
    if pix_key:
        try:
            r = requests.get(
                f"https://pixabay.com/api/videos/?key={pix_key}&q=nature&per_page=3",
                timeout=6
            )
            results["pixabay"] = {"status": "ok" if r.status_code == 200 else "error", "code": r.status_code}
        except Exception as e:
            results["pixabay"] = {"status": "error", "error": str(e)}
    else:
        results["pixabay"] = {"status": "unconfigured"}

    # 3. Test Coverr
    c_key = settings.get("coverr_api_key", "").strip()
    if c_key:
        try:
            r = requests.get(
                "https://api.coverr.co/videos?query=nature&urls=mp4",
                headers={"Authorization": f"Bearer {c_key}"},
                timeout=6
            )
            results["coverr"] = {"status": "ok" if r.status_code == 200 else "error", "code": r.status_code}
        except Exception as e:
            results["coverr"] = {"status": "error", "error": str(e)}
    else:
        results["coverr"] = {"status": "unconfigured"}

    # 4. Test Videvo
    v_key = settings.get("videvo_api_key", "").strip()
    if v_key:
        try:
            r = requests.get(
                f"https://api.videvo.net/v1/videos?q=nature&api_key={v_key}",
                timeout=6
            )
            results["videvo"] = {"status": "ok" if r.status_code == 200 else "error", "code": r.status_code}
        except Exception as e:
            results["videvo"] = {"status": "error", "error": str(e)}
    else:
        results["videvo"] = {"status": "unconfigured"}

    # 5. Test NASA Open Media (Free public domain)
    try:
        r = requests.get("https://images-api.nasa.gov/search?q=earth&media_type=video", timeout=6)
        results["nasa"] = {"status": "ok" if r.status_code == 200 else "error", "code": r.status_code}
    except Exception as e:
        results["nasa"] = {"status": "error", "error": str(e)}

    # 6. Test Wikimedia Commons (Free open video)
    try:
        r = requests.get(
            "https://commons.wikimedia.org/w/api.php?action=query&generator=search&gsrsearch=nature+filetype:video&prop=imageinfo&format=json",
            headers={"User-Agent": "VideoGen/1.0"},
            timeout=6
        )
        results["wikimedia"] = {"status": "ok" if r.status_code == 200 else "error", "code": r.status_code}
    except Exception as e:
        results["wikimedia"] = {"status": "error", "error": str(e)}

    # 7. Test Custom Webhook / RapidAPI
    hook = settings.get("custom_stock_webhook", "").strip()
    if hook:
        results["custom_webhook"] = {"status": "configured", "url": hook}
    else:
        results["custom_webhook"] = {"status": "unconfigured"}

    # 8. Test Groq Whisper
    g_key = settings.get("groq_api_key", "").strip()
    if g_key:
        try:
            r = requests.get(
                "https://api.groq.com/openai/v1/models",
                headers={"Authorization": f"Bearer {g_key}"},
                timeout=6
            )
            results["groq"] = {"status": "ok" if r.status_code == 200 else "error", "code": r.status_code}
        except Exception as e:
            results["groq"] = {"status": "error", "error": str(e)}
    else:
        results["groq"] = {"status": "unconfigured"}

    # 9. Test OpenAI
    o_key = settings.get("openai_api_key", "").strip()
    if o_key:
        try:
            r = requests.get(
                "https://api.openai.com/v1/models",
                headers={"Authorization": f"Bearer {o_key}"},
                timeout=6
            )
            results["openai"] = {"status": "ok" if r.status_code == 200 else "error", "code": r.status_code}
        except Exception as e:
            results["openai"] = {"status": "error", "error": str(e)}
    else:
        results["openai"] = {"status": "unconfigured"}

    return results


# ======================== PRESETS ENDPOINT ========================

@app.get("/api/presets")
def get_presets():
    return PRESET_STYLES


# ======================== AUDIO UPLOAD & GENERATION ========================

@app.post("/api/upload-audio")
async def upload_audio(file: UploadFile = File(...)):
    ext = Path(file.filename).suffix or ".mp3"
    filename = f"audio_{int(time.time())}{ext}"
    dest = TEMP_DIR / filename
    with open(dest, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    duration = get_audio_duration(str(dest))
    return {
        "status": "success",
        "filename": filename,
        "original_name": file.filename,
        "duration": round(duration, 2),
        "url": f"/media/temp/{filename}"
    }


import threading

ACTIVE_JOBS: Dict[str, Dict[str, Any]] = {}


class GenerateRequest(BaseModel):
    audio_filename: str
    niche: str = "Motivation Psychology"
    pipeline: str = "Main"


@app.post("/api/start-generate")
def start_generation_job(req: GenerateRequest):
    audio_path = TEMP_DIR / req.audio_filename
    if not audio_path.exists():
        raise HTTPException(status_code=404, detail="Audio file not found")

    job_id = f"job_{int(time.time() * 1000)}"
    ACTIVE_JOBS[job_id] = {
        "status": "processing",
        "stage": "transcribing",
        "stage_title": "Transcribing Voiceover Speech...",
        "stage_desc": "Analyzing speech waveforms and generating word micro-timestamps...",
        "percent": 10,
        "completed_scenes": 0,
        "total_scenes": 0,
        "current_scene_title": "",
        "project": None,
        "error": None
    }

    def run_job():
        try:
            # 1. Transcribe
            ACTIVE_JOBS[job_id]["stage"] = "transcribing"
            ACTIVE_JOBS[job_id]["stage_title"] = "Transcribing Speech & Timestamps..."
            ACTIVE_JOBS[job_id]["stage_desc"] = "Extracting sentence and word-level micro timing..."
            ACTIVE_JOBS[job_id]["percent"] = 15

            transcription = transcribe_audio(str(audio_path), niche=req.niche)
            
            # 2. Scene Analysis
            ACTIVE_JOBS[job_id]["stage"] = "analyzing"
            ACTIVE_JOBS[job_id]["stage_title"] = "Semantic Scene & Visual Query Tagging..."
            ACTIVE_JOBS[job_id]["stage_desc"] = "Contextual visual search tags matching what is being spoken..."
            ACTIVE_JOBS[job_id]["percent"] = 25

            scenes = build_scenes(transcription, niche=req.niche)
            total_scenes = len(scenes)
            ACTIVE_JOBS[job_id]["total_scenes"] = total_scenes

            # 3. Parallel Downloads with live progress callback
            ACTIVE_JOBS[job_id]["stage"] = "downloading"
            ACTIVE_JOBS[job_id]["stage_title"] = f"Multi-Worker Parallel Download (0 / {total_scenes})..."
            ACTIVE_JOBS[job_id]["stage_desc"] = f"Querying stock APIs concurrently across workers..."

            def on_progress(done, total, scene_item):
                pct = int(25 + (done / total) * 65)
                ACTIVE_JOBS[job_id]["completed_scenes"] = done
                ACTIVE_JOBS[job_id]["total_scenes"] = total
                ACTIVE_JOBS[job_id]["percent"] = pct
                ACTIVE_JOBS[job_id]["current_scene_title"] = scene_item.get("text", "")[:45]
                ACTIVE_JOBS[job_id]["stage_title"] = f"Downloading Stock Videos ({done} / {total})..."
                ACTIVE_JOBS[job_id]["stage_desc"] = f"Worker downloaded Scene #{scene_item.get('scene_number')}: \"{scene_item.get('text','')[:35]}...\""

            processed_scenes = download_scenes_concurrently(scenes, progress_callback=on_progress)

            # Web URLs
            for sc in processed_scenes:
                if sc.get("video_clip") and sc["video_clip"].get("file_path"):
                    sc["video_clip"]["web_url"] = _to_media_url(sc["video_clip"]["file_path"])

            project_id = f"proj_{int(time.time())}"
            project_data = {
                "id": project_id,
                "name": req.audio_filename.rsplit('.', 1)[0],
                "niche": req.niche,
                "pipeline": req.pipeline,
                "audio_filename": req.audio_filename,
                "audio_path": str(audio_path),
                "audio_url": f"/media/temp/{req.audio_filename}",
                "duration": transcription.get("duration", 30.0),
                "scenes": processed_scenes,
                "created_at": time.strftime("%b %d, %Y %I:%M %p"),
                "status": "ready_for_preview"
            }

            ACTIVE_PROJECTS[project_id] = project_data
            save_project_to_history(project_data)

            ACTIVE_JOBS[job_id]["status"] = "completed"
            ACTIVE_JOBS[job_id]["percent"] = 100
            ACTIVE_JOBS[job_id]["stage"] = "finalizing"
            ACTIVE_JOBS[job_id]["stage_title"] = "Interactive Preview Ready!"
            ACTIVE_JOBS[job_id]["stage_desc"] = "All stock clips downloaded and synchronized."
            ACTIVE_JOBS[job_id]["project"] = project_data

        except Exception as e:
            import traceback
            traceback.print_exc()
            ACTIVE_JOBS[job_id]["status"] = "error"
            ACTIVE_JOBS[job_id]["error"] = str(e)

    threading.Thread(target=run_job, daemon=True).start()
    return {"status": "started", "job_id": job_id}


@app.get("/api/job-progress/{job_id}")
def get_job_progress(job_id: str):
    job = ACTIVE_JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@app.post("/api/generate")
def generate_project(req: GenerateRequest):
    # Synchronous fallback endpoint
    audio_path = TEMP_DIR / req.audio_filename
    if not audio_path.exists():
        raise HTTPException(status_code=404, detail="Audio file not found")

    project_id = f"proj_{int(time.time())}"
    transcription = transcribe_audio(str(audio_path), niche=req.niche)
    scenes = build_scenes(transcription, niche=req.niche)
    processed_scenes = download_scenes_concurrently(scenes)

    for sc in processed_scenes:
        if sc.get("video_clip") and sc["video_clip"].get("file_path"):
            sc["video_clip"]["web_url"] = _to_media_url(sc["video_clip"]["file_path"])

    project_data = {
        "id": project_id,
        "name": req.audio_filename.rsplit('.', 1)[0],
        "niche": req.niche,
        "pipeline": req.pipeline,
        "audio_filename": req.audio_filename,
        "audio_path": str(audio_path),
        "audio_url": f"/media/temp/{req.audio_filename}",
        "duration": transcription.get("duration", 30.0),
        "scenes": processed_scenes,
        "created_at": time.strftime("%b %d, %Y %I:%M %p"),
        "status": "ready_for_preview"
    }

    ACTIVE_PROJECTS[project_id] = project_data
    save_project_to_history(project_data)

    return {"status": "success", "project": project_data}


# ======================== SCENE CLIP SEARCH & SWAP ========================

@app.get("/api/search-clips")
def search_clips(query: str):
    results = search_alternative_clips(query)
    return {"query": query, "results": results}


class SwapClipRequest(BaseModel):
    project_id: str
    scene_id: int
    download_url: str
    provider: str = "pexels"
    thumbnail_url: str = ""


@app.post("/api/swap-clip")
def swap_clip(req: SwapClipRequest):
    project = ACTIVE_PROJECTS.get(req.project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Download alternative clip
    from .stock_downloader import _download_file_cached, trim_and_fit_clip
    local_path = _download_file_cached(req.download_url, f"swap_{req.provider}_{int(time.time())}.mp4")
    if not local_path or not os.path.exists(local_path):
        raise HTTPException(status_code=500, detail="Failed to download replacement clip")

    # Update scene clip and trim it to exact sentence duration
    for sc in project["scenes"]:
        if sc["id"] == req.scene_id:
            dur = float(sc.get("duration", 4.0))
            trimmed_path = trim_and_fit_clip(str(local_path), dur, sc["id"])
            sc["video_clip"] = {
                "provider": req.provider,
                "file_path": str(trimmed_path),
                "raw_file_path": str(local_path),
                "web_url": _to_media_url(trimmed_path),
                "thumbnail_url": req.thumbnail_url,
                "duration": dur
            }
            break

    save_project_to_history(project)
    return {"status": "success", "scenes": project["scenes"]}


# ======================== MERGE & EXPORT VIDEO ========================

class RenderRequest(BaseModel):
    project_id: str
    preset_key: str = "capcut_yellow"
    custom_options: Dict[str, Any] = {}
    fps: int = 30


@app.post("/api/render")
def render_video(req: RenderRequest):
    project = ACTIVE_PROJECTS.get(req.project_id)
    if not project:
        # Check history
        history = load_projects_history()
        project = next((p for p in history if p.get("id") == req.project_id), None)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

    audio_path = project["audio_path"]
    scenes = project["scenes"]

    # 1. Generate ASS Subtitles
    ass_path = str(TEMP_DIR / f"{req.project_id}_subtitles.ass")
    generate_ass_subtitles(
        scenes=scenes,
        output_path=ass_path,
        preset_key=req.preset_key,
        custom_options=req.custom_options
    )

    # 2. Render Full HD MP4 Video with BGM, Ken Burns FX, Modern Transitions, and Audio Muxing
    out_filename = f"{project['name']}_FullHD_1080p_{int(time.time())}.mp4"
    render_opts = {
        "fps": req.fps,
        "bgm_track": req.custom_options.get("bgm_track", project.get("bgm_track", "cinematic_ambient")),
        "bgm_volume": float(req.custom_options.get("bgm_volume", project.get("bgm_volume", 0.10))),
        "enable_motion": bool(req.custom_options.get("enable_motion", project.get("enable_motion", True))),
        "enable_vignette": bool(req.custom_options.get("enable_vignette", project.get("enable_vignette", False))),
        "color_grade": req.custom_options.get("color_grade", project.get("color_grade", "clean")),
        "transition": req.custom_options.get("transition", project.get("transition", "none")),
        "transition_mode": req.custom_options.get("transition_mode", project.get("transition_mode", "fixed")),
        "mute_stock_audio": bool(req.custom_options.get("mute_stock_audio", True)),
        **req.custom_options
    }
    with RENDER_LOCK:
        rendered_path = render_final_video(
            audio_path=audio_path,
            scenes=scenes,
            ass_subtitle_path=ass_path,
            output_filename=out_filename,
            custom_options=render_opts
        )


    web_url = _to_media_url(rendered_path)
    project["rendered_video"] = {
        "filename": out_filename,
        "file_path": rendered_path,
        "web_url": web_url,
        "rendered_at": time.strftime("%b %d, %Y %I:%M %p")
    }
    project["status"] = "completed"
    save_project_to_history(project)

    return {
        "status": "success",
        "output_file": out_filename,
        "output_path": rendered_path,
        "web_url": web_url
    }


# ======================== PROJECTS & SYSTEM HELPERS ========================

@app.get("/api/projects")
def get_projects():
    return load_projects_history()


class OpenFolderRequest(BaseModel):
    path: Optional[str] = None


@app.post("/api/open-folder")
@app.post("/api/open-output-folder")
def open_folder(req: Optional[OpenFolderRequest] = None):
    settings = load_settings()
    if req and req.path:
        target_path = Path(req.path)
    else:
        target_path = Path(settings.get("output_dir", str(OUTPUT_DIR)))

    target_path.mkdir(parents=True, exist_ok=True)
    abs_path = str(target_path.resolve())

    if os.name == "nt":
        try:
            os.startfile(abs_path)
        except Exception:
            subprocess.Popen(f'explorer "{abs_path}"', shell=True)
    return {"status": "success", "path": abs_path}


class CapCutExportRequest(BaseModel):
    project_id: str
    custom_options: Dict[str, Any] = {}


@app.get("/api/capcut-status")
def get_capcut_status():
    capcut_exe = find_capcut_executable()
    drafts_dir = str(get_capcut_drafts_dir().resolve())
    return {
        "installed": bool(capcut_exe),
        "capcut_exe": capcut_exe,
        "drafts_dir": drafts_dir
    }


@app.post("/api/export-capcut")
def export_capcut(req: CapCutExportRequest):
    project = ACTIVE_PROJECTS.get(req.project_id)
    if not project:
        history = load_projects_history()
        project = next((p for p in history if p.get("id") == req.project_id), None)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

    result = export_project_to_capcut(project, req.custom_options)
    return result




# ======================== BGM AUDIO ENDPOINTS ========================

@app.get("/api/bgm-tracks")
def get_bgm_tracks():
    bgm_dir = DATA_DIR / "assets" / "bgm"
    bgm_dir.mkdir(parents=True, exist_ok=True)
    tracks = [
        {"id": "cinematic_ambient", "name": "✨ Cinematic Ambient (Ethereal)", "file": "cinematic_ambient.mp3"},
        {"id": "lofi_chill", "name": "☕ Lofi Chill Beats (Relaxing)", "file": "lofi_chill.mp3"},
        {"id": "deep_focus", "name": "🧘 Deep Focus Drone (Atmospheric)", "file": "deep_focus.mp3"},
        {"id": "none", "name": "🔇 None (Voiceover Only)", "file": ""}
    ]
    for p in bgm_dir.glob("*.mp3"):
        if p.stem not in ("cinematic_ambient", "lofi_chill", "deep_focus"):
            tracks.append({"id": p.name, "name": f"🎵 {p.stem}", "file": p.name})
    return tracks


@app.post("/api/upload-bgm")
async def upload_bgm(file: UploadFile = File(...)):
    bgm_dir = DATA_DIR / "assets" / "bgm"
    bgm_dir.mkdir(parents=True, exist_ok=True)
    filename = f"custom_{int(time.time())}_{file.filename}"
    target_path = bgm_dir / filename
    with open(target_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    return {
        "status": "success",
        "bgm_key": filename,
        "filename": file.filename,
        "path": str(target_path),
        "web_url": f"/media/assets/bgm/{filename}"
    }
# ======================== EDITING TEMPLATES ENDPOINTS ========================

from .templates import list_templates, get_template, resolve_template_variant, EDITING_TEMPLATES

@app.get("/api/templates")
def get_templates():
    return list_templates()


# ======================== BATCH / BULK VIDEO GENERATION & CONCURRENCY LOCKS ========================

RENDER_LOCK = threading.Lock()       # Serializes heavy FFmpeg rendering to 1 active process to prevent GPU NVENC limit exhaustion
GLOBAL_BATCH_LOCK = threading.Lock() # Prevents overlapping batch runs if clicked twice
BATCH_LOCK = threading.Lock()        # Protects batch dictionary and counter state updates

BATCH_JOBS_FILE = DATA_DIR / "batch_jobs.json"

def load_batch_jobs_from_disk() -> Dict[str, Dict[str, Any]]:
    if BATCH_JOBS_FILE.exists():
        try:
            with open(BATCH_JOBS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[WARN] Failed to load batch jobs: {e}")
    return {}

def save_batch_jobs_to_disk():
    try:
        with open(BATCH_JOBS_FILE, "w", encoding="utf-8") as f:
            json.dump(BATCH_JOBS, f, indent=2)
    except Exception as e:
        print(f"[WARN] Failed to save batch jobs: {e}")

BATCH_JOBS: Dict[str, Dict[str, Any]] = load_batch_jobs_from_disk()

@app.post("/api/batch-upload-audio")
async def batch_upload_audio(files: List[UploadFile] = File(...)):
    uploaded = []
    for f in files:
        ext = Path(f.filename).suffix or ".mp3"
        safe_base = Path(f.filename).stem
        fname = f"batch_{int(time.time() * 1000)}_{safe_base}{ext}"
        dest = TEMP_DIR / fname
        with open(dest, "wb") as buffer:
            shutil.copyfileobj(f.file, buffer)
        dur = get_audio_duration(str(dest))
        uploaded.append({
            "filename": fname,
            "original_name": f.filename,
            "duration": round(dur, 2),
            "url": f"/media/temp/{fname}"
        })
    return {"status": "success", "count": len(uploaded), "files": uploaded}


class BatchGenerateRequest(BaseModel):
    audio_filenames: List[str]
    template_id: str = "shorts_viral"
    niche: Optional[str] = None
    pipeline: str = "Main"
    auto_render: bool = True


@app.post("/api/start-batch-generate")
def start_batch_generation(req: BatchGenerateRequest):
    if not req.audio_filenames:
        raise HTTPException(status_code=400, detail="No audio files provided")

    if GLOBAL_BATCH_LOCK.locked():
        raise HTTPException(
            status_code=409,
            detail="A batch generation job is currently running. Please wait for it to complete or cancel it before starting a new batch."
        )

    batch_id = f"batch_{int(time.time() * 1000)}"
    tmpl = get_template(req.template_id)
    niche = req.niche or tmpl.get("niche", "Motivation Psychology")

    items = []
    for fn in req.audio_filenames:
        items.append({
            "filename": fn,
            "name": Path(fn).stem.replace("batch_", ""),
            "status": "queued",
            "percent": 0,
            "stage_desc": "Waiting in queue...",
            "project_id": None,
            "rendered_url": None,
            "error": None,
            "fallback_scenes_count": 0
        })

    with BATCH_LOCK:
        BATCH_JOBS[batch_id] = {
            "id": batch_id,
            "template": tmpl,
            "niche": niche,
            "pipeline": req.pipeline,
            "total": len(items),
            "completed": 0,
            "percent": 0,
            "status": "processing",
            "cancel_requested": False,
            "items": items,
            "created_at": time.strftime("%b %d, %Y %I:%M %p")
        }
        save_batch_jobs_to_disk()

    def run_batch():
        if not GLOBAL_BATCH_LOCK.acquire(blocking=False):
            return
        try:
            batch = BATCH_JOBS[batch_id]
            from concurrent.futures import ThreadPoolExecutor

            last_used = {"bgm_track": None, "caption_style": None}
            last_used_lock = threading.Lock()

            def process_single_audio(idx: int, item: Dict[str, Any]):
                if batch.get("cancel_requested"):
                    item["status"] = "cancelled"
                    item["stage_desc"] = "Cancelled by user"
                    return

                # Resolve per-item template variant from pool to ensure variation across batch
                with last_used_lock:
                    item_tmpl = resolve_template_variant(req.template_id, exclude=last_used)
                    last_used["bgm_track"] = item_tmpl.get("bgm_track")
                    last_used["caption_style"] = item_tmpl.get("caption_style")

                item["bgm_track"] = item_tmpl.get("bgm_track")
                item["caption_style"] = item_tmpl.get("caption_style")

                audio_fn = item["filename"]
                audio_path = TEMP_DIR / audio_fn
                if not audio_path.exists():
                    item["status"] = "error"
                    item["error"] = "Audio file missing"
                    return

                try:
                    item["status"] = "processing"
                    item["percent"] = 10
                    item["stage_desc"] = "Transcribing speech..."

                    # 1. Transcribe
                    transcription = transcribe_audio(str(audio_path), niche=niche)
                    if batch.get("cancel_requested"):
                        item["status"] = "cancelled"
                        item["stage_desc"] = "Cancelled by user"
                        return

                    item["percent"] = 25
                    item["stage_desc"] = "Building sentence scenes..."

                    # 2. Scene analysis with template max duration
                    max_dur = item_tmpl.get("max_scene_duration", 3.5)
                    scenes = build_scenes(transcription, niche=niche)
                    for sc in scenes:
                        if sc.get("duration", 0) > max_dur:
                            sc["duration"] = round(min(sc["duration"], max_dur), 2)
                    
                    if batch.get("cancel_requested"):
                        item["status"] = "cancelled"
                        item["stage_desc"] = "Cancelled by user"
                        return

                    item["percent"] = 40
                    item["stage_desc"] = f"Downloading {len(scenes)} stock clips in parallel..."

                    # 3. Download stock clips concurrently
                    def on_download(done, total, sc_item):
                        pct = int(40 + (done / max(1, total)) * 30)
                        item["percent"] = pct
                        item["stage_desc"] = f"Downloaded stock clip {done}/{total}..."

                    processed_scenes = download_scenes_concurrently(scenes, progress_callback=on_download)
                    for sc in processed_scenes:
                        if sc.get("video_clip") and sc["video_clip"].get("file_path"):
                            sc["video_clip"]["web_url"] = _to_media_url(sc["video_clip"]["file_path"])

                    # Count fallback scenes
                    fallback_count = sum(1 for sc in processed_scenes if sc.get("fallback_used"))
                    item["fallback_scenes_count"] = fallback_count

                    if batch.get("cancel_requested"):
                        item["status"] = "cancelled"
                        item["stage_desc"] = "Cancelled by user"
                        return

                    # 4. Create project data with item-specific template variant
                    proj_id = f"proj_batch_{int(time.time() * 1000)}_{idx}"
                    proj_name = Path(audio_fn).stem
                    project_data = {
                        "id": proj_id,
                        "name": proj_name,
                        "niche": niche,
                        "pipeline": req.pipeline,
                        "template_id": item_tmpl["id"],
                        "audio_filename": audio_fn,
                        "audio_path": str(audio_path),
                        "audio_url": f"/media/temp/{audio_fn}",
                        "duration": transcription.get("duration", 30.0),
                        "scenes": processed_scenes,
                        "fallback_scenes_count": fallback_count,
                        "created_at": time.strftime("%b %d, %Y %I:%M %p"),
                        "status": "ready_for_preview",
                        "aspect_ratio": item_tmpl.get("aspect_ratio", "16:9"),
                        "transition": item_tmpl.get("transition", "smoothleft"),
                        "transition_mode": item_tmpl.get("transition_mode", "fixed"),
                        "transition_duration": item_tmpl.get("transition_duration", 0.30),
                        "bgm_track": item_tmpl.get("bgm_track", "lofi_chill.mp3"),
                        "bgm_volume": item_tmpl.get("bgm_volume", 0.10),
                        "caption_style": item_tmpl.get("caption_style", "capcut-yellow")
                    }
                    ACTIVE_PROJECTS[proj_id] = project_data
                    save_project_to_history(project_data)
                    item["project_id"] = proj_id

                    # 5. Auto Render if requested (STRICTLY SERIALIZED via RENDER_LOCK)
                    if req.auto_render:
                        if batch.get("cancel_requested"):
                            item["status"] = "cancelled"
                            item["stage_desc"] = "Cancelled by user"
                            return

                        item["percent"] = 72
                        item["stage_desc"] = "Queued for GPU/CPU render slot..."

                        ass_path = str(TEMP_DIR / f"{proj_id}_subtitles.ass")
                        generate_ass_subtitles(
                            scenes=processed_scenes,
                            output_path=ass_path,
                            preset_key=item_tmpl.get("caption_style", "capcut_yellow"),
                            custom_options={"aspect_ratio": item_tmpl.get("aspect_ratio", "16:9")}
                        )

                        out_filename = f"{proj_name}_1080p_{item_tmpl['id']}_{int(time.time())}.mp4"
                        render_opts = {
                            "fps": 30,
                            "aspect_ratio": item_tmpl.get("aspect_ratio", "16:9"),
                            "bgm_track": item_tmpl.get("bgm_track", "lofi_chill.mp3"),
                            "bgm_volume": item_tmpl.get("bgm_volume", 0.10),
                            "transition": item_tmpl.get("transition", "smoothleft"),
                            "transition_mode": item_tmpl.get("transition_mode", "fixed"),
                            "transition_duration": item_tmpl.get("transition_duration", 0.30),
                            "enable_motion": True,
                            "mute_stock_audio": True
                        }

                        with RENDER_LOCK:
                            if batch.get("cancel_requested"):
                                item["status"] = "cancelled"
                                item["stage_desc"] = "Cancelled by user"
                                return
                            item["percent"] = 75
                            item["stage_desc"] = "Rendering 1080p MP4 (exclusive GPU render slot)..."
                            rendered_path = render_final_video(
                                audio_path=str(audio_path),
                                scenes=processed_scenes,
                                ass_subtitle_path=ass_path,
                                output_filename=out_filename,
                                custom_options=render_opts
                            )

                        web_url = _to_media_url(rendered_path)
                        project_data["rendered_video"] = {
                            "filename": out_filename,
                            "file_path": rendered_path,
                            "web_url": web_url,
                            "rendered_at": time.strftime("%b %d, %Y %I:%M %p")
                        }
                        project_data["status"] = "completed"
                        save_project_to_history(project_data)
                        item["rendered_url"] = web_url

                        # Generate CapCut draft automatically
                        try:
                            export_project_to_capcut(project_data, render_opts)
                        except Exception:
                            pass

                    item["status"] = "completed"
                    item["percent"] = 100
                    status_text = "Completed successfully!"
                    if fallback_count > 0:
                        status_text += f" (⚠️ {fallback_count} offline gradient scenes used)"
                    item["stage_desc"] = status_text

                except Exception as e:
                    import traceback
                    traceback.print_exc()
                    item["status"] = "error"
                    item["error"] = str(e)

                finally:
                    with BATCH_LOCK:
                        batch["completed"] += 1
                        batch["percent"] = int((batch["completed"] / max(1, batch["total"])) * 100)
                        save_batch_jobs_to_disk()

            # Bounded concurrency: 2 audio projects transcribe/download in parallel, but FFmpeg rendering is serialized
            with ThreadPoolExecutor(max_workers=2) as pool:
                futures = [pool.submit(process_single_audio, i, item) for i, item in enumerate(items)]
                for fut in futures:
                    fut.result()

            with BATCH_LOCK:
                if batch.get("cancel_requested"):
                    batch["status"] = "cancelled"
                else:
                    batch["status"] = "completed"
                    batch["percent"] = 100
                save_batch_jobs_to_disk()

        finally:
            if GLOBAL_BATCH_LOCK.locked():
                GLOBAL_BATCH_LOCK.release()

    threading.Thread(target=run_batch, daemon=True).start()
    return {"status": "started", "batch_id": batch_id, "total": len(items)}


@app.get("/api/batch-progress/{batch_id}")
def get_batch_progress(batch_id: str):
    with BATCH_LOCK:
        batch = BATCH_JOBS.get(batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Batch job not found")
    return batch


@app.post("/api/batch-cancel/{batch_id}")
def cancel_batch(batch_id: str):
    with BATCH_LOCK:
        batch = BATCH_JOBS.get(batch_id)
        if not batch:
            raise HTTPException(status_code=404, detail="Batch job not found")
        batch["cancel_requested"] = True
        batch["status"] = "cancelled"
        for item in batch.get("items", []):
            if item.get("status") in ("queued", "waiting"):
                item["status"] = "cancelled"
                item["stage_desc"] = "Cancelled by user"
        save_batch_jobs_to_disk()
    return {"status": "success", "message": "Batch cancellation requested", "batch_id": batch_id}


# Mount data folder to serve audio, video clips, and exported MP4s
app.mount("/media", StaticFiles(directory=str(DATA_DIR)), name="media")

# Mount frontend files
frontend_dir = BASE_DIR / "frontend"
if frontend_dir.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")
