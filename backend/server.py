import os
import re
import json
import time
import shutil
import threading
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional

import asyncio
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from .config import (
    BASE_DIR, DATA_DIR, CACHE_DIR, OUTPUT_DIR, TEMP_DIR, FRONTEND_DIR,
    load_settings, save_settings, find_ffmpeg
)
from .transcriber import transcribe_audio, get_audio_duration
from .scene_analyzer import build_scenes, analyze_script_editorial_direction
from .stock_downloader import download_scenes_concurrently, search_alternative_clips
from .subtitle_generator import generate_ass_subtitles, PRESET_STYLES
from .video_renderer import render_final_video
from .capcut_exporter import export_project_to_capcut, find_capcut_executable, get_capcut_drafts_dir

app = FastAPI(title="VideoGen Studio API", version="1.0.0")


def _silence_proactor_reset(loop, context):
    """Silences harmless WinError 10054 (client disconnected/seeked media stream) in Windows asyncio event loop."""
    exc = context.get("exception")
    if isinstance(exc, (ConnectionResetError, ConnectionAbortedError, BrokenPipeError)):
        return
    if getattr(exc, "winerror", None) == 10054:
        return
    loop.default_exception_handler(context)


@app.on_event("startup")
async def startup_event():
    try:
        loop = asyncio.get_running_loop()
        loop.set_exception_handler(_silence_proactor_reset)
    except Exception as e:
        print(f"[Server] Event loop handler notice: {e}")


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory storage for active projects and rendering jobs
ACTIVE_PROJECTS: Dict[str, Dict[str, Any]] = {}
ACTIVE_RENDER_JOBS: Dict[str, Dict[str, Any]] = {}
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
    """Safely converts a disk path to a /media/... web URL."""
    if not file_path:
        return ""
    p = Path(file_path)
    # Check if under DATA_DIR
    try:
        rel = p.resolve().relative_to(DATA_DIR.resolve()).as_posix()
        return f"/media/{rel}"
    except Exception:
        pass
    # Check if inside known subdirectories
    p_str = str(p).replace("\\", "/")
    if "scene_clips" in p_str:
        return f"/media/cache/scene_clips/{p.name}"
    elif "stock_videos" in p_str:
        return f"/media/cache/stock_videos/{p.name}"
    elif "temp" in p_str:
        return f"/media/temp/{p.name}"
    return f"/media/cache/stock_videos/{p.name}"



# ======================== SETTINGS ENDPOINTS ========================

@app.get("/api/settings")
def get_settings():
    return load_settings()


@app.post("/api/settings")
def update_settings(payload: Dict[str, Any]):
    updated = save_settings(payload)
    return {"status": "success", "settings": updated}


def _cleanup_old_temp_files():
    """Cleans up leftover segments and temporary render folders older than 12 hours."""
    try:
        cutoff = time.time() - (12 * 3600)
        for item in TEMP_DIR.iterdir():
            try:
                if item.stat().st_mtime < cutoff:
                    if item.is_dir():
                        shutil.rmtree(item, ignore_errors=True)
                    else:
                        item.unlink()
            except Exception:
                pass
    except Exception as e:
        print(f"[Server] Notice during temp cleanup: {e}")

# Trigger non-blocking temp cleanup on startup
threading.Thread(target=_cleanup_old_temp_files, daemon=True).start()


@app.post("/api/test-apis")
def test_apis():
    import requests
    from concurrent.futures import ThreadPoolExecutor
    settings = load_settings()
    results = {}

    def test_pexels():
        p_keys = settings.get("pexels_api_keys") or ([settings.get("pexels_api_key")] if settings.get("pexels_api_key") else [])
        p_keys = [k for k in p_keys if k.strip()]
        if not p_keys:
            return "pexels", {"status": "unconfigured"}
        valid_p = 0
        last_err = ""
        for pk in p_keys:
            try:
                r = requests.get("https://api.pexels.com/videos/search?query=nature&per_page=1", headers={"Authorization": pk}, timeout=4)
                if r.status_code == 200:
                    valid_p += 1
                elif r.status_code == 429:
                    last_err = "429 Rate Limit"
            except Exception as e:
                last_err = str(e)
        if valid_p > 0:
            return "pexels", {"status": "ok", "active_keys": valid_p, "total_keys": len(p_keys), "code": 200}
        return "pexels", {"status": "error", "error": last_err or "All keys failed"}

    def test_pixabay():
        pb_keys = settings.get("pixabay_api_keys") or ([settings.get("pixabay_api_key")] if settings.get("pixabay_api_key") else [])
        pb_keys = [k for k in pb_keys if k.strip()]
        if not pb_keys:
            return "pixabay", {"status": "unconfigured"}
        valid_pb = 0
        last_err = ""
        for pbk in pb_keys:
            try:
                r = requests.get(f"https://pixabay.com/api/videos/?key={pbk}&q=nature&per_page=3", timeout=4)
                if r.status_code == 200:
                    valid_pb += 1
                elif r.status_code == 429:
                    last_err = "429 Rate Limit"
            except Exception as e:
                last_err = str(e)
        if valid_pb > 0:
            return "pixabay", {"status": "ok", "active_keys": valid_pb, "total_keys": len(pb_keys), "code": 200}
        return "pixabay", {"status": "error", "error": last_err or "All keys failed"}

    def test_gemini():
        g_keys = settings.get("gemini_api_keys") or ([settings.get("gemini_api_key")] if settings.get("gemini_api_key") else [])
        g_keys = [k for k in g_keys if k and k.strip()]
        if not g_keys:
            return "gemini", {"status": "unconfigured"}
        valid_g = 0
        last_err = ""
        for gk in g_keys:
            try:
                r = requests.get(f"https://generativelanguage.googleapis.com/v1beta/models?key={gk}", timeout=4)
                if r.status_code == 200:
                    valid_g += 1
                elif r.status_code == 429:
                    last_err = "429 Quota/Rate Limit"
                else:
                    last_err = f"HTTP {r.status_code}"
            except Exception as e:
                last_err = str(e)
        if valid_g > 0:
            return "gemini", {"status": "ok", "active_keys": valid_g, "total_keys": len(g_keys), "code": 200}
        return "gemini", {"status": "error", "error": last_err or "All Gemini keys failed"}

    def test_groq():
        g_key = settings.get("groq_api_key", "").strip()
        if not g_key:
            return "groq", {"status": "unconfigured"}
        try:
            r = requests.get("https://api.groq.com/openai/v1/models", headers={"Authorization": f"Bearer {g_key}"}, timeout=4)
            return "groq", {"status": "ok" if r.status_code == 200 else "error", "code": r.status_code}
        except Exception as e:
            return "groq", {"status": "error", "error": str(e)}

    def test_openai():
        o_key = settings.get("openai_api_key", "").strip()
        if not o_key:
            return "openai", {"status": "unconfigured"}
        try:
            r = requests.get("https://api.openai.com/v1/models", headers={"Authorization": f"Bearer {o_key}"}, timeout=4)
            return "openai", {"status": "ok" if r.status_code == 200 else "error", "code": r.status_code}
        except Exception as e:
            return "openai", {"status": "error", "error": str(e)}

    def test_coverr():
        c_key = settings.get("coverr_api_key", "").strip()
        if not c_key:
            return "coverr", {"status": "unconfigured"}
        try:
            r = requests.get("https://api.coverr.co/videos?query=nature&urls=mp4", headers={"Authorization": f"Bearer {c_key}"}, timeout=4)
            return "coverr", {"status": "ok" if r.status_code == 200 else "error", "code": r.status_code}
        except Exception as e:
            return "coverr", {"status": "error", "error": str(e)}

    def test_videvo():
        v_key = settings.get("videvo_api_key", "").strip()
        if not v_key:
            return "videvo", {"status": "unconfigured"}
        try:
            r = requests.get(f"https://api.videvo.net/v1/videos?q=nature&api_key={v_key}", timeout=4)
            return "videvo", {"status": "ok" if r.status_code == 200 else "error", "code": r.status_code}
        except Exception as e:
            return "videvo", {"status": "error", "error": str(e)}

    def test_nasa():
        try:
            r = requests.get("https://images-api.nasa.gov/search?q=earth&media_type=video", timeout=4)
            return "nasa", {"status": "ok" if r.status_code == 200 else "error", "code": r.status_code}
        except Exception as e:
            return "nasa", {"status": "error", "error": str(e)}

    def test_wikimedia():
        try:
            r = requests.get(
                "https://commons.wikimedia.org/w/api.php?action=query&generator=search&gsrsearch=nature+filetype:video&prop=imageinfo&format=json",
                headers={"User-Agent": "VideoGen/1.0"},
                timeout=4
            )
            return "wikimedia", {"status": "ok" if r.status_code == 200 else "error", "code": r.status_code}
        except Exception as e:
            return "wikimedia", {"status": "error", "error": str(e)}

    testers = [test_pexels, test_pixabay, test_gemini, test_groq, test_openai, test_coverr, test_videvo, test_nasa, test_wikimedia]
    with ThreadPoolExecutor(max_workers=9) as executor:
        futures = [executor.submit(fn) for fn in testers]
        for f in futures:
            try:
                name, res = f.result()
                results[name] = res
            except Exception as e:
                pass

    hook = settings.get("custom_stock_webhook", "").strip()
    results["custom_webhook"] = {"status": "configured", "url": hook} if hook else {"status": "unconfigured"}

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


class VoiceoverRequest(BaseModel):
    text: str
    voice: str = "en-US-ChristopherNeural"
    rate: str = "+0%"
    pitch: str = "+0Hz"


@app.get("/api/tts-voices")
def list_tts_voices():
    from backend.tts_generator import get_curated_voices
    return {"status": "success", "voices": get_curated_voices()}


@app.post("/api/generate-voiceover")
async def generate_voiceover_endpoint(req: VoiceoverRequest):
    from backend.tts_generator import generate_speech_async
    if not req.text or not req.text.strip():
        raise HTTPException(status_code=400, detail="Script text cannot be empty.")

    filename = f"voiceover_{int(time.time())}.mp3"
    dest = TEMP_DIR / filename
    try:
        meta = await generate_speech_async(
            text=req.text,
            voice=req.voice,
            rate=req.rate,
            pitch=req.pitch,
            output_path=str(dest)
        )
        duration = get_audio_duration(str(dest))
        return {
            "status": "success",
            "filename": filename,
            "original_name": f"{meta['voice']}_script.mp3",
            "duration": round(duration, 2),
            "word_count": meta["word_count"],
            "approx_duration": meta["approx_duration"],
            "url": f"/media/temp/{filename}",
            "audio_url": f"/media/temp/{filename}",
            "cleaned_text": meta["cleaned_text"]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"TTS generation failed: {str(e)}")


import threading

ACTIVE_JOBS: Dict[str, Dict[str, Any]] = {}


class GenerateRequest(BaseModel):
    audio_filename: str
    niche: str = "Motivation Psychology"
    pipeline: str = "Main"
    target_resolution: str = "1080p"


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
            
            # 2. Editorial Direction & Scene Analysis
            ACTIVE_JOBS[job_id]["stage"] = "analyzing"
            ACTIVE_JOBS[job_id]["stage_title"] = "Editorial Direction & Scene Analysis..."
            ACTIVE_JOBS[job_id]["stage_desc"] = "Analyzing script pacing, climax emphasis, and visual tags..."
            ACTIVE_JOBS[job_id]["percent"] = 25

            editorial_dir = analyze_script_editorial_direction(
                full_transcript_text=transcription.get("text", ""),
                niche=req.niche
            )
            scenes = build_scenes(transcription, niche=req.niche, editorial_direction=editorial_dir)
            total_scenes = len(scenes)
            ACTIVE_JOBS[job_id]["total_scenes"] = total_scenes

            # 3. Parallel Downloads with live progress callback and target resolution
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

            processed_scenes = download_scenes_concurrently(
                scenes,
                progress_callback=on_progress,
                target_resolution=req.target_resolution,
                niche=req.niche
            )

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
                "target_resolution": req.target_resolution,
                "audio_filename": req.audio_filename,
                "audio_path": str(audio_path),
                "audio_url": f"/media/temp/{req.audio_filename}",
                "duration": transcription.get("duration", 30.0),
                "scenes": processed_scenes,
                "editorial_direction": editorial_dir,
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
    editorial_dir = analyze_script_editorial_direction(
        full_transcript_text=transcription.get("text", ""),
        niche=req.niche
    )
    scenes = build_scenes(transcription, niche=req.niche, editorial_direction=editorial_dir)
    processed_scenes = download_scenes_concurrently(scenes, niche=req.niche)

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
        "editorial_direction": editorial_dir,
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


class GenerateMissingImagesRequest(BaseModel):
    project_id: str
    scene_ids: Optional[List[int]] = None
    motion: bool = True


@app.post("/api/generate-missing-scene-images")
def generate_missing_scene_images(req: GenerateMissingImagesRequest):
    project = ACTIVE_PROJECTS.get(req.project_id)
    if not project:
        history = load_projects_history()
        for p in history:
            if p.get("id") == req.project_id:
                project = p
                ACTIVE_PROJECTS[req.project_id] = p
                break
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    from .image_generator import generate_scene_image, convert_image_to_scene_clip

    niche = project.get("niche", "General")
    target_res = load_settings().get("resolution", "1080p")
    fixed_count = 0
    target_ids = set(req.scene_ids) if req.scene_ids is not None else None

    for sc in project.get("scenes", []):
        sc_id = sc.get("id", 0)
        is_missing = bool(sc.get("fallback_used")) or bool(sc.get("video_clip", {}).get("is_fallback")) or not bool(sc.get("video_clip", {}).get("file_path"))

        if (target_ids is not None and sc_id in target_ids) or (target_ids is None and is_missing):
            text = sc.get("text", "")
            tags = sc.get("search_tags", [])
            dur = float(sc.get("duration", 4.0))

            try:
                img_path = generate_scene_image(
                    prompt=text,
                    scene_id=sc_id,
                    tags=tags,
                    niche=niche,
                    target_resolution=target_res
                )
                clip_path = convert_image_to_scene_clip(
                    image_path=str(img_path),
                    duration=dur,
                    scene_id=sc_id,
                    target_resolution=target_res,
                    motion=req.motion
                )
                if clip_path and os.path.exists(clip_path):
                    sc["video_clip"] = {
                        "provider": "ai_image",
                        "video_id": f"ai_img_{sc_id}_{int(time.time())}",
                        "query": sc.get("selected_tag") or (tags[0] if tags else "cinematic"),
                        "file_path": str(clip_path),
                        "raw_file_path": str(img_path),
                        "web_url": _to_media_url(clip_path),
                        "thumbnail_url": _to_media_url(img_path),
                        "duration": dur,
                        "width": 1920,
                        "height": 1080,
                        "is_fallback": False
                    }
                    sc["fallback_used"] = False
                    sc["status"] = "ready"
                    fixed_count += 1
            except Exception as e:
                print(f"[Server] Failed to generate AI image for scene {sc_id}: {e}")

    save_project_to_history(project)
    return {
        "status": "success",
        "fixed_count": fixed_count,
        "scenes": project.get("scenes", [])
    }


class SingleSceneImageRequest(BaseModel):
    project_id: str
    scene_id: int
    custom_prompt: Optional[str] = None
    motion: bool = True


@app.post("/api/generate-single-scene-image")
def generate_single_scene_image(req: SingleSceneImageRequest):
    project = ACTIVE_PROJECTS.get(req.project_id)
    if not project:
        history = load_projects_history()
        for p in history:
            if p.get("id") == req.project_id:
                project = p
                ACTIVE_PROJECTS[req.project_id] = p
                break
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    from .image_generator import generate_scene_image, convert_image_to_scene_clip

    niche = project.get("niche", "General")
    target_res = load_settings().get("resolution", "1080p")

    for sc in project.get("scenes", []):
        if sc.get("id") == req.scene_id:
            dur = float(sc.get("duration", 4.0))
            prompt = req.custom_prompt or sc.get("text", "")
            tags = sc.get("search_tags", [])
            try:
                img_path = generate_scene_image(
                    prompt=prompt,
                    scene_id=req.scene_id,
                    tags=tags,
                    niche=niche,
                    target_resolution=target_res
                )
                clip_path = convert_image_to_scene_clip(
                    image_path=str(img_path),
                    duration=dur,
                    scene_id=req.scene_id,
                    target_resolution=target_res,
                    motion=req.motion
                )
                if not clip_path or not os.path.exists(clip_path):
                    raise HTTPException(status_code=500, detail=f"AI image generation succeeded but video clip conversion failed for scene {req.scene_id}")
                sc["video_clip"] = {
                    "provider": "ai_image",
                    "video_id": f"ai_img_{req.scene_id}_{int(time.time())}",
                    "query": req.custom_prompt or sc.get("selected_tag") or "cinematic",
                    "file_path": str(clip_path),
                    "raw_file_path": str(img_path),
                    "web_url": _to_media_url(clip_path),
                    "thumbnail_url": _to_media_url(img_path),
                    "duration": dur,
                    "width": 1920,
                    "height": 1080,
                    "is_fallback": False
                }
                sc["fallback_used"] = False
                sc["status"] = "ready"
                save_project_to_history(project)
                return {"status": "success", "scene": sc, "scenes": project.get("scenes", [])}
            except HTTPException:
                raise
            except Exception as e:
                print(f"[Server] Failed to generate AI image for scene {req.scene_id}: {e}")
                raise HTTPException(status_code=500, detail=f"AI image generation failed for scene {req.scene_id}: {str(e)}")

    raise HTTPException(status_code=404, detail="Scene not found")


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

    # 1. Check captions toggle and target resolution
    custom_opts = req.custom_options or {}
    enable_captions = bool(custom_opts.get("enable_captions", project.get("enable_captions", True)))
    target_res = str(custom_opts.get("target_resolution", project.get("target_resolution", "1080p"))).lower().strip()

    if enable_captions:
        ass_path = str(TEMP_DIR / f"{req.project_id}_subtitles.ass")
        callouts_on = custom_opts.get("callouts_enabled", project.get("callouts_enabled", False))
        callout_st = custom_opts.get("callout_style", project.get("callout_style", "badge_yellow"))
        render_custom_options = {
            **custom_opts,
            "callouts_enabled": callouts_on,
            "callout_style": callout_st
        }
        generate_ass_subtitles(
            scenes=scenes,
            output_path=ass_path,
            preset_key=req.preset_key,
            custom_options=render_custom_options
        )
        final_ass_path = ass_path
    else:
        final_ass_path = None

    # 2. Render Video with BGM, Ken Burns FX, Modern Transitions, and Audio Muxing
    res_tag = "8K_UHD" if target_res == "8k" else ("4K_UHD" if target_res == "4k" else "FullHD_1080p")
    out_filename = f"{project['name']}_{res_tag}_{int(time.time())}.mp4"
    render_opts = {
        "fps": req.fps,
        "target_resolution": target_res,
        "bgm_track": req.custom_options.get("bgm_track", project.get("bgm_track", "cinematic_ambient")),
        "bgm_volume": float(req.custom_options.get("bgm_volume", project.get("bgm_volume", 0.10))),
        "enable_motion": bool(req.custom_options.get("enable_motion", project.get("enable_motion", False))),
        "enable_vignette": bool(req.custom_options.get("enable_vignette", project.get("enable_vignette", False))),
        "color_grade": req.custom_options.get("color_grade", project.get("color_grade", "clean")),
        "transition": req.custom_options.get("transition", project.get("transition", "none")),
        "transition_mode": req.custom_options.get("transition_mode", project.get("transition_mode", "fixed")),
        "transition_sfx": req.custom_options.get("transition_sfx", project.get("transition_sfx", None)),
        "transition_sfx_volume": float(req.custom_options.get("transition_sfx_volume", project.get("transition_sfx_volume", 0.40))),
        "emphasis_zoom_enabled": bool(req.custom_options.get("emphasis_zoom_enabled", project.get("emphasis_zoom_enabled", False))),
        "emphasis_zoom_intensity": float(req.custom_options.get("emphasis_zoom_intensity", project.get("emphasis_zoom_intensity", 1.15))),
        "mute_stock_audio": bool(req.custom_options.get("mute_stock_audio", True)),
        **req.custom_options
    }
    with RENDER_LOCK:
        rendered_path = render_final_video(
            audio_path=audio_path,
            scenes=scenes,
            ass_subtitle_path=final_ass_path,
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

    # Auto-generate 2 YouTube Thumbnails (Viral & Cinematic)
    try:
        from backend.thumbnail_generator import generate_youtube_thumbnails
        conf_thumb = str(load_settings().get("thumbnail_output_dir", "")).strip()
        thumb_dir = Path(conf_thumb) if conf_thumb else (DATA_DIR / "thumbnails")
        thumb_dir.mkdir(parents=True, exist_ok=True)
        thumb_res = generate_youtube_thumbnails(project, target_dir=thumb_dir)
        project["thumbnails"] = thumb_res
    except Exception as th_err:
        print(f"[ThumbnailGenerator] Auto-generation notice: {th_err}")

    save_project_to_history(project)

    return {
        "status": "success",
        "output_file": out_filename,
        "output_path": rendered_path,
        "web_url": web_url,
        "thumbnails": project.get("thumbnails")
    }


@app.post("/api/start-render")
def start_render_job(req: RenderRequest):
    project = ACTIVE_PROJECTS.get(req.project_id)
    if not project:
        history = load_projects_history()
        project = next((p for p in history if p.get("id") == req.project_id), None)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

    job_id = f"render_{int(time.time() * 1000)}"
    start_ts = time.time()
    ACTIVE_RENDER_JOBS[job_id] = {
        "job_id": job_id,
        "project_id": req.project_id,
        "status": "processing",
        "percent": 5,
        "stage": "starting",
        "stage_title": "Starting Multi-Worker Render...",
        "stage_desc": "Compiling kinetic typography and subtitle timing...",
        "start_time": start_ts,
        "elapsed_seconds": 0,
        "eta_seconds": None,
        "output_file": None,
        "output_path": None,
        "web_url": None,
        "error": None
    }

    def run_render():
        try:
            job = ACTIVE_RENDER_JOBS[job_id]
            audio_path = project["audio_path"]
            scenes = project["scenes"]

            # 1. Check captions toggle and target resolution
            custom_opts = req.custom_options or {}
            enable_captions = bool(custom_opts.get("enable_captions", project.get("enable_captions", True)))
            target_res = str(custom_opts.get("target_resolution", project.get("target_resolution", "1080p"))).lower().strip()

            if enable_captions:
                ass_path = str(TEMP_DIR / f"{req.project_id}_subtitles.ass")
                callouts_on = custom_opts.get("callouts_enabled", project.get("callouts_enabled", False))
                callout_st = custom_opts.get("callout_style", project.get("callout_style", "badge_yellow"))
                render_custom_options = {
                    **custom_opts,
                    "callouts_enabled": callouts_on,
                    "callout_style": callout_st
                }
                generate_ass_subtitles(
                    scenes=scenes,
                    output_path=ass_path,
                    preset_key=req.preset_key,
                    custom_options=render_custom_options
                )
                final_ass_path = ass_path
            else:
                final_ass_path = None

            job["percent"] = 10
            job["stage_desc"] = "Ready. Initializing parallel video normalization..."

            proj_name = project.get("name") or project.get("id") or "VideoGen"
            res_tag = "8K_UHD" if target_res == "8k" else ("4K_UHD" if target_res == "4k" else "FullHD_1080p")
            out_filename = f"{proj_name}_{res_tag}_{int(time.time())}.mp4"
            render_opts = {
                "fps": req.fps,
                "target_resolution": target_res,
                "bgm_track": req.custom_options.get("bgm_track", project.get("bgm_track", "cinematic_ambient")),
                "bgm_volume": float(req.custom_options.get("bgm_volume", project.get("bgm_volume", 0.10))),
                "enable_motion": bool(req.custom_options.get("enable_motion", project.get("enable_motion", False))),
                "enable_vignette": bool(req.custom_options.get("enable_vignette", project.get("enable_vignette", False))),
                "color_grade": req.custom_options.get("color_grade", project.get("color_grade", "clean")),
                "transition": req.custom_options.get("transition", project.get("transition", "none")),
                "transition_mode": req.custom_options.get("transition_mode", project.get("transition_mode", "fixed")),
                "transition_sfx": req.custom_options.get("transition_sfx", project.get("transition_sfx", None)),
                "transition_sfx_volume": float(req.custom_options.get("transition_sfx_volume", project.get("transition_sfx_volume", 0.40))),
                "emphasis_zoom_enabled": bool(req.custom_options.get("emphasis_zoom_enabled", project.get("emphasis_zoom_enabled", False))),
                "emphasis_zoom_intensity": float(req.custom_options.get("emphasis_zoom_intensity", project.get("emphasis_zoom_intensity", 1.15))),
                "mute_stock_audio": bool(req.custom_options.get("mute_stock_audio", True)),
                **req.custom_options
            }

            def on_render_progress(stage, pct, desc):
                now = time.time()
                elapsed = max(0.5, now - start_ts)
                clamped_pct = max(10, min(99, int(pct)))
                job["percent"] = clamped_pct
                job["stage"] = stage
                job["stage_desc"] = desc
                job["elapsed_seconds"] = int(elapsed)
                if stage == "normalizing":
                    job["stage_title"] = f"Parallel Normalization ({clamped_pct}%)..."
                elif stage == "concatenating":
                    job["stage_title"] = "Timeline Transitions & Stitching..."
                elif stage == "completed":
                    job["stage_title"] = "Audio Muxing & Video Export Complete!"

                if clamped_pct > 12:
                    total_est = elapsed / (clamped_pct / 100.0)
                    job["eta_seconds"] = max(1, int(total_est - elapsed))

            with RENDER_LOCK:
                rendered_path = render_final_video(
                    audio_path=audio_path,
                    scenes=scenes,
                    ass_subtitle_path=final_ass_path,
                    output_filename=out_filename,
                    custom_options=render_opts,
                    progress_callback=on_render_progress
                )

            web_url = _to_media_url(rendered_path)
            project["rendered_video"] = {
                "filename": out_filename,
                "file_path": rendered_path,
                "web_url": web_url,
                "rendered_at": time.strftime("%b %d, %Y %I:%M %p")
            }
            project["status"] = "completed"

            # Auto-generate 2 YouTube Thumbnails (Viral & Cinematic)
            try:
                from backend.thumbnail_generator import generate_youtube_thumbnails
                conf_thumb = str(load_settings().get("thumbnail_output_dir", "")).strip()
                thumb_dir = Path(conf_thumb) if conf_thumb else (DATA_DIR / "thumbnails")
                thumb_dir.mkdir(parents=True, exist_ok=True)
                thumb_res = generate_youtube_thumbnails(project, target_dir=thumb_dir)
                project["thumbnails"] = thumb_res
                job["thumbnails"] = thumb_res
            except Exception as th_err:
                print(f"[ThumbnailGenerator] Auto-generation notice: {th_err}")

            # Auto-generate YouTube SEO Suite metadata in background
            try:
                from backend.seo_generator import generate_youtube_seo
                full_text = " ".join([sc.get("narration", "") for sc in project.get("scenes", [])])
                seo_meta = generate_youtube_seo(text=full_text, scenes=project.get("scenes", []), topic=project.get("name"))
                project["seo"] = seo_meta
                seo_dir = DATA_DIR / "seo"
                seo_dir.mkdir(parents=True, exist_ok=True)
                with open(seo_dir / f"{project['id']}_seo.json", "w", encoding="utf-8") as f:
                    json.dump(seo_meta, f, indent=2)
            except Exception as seo_err:
                print(f"[SEOGenerator] Auto-generation notice: {seo_err}")

            save_project_to_history(project)

            job["status"] = "completed"
            job["percent"] = 100
            job["stage"] = "completed"
            job["stage_title"] = "Render Complete!"
            job["stage_desc"] = "Ultra HD video ready in output folder."
            job["output_file"] = out_filename
            job["output_path"] = rendered_path
            job["web_url"] = web_url

        except Exception as e:
            import traceback
            traceback.print_exc()
            job = ACTIVE_RENDER_JOBS.get(job_id)
            if job:
                job["status"] = "error"
                job["error"] = str(e)

    threading.Thread(target=run_render, daemon=True).start()
    return {"status": "started", "job_id": job_id}


@app.get("/api/render-progress/{job_id}")
def get_render_progress(job_id: str):
    job = ACTIVE_RENDER_JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Render job not found")
    if job.get("status") == "processing":
        job["elapsed_seconds"] = int(time.time() - job["start_time"])
    job["progress"] = job.get("percent", 0)
    job["result"] = {
        "output_file": job.get("output_file"),
        "output_path": job.get("output_path"),
        "web_url": job.get("web_url"),
        "project_id": job.get("project_id"),
        "thumbnails": job.get("thumbnails")
    }
    return job


# ======================== PROJECTS & SYSTEM HELPERS ========================

@app.get("/api/projects")
def get_projects():
    return load_projects_history()


@app.delete("/api/projects/all")
def delete_all_projects():
    global ACTIVE_PROJECTS
    ACTIVE_PROJECTS.clear()
    with open(PROJECTS_FILE, "w", encoding="utf-8") as f:
        json.dump([], f, indent=2)
    return {"status": "success", "message": "All projects cleared successfully"}


@app.delete("/api/projects/{project_id}")
def delete_single_project(project_id: str):
    global ACTIVE_PROJECTS
    if project_id in ACTIVE_PROJECTS:
        del ACTIVE_PROJECTS[project_id]

    history = load_projects_history()
    new_history = [p for p in history if p.get("id") != project_id]
    with open(PROJECTS_FILE, "w", encoding="utf-8") as f:
        json.dump(new_history, f, indent=2)

    return {"status": "success", "message": f"Project {project_id} deleted successfully"}


# ======================== YOUTUBE THUMBNAIL STUDIO ========================

class GenerateThumbnailRequest(BaseModel):
    project_id: str
    custom_headline: Optional[str] = None


@app.post("/api/generate-thumbnails")
def generate_thumbnails_endpoint(req: GenerateThumbnailRequest):
    project = ACTIVE_PROJECTS.get(req.project_id)
    if not project:
        history = load_projects_history()
        project = next((p for p in history if p.get("id") == req.project_id), None)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

    from backend.thumbnail_generator import generate_youtube_thumbnails
    thumb_res = generate_youtube_thumbnails(project, custom_headline=req.custom_headline, target_dir=DATA_DIR / "thumbnails")
    project["thumbnails"] = thumb_res
    save_project_to_history(project)
    return {"status": "success", "thumbnails": thumb_res}


@app.get("/api/thumbnails/{project_id}")
def get_thumbnails_endpoint(project_id: str):
    project = ACTIVE_PROJECTS.get(project_id)
    if not project:
        history = load_projects_history()
        project = next((p for p in history if p.get("id") == project_id), None)

    # 1. Project in memory or history has thumbnails
    if project and project.get("thumbnails"):
        return {"status": "success", "thumbnails": project["thumbnails"]}

    # 2. Check disk in DATA_DIR / "thumbnails" for this project_id
    t1 = DATA_DIR / "thumbnails" / f"{project_id}_thumb_1_viral.jpg"
    t2 = DATA_DIR / "thumbnails" / f"{project_id}_thumb_2_cinematic.jpg"
    if t1.exists() or t2.exists():
        thumbs = {
            "thumb1_url": f"/media/thumbnails/{t1.name}" if t1.exists() else None,
            "thumb2_url": f"/media/thumbnails/{t2.name}" if t2.exists() else None,
            "thumb1_path": str(t1) if t1.exists() else "",
            "thumb2_path": str(t2) if t2.exists() else "",
            "headline_line1": "VIRAL HOOK",
            "headline_line2": "WATCH NOW"
        }
        if project:
            project["thumbnails"] = thumbs
            save_project_to_history(project)
        return {"status": "success", "thumbnails": thumbs}

    # 3. Check OUTPUT_DIR for any matching thumbnail files
    if project:
        safe_name = re.sub(r'[^a-zA-Z0-9_\-]', '_', project.get("name", project_id))
        conf_out = str(load_settings().get("output_dir", "")).strip()
        dest_dir = Path(conf_out) if conf_out else OUTPUT_DIR
        out_t1 = dest_dir / f"{safe_name}_Thumbnail_Style1_ViralPunch.jpg"
        out_t2 = dest_dir / f"{safe_name}_Thumbnail_Style2_CinematicMystery.jpg"
        if out_t1.exists() or out_t2.exists():
            thumbs = {
                "thumb1_url": f"/media/output/{out_t1.name}" if out_t1.exists() else None,
                "thumb2_url": f"/media/output/{out_t2.name}" if out_t2.exists() else None,
                "thumb1_path": str(out_t1) if out_t1.exists() else "",
                "thumb2_path": str(out_t2) if out_t2.exists() else "",
                "headline_line1": "VIRAL HOOK",
                "headline_line2": "WATCH NOW"
            }
            project["thumbnails"] = thumbs
            save_project_to_history(project)
            return {"status": "success", "thumbnails": thumbs}

    # 4. If project exists, generate thumbnails now
    if project:
        try:
            from backend.thumbnail_generator import generate_youtube_thumbnails
            thumb_dir = DATA_DIR / "thumbnails"
            thumb_dir.mkdir(parents=True, exist_ok=True)
            thumbs = generate_youtube_thumbnails(project, target_dir=thumb_dir)
            project["thumbnails"] = thumbs
            save_project_to_history(project)
            return {"status": "success", "thumbnails": thumbs}
        except Exception as e:
            print(f"[ThumbnailGenerator] On-demand generation error: {e}")

    # 5. Fallback to latest project thumbnails from history
    history = load_projects_history()
    for p in history:
        if p.get("thumbnails"):
            return {"status": "success", "thumbnails": p["thumbnails"]}

    # Return empty success rather than 404 so UI doesn't crash
    return {
        "status": "not_ready",
        "thumbnails": None,
        "message": "Render a video to generate thumbnails"
    }


# ======================== TRANSITION SFX & YOUTUBE SEO SUITE ========================

@app.get("/api/sfx-tracks")
def list_sfx_tracks():
    sfx_dir = DATA_DIR / "sfx"
    sfx_dir.mkdir(parents=True, exist_ok=True)
    tracks = [
        {"id": "whoosh_soft", "name": "💨 Cinematic Whoosh", "recommended": True},
        {"id": "pop_punch", "name": "🥊 Punchy Pop", "recommended": True},
        {"id": "click_modern", "name": "📸 Modern Click", "recommended": False},
        {"id": "ding_bell", "name": "🔔 Ding Bell", "recommended": False},
        {"id": "none", "name": "🚫 Silent (No SFX)", "recommended": False}
    ]
    for t in tracks:
        if t["id"] != "none":
            fpath = sfx_dir / f"{t['id']}.mp3"
            t["exists"] = fpath.exists()
            t["web_url"] = f"/media/sfx/{t['id']}.mp3" if fpath.exists() else None
        else:
            t["exists"] = True
            t["web_url"] = None
    return {"status": "success", "tracks": tracks}


class GenerateSEORequest(BaseModel):
    project_id: Optional[str] = None
    text: Optional[str] = None
    topic: Optional[str] = None


@app.post("/api/generate-seo")
def generate_seo_endpoint(req: GenerateSEORequest):
    from backend.seo_generator import generate_youtube_seo
    text = (req.text or "").strip()
    scenes = None
    proj_id = req.project_id

    if proj_id:
        proj = ACTIVE_PROJECTS.get(proj_id)
        if not proj:
            history = load_projects_history()
            proj = next((p for p in history if p.get("id") == proj_id), None)
        if proj:
            if not text:
                text = " ".join([sc.get("narration", "") for sc in proj.get("scenes", [])])
            scenes = proj.get("scenes", [])

    if not text:
        text = "YouTube automated viral video breakdown and high value tips."

    seo_data = generate_youtube_seo(text=text, scenes=scenes, topic=req.topic)

    if proj_id:
        seo_dir = DATA_DIR / "seo"
        seo_dir.mkdir(parents=True, exist_ok=True)
        seo_file = seo_dir / f"{proj_id}_seo.json"
        with open(seo_file, "w", encoding="utf-8") as f:
            json.dump(seo_data, f, indent=2)

        proj = ACTIVE_PROJECTS.get(proj_id)
        if proj:
            proj["seo"] = seo_data
            save_project_to_history(proj)

    return seo_data


@app.get("/api/seo/{project_id}")
def get_seo_for_project(project_id: str):
    seo_file = DATA_DIR / "seo" / f"{project_id}_seo.json"
    if seo_file.exists():
        try:
            with open(seo_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    proj = ACTIVE_PROJECTS.get(project_id)
    if proj and "seo" in proj:
        return proj["seo"]
    return {"status": "not_found"}


class OpenFolderRequest(BaseModel):
    path: Optional[str] = None


class BrowseDirectoryRequest(BaseModel):
    initial_dir: Optional[str] = None


@app.post("/api/browse-directory")
def browse_directory(req: Optional[BrowseDirectoryRequest] = None):
    """Opens a native Windows directory picker dialog and returns the selected path."""
    settings = load_settings()
    init_dir = (req.initial_dir if req and req.initial_dir else None) or str(settings.get("output_dir", OUTPUT_DIR))
    selected_dir = ""
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        selected_dir = filedialog.askdirectory(initialdir=init_dir)
        root.destroy()
    except Exception as e:
        print(f"[BrowseDirectory] Native picker notice: {e}")
    return {"status": "success", "path": selected_dir or ""}


@app.get("/api/open-docs")
@app.post("/api/open-docs")
def open_docs_endpoint():
    """Opens docs.html in the user's default Windows web browser."""
    url = "http://127.0.0.1:8765/docs.html"
    try:
        import webbrowser
        webbrowser.open_new_tab(url)
        return {"status": "success", "url": url}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.get("/api/open-output-folder")
@app.post("/api/open-output-folder")
@app.get("/api/open-folder")
@app.post("/api/open-folder")
def open_folder(req: Optional[OpenFolderRequest] = None, path: Optional[str] = None):
    settings = load_settings()
    req_path = None
    if req and req.path:
        req_path = req.path
    elif path:
        req_path = path

    if req_path in ("thumbnails", "thumbnail"):
        conf_thumb = str(settings.get("thumbnail_output_dir", "")).strip()
        target_path = Path(conf_thumb) if conf_thumb else (DATA_DIR / "thumbnails")
    elif req_path in ("videos", "video", "output", "outputs") or not req_path:
        conf = str(settings.get("output_dir", "")).strip()
        target_path = Path(conf) if conf else OUTPUT_DIR
    else:
        target_path = Path(req_path)

    # If relative, resolve against DATA_DIR / BASE_DIR / OUTPUT_DIR
    if not target_path.is_absolute():
        if (OUTPUT_DIR / target_path).exists():
            target_path = OUTPUT_DIR / target_path
        elif (DATA_DIR / target_path).exists():
            target_path = DATA_DIR / target_path
        elif (BASE_DIR / target_path).exists():
            target_path = BASE_DIR / target_path
        else:
            target_path = OUTPUT_DIR / target_path

    # If target is an existing file (e.g. rendered mp4 video), open Explorer with file selected!
    if target_path.exists() and target_path.is_file():
        abs_path = os.path.normpath(str(target_path.resolve()))
        if os.name == "nt":
            try:
                subprocess.Popen(f'explorer.exe /select,"{abs_path}"')
            except Exception as e:
                print(f"[OpenFolder] explorer select failed: {e}")
        return {"status": "success", "path": abs_path, "type": "file"}

    # Target is a folder
    try:
        target_path.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    abs_path = os.path.normpath(str(target_path.resolve()))

    if os.name == "nt":
        try:
            os.startfile(abs_path)
        except Exception:
            try:
                subprocess.Popen(['explorer.exe', abs_path])
            except Exception as e2:
                print(f"[OpenFolder] explorer folder failed: {e2}")
    return {"status": "success", "path": abs_path, "type": "folder"}


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
        if not project and history:
            project = history[0]
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

    result = export_project_to_capcut(project, req.custom_options)
    return result




# ======================== BGM AUDIO ENDPOINTS ========================

SUPPORTED_BGM_EXTENSIONS = (".mp3", ".wav", ".aac", ".m4a", ".ogg")

@app.get("/api/bgm-tracks")
def get_bgm_tracks():
    bgm_dir = DATA_DIR / "assets" / "bgm"
    bgm_dir.mkdir(parents=True, exist_ok=True)
    tracks = [
        {"id": "cinematic_ambient", "name": "✨ Cinematic Ambient (Soft Chord Pad)", "file": "cinematic_ambient.mp3"},
        {"id": "lofi_chill", "name": "☕ Lofi Chill Beats (Relaxing Warm 7ths)", "file": "lofi_chill.mp3"},
        {"id": "deep_focus", "name": "🧘 Deep Focus Drone (Atmospheric)", "file": "deep_focus.mp3"},
        {"id": "none", "name": "🔇 None (Voiceover Only)", "file": ""}
    ]
    for p in bgm_dir.glob("*.*"):
        if p.suffix.lower() in SUPPORTED_BGM_EXTENSIONS:
            if p.stem not in ("cinematic_ambient", "lofi_chill", "deep_focus"):
                display_name = p.stem.replace("custom_", "", 1)
                # Remove timestamp prefix if present
                display_name = re.sub(r'^\d+_', '', display_name)
                tracks.append({
                    "id": p.name,
                    "name": f"🎵 {display_name} (Custom)",
                    "file": p.name,
                    "is_custom": True
                })
    return tracks


@app.post("/api/upload-bgm")
async def upload_bgm(file: UploadFile = File(...)):
    try:
        bgm_dir = DATA_DIR / "assets" / "bgm"
        bgm_dir.mkdir(parents=True, exist_ok=True)
        raw_name = file.filename or "custom_bgm.mp3"
        clean_name = re.sub(r'[^a-zA-Z0-9_.-]', '_', raw_name)
        if not clean_name.strip('_'):
            clean_name = "custom_bgm.mp3"
        filename = f"custom_{int(time.time())}_{clean_name}"
        target_path = bgm_dir / filename
        content = await file.read()
        with open(target_path, "wb") as buffer:
            buffer.write(content)

        return {
            "status": "success",
            "bgm_key": filename,
            "filename": file.filename,
            "path": str(target_path),
            "web_url": f"/media/assets/bgm/{filename}"
        }
    except Exception as e:
        print(f"[Server] upload_bgm error: {e}")
        raise HTTPException(status_code=500, detail=f"BGM upload failed: {str(e)}")

# ======================== VIDEO OVERLAY ENDPOINTS ========================

from .video_overlay import list_overlay_files, OVERLAY_DIR

@app.get("/api/overlay-files")
def get_overlay_files():
    """Lists all available overlay files (videos, images, logos)."""
    return list_overlay_files()

@app.post("/api/upload-overlay")
async def upload_overlay(file: UploadFile = File(...)):
    """Uploads a video/image file to use as a video overlay."""
    try:
        OVERLAY_DIR.mkdir(parents=True, exist_ok=True)
        raw_name = file.filename or "custom_overlay.mp4"
        clean_name = re.sub(r'[^a-zA-Z0-9_.-]', '_', raw_name)
        if not clean_name.strip('_'):
            clean_name = "custom_overlay.mp4"
        filename = f"overlay_{int(time.time())}_{clean_name}"
        target_path = OVERLAY_DIR / filename
        content = await file.read()
        with open(target_path, "wb") as buffer:
            buffer.write(content)

        # Determine type
        ext = Path(filename).suffix.lower()
        ovr_type = "video" if ext in (".mp4", ".mov", ".webm", ".avi") else "image"

        return {
            "status": "success",
            "overlay_key": str(target_path),
            "filename": file.filename,
            "path": str(target_path),
            "type": ovr_type,
            "size_kb": round(len(content) / 1024, 1),
            "web_url": f"/media/assets/overlays/{filename}"
        }
    except Exception as e:
        print(f"[Server] upload_overlay error: {e}")
        raise HTTPException(status_code=500, detail=f"Overlay upload failed: {str(e)}")

@app.delete("/api/overlay/{filename}")
def delete_overlay(filename: str):
    """Removes an uploaded overlay file."""
    try:
        target = OVERLAY_DIR / filename
        if target.exists():
            target.unlink()
            return {"status": "success", "message": f"Deleted {filename}"}
        raise HTTPException(status_code=404, detail="Overlay file not found")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ======================== VOICE CLONING ENDPOINTS ========================

@app.get("/api/clone-status")
def get_clone_status():
    """Returns voice cloning system status (available, model info, samples)."""
    try:
        from .voice_cloner import get_clone_status as _get_status
        return _get_status()
    except ImportError:
        return {
            "available": False,
            "model_name": "Kokoro-82M",
            "install_command": "pip install kokoro soundfile numpy",
            "samples_count": 0,
            "samples": []
        }

@app.get("/api/kokoro-voices")
def get_kokoro_voices():
    """Returns available Kokoro voice presets for the UI dropdown."""
    try:
        from .voice_cloner import KOKORO_VOICES
        return KOKORO_VOICES
    except ImportError:
        return []

@app.post("/api/upload-voice-sample")
async def upload_voice_sample(file: UploadFile = File(...)):
    """Uploads a 3-10 second voice reference audio sample for cloning."""
    try:
        from .config import VOICE_SAMPLES_DIR
        VOICE_SAMPLES_DIR.mkdir(parents=True, exist_ok=True)
        raw_name = file.filename or "voice_sample.mp3"
        clean_name = re.sub(r'[^a-zA-Z0-9_.-]', '_', raw_name)
        if not clean_name.strip('_'):
            clean_name = "voice_sample.mp3"
        filename = f"sample_{int(time.time())}_{clean_name}"
        target_path = VOICE_SAMPLES_DIR / filename
        content = await file.read()
        with open(target_path, "wb") as buffer:
            buffer.write(content)

        return {
            "status": "success",
            "filename": file.filename,
            "path": str(target_path),
            "size_kb": round(len(content) / 1024, 1),
            "web_url": f"/media/voice_samples/{filename}"
        }
    except Exception as e:
        print(f"[Server] upload_voice_sample error: {e}")
        raise HTTPException(status_code=500, detail=f"Voice sample upload failed: {str(e)}")

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
                    item["stage_desc"] = "Building sentence scenes with editorial direction..."

                    # 2. Editorial & Scene analysis with template max duration
                    editorial_dir = analyze_script_editorial_direction(
                        full_transcript_text=transcription.get("text", ""),
                        niche=niche
                    )
                    item["editorial_direction"] = editorial_dir

                    max_dur = item_tmpl.get("max_scene_duration", 3.5)
                    scenes = build_scenes(
                        transcription,
                        niche=niche,
                        editorial_direction=editorial_dir,
                        max_scene_duration=max_dur
                    )
                    
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
                        "editorial_direction": editorial_dir,
                        "fallback_scenes_count": fallback_count,
                        "created_at": time.strftime("%b %d, %Y %I:%M %p"),
                        "status": "ready_for_preview",
                        "aspect_ratio": item_tmpl.get("aspect_ratio", "16:9"),
                        "transition": item_tmpl.get("transition", "smoothleft"),
                        "transition_mode": item_tmpl.get("transition_mode", "fixed"),
                        "transition_duration": item_tmpl.get("transition_duration", 0.30),
                        "bgm_track": item_tmpl.get("bgm_track", "lofi_chill.mp3"),
                        "bgm_volume": item_tmpl.get("bgm_volume", 0.10),
                        "caption_style": item_tmpl.get("caption_style", "capcut-yellow"),
                        "callouts_enabled": item_tmpl.get("callouts_enabled", False),
                        "callout_style": item_tmpl.get("callout_style", "badge_yellow"),
                        "transition_sfx": item_tmpl.get("transition_sfx", None),
                        "transition_sfx_volume": item_tmpl.get("transition_sfx_volume", 0.40),
                        "emphasis_zoom_enabled": item_tmpl.get("emphasis_zoom_enabled", False),
                        "emphasis_zoom_intensity": item_tmpl.get("emphasis_zoom_intensity", 1.15)
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
                            custom_options={
                                "aspect_ratio": item_tmpl.get("aspect_ratio", "16:9"),
                                "callouts_enabled": item_tmpl.get("callouts_enabled", False),
                                "callout_style": item_tmpl.get("callout_style", "badge_yellow")
                            }
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
                            "transition_sfx": item_tmpl.get("transition_sfx", None),
                            "transition_sfx_volume": item_tmpl.get("transition_sfx_volume", 0.40),
                            "emphasis_zoom_enabled": item_tmpl.get("emphasis_zoom_enabled", False),
                            "emphasis_zoom_intensity": item_tmpl.get("emphasis_zoom_intensity", 1.15),
                            "enable_motion": item_tmpl.get("enable_motion", False),
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


@app.get("/favicon.ico")
def get_favicon():
    ico_file = FRONTEND_DIR / "favicon.ico"
    if ico_file.exists():
        return FileResponse(str(ico_file), media_type="image/x-icon")
    raise HTTPException(status_code=404, detail="Favicon not found")


@app.get("/media/{file_path:path}")
async def serve_media(file_path: str):
    """
    Robust media streaming endpoint that resolves audio/video files across
    DATA_DIR, cache directories, and alternative project paths with HTTP range support.
    """
    clean_rel = file_path.replace("\\", "/").lstrip("/")
    fname = Path(clean_rel).name

    candidates = [
        DATA_DIR / clean_rel,
        CACHE_DIR / clean_rel,
        CACHE_DIR / "scene_clips" / fname,
        CACHE_DIR / "stock_videos" / fname,
        DATA_DIR / "temp" / fname,
        DATA_DIR / "assets" / "bgm" / fname,

    ]
    for c in candidates:
        if c.exists() and c.is_file():
            ext = c.suffix.lower()
            media_type = "video/mp4" if ext == ".mp4" else ("audio/mpeg" if ext == ".mp3" else None)
            return FileResponse(str(c), media_type=media_type)
    raise HTTPException(status_code=404, detail=f"Media file '{file_path}' not found")


# Mount data folder to serve audio, video clips, and exported MP4s
app.mount("/media", StaticFiles(directory=str(DATA_DIR)), name="media")

# Mount frontend files
frontend_dir = FRONTEND_DIR
if frontend_dir.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8765, log_level="warning")
