import sys
import os
import time
import webbrowser
import threading
import uvicorn
from pathlib import Path

# Ensure backend can be imported
sys.path.insert(0, str(Path(__file__).resolve().parent))

PORT = 8765
HOST = "127.0.0.1"
URL = f"http://{HOST}:{PORT}"


def open_browser():
    time.sleep(1.2)
    print(f"\n[VideoGen] VideoGen Studio is live! Opening browser at {URL} ...")
    webbrowser.open(URL)


if __name__ == "__main__":
    print("=" * 65)
    print("   [VideoGen] VideoGen Studio - AI YouTube Full HD Video Generator   ")
    print("=" * 65)
    print(f"Starting server on {URL} ...")

    # Launch browser in a background thread
    threading.Thread(target=open_browser, daemon=True).start()

    # Run FastAPI app via uvicorn
    uvicorn.run("backend.server:app", host=HOST, port=PORT, log_level="info")
