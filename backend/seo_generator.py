"""
AI YouTube SEO Suite: Titles, Timestamps Description & High-Ranking Tags Generator.
Supports Google Gemini multi-key pool, Groq LLM multi-key pool, with smart algorithmic fallback.
"""

import os
import json
import re
import requests
from typing import Dict, List, Any, Optional
from backend.config import load_settings


def _generate_seo_with_gemini(
    gemini_keys: List[str],
    text: str,
    scenes: Optional[List[Dict[str, Any]]] = None,
    topic: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """Generates viral YouTube metadata using Google Gemini Flash model pool."""
    context_snippets = text[:2800]
    prompt = f"""
You are an elite YouTube Growth Consultant & Viral SEO Strategist (like Paddy Galloway / Derral Eves).
Analyze this video script/voiceover content:
\"\"\"
{context_snippets}
\"\"\"

Produce high-CTR YouTube metadata formatted as a valid JSON object with the following keys:
1. "titles": Array of 5 diverse, irresistible, high-CTR YouTube titles that obey modern YouTube packaging:
   - Title 1: Extreme Curiosity / Mystery Hook
   - Title 2: High Urgency / Warning Hook (e.g. "Do NOT ... Before You See This!")
   - Title 3: Educational Authority / How-To Breakdown
   - Title 4: Shocking Contrast / Transformation
   - Title 5: Masterclass / Blueprint
2. "hook_summary": 2-3 engaging, high-retention opening sentences for the YouTube description.
3. "key_takeaways": Array of 3-4 bullet point insights covered in the video.
4. "tags": Array of 18-22 high-ranking, competitive SEO search tags.
5. "hashtags": Array of 5-7 popular hashtags with '#' (e.g. #automation #tech #viral).

Only return valid JSON, nothing else.
"""

    for gkey in gemini_keys:
        if not gkey or not str(gkey).strip():
            continue
        clean_key = str(gkey).strip()
        for model in ["gemini-1.5-flash", "gemini-2.0-flash", "gemini-1.5-pro"]:
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={clean_key}"
                payload = {
                    "contents": [{
                        "parts": [{"text": prompt}]
                    }],
                    "generationConfig": {
                        "temperature": 0.7,
                        "responseMimeType": "application/json"
                    }
                }
                res = requests.post(url, json=payload, timeout=12)
                if res.status_code == 200:
                    cand = res.json().get("candidates", [])
                    if cand:
                        raw_text = cand[0]["content"]["parts"][0]["text"].strip()
                        # Clean backticks if any
                        if raw_text.startswith("```"):
                            raw_text = re.sub(r"^```(?:json)?\s*", "", raw_text)
                            raw_text = re.sub(r"\s*```$", "", raw_text)
                        data = json.loads(raw_text)
                        if data.get("titles"):
                            return data
            except Exception:
                continue
    return None


def _generate_seo_with_groq(
    groq_keys: List[str],
    text: str,
    scenes: Optional[List[Dict[str, Any]]] = None,
    topic: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """Generates viral YouTube metadata using Groq LLM across multi-account pool."""
    context_snippets = text[:2500]
    prompt = f"""
You are an expert YouTube Strategist and Viral Growth Consultant specializing in high CTR titles, SEO descriptions, and high-ranking tags.

Analyze this video script/voiceover content:
\"\"\"
{context_snippets}
\"\"\"

Output a strictly valid JSON object with the following keys:
1. "titles": Array of 5 high-CTR, clickbait yet truthful YouTube titles:
   - 1 Mystery / Curiosity Gap
   - 1 High Urgency Warning
   - 1 How-To / Educational Breakdown
   - 1 Shock / Extreme Transformation
   - 1 Ultimate Blueprint / Masterclass
2. "hook_summary": 2-3 engaging sentences summarizing the video for the top of the description.
3. "key_takeaways": Array of 3-4 bullet point takeaways.
4. "tags": Array of 18-22 high-ranking, comma-separated SEO tags for YouTube Studio.
5. "hashtags": Array of 5-7 relevant hashtags starting with '#' (e.g. #automation #tech).

Only return valid JSON, nothing else.
"""
    for g_key in groq_keys:
        if not g_key or not str(g_key).strip():
            continue
        clean_key = str(g_key).strip()
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {clean_key}",
            "Content-Type": "application/json"
        }
        for model_id in ["llama-3.1-8b-instant", "llama-3.3-70b-versatile", "mixtral-8x7b-32768"]:
            try:
                payload = {
                    "model": model_id,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.7,
                    "response_format": {"type": "json_object"}
                }
                res = requests.post(url, headers=headers, json=payload, timeout=10)
                if res.status_code == 200:
                    raw_json = res.json()["choices"][0]["message"]["content"]
                    data = json.loads(raw_json)
                    if data.get("titles"):
                        return data
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
    """Rule-based smart generator when AI APIs are unconfigured or offline."""
    words = re.findall(r"\b[A-Za-z]{4,}\b", text)
    from collections import Counter
    stopwords = {"this", "that", "with", "from", "your", "have", "more", "will", "what", "when", "there", "about", "which", "their", "they", "them", "some", "like", "into", "than", "then", "just"}
    filtered_words = [w.capitalize() for w in words if w.lower() not in stopwords]
    top_keywords = [item[0] for item in Counter(filtered_words).most_common(12)]

    primary_keyword = topic or (top_keywords[0] if top_keywords else "The Breakthrough")
    sec_keyword = top_keywords[1] if len(top_keywords) > 1 else "Secret"

    titles = [
        f"The TRUTH About {primary_keyword} Nobody Tells You! [MUST WATCH]",
        f"Why {primary_keyword} Will Change Everything in 2026 (Full Breakdown)",
        f"I Tested {primary_keyword} For 30 Days... Here's What Happened!",
        f"Do NOT Ignore {primary_keyword}! (The Shocking Reality)",
        f"The Ultimate {primary_keyword} Blueprint: Step-By-Step Guide"
    ]

    hook = f"In this video, we dive deep into {primary_keyword} and uncover how {sec_keyword.lower()} is transforming everything. Watch until the end for the key insights!"

    takeaways = [
        f"The fundamental principles behind {primary_keyword}",
        f"Why most people fail with {sec_keyword.lower()} and how to avoid it",
        f"Actionable step-by-step strategies for high-impact results"
    ]

    tags = [
        primary_keyword.lower(),
        f"{primary_keyword.lower()} guide",
        f"{primary_keyword.lower()} 2026",
        "how to",
        "tutorial",
        "breakdown",
        "full explanation",
        "viral video",
        "tips and tricks",
        "insights",
        "step by step"
    ] + [kw.lower() for kw in top_keywords[:8]]

    hashtags = [
        f"#{primary_keyword.replace(' ', '')}",
        "#viral",
        "#video",
        "#trending",
        "#guide",
        "#breakthrough"
    ]

    return {
        "titles": titles,
        "hook_summary": hook,
        "key_takeaways": takeaways,
        "tags": list(dict.fromkeys(tags))[:22],
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

    # Collect Gemini keys
    gemini_keys = settings.get("gemini_api_keys") or []
    if settings.get("gemini_api_key"):
        gemini_keys.append(settings.get("gemini_api_key"))

    # Collect Groq keys
    groq_keys = settings.get("groq_api_keys") or []
    if settings.get("groq_api_key"):
        groq_keys.append(settings.get("groq_api_key"))

    data = None

    # 1. Try Gemini first (Best reasoning & viral YouTube context)
    if gemini_keys:
        try:
            data = _generate_seo_with_gemini(gemini_keys, text, scenes, topic)
        except Exception as e:
            print(f"[SEOGenerator] Gemini pool notice: {e}")

    # 2. Fallback to Groq multi-key pool
    if not data and groq_keys:
        try:
            data = _generate_seo_with_groq(groq_keys, text, scenes, topic)
        except Exception as e:
            print(f"[SEOGenerator] Groq pool notice: {e}")

    # 3. Fallback to algorithmic generator
    if not data or not data.get("titles"):
        data = _generate_seo_fallback(text, scenes, topic)

    # Build structured description with Chapters / Timestamps
    chapters_lines = ["\n⏱️ TIMESTAMPS:"]
    chapters_lines.append("00:00 - Introduction & Overview")

    if scenes:
        curr_time = 0.0
        for i, sc in enumerate(scenes):
            dur = float(sc.get("duration", 4.0))
            if i > 0 and curr_time > 0:
                sc_title = sc.get("narration") or sc.get("search_keyword") or f"Part {i+1}"
                sc_title_clean = sc_title[:40].strip()
                if sc_title_clean:
                    chapters_lines.append(f"{_format_timestamp(curr_time)} - {sc_title_clean}")
            curr_time += dur

    timestamps_block = "\n".join(chapters_lines) if len(chapters_lines) > 1 else ""

    takeaways = data.get("key_takeaways", [])
    takeaways_block = ""
    if takeaways:
        takeaways_block = "\n💡 KEY TAKEAWAYS:\n" + "\n".join([f"• {t}" for t in takeaways])

    description_full = (
        f"{data.get('hook_summary', '')}\n\n"
        f"{takeaways_block}\n\n"
        f"{timestamps_block}\n\n"
        f"🔔 Subscribe to the channel for more high-value breakdowns!\n"
        f"💬 What was your biggest takeaway? Let us know in the comments below!\n\n"
        f"{' '.join(data.get('hashtags', []))}"
    ).strip()

    tags_str = ", ".join(data.get("tags", []))

    # Categorize titles for rich UI display
    raw_titles = data.get("titles", [])
    categories = [
        "🔥 High Hook / Urgency",
        "🔍 Curiosity Gap / Mystery",
        "📈 How-To / Educational Authority",
        "💥 Extreme Contrast / Shock",
        "🏆 Masterclass / Formula"
    ]
    categorized = []
    for i, t in enumerate(raw_titles):
        cat = categories[i] if i < len(categories) else f"Option {i+1}"
        categorized.append({"category": cat, "title": t})

    return {
        "status": "success",
        "titles": raw_titles,
        "categorized_titles": categorized,
        "description": description_full,
        "tags_list": data.get("tags", []),
        "tags_string": tags_str,
        "hashtags": data.get("hashtags", []),
        "hook_summary": data.get("hook_summary", ""),
        "key_takeaways": takeaways
    }
