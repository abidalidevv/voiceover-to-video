"""
In-App Neural AI Voiceover Generator using Microsoft Edge-TTS & ElevenLabs Free Tier.
Free, zero API cost, unlimited usage, and ultra-realistic human voices.
"""

import os
import asyncio
import re
import requests
from pathlib import Path
from typing import Dict, List, Any, Optional
import edge_tts
from backend.config import load_settings

# Curated top-tier natural human neural voices (sorted by realism and popularity)
CURATED_VOICES = [
    {
        "id": "en-US-AndrewMultilingualNeural",
        "name": "Andrew V2 (Ultra-Natural Male)",
        "lang": "English (US)",
        "locale": "en-US",
        "gender": "Male",
        "style": "Ultra-Realistic Human Narration with Breathing & Vocal Warmth",
        "flag": "🌟",
        "recommended": True,
        "provider": "edge"
    },
    {
        "id": "en-US-AvaMultilingualNeural",
        "name": "Ava V2 (Ultra-Natural Female)",
        "lang": "English (US)",
        "locale": "en-US",
        "gender": "Female",
        "style": "Expressive Human Storyteller with Natural Emotion",
        "flag": "🌟",
        "recommended": True,
        "provider": "edge"
    },
    {
        "id": "en-US-BrianMultilingualNeural",
        "name": "Brian V2 (Conversational Tech Male)",
        "lang": "English (US)",
        "locale": "en-US",
        "gender": "Male",
        "style": "Casual, Engaging YouTube Tech Explainer",
        "flag": "🌟",
        "recommended": True,
        "provider": "edge"
    },
    {
        "id": "en-US-EmmaMultilingualNeural",
        "name": "Emma V2 (Polished Studio Female)",
        "lang": "English (US)",
        "locale": "en-US",
        "gender": "Female",
        "style": "Crisp, Clear & Professional Studio Narrator",
        "flag": "🌟",
        "recommended": True,
        "provider": "edge"
    },
    {
        "id": "en-US-ChristopherNeural",
        "name": "Christopher (Deep Cinematic Male)",
        "lang": "English (US)",
        "locale": "en-US",
        "gender": "Male",
        "style": "Deep, Authoritative & Movie Documentary",
        "flag": "🎬",
        "recommended": True,
        "provider": "edge"
    },
    {
        "id": "en-US-GuyNeural",
        "name": "Guy (YouTube Creator Male)",
        "lang": "English (US)",
        "locale": "en-US",
        "gender": "Male",
        "style": "Natural, Dynamic & High-Retention Storyteller",
        "flag": "⚡",
        "recommended": True,
        "provider": "edge"
    },
    {
        "id": "en-US-JennyNeural",
        "name": "Jenny (Warm & Clear Female)",
        "lang": "English (US)",
        "locale": "en-US",
        "gender": "Female",
        "style": "Warm, Relatable & Energetic Explainer",
        "flag": "🎙️",
        "recommended": False,
        "provider": "edge"
    },
    {
        "id": "en-GB-RyanNeural",
        "name": "Ryan (British BBC Documentary Male)",
        "lang": "English (UK)",
        "locale": "en-GB",
        "gender": "Male",
        "style": "Sophisticated, Engaging British Voiceover",
        "flag": "🇬🇧",
        "recommended": True,
        "provider": "edge"
    },
    {
        "id": "en-GB-SoniaNeural",
        "name": "Sonia (British Narrative Female)",
        "lang": "English (UK)",
        "locale": "en-GB",
        "gender": "Female",
        "style": "Polished & Elegant British Storyteller",
        "flag": "🇬🇧",
        "recommended": False,
        "provider": "edge"
    },
    {
        "id": "ur-PK-AsadNeural",
        "name": "Asad (Authentic Natural Urdu Male)",
        "lang": "Urdu (Pakistan)",
        "locale": "ur-PK",
        "gender": "Male",
        "style": "Clear, Natural & Authoritative Urdu",
        "flag": "🇵🇰",
        "recommended": True,
        "provider": "edge"
    },
    {
        "id": "ur-PK-UzmaNeural",
        "name": "Uzma (Natural Expressive Urdu Female)",
        "lang": "Urdu (Pakistan)",
        "locale": "ur-PK",
        "gender": "Female",
        "style": "Melodious, Expressive & Clean Urdu",
        "flag": "🇵🇰",
        "recommended": False,
        "provider": "edge"
    },
    {
        "id": "hi-IN-MadhurNeural",
        "name": "Madhur (Dynamic Natural Hindi Male)",
        "lang": "Hindi (India)",
        "locale": "hi-IN",
        "gender": "Male",
        "style": "Engaging & Relatable Hindi Storyteller",
        "flag": "🇮🇳",
        "recommended": True,
        "provider": "edge"
    },
    {
        "id": "hi-IN-SwaraNeural",
        "name": "Swara (Conversational Hindi Female)",
        "lang": "Hindi (India)",
        "locale": "hi-IN",
        "gender": "Female",
        "style": "Warm, Friendly & Conversational Hindi",
        "flag": "🇮🇳",
        "recommended": False,
        "provider": "edge"
    },
    {
        "id": "en-US-AriaNeural",
        "name": "Aria (Expressive Narrative Female)",
        "lang": "English (US)",
        "locale": "en-US",
        "gender": "Female",
        "style": "Positive, Confident & Emotional Storyteller",
        "flag": "✨",
        "recommended": False,
        "provider": "edge"
    },
    {
        "id": "en-US-EricNeural",
        "name": "Eric (Crisp Business Male)",
        "lang": "English (US)",
        "locale": "en-US",
        "gender": "Male",
        "style": "Rational, Clear & Professional Business Narrator",
        "flag": "💼",
        "recommended": False,
        "provider": "edge"
    },
    {
        "id": "en-AU-WilliamMultilingualNeural",
        "name": "William (Australian Storyteller Male)",
        "lang": "English (AU)",
        "locale": "en-AU",
        "gender": "Male",
        "style": "Friendly, Positive & Laid-back Australian Tone",
        "flag": "🇦🇺",
        "recommended": False,
        "provider": "edge"
    },
    {
        "id": "es-ES-AlvaroNeural",
        "name": "Alvaro (Natural Spanish Male)",
        "lang": "Spanish (Spain)",
        "locale": "es-ES",
        "gender": "Male",
        "style": "Warm, Authentic Spanish Storytelling",
        "flag": "🇪🇸",
        "recommended": False,
        "provider": "edge"
    },
    # ElevenLabs Free Tier Compatible Models (optional via user key in Settings)
    {
        "id": "eleven_adam",
        "name": "Adam (ElevenLabs Deep American Male)",
        "lang": "English (US)",
        "locale": "en-US",
        "gender": "Male",
        "style": "Legendary Deep Narration (Free Tier Key or Edge Backup)",
        "flag": "💎",
        "recommended": False,
        "provider": "elevenlabs",
        "eleven_id": "pNInz6obpgDQGcFmaJgB"
    },
    {
        "id": "eleven_rachel",
        "name": "Rachel (ElevenLabs Calm Female)",
        "lang": "English (US)",
        "locale": "en-US",
        "gender": "Female",
        "style": "Calm, Authentic Narrative (Free Tier Key or Edge Backup)",
        "flag": "💎",
        "recommended": False,
        "provider": "elevenlabs",
        "eleven_id": "21m00Tcm4TlvDq8ikWAM"
    },
    # OpenAI Voice Engine (optional via user key in Settings)
    {
        "id": "openai_onyx",
        "name": "Onyx (OpenAI Deep Voice Male)",
        "lang": "English (US)",
        "locale": "en-US",
        "gender": "Male",
        "style": "Deep, Resonant & Authoritative (OpenAI Key or Edge Backup)",
        "flag": "🤖",
        "recommended": False,
        "provider": "openai"
    },
    {
        "id": "openai_nova",
        "name": "Nova (OpenAI Energetic Female)",
        "lang": "English (US)",
        "locale": "en-US",
        "gender": "Female",
        "style": "Upbeat, Friendly & High-Energy (OpenAI Key or Edge Backup)",
        "flag": "🤖",
        "recommended": False,
        "provider": "openai"
    }
]


def get_curated_voices() -> List[Dict[str, Any]]:
    """Returns curated list of recommended high quality voices with sample URLs."""
    voices = []
    for v in CURATED_VOICES:
        item = dict(v)
        # Sample audio URL mapping
        if v["id"].startswith("eleven_") or v["id"].startswith("openai_"):
            fallback_sample = "en-US-ChristopherNeural" if v["gender"] == "Male" else "en-US-AvaMultilingualNeural"
            item["sample_url"] = f"/media/sfx/tts_samples/{fallback_sample}.mp3"
        else:
            item["sample_url"] = f"/media/sfx/tts_samples/{v['id']}.mp3"
        voices.append(item)
    return voices


def clean_script_text(text: str) -> str:
    """Cleans up script formatting, removes markdown tags or stage cues."""
    if not text:
        return ""
    cleaned = re.sub(r"\[.*?\]", "", text)
    cleaned = re.sub(r"\(.*?\)", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def _generate_with_elevenlabs(text: str, eleven_id: str, api_key: str, output_path: str) -> Dict[str, Any]:
    """Generates speech via ElevenLabs API using user key."""
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{eleven_id}"
    headers = {
        "xi-api-key": api_key,
        "Content-Type": "application/json"
    }
    payload = {
        "text": text,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.75
        }
    }
    r = requests.post(url, headers=headers, json=payload, timeout=25)
    if r.status_code != 200:
        raise Exception(f"ElevenLabs HTTP {r.status_code}: {r.text}")
    with open(output_path, "wb") as f:
        f.write(r.content)
    words = len(text.split())
    return {
        "output_path": output_path,
        "voice": f"ElevenLabs_{eleven_id}",
        "word_count": words,
        "approx_duration": round(words / 2.5, 2),
        "cleaned_text": text
    }


def _generate_with_openai(text: str, openai_voice: str, api_key: str, output_path: str) -> Dict[str, Any]:
    """Generates speech via OpenAI Audio Speech API."""
    url = "https://api.openai.com/v1/audio/speech"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "tts-1",
        "input": text,
        "voice": openai_voice
    }
    r = requests.post(url, headers=headers, json=payload, timeout=30)
    if r.status_code != 200:
        raise Exception(f"OpenAI TTS HTTP {r.status_code}: {r.text}")
    with open(output_path, "wb") as f:
        f.write(r.content)
    words = len(text.split())
    return {
        "output_path": output_path,
        "voice": f"OpenAI_{openai_voice}",
        "word_count": words,
        "approx_duration": round(words / 2.5, 2),
        "cleaned_text": text
    }


async def generate_speech_async(
    text: str,
    voice: str = "en-US-AndrewMultilingualNeural",
    rate: str = "+0%",
    pitch: str = "+0Hz",
    output_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Synthesizes speech using Microsoft Edge Neural V2, ElevenLabs, or OpenAI.
    """
    cleaned = clean_script_text(text)
    if not cleaned:
        raise ValueError("Script text cannot be empty.")

    if not output_path:
        raise ValueError("output_path must be specified.")

    p = Path(output_path)
    p.parent.mkdir(parents=True, exist_ok=True)

    # Check if ElevenLabs voice was selected
    if voice.startswith("eleven_"):
        settings = load_settings()
        eleven_key = settings.get("elevenlabs_api_key", "").strip()
        eleven_meta = next((v for v in CURATED_VOICES if v["id"] == voice), None)
        eleven_id = eleven_meta.get("eleven_id", "pNInz6obpgDQGcFmaJgB") if eleven_meta else "pNInz6obpgDQGcFmaJgB"

        if eleven_key:
            try:
                print(f"[TTS] Synthesizing via ElevenLabs API ({eleven_id})...")
                return _generate_with_elevenlabs(cleaned, eleven_id, eleven_key, str(p))
            except Exception as e:
                print(f"[TTS] ElevenLabs notice: {e}, falling back to Microsoft Neural V2...")

        # Fallback to Andrew or Ava if ElevenLabs key is missing or errored
        fallback_voice = "en-US-AndrewMultilingualNeural" if "adam" in voice else "en-US-AvaMultilingualNeural"
        voice = fallback_voice

    elif voice.startswith("openai_"):
        settings = load_settings()
        openai_key = settings.get("openai_api_key", "").strip()
        openai_voice_name = voice.replace("openai_", "")

        if openai_key:
            try:
                print(f"[TTS] Synthesizing via OpenAI TTS API ({openai_voice_name})...")
                return _generate_with_openai(cleaned, openai_voice_name, openai_key, str(p))
            except Exception as e:
                print(f"[TTS] OpenAI TTS notice: {e}, falling back to Microsoft Neural V2...")

        # Fallback to Christopher or Ava if OpenAI key is missing or errored
        fallback_voice = "en-US-ChristopherNeural" if openai_voice_name in ("onyx", "echo", "fable") else "en-US-AvaMultilingualNeural"
        voice = fallback_voice

    # Format rate string e.g. "+10%" or "-10%"
    rate_str = rate if rate.startswith(("+", "-")) else f"+{rate}"
    if not rate_str.endswith("%"):
        rate_str += "%"

    pitch_str = pitch if pitch.startswith(("+", "-")) else f"+{pitch}"
    if not pitch_str.endswith("Hz"):
        pitch_str += "Hz"

    communicate = edge_tts.Communicate(
        text=cleaned,
        voice=voice,
        rate=rate_str,
        pitch=pitch_str
    )

    await communicate.save(str(p))

    words = len(cleaned.split())
    approx_duration = round(words / 2.5, 2)

    return {
        "output_path": str(p.resolve()),
        "voice": voice,
        "word_count": words,
        "approx_duration": approx_duration,
        "cleaned_text": cleaned
    }


def generate_speech(
    text: str,
    voice: str = "en-US-AndrewMultilingualNeural",
    rate: str = "+0%",
    pitch: str = "+0Hz",
    output_path: Optional[str] = None
) -> Dict[str, Any]:
    """Synchronous wrapper for generate_speech_async."""
    return asyncio.run(generate_speech_async(text, voice, rate, pitch, output_path))
