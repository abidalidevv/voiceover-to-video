import os
import sys
import shutil
import zipfile
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DIST_DIR = BASE_DIR / "dist"
RELEASE_FOLDER = DIST_DIR / "VideoGenStudio"
ZIP_OUTPUT = DIST_DIR / "VideoGenStudio-Windows-Portable.zip"


def create_release_zip():
    print("=" * 68)
    print("    VideoGen Studio - Standalone Portable Release Packager")
    print("=" * 68)

    if not RELEASE_FOLDER.exists():
        print(f"[ERROR] Release directory does not exist: {RELEASE_FOLDER}")
        print("Please run build_exe.bat first to compile VideoGenStudio.exe!")
        sys.exit(1)

    exe_file = RELEASE_FOLDER / "VideoGenStudio.exe"
    if not exe_file.exists():
        print(f"[ERROR] VideoGenStudio.exe not found in {RELEASE_FOLDER}")
        sys.exit(1)

    print(f"\n[1/3] Cleaning temporary caches from release folder...")
    # Clean cache/output/temp media files
    for media_dir in [RELEASE_FOLDER / "data" / "cache", RELEASE_FOLDER / "data" / "output", RELEASE_FOLDER / "data" / "temp", RELEASE_FOLDER / "_internal" / "data" / "cache", RELEASE_FOLDER / "_internal" / "data" / "output", RELEASE_FOLDER / "_internal" / "data" / "temp"]:
        if media_dir.exists():
            for f in media_dir.glob("*.*"):
                try:
                    f.unlink()
                except Exception:
                    pass

    print(f"[2/3] Preparing portable package from {RELEASE_FOLDER}...")
    if ZIP_OUTPUT.exists():
        try:
            ZIP_OUTPUT.unlink()
        except Exception:
            pass

    print(f"[3/3] Compressing into {ZIP_OUTPUT.name}...")
    with zipfile.ZipFile(ZIP_OUTPUT, "w", zipfile.ZIP_DEFLATED, compresslevel=3) as zf:
        for root, dirs, files in os.walk(RELEASE_FOLDER):
            for file in files:
                full_path = Path(root) / file
                rel_path = full_path.relative_to(DIST_DIR)
                zf.write(full_path, arcname=str(rel_path))

    size_mb = ZIP_OUTPUT.stat().st_size / (1024 * 1024)
    print("\n" + "=" * 68)
    print(f"[SUCCESS] Standalone Portable Package Ready!")
    print(f"Archive: {ZIP_OUTPUT}")
    print(f"Size:    {size_mb:.1f} MB")
    print("=" * 68)
    print("You can share this single ZIP file with anyone. They only need to:")
    print("1. Extract the ZIP file.")
    print("2. Double-click VideoGenStudio.exe.")
    print("Zero installation, zero errors on any Windows PC!\n")


if __name__ == "__main__":
    create_release_zip()
