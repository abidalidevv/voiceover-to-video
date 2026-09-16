import subprocess
import os

ass_content = """[Script Info]
Title: Test Captions
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial Black,48,&H0000FFFF,&H00FFFFFF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,4,2,2,40,40,100,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:00.00,0:00:03.00,Default,,0,0,0,,{\\kf100}Positive {\\kf100}Psychology {\\kf100}Science
"""

with open("test_sub.ass", "w", encoding="utf-8") as f:
    f.write(ass_content)

# Render 3 sec test video with black background and burn in subtitles
escaped_ass = os.path.abspath("test_sub.ass").replace("\\", "/").replace(":", "\\:")
cmd = [
    "ffmpeg", "-y",
    "-f", "lavfi", "-i", "color=c=navy:s=1920x1080:d=3",
    "-vf", f"ass='{escaped_ass}'",
    "-c:v", "libx264", "-pix_fmt", "yuv420p",
    "test_sub_out.mp4"
]

print("Running ffmpeg...")
res = subprocess.run(cmd, capture_output=True, text=True)
if res.returncode == 0:
    print("SUCCESS: test_sub_out.mp4 created!")
    # Check with ffprobe
    p = subprocess.run(["ffprobe", "-v", "quiet", "-show_entries", "stream=width,height,duration", "-of", "csv=p=0", "test_sub_out.mp4"], capture_output=True, text=True)
    print("Probe output:", p.stdout.strip())
else:
    print("FFmpeg error:", res.stderr[-500:])
