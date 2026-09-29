import os
import json
import time
import shutil
import threading
from pathlib import Path
from typing import Dict, Any, List, Optional, Set
from .config import CACHE_DIR, TEMP_DIR, OUTPUT_DIR, DATA_DIR, load_settings

# Thread lock to prevent race conditions during file pruning
CLEANER_LOCK = threading.Lock()
_CLEANER_DAEMON_STARTED = False


def get_directory_size(path: Path) -> int:
    """Calculates total size of all files in a directory in bytes."""
    if not path or not path.exists():
        return 0
    total = 0
    try:
        for entry in os.scandir(str(path)):
            if entry.is_file(follow_symlinks=False):
                total += entry.stat().st_size
            elif entry.is_dir(follow_symlinks=False):
                total += get_directory_size(Path(entry.path))
    except Exception:
        pass
    return total


def get_storage_usage() -> Dict[str, Any]:
    """Returns current disk usage breakdown of VideoGen data folders in Megabytes."""
    stock_videos_dir = CACHE_DIR / "stock_videos"
    scene_clips_dir = CACHE_DIR / "scene_clips"
    temp_dir = TEMP_DIR
    output_dir = OUTPUT_DIR
    exports_dir = DATA_DIR / "exports"

    stock_mb = round(get_directory_size(stock_videos_dir) / (1024 * 1024), 2)
    scenes_mb = round(get_directory_size(scene_clips_dir) / (1024 * 1024), 2)
    temp_mb = round(get_directory_size(temp_dir) / (1024 * 1024), 2)
    output_mb = round(get_directory_size(output_dir) / (1024 * 1024), 2)
    exports_mb = round(get_directory_size(exports_dir) / (1024 * 1024), 2)
    total_cache_mb = round(stock_mb + scenes_mb + temp_mb, 2)

    return {
        "stock_videos_mb": stock_mb,
        "scene_clips_mb": scenes_mb,
        "temp_mb": temp_mb,
        "output_mb": output_mb,
        "exports_mb": exports_mb,
        "total_cache_mb": total_cache_mb
    }


def get_protected_project_paths() -> Set[str]:
    """
    Scans active in-memory projects and projects_history.json.
    Returns a normalized set of absolute file paths that are currently in use
    and MUST NEVER be deleted by background or automatic cache cleanups.
    """
    protected: Set[str] = set()
    try:
        projects_file = DATA_DIR / "projects_history.json"
        all_projects: List[Dict[str, Any]] = []
        if projects_file.exists():
            try:
                with open(projects_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        all_projects.extend(data)
            except Exception:
                pass

        # Try to read active in-memory projects from server if already imported
        try:
            from .server import ACTIVE_PROJECTS
            all_projects.extend(list(ACTIVE_PROJECTS.values()))
        except Exception:
            pass

        for p in all_projects:
            if not isinstance(p, dict):
                continue

            # 1. Voiceover audio path
            if p.get("audio_path"):
                try:
                    protected.add(str(Path(p["audio_path"]).resolve()).lower())
                except Exception:
                    pass

            # 2. Rendered video output
            rv = p.get("rendered_video")
            if isinstance(rv, dict) and rv.get("file_path"):
                try:
                    protected.add(str(Path(rv["file_path"]).resolve()).lower())
                except Exception:
                    pass

            # 3. Scene clips (both trimmed clip and source raw stock video)
            for sc in p.get("scenes", []):
                if not isinstance(sc, dict):
                    continue
                vc = sc.get("video_clip")
                if isinstance(vc, dict):
                    if vc.get("file_path"):
                        try:
                            protected.add(str(Path(vc["file_path"]).resolve()).lower())
                        except Exception:
                            pass
                    if vc.get("raw_file_path"):
                        try:
                            protected.add(str(Path(vc["raw_file_path"]).resolve()).lower())
                        except Exception:
                            pass

            # 4. Thumbnails
            for t in p.get("thumbnails", []):
                if isinstance(t, dict) and t.get("path"):
                    try:
                        protected.add(str(Path(t["path"]).resolve()).lower())
                    except Exception:
                        pass
    except Exception as e:
        print(f"[StorageCleaner] Notice gathering protected project paths: {e}")

    return protected


def purge_old_cache(
    max_age_seconds: int = 3 * 3600,
    include_outputs: bool = False,
    output_max_age_seconds: Optional[int] = None
) -> Dict[str, Any]:
    """
    Project-Aware Cache Cleaner:
    Deletes truly orphaned stock video cache files, intermediate scene clips, and temp files older than max_age_seconds.
    PROTECTS all active/saved projects: files currently referenced by any project are NEVER deleted.
    Safely ignores locked files without crashing.
    """
    with CLEANER_LOCK:
        now = time.time()
        deleted_count = 0
        bytes_freed = 0
        errors = 0

        # Protect all assets belonging to active or saved projects
        protected_paths = get_protected_project_paths()

        target_dirs: List[Path] = [
            CACHE_DIR / "stock_videos",
            CACHE_DIR / "scene_clips",
            CACHE_DIR / "scene_images",
            TEMP_DIR
        ]

        # Scan cache and temp folders
        for folder in target_dirs:
            if not folder.exists():
                continue
            try:
                for entry in os.scandir(str(folder)):
                    if entry.is_file(follow_symlinks=False):
                        try:
                            resolved_str = str(Path(entry.path).resolve()).lower()
                            # Never delete a file in use by an active/saved project!
                            if resolved_str in protected_paths:
                                continue

                            stat = entry.stat()
                            file_age = now - stat.st_mtime
                            if file_age >= max_age_seconds:
                                fsize = stat.st_size
                                os.remove(entry.path)
                                deleted_count += 1
                                bytes_freed += fsize
                        except Exception:
                            errors += 1
            except Exception:
                errors += 1

        # Optionally prune older output and export videos (only unreferenced ones)
        if include_outputs:
            out_cutoff = output_max_age_seconds if output_max_age_seconds is not None else max_age_seconds
            out_folders = [OUTPUT_DIR, DATA_DIR / "exports"]
            for folder in out_folders:
                if not folder.exists():
                    continue
                try:
                    for entry in os.scandir(str(folder)):
                        if entry.is_file(follow_symlinks=False) and entry.name.lower().endswith((".mp4", ".mov", ".zip")):
                            try:
                                resolved_str = str(Path(entry.path).resolve()).lower()
                                if resolved_str in protected_paths:
                                    continue
                                stat = entry.stat()
                                file_age = now - stat.st_mtime
                                if file_age >= out_cutoff:
                                    fsize = stat.st_size
                                    os.remove(entry.path)
                                    deleted_count += 1
                                    bytes_freed += fsize
                            except Exception:
                                errors += 1
                except Exception:
                    errors += 1

        mb_freed = round(bytes_freed / (1024 * 1024), 2)
        if deleted_count > 0:
            print(f"[StorageCleaner] Project-aware auto-clean: removed {deleted_count} orphaned files (freed {mb_freed} MB). Active projects untouched.")

        return {
            "deleted_count": deleted_count,
            "bytes_freed": bytes_freed,
            "mb_freed": mb_freed,
            "errors": errors
        }


def cleanup_post_render(project_id: str = "") -> Dict[str, Any]:
    """
    Called immediately after a video is rendered:
    1. Removes temporary intermediate render segment folders (e.g. TEMP_DIR / render_XXXX) and stale .tmp/.ts files.
    2. KEEPS project scene clips (CACHE_DIR / 'scene_clips') INTACT so the user can:
       - Replay scenes smoothly in the studio preview
       - Re-render in different resolutions/aspect ratios
       - Export to CapCut PC without missing media
    """
    with CLEANER_LOCK:
        deleted_count = 0
        bytes_freed = 0
        errors = 0

        # Clean only intermediate render segment folders and temporary chunk files in TEMP_DIR
        if TEMP_DIR.exists():
            now_ts = time.time()
            try:
                for entry in os.scandir(str(TEMP_DIR)):
                    if entry.is_dir(follow_symlinks=False):
                        # Intermediate render segment folders (e.g. render_1790544467)
                        if entry.name.startswith("render_"):
                            try:
                                dir_age = now_ts - entry.stat().st_mtime
                                if dir_age >= 120:  # Older than 2 minutes
                                    d_size = get_directory_size(Path(entry.path))
                                    shutil.rmtree(entry.path, ignore_errors=True)
                                    bytes_freed += d_size
                                    deleted_count += 1
                            except Exception:
                                errors += 1
                    elif entry.is_file(follow_symlinks=False):
                        try:
                            file_age = now_ts - entry.stat().st_mtime
                            # Only purge temporary render segment/mux artifacts older than 10 minutes
                            if file_age >= 600:
                                name_lower = entry.name.lower()
                                if name_lower.endswith((".tmp", ".ts", ".m4s")):
                                    fsize = entry.stat().st_size
                                    os.remove(entry.path)
                                    deleted_count += 1
                                    bytes_freed += fsize
                        except Exception:
                            errors += 1
            except Exception:
                errors += 1

        mb_freed = round(bytes_freed / (1024 * 1024), 2)
        if deleted_count > 0:
            print(f"[StorageCleaner] Post-render temp cleanup: freed {mb_freed} MB of render chunk files.")

        return {
            "deleted_count": deleted_count,
            "bytes_freed": bytes_freed,
            "mb_freed": mb_freed,
            "errors": errors
        }


def delete_project_assets(project_id: str, project_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Safely and completely deletes all assets belonging specifically to a single project:
    - Intermediate scene clips (CACHE_DIR / scene_clips)
    - Rendered output video in OUTPUT_DIR
    - Project temporary audio & .ass subtitle files in TEMP_DIR
    - Generated thumbnails in DATA_DIR / thumbnails
    - Project SEO metadata
    Leaves all other projects 100% untouched.
    """
    if not project_id:
        return {"status": "error", "message": "No project_id provided", "deleted_count": 0, "bytes_freed": 0}

    with CLEANER_LOCK:
        deleted_count = 0
        bytes_freed = 0
        errors = 0

        # Find project data if not passed
        p = project_data
        if not p:
            projects_file = DATA_DIR / "projects_history.json"
            if projects_file.exists():
                try:
                    with open(projects_file, "r", encoding="utf-8") as f:
                        history = json.load(f)
                        p = next((item for item in history if item.get("id") == project_id), None)
                except Exception:
                    pass

        files_to_delete: List[Path] = []

        if p:
            # 1. Rendered master video
            rv = p.get("rendered_video")
            if isinstance(rv, dict) and rv.get("file_path"):
                files_to_delete.append(Path(rv["file_path"]))
            elif isinstance(rv, dict) and rv.get("filename"):
                files_to_delete.append(OUTPUT_DIR / rv["filename"])

            # 2. Scene clips
            for sc in p.get("scenes", []):
                if not isinstance(sc, dict):
                    continue
                vc = sc.get("video_clip")
                if isinstance(vc, dict) and vc.get("file_path"):
                    files_to_delete.append(Path(vc["file_path"]))

            # 3. Voiceover audio in temp
            if p.get("audio_filename"):
                files_to_delete.append(TEMP_DIR / p["audio_filename"])
            if p.get("audio_path"):
                aud_p = Path(p["audio_path"])
                # Only delete if inside TEMP_DIR so we never delete user's source files outside project
                try:
                    if TEMP_DIR.resolve() in aud_p.resolve().parents or aud_p.parent == TEMP_DIR:
                        files_to_delete.append(aud_p)
                except Exception:
                    pass

            # 4. Project thumbnails
            for t in p.get("thumbnails", []):
                if isinstance(t, dict) and t.get("path"):
                    files_to_delete.append(Path(t["path"]))

            # 5. Bundle prefix thumbnails
            b_prefix = p.get("bundle_prefix")
            if b_prefix:
                thumb_dir = DATA_DIR / "thumbnails"
                if thumb_dir.exists():
                    for t_file in thumb_dir.glob(f"{b_prefix}_*.*"):
                        files_to_delete.append(t_file)

        # 6. Specific project subtitle file
        ass_file = TEMP_DIR / f"{project_id}_subtitles.ass"
        if ass_file.exists():
            files_to_delete.append(ass_file)

        # 7. Specific SEO cache file
        seo_file = DATA_DIR / "seo" / f"{project_id}.json"
        if seo_file.exists():
            files_to_delete.append(seo_file)

        # De-duplicate files list
        unique_paths: Set[str] = set()
        for f in files_to_delete:
            try:
                res_str = str(f.resolve())
                if res_str not in unique_paths:
                    unique_paths.add(res_str)
                    if f.exists() and f.is_file():
                        fsize = f.stat().st_size
                        f.unlink(missing_ok=True)
                        deleted_count += 1
                        bytes_freed += fsize
            except Exception:
                errors += 1

        mb_freed = round(bytes_freed / (1024 * 1024), 2)
        print(f"[StorageCleaner] Manual project delete ({project_id}): removed {deleted_count} associated assets (freed {mb_freed} MB).")

        return {
            "status": "success",
            "project_id": project_id,
            "deleted_count": deleted_count,
            "bytes_freed": bytes_freed,
            "mb_freed": mb_freed,
            "errors": errors
        }


def delete_all_projects_assets(history: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """
    Safely deletes all assets for all projects in history and clears cache.
    """
    all_projects = history or []
    if not all_projects:
        projects_file = DATA_DIR / "projects_history.json"
        if projects_file.exists():
            try:
                with open(projects_file, "r", encoding="utf-8") as f:
                    all_projects = json.load(f)
            except Exception:
                all_projects = []

    total_deleted = 0
    total_freed = 0
    for p in all_projects:
        pid = p.get("id")
        if pid:
            res = delete_project_assets(pid, project_data=p)
            total_deleted += res.get("deleted_count", 0)
            total_freed += res.get("bytes_freed", 0)

    # Clean orphaned thumbnails and scene clips
    purge_res = purge_old_cache(max_age_seconds=0, include_outputs=True)
    total_deleted += purge_res.get("deleted_count", 0)
    total_freed += purge_res.get("bytes_freed", 0)

    mb_freed = round(total_freed / (1024 * 1024), 2)
    return {
        "status": "success",
        "deleted_count": total_deleted,
        "bytes_freed": total_freed,
        "mb_freed": mb_freed
    }


def purge_all_cache(keep_outputs: bool = True) -> Dict[str, Any]:
    """
    Immediate full purge of unreferenced stock videos, scene clips, and temp files.
    Preserves final master videos in OUTPUT_DIR if keep_outputs is True.
    """
    return purge_old_cache(max_age_seconds=0, include_outputs=not keep_outputs)


def start_auto_cleaner_daemon(interval_minutes: int = 30, retention_hours: int = 3):
    """
    Starts a background daemon thread that periodically runs every interval_minutes.
    Automatically purges unreferenced orphaned clips and old temporary data older than retention_hours (default: 3 hours).
    PROTECTS all active/saved projects: files belonging to any project are NEVER deleted.
    """
    global _CLEANER_DAEMON_STARTED
    if _CLEANER_DAEMON_STARTED:
        return
    _CLEANER_DAEMON_STARTED = True

    def _cleaner_loop():
        time.sleep(15)
        while True:
            try:
                settings = load_settings()
                if bool(settings.get("auto_cleanup_cache", True)):
                    cfg_hours = int(settings.get("cache_retention_hours", retention_hours))
                    max_age_s = max(1800, cfg_hours * 3600)  # Minimum 30 mins
                    purge_old_cache(max_age_seconds=max_age_s, include_outputs=False)
            except Exception as e:
                print(f"[StorageCleaner] Daemon notice: {e}")
            time.sleep(interval_minutes * 60)

    t = threading.Thread(target=_cleaner_loop, daemon=True, name="StorageCleanerDaemon")
    t.start()
    print(f"[StorageCleaner] Background auto-cleaner daemon started (checks every {interval_minutes}m, retention: {retention_hours}h, project-aware: YES).")
