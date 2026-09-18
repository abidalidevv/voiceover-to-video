"""
AI YouTube SEO Suite: Titles, Timestamps Description & High-Ranking Tags Generator.
Supports Groq LLM with smart offline template fallback.
"""

import os
import json
import re
import requests
from typing import Dict, List, Any, Optional
from backend.config import load_settings


def _generate_seo_with_groq(
    groq_key: str,
    text: str,
    scenes: Optional[List[Dict[str, Any]]] = None,
    topic: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """Generates viral YouTube metadata using Groq LLM with model fallback."""
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {groq_key}",
        "Content-Type": "application/json"
    }

    context_snippets = text[:2500]
    prompt = f"""
You are an expert YouTube Strategist and Viral Growth Consultant specializing in high CTR titles, SEO descriptions, and high-ranking tags.

Analyze this video script/voiceover content:
\"\"\"
{context_snippets}
\"\"\"

Output a strictly valid JSON object with the following keys:
1. "titles": Array of 3 high-CTR, clickbait yet truthful YouTube titles (using power words, curiosity gap, brackets or numbers).
2. "hook_summary": 2-3 engaging sentences summarizing the video for the top of the description.
3. "tags": Array of 15-20 high-ranking, comma-separated SEO tags for YouTube Studio.
4. "hashtags": Array of 4-6 relevant hashtags starting with '#' (e.g. #automation #tech).

Only return valid JSON, nothing else.
"""

    for model_id in ["llama-3.1-8b-instant", "llama-3.3-70b-versatile", "mixtral-8x7b-32768", "gemma2-9b-it"]:
        try:
            payload = {
                "model": model_id,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.7,
                "response_format": {"type": "json_object"}
            }
            res = requests.post(url, headers=headers, json=payload, timeout=12)
            if res.status_code == 200:
                raw_json = res.json()["choices"][0]["message"]["content"]
                return json.loads(raw_json)
        except Exception:
            continue
    return None


def _format_timestamp(seconds: float) -> str:
    """Formats float seconds into MM:SS format."""
    total_sec = int(round(seconds))
    mins = total_sec // 60
    secs = total_sec % 60
    return f"{mins:02d}:{secs:02d}"


def _generate_seo_fallback(
    text: str,
    scenes: Optional[List[Dict[str, Any]]] = None,
    topic: Optional[str] = None
) -> Dict[str, Any]:
    """Rule-based smart generator when Groq is unconfigured or offline."""
    words = re.findall(r"\b[A-Za-z]{4,}\b", text)
    from collections import Counter
    stopwords = {"this", "that", "with", "from", "your", "have", "more", "will", "what", "when", "there", "about", "which", "their", "they", "them", "some", "like", "into", "than", "then", "just"}
    filtered_words = [w.capitalize() for w in words if w.lower() not in stopwords]
    top_keywords = [item[0] for item in Counter(filtered_words).most_common(12)]

    primary_keyword = topic or (top_keywords[0] if top_keywords else "Ultimate Guide")
    sec_keyword = top_keywords[1] if len(top_keywords) > 1 else "Secret"

    titles = [
        f"The TRUTH About {primary_keyword} Nobody Tells You! [MUST WATCH]",
        f"Why {primary_keyword} Will Change Everything in 2026 (Full Breakdown)",
        f"I Tested {primary_keyword} For 30 Days... Here's What Happened!"
    ]

    hook = f"In this video, we dive deep into {primary_keyword} and explore how {sec_keyword.lower()} is transforming everything. Watch until the end for the key insights!"

    tags = [
        primary_keyword.lower(),
        f"{primary_keyword.lower()} guide",
        f"{primary_keyword.lower()} 2026",
        "how to",
        "tutorial",
        "breakdown",
        "full explanation",
        "viral video",
        "tips and tricks"
    ] + [kw.lower() for kw in top_keywords[:8]]

    hashtags = [
        f"#{primary_keyword.replace(' ', '')}",
        "#viral",
        "#video",
        "#trending",
        "#guide"
    ]

    return {
        "titles": titles,
        "hook_summary": hook,
        "tags": list(dict.fromkeys(tags))[:20],
        "hashtags": hashtags
    }


def generate_youtube_seo(
    text: str,
    scenes: Optional[List[Dict[str, Any]]] = None,
    topic: Optional[str] = None
) -> Dict[str, Any]:
    """
    Master function: Generates titles, complete description with timestamps, and tags.
    """
    settings = load_settings()
    groq_key = settings.get("groq_api_key", "").strip()

    data = None
    if groq_key:
        try:
            data = _generate_seo_with_groq(groq_key, text, scenes, topic)
        except Exception as e:
            print(f"[SEO Generator] Groq LLM notice: {e}, using algorithmic fallback.")

    if not data or not data.get("titles"):
        data = _generate_seo_fallback(text, scenes, topic)

    # Build structured description with Chapters/Timestamps
    chapters_lines = ["\nTIMESTAMPS:"]
    chapters_lines.append("00:00 - Introduction & Overview")

    if scenes:
        curr_time = 0.0
        for i, sc in enumerate(scenes):
            dur = float(sc.get("duration", 4.0))
            if i > 0 and curr_time > 0:
                sc_title = sc.get("narration") or sc.get("search_keyword") or f"Chapter {i+1}"
                sc_title_clean = sc_title[:35].strip()
                if sc_title_clean:
                    chapters_lines.append(f"{_format_timestamp(curr_time)} - {sc_title_clean}")
            curr_time += dur

    timestamps_block = "\n".join(chapters_lines) if len(chapters_lines) > 1 else ""

    description_full = (
        f"{data.get('hook_summary', '')}\n\n"
        f"{timestamps_block}\n\n"
        f"Subscribe for more high-value videos!\n"
        f"If this was helpful, please leave a LIKE and COMMENT below.\n\n"
        f"{' '.join(data.get('hashtags', []))}"
    ).strip()

    tags_str = ", ".join(data.get("tags", []))

    return {
        "status": "success",
        "titles": data.get("titles", []),
        "description": description_full,
        "tags_list": data.get("tags", []),
        "tags_string": tags_str,
        "hashtags": data.get("hashtags", []),
        "hook_summary": data.get("hook_summary", "")
    }
