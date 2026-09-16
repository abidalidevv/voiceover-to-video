"""
VideoGen Studio — Production Video Editing Templates
Bundles aspect ratio, pacing, transitions, kinetic caption styling, and ambient BGM into 1-click presets.
"""

from typing import Dict, Any, List

EDITING_TEMPLATES: Dict[str, Dict[str, Any]] = {
    "shorts_viral": {
        "id": "shorts_viral",
        "name": "🔥 YouTube Shorts & TikTok Viral",
        "badge": "9:16 Viral Pacing",
        "tagline": "Fast 2-3s visual cuts, dynamic whip pan slides, CapCut viral yellow captions, and upbeat chill beats.",
        "aspect_ratio": "9:16",
        "width": 1080,
        "height": 1920,
        "max_scene_duration": 3.2,
        "transition": "smoothleft",
        "transition_mode": "random",
        "transition_duration": 0.30,
        "caption_style": "capcut-yellow",
        "caption_preset_name": "CapCut Viral",
        "bgm_track": "lofi_chill.mp3",
        "bgm_name": "☕ Lofi Chill Beats",
        "bgm_volume": 0.12,
        "niche": "Motivation Psychology",
        "icon": "📱"
    },
    "documentary_cinematic": {
        "id": "documentary_cinematic",
        "name": "🎬 YouTube Long-Form Documentary",
        "badge": "16:9 1080p Cinematic",
        "tagline": "Elegant 4-5s documentary pacing, smooth cinematic crossfades, Iman Gadzhi serif captions, and deep focus ambient music.",
        "aspect_ratio": "16:9",
        "width": 1920,
        "height": 1080,
        "max_scene_duration": 5.0,
        "transition": "fade",
        "transition_mode": "fixed",
        "transition_duration": 0.40,
        "caption_style": "iman-gadzhi",
        "caption_preset_name": "Iman Gadzhi",
        "bgm_track": "deep_focus.mp3",
        "bgm_name": "🧘 Deep Focus Drone",
        "bgm_volume": 0.08,
        "niche": "Finance & Wealth",
        "icon": "🎥"
    },
    "tech_explainer": {
        "id": "tech_explainer",
        "name": "⚡ Tech, AI & Future Explainer",
        "badge": "16:9 High-Tech",
        "tagline": "Punchy 3s cuts with dynamic zoom punch transitions, glowing neon cyber captions, and cinematic ambient synth.",
        "aspect_ratio": "16:9",
        "width": 1920,
        "height": 1080,
        "max_scene_duration": 3.5,
        "transition": "zoomin",
        "transition_mode": "random",
        "transition_duration": 0.32,
        "caption_style": "neon-cyber",
        "caption_preset_name": "Neon Cyber",
        "bgm_track": "cinematic_ambient.mp3",
        "bgm_name": "✨ Cinematic Ambient",
        "bgm_volume": 0.10,
        "niche": "Tech & AI",
        "icon": "🤖"
    },
    "stoic_motivation": {
        "id": "stoic_motivation",
        "name": "🗿 Dark Stoic & Discipline Reel",
        "badge": "Universal 9:16 / 16:9",
        "tagline": "High-contrast visuals, fast flash cuts, bold dark stoic captions, and deep atmospheric drone soundscapes.",
        "aspect_ratio": "9:16",
        "width": 1080,
        "height": 1920,
        "max_scene_duration": 3.2,
        "transition": "fadefast",
        "transition_mode": "random",
        "transition_duration": 0.22,
        "caption_style": "dark-stoic",
        "caption_preset_name": "Dark Stoic",
        "bgm_track": "deep_focus.mp3",
        "bgm_name": "🧘 Deep Focus Drone",
        "bgm_volume": 0.15,
        "niche": "Motivation Psychology",
        "icon": "🏛️"
    },
    "podcast_pill": {
        "id": "podcast_pill",
        "name": "🎙️ Podcast & Interview Explainer",
        "badge": "Clean Creator Cut",
        "tagline": "Clean jump cuts on natural sentence boundaries, pill-box captions with yellow active highlights, and gentle background lofi.",
        "aspect_ratio": "16:9",
        "width": 1920,
        "height": 1080,
        "max_scene_duration": 4.2,
        "transition": "none",
        "transition_mode": "fixed",
        "transition_duration": 0.0,
        "caption_style": "podcast-pill",
        "caption_preset_name": "Podcast Box",
        "bgm_track": "lofi_chill.mp3",
        "bgm_name": "☕ Lofi Chill Beats",
        "bgm_volume": 0.08,
        "niche": "Podcast & Interview",
        "icon": "🎙️"
    }
}


def get_template(template_id: str) -> Dict[str, Any]:
    """Retrieves an editing template by ID with fallback to shorts_viral."""
    return EDITING_TEMPLATES.get(template_id, EDITING_TEMPLATES["shorts_viral"])


def list_templates() -> List[Dict[str, Any]]:
    """Returns all available editing templates as a list."""
    return list(EDITING_TEMPLATES.values())
