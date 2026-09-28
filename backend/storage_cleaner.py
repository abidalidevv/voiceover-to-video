import os
import time
import shutil
import threading
from pathlib import Path
from typing import Dict, Any, List, Optional
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


def purge_old_cache(
    max_age_seconds: int = 3 * 3600,
    include_outputs: bool = False,
    output_max_age_seconds: Optional[int] = None
) -> Dict[str, Any]:
    """
    Deletes stock video cache files, intermediate scene clips, and temp files older than max_age_seconds (default: 3 hours).
    Optionally cleans older rendered output/export files if include_outputs is True.
    Safely ignores locked files without crashing.
    """
    with CLEANER_LOCK:
        now = time.time()
        deleted_count = 0
        bytes_freed = 0
        errors = 0

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

        # Optionally prune older output and export videos (older than 3 hours or custom threshold)
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
            print(f"[StorageCleaner] Auto-cleaned {deleted_count} stale cache files (freed {mb_freed} MB).")

        return {
            "deleted_count": deleted_count,
            "bytes_freed": bytes_freed,
            "mb_freed": mb_freed,
            "errors": errors
        }


def cleanup_post_render(project_id: str = "") -> Dict[str, Any]:
    """
    Called immediately after a video is rendered:
    1. Removes all trimmed intermediate scene clips (CACHE_DIR / 'scene_clips') to immediately free space.
    2. Removes temporary subtitle (.ass) and audio files in TEMP_DIR.
    Leaves the final master rendered video in OUTPUT_DIR completely intact.
    """
    with CLEANER_LOCK:
        deleted_count = 0
        bytes_freed = 0
        errors = 0

        # Clean scene clips
        scene_clips_dir = CACHE_DIR / "scene_clips"
        if scene_clips_dir.exists():
            try:
                for entry in os.scandir(str(scene_clips_dir)):
                    if entry.is_file(follow_symlinks=False):
                        try:
                            fsize = entry.stat().st_size
                            os.remove(entry.path)
                            deleted_count += 1
                            bytes_freed += fsize
                        except Exception:
                            errors += 1
            except Exception:
                errors += 1

        # Clean temp rendering folders and stale intermediate files in TEMP_DIR
        if TEMP_DIR.exists():
            now_ts = time.time()
            try:
                for entry in os.scandir(str(TEMP_DIR)):
                    if entry.is_dir(follow_symlinks=False):
                        # Intermediate render segment folders (e.g. render_1790544467)
                        if entry.name.startswith("render_"):
                            try:
                                dir_age = now_ts - entry.stat().st_mtime
                                if dir_age >= 120:  # Only clean segment folders older than 2 minutes
                                    d_size = get_directory_size(Path(entry.path))
                                    shutil.rmtree(entry.path, ignore_errors=True)
                                    bytes_freed += d_size
                                    deleted_count += 1
                            except Exception:
                                errors += 1
                    elif entry.is_file(follow_symlinks=False):
                        try:
                            file_age = now_ts - entry.stat().st_mtime
                            # Protect active preview/render files: only purge temp files older than 10 minutes
                            if file_age >= 600:
                                name_lower = entry.name.lower()
                                if name_lower.endswith((".ass", ".tmp", ".wav", ".aac", ".ts")):
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
            print(f"[StorageCleaner] Post-render cleanup: freed {mb_freed} MB of intermediate scene data.")

        return {
            "deleted_count": deleted_count,
            "bytes_freed": bytes_freed,
            "mb_freed": mb_freed,
            "errors": errors
        }


def purge_all_cache(keep_outputs: bool = True) -> Dict[str, Any]:
    """
    Immediate full purge of all raw stock videos, scene clips, and temp files.
    Preserves final master videos in OUTPUT_DIR if keep_outputs is True.
    """
    with CLEANER_LOCK:
        deleted_count = 0
        bytes_freed = 0
        errors = 0

        target_dirs = [
            CACHE_DIR / "stock_videos",
            CACHE_DIR / "scene_clips",
            CACHE_DIR / "scene_images",
            TEMP_DIR
        ]

        if not keep_outputs:
            target_dirs.extend([OUTPUT_DIR, DATA_DIR / "exports"])

        for folder in target_dirs:
            if not folder.exists():
                continue
            try:
                for entry in os.scandir(str(folder)):
                    if entry.is_file(follow_symlinks=False):
                        try:
                            fsize = entry.stat().st_size
                            os.remove(entry.path)
                            deleted_count += 1
                            bytes_freed += fsize
                        except Exception:
                            errors += 1
            except Exception:
                errors += 1

        mb_freed = round(bytes_freed / (1024 * 1024), 2)
        print(f"[StorageCleaner] Full cache purge: deleted {deleted_count} files, reclaimed {mb_freed} MB.")

        return {
            "deleted_count": deleted_count,
            "bytes_freed": bytes_freed,
            "mb_freed": mb_freed,
            "errors": errors
        }


def start_auto_cleaner_daemon(interval_minutes: int = 30, retention_hours: int = 3):
    """
    Starts a background daemon thread that periodically runs every interval_minutes.
    Automatically purges cache, raw clips, and old output files older than retention_hours (default: 3 hours).
    Ensures the hard drive never gets overloaded.
    """
    global _CLEANER_DAEMON_STARTED
    if _CLEANER_DAEMON_STARTED:
        return
    _CLEANER_DAEMON_STARTED = True

    def _cleaner_loop():
        # Small delay at launch to let server boot up smoothly
        time.sleep(15)
        while True:
            try:
                settings = load_settings()
                if bool(settings.get("auto_cleanup_cache", True)):
                    cfg_hours = int(settings.get("cache_retention_hours", retention_hours))
                    max_age_s = max(1800, cfg_hours * 3600)  # Minimum 30 mins
                    # Clean cache and old temporary data older than retention hours
                    purge_old_cache(max_age_seconds=max_age_s, include_outputs=False)
            except Exception as e:
                print(f"[StorageCleaner] Daemon notice: {e}")
            time.sleep(interval_minutes * 60)

    t = threading.Thread(target=_cleaner_loop, daemon=True, name="StorageCleanerDaemon")
    t.start()
    print(f"[StorageCleaner] Background auto-cleaner daemon started (checks every {interval_minutes}m, retention: {retention_hours}h).")
