import json
import sqlite3
import re
import time
from groq import Groq

conn = sqlite3.connect("data/videogen.db")
row = conn.execute("SELECT transcript_json, niche FROM projects WHERE id='b3a9c9fa'").fetchone()
key = conn.execute("SELECT value FROM settings WHERE key='groq_api_key'").fetchone()[0]
transcript = json.loads(row[0])
niche = row[1] or "educational"
duration = transcript.get("duration", 298.0)
text = transcript.get("text", "")

client = Groq(api_key=key)

prompt = f"""You are a professional video editor AI.
Video Niche: {niche}
Total Duration: {duration:.1f} seconds
Full Narration:
{text}

Create a scene plan of 12 to 18 visual scenes covering the entire video from 0.0s to {duration:.1f}s.
For each scene provide:
- index: 0, 1, 2...
- start_time and end_time (in seconds, contiguous from 0 to {duration:.1f})
- text: brief excerpt of narration
- search_queries: 2 specific visual search queries for stock video (e.g. "student library books", "scientist lab microscope")
- mood: visual mood

Return ONLY a JSON object:
{{"scenes": [{{"index": 0, "start_time": 0.0, "end_time": 18.5, "text": "...", "search_queries": ["query 1", "query 2"], "mood": "inspiring"}}]}}"""

print(f"Prompt length: {len(prompt)} chars. Calling qwen/qwen3.8-27b in ONE call...", flush=True)
t0 = time.time()
resp = client.chat.completions.create(
    model="qwen/qwen3.8-27b",
    messages=[{"role": "user", "content": prompt}],
    temperature=0.2,
    max_tokens=850
)
dt = time.time() - t0
print(f"Call finished in {dt:.2f}s!", flush=True)

raw = resp.choices[0].message.content
print(f"Response length: {len(raw)} chars.", flush=True)
match = re.search(r'\{.*\}', raw, re.DOTALL)
if match:
    data = json.loads(match.group(0))
    scenes = data.get("scenes", [])
    print(f"SUCCESS! Parsed {len(scenes)} scenes.", flush=True)
    for s in scenes[:3]:
        print(f"  [{s.get('start_time')}s - {s.get('end_time')}s] {s.get('search_queries')}", flush=True)
else:
    print("Could not match JSON", flush=True)
