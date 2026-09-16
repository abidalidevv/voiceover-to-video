import json
import sqlite3
import re
import time
from groq import Groq

conn = sqlite3.connect("data/videogen.db")
row = conn.execute("SELECT transcript_json, niche FROM projects WHERE id='b3a9c9fa'").fetchone()
key = conn.execute("SELECT value FROM settings WHERE key='groq_api_key'").fetchone()[0]
transcript = json.loads(row[0])
niche = row[1] or "educational / psychology"
duration = transcript.get("duration", 298.0)
text = transcript.get("text", "")

client = Groq(api_key=key)

prompt = f"""You are a professional video editor AI.
Video Niche: {niche}
Total Duration: {duration:.1f} seconds
Narration:
{text[:3000]}

Generate 10 to 14 visual scenes covering the video from 0.0s to {duration:.1f}s.
For each scene provide:
- index: 0, 1, 2...
- start_time and end_time (in seconds)
- text: brief excerpt of narration
- search_queries: array of 2 visual search queries for stock video APIs (e.g. "scientist laboratory microscope", "happy group friends outdoors")
- mood: visual mood

Return ONLY valid JSON in this structure:
{{"scenes": [{{"index": 0, "start_time": 0.0, "end_time": 20.0, "text": "...", "search_queries": ["query 1", "query 2"], "mood": "inspiring"}}]}}
"""

print("Calling openai/gpt-oss-120b...", flush=True)
t0 = time.time()
res = client.chat.completions.create(
    model="openai/gpt-oss-120b",
    messages=[{"role": "user", "content": prompt}],
    max_tokens=900,
    temperature=0.2
)
dt = time.time() - t0
print(f"Call finished in {dt:.2f}s!", flush=True)

content = res.choices[0].message.content
match = re.search(r'\{.*\}', content, re.DOTALL)
if match:
    data = json.loads(match.group(0))
    scenes = data.get("scenes", [])
    print(f"SUCCESS! Parsed {len(scenes)} scenes.", flush=True)
    for s in scenes[:4]:
        print(f"  [{s.get('start_time')}s - {s.get('end_time')}s]: {s.get('search_queries')}", flush=True)
else:
    print("Could not parse JSON", flush=True)
