import sys
import os
import time
import socket
import subprocess
import threading
import urllib.request
import webbrowser
from pathlib import Path

# Setup root paths and frozen bundle detection
if getattr(sys, "frozen", False):
    APP_DIR = Path(sys.executable).resolve().parent
    BUNDLE_DIR = Path(getattr(sys, "_MEIPASS", str(APP_DIR)))
else:
    APP_DIR = Path(__file__).resolve().parent
    BUNDLE_DIR = APP_DIR

# Ensure repository root is in Python import path
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))
if str(BUNDLE_DIR) not in sys.path:
    sys.path.insert(0, str(BUNDLE_DIR))

# Ensure bundled portable bin/ (ffmpeg, ffprobe) is prepended to system PATH
bin_candidates = [
    APP_DIR / "bin",
    BUNDLE_DIR / "bin",
    APP_DIR,
    BUNDLE_DIR
]
for b in bin_candidates:
    if b.exists() and (b / "ffmpeg.exe").exists():
        os.environ["PATH"] = str(b) + os.pathsep + os.environ.get("PATH", "")
        break

PORT = 8765
HOST = "127.0.0.1"
URL = f"http://{HOST}:{PORT}"


def wait_for_server(timeout: float = 12.0) -> bool:
    """Polls the local server until it responds to HTTP requests."""
    start = time.time()
    while time.time() - start < timeout:
        try:
            with urllib.request.urlopen(f"{URL}/api/projects", timeout=1.0) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            time.sleep(0.3)
    return False


def launch_native_window():
    """Launches Microsoft Edge in borderless standalone desktop App Mode or opens default browser."""
    # Wait for server to start responding
    ready = wait_for_server()
    if not ready:
        time.sleep(1.5)

    print(f"\n[VideoGen Studio] Server is ready at {URL}")

    # Check for Microsoft Edge to run in native App Mode
    edge_candidates = [
        Path(os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)")) / "Microsoft" / "Edge" / "Application" / "msedge.exe",
        Path(os.environ.get("ProgramFiles", "C:\\Program Files")) / "Microsoft" / "Edge" / "Application" / "msedge.exe",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "Edge" / "Application" / "msedge.exe",
    ]

    edge_found = None
    for cand in edge_candidates:
        if cand.exists():
            edge_found = cand
            break

    if edge_found:
        try:
            print(f"[VideoGen Studio] Opening in native desktop app mode via Edge: {edge_found}")
            subprocess.Popen([
                str(edge_found),
                f"--app={URL}",
                "--window-size=1380,880",
                "--window-position=60,40",
                "--title=VideoGen Studio"
            ])
            return
        except Exception as e:
            print(f"[VideoGen Studio] Could not launch Edge app mode: {e}")

    # Fallback to standard system browser
    print("[VideoGen Studio] Opening in default web browser...")
    webbrowser.open(URL)


def main():
    print("=" * 68)
    print("      VIDEO GEN STUDIO - AI YOUTUBE FULL HD VIDEO GENERATOR")
    print("                     Desktop Standalone Engine")
    print("=" * 68)
    print(f"[VideoGen Studio] App Directory: {APP_DIR}")
    print(f"[VideoGen Studio] Starting backend server at {URL} ...")

    # Import backend app
    try:
        from backend.server import app
        from backend.config import find_ffmpeg, find_ffprobe
        print(f"[VideoGen Studio] FFmpeg engine located: {find_ffmpeg()}")
        print(f"[VideoGen Studio] FFprobe engine located: {find_ffprobe()}")
    except Exception as e:
        print(f"[ERROR] Failed to load VideoGen Studio backend: {e}")
        import traceback
        traceback.print_exc()
        input("\nPress Enter to exit...")
        sys.exit(1)

    # Spawn UI launcher in a background thread
    launcher_thread = threading.Thread(target=launch_native_window, daemon=True)
    launcher_thread.start()

    # Run Uvicorn server directly with app instance
    import uvicorn
    uvicorn.run(app, host=HOST, port=PORT, log_level="warning")


if __name__ == "__main__":
    main()
