import json
import sqlite3
import time
from groq import Groq

conn = sqlite3.connect("data/videogen.db")
row = conn.execute("SELECT transcript_json, niche FROM projects WHERE id='b3a9c9fa'").fetchone()
key = conn.execute("SELECT value FROM settings WHERE key='groq_api_key'").fetchone()[0]
transcript = json.loads(row[0])
niche = row[1] or "general"

client = Groq(api_key=key)
raw_segments = transcript.get("segments", [])
duration = transcript.get("duration", 0)

# Compact segments: only start, end, text
compact_segments = [
    {"start": round(s.get("start", 0), 1), "end": round(s.get("end", 0), 1), "text": s.get("text", "").strip()}
    for s in raw_segments
]

prompt = f"""You are a professional video editor AI. Given a voiceover transcript for a "{niche}" YouTube video, create a scene plan that maps semantic segments of the narration to visual search queries for stock footage.

Total duration: {duration:.1f} seconds
Narration text:
{transcript.get('text', '')[:2000]}

Segments:
{json.dumps(compact_segments[:35])}

RULES:
1. Group related segments into 8-15 semantic scenes.
2. Each scene must be 5-15 seconds long with start_time and end_time.
3. Generate 2-3 specific, visual stock footage search queries per scene (e.g. "student studying library laptop", "scientist laboratory microscope").
4. Queries should describe VISUAL content, not abstract concepts.
5. Avoid repeating queries across scenes.

Return ONLY a JSON object:
{{
    "scenes": [
        {{
            "index": 0,
            "start_time": 0.0,
            "end_time": 6.5,
            "text": "Positive psychology is the scientific study...",
            "search_queries": ["psychology brain science research", "university lecture hall professor"],
            "mood": "inspirational"
        }}
    ]
}}"""

models_to_try = [
    "groq/compound",
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b"
]

for m in models_to_try:
    try:
        print(f"Testing model {m} with compact prompt...")
        res = client.chat.completions.create(
            model=m,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=2000,
            response_format={"type": "json_object"}
        )
        content = res.choices[0].message.content
        data = json.loads(content)
        scenes = data.get("scenes", [])
        print(f"SUCCESS with {m}! Generated {len(scenes)} scenes.")
        print(json.dumps(scenes[:2], indent=2))
        break
    except Exception as e:
        print(f"FAILED {m}: {e}")
        time.sleep(2)
