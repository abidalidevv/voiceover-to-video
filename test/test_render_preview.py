import subprocess
import os

ass_path = os.path.abspath("data/projects/b3a9c9fa/captions.ass").replace("\\", "/").replace(":", "\\:")
audio_path = os.path.abspath("data/projects/b3a9c9fa/audio.mp3").replace("\\", "/")

cmd = [
    "ffmpeg", "-y",
    "-i", "test_concat_out.mp4",
    "-i", "data/projects/b3a9c9fa/audio.mp3",
    "-vf", f"ass='{ass_path}'",
    "-c:v", "libx264", "-preset", "ultrafast", "-crf", "22",
    "-c:a", "aac", "-b:a", "192k",
    "-pix_fmt", "yuv420p",
    "-shortest",
    "-t", "30", # render first 30 seconds for verification
    "test_final_preview_30s.mp4"
]

print("Rendering 30s verified video with captions and audio...")
res = subprocess.run(cmd, capture_output=True, text=True)
if res.returncode == 0:
    print("SUCCESS: test_final_preview_30s.mp4 rendered!")
    p = subprocess.run(["ffprobe", "-v", "quiet", "-show_entries", "stream=width,height,codec_name:format=duration", "-of", "csv=p=0", "test_final_preview_30s.mp4"], capture_output=True, text=True)
    print("FFprobe info:\n", p.stdout.strip())
else:
    print("FFmpeg error:", res.stderr[-500:])
