import re
import json
import requests
from typing import List, Dict, Any
from .config import load_settings


NICHE_VISUAL_FLAVORS = {
    "Motivation Psychology": ["cinematic dramatic lighting", "focused entrepreneur", "person looking out window", "city night moody", "determined runner", "deep thought"],
    "Nature & Wildlife": ["majestic aerial landscape 4k", "dense emerald forest mist", "mountain waterfall scenic", "wild ocean waves sunset", "sunrise clouds timelapse"],
    "Tech & AI": ["futuristic server room glowing", "cyberpunk holographic data", "artificial intelligence robotic hand", "modern high tech workspace", "digital code matrix"],
    "Finance & Wealth": ["luxury skyscraper trading floor", "businessman counting money cash", "stock market chart ticker green", "private jet luxury lifestyle", "financial district wall street"],
    "Luxury & Lifestyle": ["supercar driving coastline sunset", "luxury modern penthouse view", "rolex watch diamond elegance", "champagne toast high society", "yacht ocean cruising"],
    "Fitness & Health": ["athlete training gym sweat", "running sunrise outdoor trail", "heavy barbell lifting focus", "healthy organic meal prep", "athletic silhouette sprint"],
    "Stoicism & Philosophy": ["ancient marble statue portrait", "lone figure standing ocean cliff", "stormy clouds dramatic sky", "candle burning dark room", "calm warrior meditation"],
    "Sci-Fi & Space": ["deep space galaxy nebula", "astronaut walking planet surface", "hubble telescope cosmos 4k", "spacewalk earth orbit satellite", "futuristic sci-fi spacecraft"],
    "Crime & Mystery": ["foggy night city street rain", "detective silhouette crime scene", "vintage typewriter noir mystery", "shadowy figure suspense corridor", "police siren night moody"],
    "Meditation & Lofi": ["calm peaceful water ripples", "zen bamboo garden soft light", "candle flame soft glow", "cozy rain window lofi room", "serene misty lake reflection"],
    "Brain & Human Facts": ["human brain glowing neural network", "optical illusion rotating abstract", "curious person thinking portrait", "dna double helix molecular", "complex clockwork gears mechanism"],
    "History & Empires": ["ancient roman colosseum aerial", "egyptian pyramids golden sunset", "medieval stone castle fortress", "ancient parchment map candle", "classical antique temple ruins"],
    "Business & Hustle": ["modern glass office boardroom", "young startup founders whiteboard", "confident ceo presentation", "busy corporate financial district", "laptop typing analytics charts"],
    "Automotive & Supercars": ["matte black supercar drifting track", "formula 1 race car speed blur", "engine pistons mechanical combustion", "luxury sports car cockpit interior", "night highway speed light trails"],
    "Gaming & Esports": ["cyberpunk gamer room neon rgb", "esports tournament crowd cheering", "futuristic mechanical robot gaming", "retro arcade machines glowing", "virtual reality gamer headset"],
    "Travel & Adventure": ["tropical beach turquoise water drone", "swiss alps snow peaks aerial", "wandering ancient european alley", "hiking backpacker mountain ridge", "traditional asian lantern temple"],
    "Science & Engineering": ["scientific laboratory beaker chemicals", "quantum physics particle collision", "laser beam laboratory precision", "robotic automated assembly arm", "microscope view living cells"],
    "Productivity & Self-Growth": ["minimalist clean wooden desk morning", "writing journal fountain pen coffee", "person meditating sunrise balcony", "organized bookshelf books library", "early morning focused study"],
    "Horror & Paranormal": ["eerie abandoned house mist", "creepy shadows dark woods night", "flickering hallway light bulb", "silhouette foggy graveyard trees", "mysterious glowing portal night"],
    "Food & Culinary": ["chef slicing gourmet steak flame", "artisanal coffee pour over barista", "fresh organic vegetables farm", "wood fired pizza oven crust", "delicious chocolate dessert drizzle"],
    "Wildlife Predators & Oceans": ["lion pride golden savannah hunting", "great white shark underwater coral", "eagle soaring mountain thermals", "orca killer whale ocean breach", "jaguar stalking rainforest river"],
    "General": ["cinematic inspiring 4k", "dramatic lighting cinematic", "people lifestyle urban", "beautiful scenery landscape"]
}


KEYWORD_MAP = {
    "tired": ["exhausted man sitting desk", "tired worker walking home", "overworked person head in hands", "fatigued face"],
    "sleep": ["person sleeping bed night", "alarm clock ringing morning", "waking up sunrise"],
    "dream": ["looking at night stars sky", "contemplative person sunset", "visionary horizon view"],
    "discipline": ["early morning workout gym", "intense focused training athlete", "studying late night desk"],
    "money": ["cash dollars counting hands", "credit card payment luxury", "gold bars vault investment"],
    "wealth": ["luxury mansion penthouse", "private luxury lifestyle yacht", "successful investor office"],
    "success": ["businessman celebrating victory summit", "climbing mountain peak success", "confident executive walking"],
    "work": ["modern office team meeting", "laptop typing coder late night", "industrial worker hands factory"],
    "walk": ["person walking through city street", "crowd commuting subway station", "walking along empty foggy road"],
    "city": ["new york city aerial timelapse", "busy urban pedestrian crosswalk", "neon city streets night"],
    "rain": ["rain drops on window glass moody", "walking in rain umbrella lonely", "wet asphalt city rain reflections"],
    "silence": ["calm peaceful lake reflection", "quiet empty room sunset light", "serene snowy forest silence"],
    "starving": ["longing hungry expression portrait", "pensive man staring into space", "reaching hand towards light"],
    "waiting": ["person waiting train platform", "clock ticking time passing timelapse", "sitting alone cafe window"],
    "fight": ["boxer punching bag training", "determined warrior intense eyes", "overcoming struggle athletic"],
    "morning": ["golden sunrise horizon dawn", "drinking coffee morning window", "morning sun rays trees"],
    "future": ["futuristic technology glowing interface", "modern architecture minimalist", "virtual reality headset person"]
}


def build_scenes(transcription: Dict[str, Any], niche: str = "General") -> List[Dict[str, Any]]:
    """
    Takes transcription data and builds structured sentence-level scene objects.
    Each scene corresponds to a single spoken sentence or natural 3-5s visual thought,
    preventing multi-sentence spillage and ensuring 1-to-1 visual-caption harmony.
    """
    settings = load_settings()
    total_dur = float(transcription.get("duration", 30.0))
    segments = transcription.get("segments", [])

    # 1. Gather all micro-timestamped words
    all_words = []
    if transcription.get("words"):
        for w in transcription["words"]:
            word_str = w.get("word", "").strip()
            if word_str:
                all_words.append({
                    "word": word_str,
                    "start": float(w.get("start", 0)),
                    "end": float(w.get("end", 0))
                })
    if not all_words:
        for seg in segments:
            for w in seg.get("words", []):
                word_str = w.get("word", "").strip()
                if word_str:
                    all_words.append({
                        "word": word_str,
                        "start": float(w.get("start", 0)),
                        "end": float(w.get("end", 0))
                    })

    # 2. Intelligent Word & Sentence Boundary Detection
    if all_words:
        sentence_groups = []
        current_group = []

        for i, w in enumerate(all_words):
            current_group.append(w)
            word_text = w["word"].strip()

            # Punctuation boundary (. ! ? ; : but not titles like Mr., Dr.)
            has_period = bool(re.search(r'[.!?]$', word_text)) and not bool(re.search(r'^(?:Mr|Mrs|Ms|Dr|Prof|vs|etc|e\.g|i\.e)\.$', word_text, re.I))
            has_semicolon = bool(re.search(r'[;:]$', word_text))

            # Speech pause boundary (speaker breathed or paused > 0.45s)
            has_pause = False
            if i < len(all_words) - 1:
                next_w = all_words[i + 1]
                if (next_w["start"] - w["end"]) >= 0.45:
                    has_pause = True

            group_duration = w["end"] - current_group[0]["start"]

            # Dynamic pacing: split long sentences (>= 5.2s) at natural commas or pauses
            has_comma = bool(re.search(r'[,]$', word_text))
            is_pacing_split = (group_duration >= 5.2 and (has_comma or has_pause))
            is_overlong = (group_duration >= 7.0 and len(current_group) >= 5)
            is_last_word = (i == len(all_words) - 1)

            if has_period or has_semicolon or has_pause or is_pacing_split or is_overlong or is_last_word:
                # Minimum duration filter: scenes should be at least 1.6s to avoid jarring flicker
                if group_duration >= 1.6 or is_last_word or len(sentence_groups) == 0:
                    sentence_groups.append(current_group)
                    current_group = []

        if current_group:
            if sentence_groups and (current_group[-1]["end"] - current_group[0]["start"]) < 1.5:
                sentence_groups[-1].extend(current_group)
            else:
                sentence_groups.append(current_group)

        # NLP Fallback: If punctuation detection found only 1 giant group (Whisper
        # returned words without any punctuation), use regex sentence splitting on
        # the full transcript text and cross-reference with word timestamps.
        if len(sentence_groups) <= 1 and len(all_words) > 8:
            full_text = " ".join(w["word"] for w in all_words)
            # Regex sentence splitter: split on .!?; and also on natural clause breaks
            nlp_sentences = [s.strip() for s in re.split(r'(?<=[.!?;])\s+', full_text) if s.strip()]
            
            # If regex didn't find sentence boundaries either, try splitting on
            # long pauses or every ~4-6 words for visual pacing
            if len(nlp_sentences) <= 1:
                nlp_sentences = _split_by_word_count(all_words, target_words=5)

            if len(nlp_sentences) > 1:
                print(f"[SceneAnalyzer] NLP fallback: punctuation-free transcript, split into {len(nlp_sentences)} sentences via regex")
                sentence_groups = _map_sentences_to_words(nlp_sentences, all_words)

        # 3. Build gapless, continuous scene timestamps
        scenes = []
        for idx, grp in enumerate(sentence_groups):
            grp_text = " ".join(x["word"] for x in grp).strip()
            start = round(grp[0]["start"], 2)
            if idx == 0 and start < 1.2:
                start = 0.0

            if idx < len(sentence_groups) - 1:
                end = round(sentence_groups[idx + 1][0]["start"], 2)
            else:
                end = round(max(grp[-1]["end"], total_dur), 2)

            dur = round(max(0.5, end - start), 2)
            tags = _extract_tags_rulebased(grp_text, niche)

            scenes.append({
                "id": idx,
                "scene_number": idx + 1,
                "start": start,
                "end": end,
                "duration": dur,
                "text": grp_text,
                "words": grp,
                "search_tags": tags,
                "selected_tag": tags[0] if tags else f"{niche} cinematic",
                "video_clip": None,
                "status": "pending"
            })
    else:
        # Fallback if words array was empty: split segments by sentence regex
        scenes = []
        for i, seg in enumerate(segments):
            seg_text = seg.get("text", "").strip()
            start = float(seg.get("start", 0))
            end = float(seg.get("end", 0))
            dur = round(max(0.5, end - start), 2)
            tags = _extract_tags_rulebased(seg_text, niche)
            scenes.append({
                "id": i,
                "scene_number": i + 1,
                "start": start,
                "end": end,
                "duration": dur,
                "text": seg_text,
                "words": seg.get("words", []),
                "search_tags": tags,
                "selected_tag": tags[0] if tags else f"{niche} cinematic",
                "video_clip": None,
                "status": "pending"
            })

    # AI Enhancement if API key is provided
    groq_key = settings.get("groq_api_key", "").strip()
    openai_key = settings.get("openai_api_key", "").strip()
    if (groq_key or openai_key) and scenes:
        try:
            enhanced_tags = _enhance_tags_with_ai(scenes, niche, groq_key, openai_key)
            for sc, new_tags in zip(scenes, enhanced_tags):
                if new_tags:
                    sc["search_tags"] = new_tags
                    sc["selected_tag"] = new_tags[0]
        except Exception as e:
            print(f"[SceneAnalyzer] AI tag enhancement notice: {e}")

    return scenes


def _split_by_word_count(all_words: list, target_words: int = 5) -> List[str]:
    """Fallback splitter: groups words into chunks of ~target_words for visual pacing."""
    sentences = []
    chunk = []
    for w in all_words:
        chunk.append(w["word"])
        if len(chunk) >= target_words:
            sentences.append(" ".join(chunk))
            chunk = []
    if chunk:
        if sentences and len(chunk) < 3:
            sentences[-1] += " " + " ".join(chunk)
        else:
            sentences.append(" ".join(chunk))
    return sentences


def _map_sentences_to_words(sentences: List[str], all_words: list) -> list:
    """Maps regex-split sentences back to word-level timestamp groups."""
    groups = []
    word_idx = 0
    for sent in sentences:
        sent_words = sent.split()
        grp = []
        matched = 0
        while word_idx < len(all_words) and matched < len(sent_words):
            grp.append(all_words[word_idx])
            word_idx += 1
            matched += 1
        if grp:
            groups.append(grp)
    # Attach any remaining words to the last group
    if word_idx < len(all_words) and groups:
        groups[-1].extend(all_words[word_idx:])
    return groups


def _extract_tags_rulebased(text: str, niche: str) -> List[str]:
    """Generates visual tags based on text tokens, emotions, and niche context."""
    text_lower = text.lower()
    matched_queries = []

    # Check for direct keyword mappings
    for kw, queries in KEYWORD_MAP.items():
        if re.search(r'\b' + re.escape(kw) + r'\b', text_lower):
            matched_queries.extend(queries[:2])

    # Clean words to find salient nouns and verbs
    clean_words = [w for w in re.findall(r'\b[a-zA-Z]{4,}\b', text_lower)
                   if w not in {"this", "that", "with", "from", "have", "been", "were", "what", "here", "there", "they", "your"}]

    if clean_words:
        keyword_phrase = " ".join(clean_words[:3])
        matched_queries.append(f"{keyword_phrase} cinematic")

    # Add niche flavored visual tags
    niche_flavor = NICHE_VISUAL_FLAVORS.get(niche, NICHE_VISUAL_FLAVORS["General"])
    matched_queries.extend(niche_flavor[:2])

    # De-duplicate while preserving order
    unique_tags = []
    for q in matched_queries:
        q_clean = q.strip()
        if q_clean and q_clean not in unique_tags:
            unique_tags.append(q_clean)

    return unique_tags[:5]


def _enhance_tags_with_ai(scenes: List[Dict[str, Any]], niche: str, groq_key: str, openai_key: str) -> List[List[str]]:
    """Calls Groq or OpenAI LLM to generate professional b-roll stock video search queries."""
    prompt = f"""You are a master YouTube video editor and B-roll visual director.
For the niche: "{niche}", analyze each sentence from the voiceover script below.
For EACH sentence, provide 3 to 4 specific, cinematic, highly searchable stock footage queries that depict what is being said or the mood.
Respond ONLY with a JSON array of arrays of strings. No markdown, no commentary.
Example: [["person looking into distance", "longing expression", "motivated man standing cliff"], ["crowd walking city subway", "tired worker rainy evening", "monotonous commute"]]

Sentences:
"""
    for i, s in enumerate(scenes):
        prompt += f"{i+1}. {s['text']}\n"

    if groq_key:
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {"Authorization": f"Bearer {groq_key}", "Content-Type": "application/json"}
        content = None
        for model_id in ["openai/gpt-oss-120b", "qwen/qwen3.8-27b", "openai/gpt-oss-20b", "llama-3.3-70b-versatile"]:
            try:
                payload = {
                    "model": model_id,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3
                }
                res = requests.post(url, headers=headers, json=payload, timeout=20)
                if res.status_code == 200:
                    content = res.json()["choices"][0]["message"]["content"]
                    break
            except Exception:
                continue
        if not content:
            return []
    elif openai_key:
        url = "https://api.openai.com/v1/chat/completions"
        headers = {"Authorization": f"Bearer {openai_key}", "Content-Type": "application/json"}
        payload = {
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3
        }
        res = requests.post(url, headers=headers, json=payload, timeout=20)
        res.raise_for_status()
        content = res.json()["choices"][0]["message"]["content"]
    else:
        return []

    content = re.sub(r'```json\s*', '', content)
    content = re.sub(r'```\s*', '', content)
    parsed = json.loads(content.strip())
    if isinstance(parsed, list):
        return parsed
    return []
