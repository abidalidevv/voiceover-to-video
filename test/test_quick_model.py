import json
import re
from groq import Groq

client = Groq(api_key="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")

prompt = """You are a video editor AI. Given this short narration, create 3 scenes with search queries for stock video.
Narration: Positive psychology is the scientific study of human flourishing and well-being. It focuses on strengths rather than weaknesses.

Return JSON in this format:
{
  "scenes": [
    {"index": 0, "start_time": 0.0, "end_time": 4.0, "text": "Positive psychology...", "search_queries": ["smiling people outdoors", "brain neuroscience research"], "mood": "inspiring"}
  ]
}
"""

for model in ["qwen/qwen3.8-27b", "openai/gpt-oss-120b", "openai/gpt-oss-20b"]:
    try:
        print(f"Testing {model}...")
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=700
        )
        content = resp.choices[0].message.content
        print(f"SUCCESS {model}:")
        print(content[:300])
        break
    except Exception as e:
        print(f"FAILED {model}: {e}")
