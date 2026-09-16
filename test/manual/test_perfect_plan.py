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
{text[:2500]}

Generate 10 visual scenes covering the video from 0.0s to {duration:.1f}s.
For each scene provide:
- index: 0 to 9
- start_time and end_time (contiguous across the {duration:.1f}s)
- text: brief summary
- search_queries: 2 concise visual search queries for stock video APIs
- mood: visual mood

Return ONLY valid JSON:
{{"scenes": [{{"index": 0, "start_time": 0.0, "end_time": 30.0, "text": "...", "search_queries": ["query 1", "query 2"], "mood": "inspiring"}}]}}"""

print("Calling Groq for 10 scenes...", flush=True)
resp = client.chat.completions.create(
    model="qwen/qwen3.8-27b",
    messages=[{"role": "user", "content": prompt}],
    temperature=0.2,
    max_tokens=800
)

raw = resp.choices[0].message.content
print(f"Raw response length: {len(raw)} chars", flush=True)

# Robust JSON extraction
data = None
match = re.search(r'\{.*\}', raw, re.DOTALL)
if match:
    try:
        data = json.loads(match.group(0))
    except Exception:
        pass

if not data:
    # Try truncated JSON repair
    last_brace = raw.rfind("}")
    if last_brace != -1:
        repaired = raw[:last_brace+1] + "\n]}"
        match2 = re.search(r'\{.*\}', repaired, re.DOTALL)
        if match2:
            try:
                data = json.loads(match2.group(0))
            except Exception:
                pass

if data and "scenes" in data:
    scenes = data["scenes"]
    print(f"PERFECT SUCCESS! Extracted {len(scenes)} scenes:", flush=True)
    for s in scenes:
        print(f"  Scene {s.get('index')}: [{s.get('start_time')}s - {s.get('end_time')}s] -> {s.get('search_queries')}", flush=True)
    
    # Save to project in database!
    plan_json = json.dumps({"scenes": scenes})
    conn.execute("UPDATE projects SET scene_plan_json=?, status='planned', updated_at=datetime('now') WHERE id='b3a9c9fa'", (plan_json,))
    conn.commit()
    print("\nSaved scene plan to database for project b3a9c9fa!", flush=True)
else:
    print("Failed to parse JSON, raw starts with:", raw[:200], flush=True)
