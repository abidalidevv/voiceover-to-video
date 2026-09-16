import subprocess
import os

concat_path = "test_concat.txt"
with open(concat_path, "w") as f:
    for i in range(7):
        p = os.path.abspath(f"data/cache/b3a9c9fa_norm_{i}.mp4").replace("\\", "/")
        f.write(f"file '{p}'\n")

cmd = [
    "ffmpeg", "-y", "-f", "concat", "-safe", "0",
    "-i", concat_path,
    "-c", "copy",
    "test_concat_out.mp4"
]

print("Running test concat...")
res = subprocess.run(cmd, capture_output=True, text=True)
if res.returncode == 0:
    print("SUCCESS: test_concat_out.mp4 created!")
    p = subprocess.run(["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", "test_concat_out.mp4"], capture_output=True, text=True)
    print("Duration:", p.stdout.strip())
else:
    print("Error:", res.stderr[-400:])
