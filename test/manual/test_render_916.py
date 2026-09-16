import subprocess
import os

# Normalize first 2 clips for 9:16 (1080x1920)
c0_in = os.path.abspath("data/projects/b3a9c9fa/clips/scene_0_pexels_9574132.mp4").replace("\\", "/")
c1_in = os.path.abspath("data/projects/b3a9c9fa/clips/scene_1_pexels_9902187.mp4").replace("\\", "/")

c0_out = os.path.abspath("data/cache/test_916_0.mp4").replace("\\", "/")
c1_out = os.path.abspath("data/cache/test_916_1.mp4").replace("\\", "/")

w, h = 1080, 1920

print("Normalizing 9:16 clips...")
# Clip 0: 15s
subprocess.run([
    "ffmpeg", "-y", "-i", c0_in, "-t", "15",
    "-vf", f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},fps=30",
    "-c:v", "libx264", "-preset", "ultrafast", "-crf", "22", "-an", "-pix_fmt", "yuv420p",
    c0_out
], check=True, capture_output=True)

# Clip 1: 15s
subprocess.run([
    "ffmpeg", "-y", "-i", c1_in, "-t", "15",
    "-vf", f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},fps=30",
    "-c:v", "libx264", "-preset", "ultrafast", "-crf", "22", "-an", "-pix_fmt", "yuv420p",
    c1_out
], check=True, capture_output=True)

# Concat
concat_txt = "test_916_concat.txt"
with open(concat_txt, "w") as f:
    f.write(f"file '{c0_out}'\nfile '{c1_out}'\n")

# Render 9:16 with audio
out_916 = "test_export_9x16.mp4"
cmd = [
    "ffmpeg", "-y",
    "-f", "concat", "-safe", "0", "-i", concat_txt,
    "-i", "data/projects/b3a9c9fa/audio.mp3",
    "-c:v", "copy",
    "-c:a", "aac", "-b:a", "192k",
    "-shortest",
    "-t", "30",
    out_916
]
subprocess.run(cmd, check=True, capture_output=True)

print("SUCCESS: 9:16 video rendered!")
p = subprocess.run(["ffprobe", "-v", "quiet", "-show_entries", "stream=width,height,codec_name:format=duration", "-of", "csv=p=0", out_916], capture_output=True, text=True)
print("9:16 FFprobe info:\n", p.stdout.strip())

# Extract frame
subprocess.run(["ffmpeg", "-y", "-ss", "00:00:05", "-i", out_916, "-vframes", "1", "-q:v", "2", "frame_916.jpg"], capture_output=True)
print("Extracted frame_916.jpg")
