from groq import Groq
import json
import re

client = Groq(api_key="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")
prompt = """You are a video editor AI.
Niche: psychology
Narration: Positive psychology is the scientific study of human flourishing. It tests theories with evidence.

Generate 2 scenes in JSON format:
{
  "scenes": [
    {"index": 0, "start_time": 0.0, "end_time": 5.0, "text": "...", "search_queries": ["brain research", "university professor"], "mood": "inspiring"}
  ]
}
"""
res = client.chat.completions.create(
    model="openai/gpt-oss-120b",
    messages=[{"role": "user", "content": prompt}],
    max_tokens=400,
    temperature=0.2
)
print("SUCCESS gpt-oss-120b:")
print(res.choices[0].message.content)
