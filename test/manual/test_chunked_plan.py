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

client = Groq(api_key=key)
segments = transcript.get("segments", [])
duration = transcript.get("duration", 0)

# Group segments into ~30-45 second chunks
chunks = []
current_chunk = []
current_start = 0.0

for s in segments:
    current_chunk.append(s)
    if (s.get("end", 0) - current_start) >= 30.0:
        chunks.append(current_chunk)
        current_chunk = []
        current_start = s.get("end", 0)

if current_chunk:
    chunks.append(current_chunk)

print(f"Total duration: {duration:.1f}s, Split into {len(chunks)} chunks.")

all_scenes = []
scene_counter = 0

for c_idx, chunk in enumerate(chunks[:3]): # test first 3 chunks
    chunk_start = round(chunk[0].get("start", 0), 1)
    chunk_end = round(chunk[-1].get("end", 0), 1)
    chunk_text = " ".join(s.get("text", "").strip() for s in chunk)
    
    prompt = f"""You are a professional video editor AI.
Niche: {niche}
Audio time slice: {chunk_start}s to {chunk_end}s.
Narration: "{chunk_text}"

Divide this into 2 to 4 visual scenes.
For each scene, provide start_time, end_time, narration text, and 2-3 specific visual search queries for stock footage (e.g. "psychologist office session", "students walking campus", "brain scan glowing digital").
Return ONLY valid JSON:
{{
  "scenes": [
    {{
      "start_time": {chunk_start},
      "end_time": {chunk_end},
      "text": "short excerpt",
      "search_queries": ["query 1", "query 2"],
      "mood": "informative"
    }}
  ]
}}"""

    print(f"Processing chunk {c_idx+1}/{len(chunks)} ({chunk_start}s - {chunk_end}s)...")
    resp = client.chat.completions.create(
        model="qwen/qwen3.8-27b",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
        max_tokens=600
    )
    raw = resp.choices[0].message.content
    # Extract json
    match = re.search(r'\{.*\}', raw, re.DOTALL)
    if match:
        data = json.loads(match.group(0))
        for sc in data.get("scenes", []):
            sc["index"] = scene_counter
            scene_counter += 1
            all_scenes.append(sc)
            print(f"  Scene {sc['index']}: [{sc.get('start_time')} - {sc.get('end_time')}] -> {sc.get('search_queries')}")
    time.sleep(1)

print(f"\nSUCCESS! Total scenes generated: {len(all_scenes)}")
