import requests
import time
import json
import subprocess
from pathlib import Path

BASE = "http://127.0.0.1:8765"
temp_dir = Path(r"c:\Users\Abid\Desktop\VideoGen\data\temp")
temp_dir.mkdir(parents=True, exist_ok=True)

# Generate dedicated 8.0s test audio file
t_mp3 = temp_dir / "quick_audit_audio.mp3"
subprocess.run([
    "ffmpeg", "-y", "-f", "lavfi",
    "-i", "sine=frequency=440:duration=8.0",
    "-c:a", "libmp3lame", "-b:a", "128k",
    str(t_mp3)
], check=True, capture_output=True)

target_audio = t_mp3.name
print(f"Starting generation test with {target_audio} (8.0s)...")

r = requests.post(f"{BASE}/api/start-generate", json={
    "audio_filename": target_audio,
    "niche": "Motivation Psychology",
    "pipeline": "Main"
})
assert r.status_code == 200, f"start-generate failed: {r.text}"
job_id = r.json()["job_id"]
print(f"Job started: {job_id}")

proj = None
for i in range(120):
    time.sleep(1)
    status_res = requests.get(f"{BASE}/api/job-progress/{job_id}").json()
    status = status_res.get("status")
    pct = status_res.get("percent", 0)
    stage = status_res.get("stage_title", "")
    print(f"  [{pct}%] {status} - {stage}")
    if status == "completed":
        proj = status_res["project"]
        print(f"Job completed! Project ID: {proj['id']}, Scenes: {len(proj['scenes'])}")
        break
    elif status == "error":
        print("Error:", status_res.get("error"))
        assert False, f"Job failed: {status_res.get('error')}"

assert proj is not None, "Project was not generated"

print("Testing render...")
render_res = requests.post(f"{BASE}/api/render", json={
    "project_id": proj["id"],
    "preset_key": "capcut_yellow",
    "custom_options": {
        "transition": "smoothleft",
        "bgm_track": "cinematic_ambient",
        "bgm_volume": 0.10
    },
    "fps": 30
})
assert render_res.status_code == 200, f"Render failed: {render_res.text}"
render_data = render_res.json()
print("Render successful! Output:", render_data["output_file"])
print("[SUCCESS] Deep audit verified complete generation + render workflow via live FastAPI!")
