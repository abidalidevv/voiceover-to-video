import re
import json
import requests
from typing import List, Dict, Any, Optional
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


def build_scenes(
    transcription: Dict[str, Any],
    niche: str = "General",
    editorial_direction: Optional[Dict[str, Any]] = None,
    max_scene_duration: Optional[float] = None
) -> List[Dict[str, Any]]:
    """
    Takes transcription data and builds structured sentence-level scene objects.
    Each scene corresponds to a single spoken sentence or natural 3-5s visual thought,
    preventing multi-sentence spillage and ensuring 1-to-1 visual-caption harmony.
    Applies editorial direction (pacing multiplier and climax scene tagging).
    """
    settings = load_settings()
    editorial = editorial_direction or {}
    pacing_mult = float(editorial.get("pacing_multiplier", 1.0))
    climax_idx = editorial.get("climax_scene_index")

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

            # Dynamic pacing: split long sentences (>= 5.2s scaled by pacing_multiplier) at natural commas or pauses
            has_comma = bool(re.search(r'[,]$', word_text))
            split_threshold = max(3.0, 5.2 * pacing_mult)
            is_pacing_split = (group_duration >= split_threshold and (has_comma or has_pause))
            overlong_threshold = max(4.5, 7.0 * pacing_mult)
            is_overlong = (group_duration >= overlong_threshold and len(current_group) >= 5)
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
                "status": "pending",
                "is_climax": (climax_idx is not None and idx == climax_idx)
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
                "status": "pending",
                "is_climax": (climax_idx is not None and i == climax_idx)
            })

    # Validate climax scene flag
    if climax_idx is not None and scenes:
        valid_climax = max(0, min(int(climax_idx), len(scenes) - 1))
        for i, sc in enumerate(scenes):
            sc["is_climax"] = (i == valid_climax)
    else:
        for sc in scenes:
            if "is_climax" not in sc:
                sc["is_climax"] = False

    # Apply pacing multiplier to max scene duration cap if specified
    if max_scene_duration is not None:
        effective_max = round(float(max_scene_duration) * pacing_mult, 2)
        for sc in scenes:
            if sc.get("duration", 0) > effective_max:
                sc["duration"] = effective_max

    # AI Enhancement if API key is provided
    groq_key = settings.get("groq_api_key", "").strip()
    openai_key = settings.get("openai_api_key", "").strip()
    if (groq_key or openai_key) and scenes:
        try:
            enhanced_data = _enhance_tags_with_ai(scenes, niche, groq_key, openai_key)
            for sc, item in zip(scenes, enhanced_data):
                if isinstance(item, list):
                    sc["search_tags"] = item
                    if item:
                        sc["selected_tag"] = item[0]
                elif isinstance(item, dict):
                    tags = item.get("search_tags", [])
                    if tags:
                        sc["search_tags"] = tags
                        sc["selected_tag"] = tags[0]
                    sc["raw_callout_text"] = item.get("callout_text")
                    sc["emphasis_word"] = item.get("emphasis_word")
        except Exception as e:
            print(f"[SceneAnalyzer] AI tag enhancement notice: {e}")

    # Prioritize & Rate-Limit Callouts (~1 in every 4-5 scenes, prioritizing is_climax)
    _apply_callouts_prioritization(scenes)

    # Match emphasis words with Whisper word timestamps and check boundary distances
    _match_emphasis_words_with_timestamps(scenes)

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


def _enhance_tags_with_ai(scenes: List[Dict[str, Any]], niche: str, groq_key: str = "", openai_key: str = "") -> List[Dict[str, Any]]:
    """
    Calls Groq or OpenAI LLM once for the script to generate:
    1. Search tags (visual B-roll queries)
    2. Callout text (3-5 words for strong claims, statistics, or key takeaways, else null)
    3. Emphasis word (single most important/punchy word for emphasis zoom timing, else null)
    """
    prompt = f"""You are a master YouTube video editor, B-roll visual director, and motion graphic designer.
For the niche: "{niche}", analyze each sentence from the voiceover script below.
For EACH sentence provide:
1. "search_tags": 3 to 4 specific, cinematic, highly searchable stock footage queries depicting what is being spoken or the mood.
2. "callout_text": If this sentence contains a strong claim, key statistic, notable fact, or list-point worth a visual text callout badge, return a concise 3-5 word callout (e.g., "93% OF USERS AGREE", "KEY TAKEAWAY: PERSISTENCE", "RULE #1: FOCUS FIRST"). Otherwise, return null.
3. "emphasis_word": The single most emphatic, high-impact word in that sentence (numbers, superlatives like "best", "never", "biggest", "critical", or key nouns) for emphasis timing, or null.

Respond ONLY with a STRICT JSON array of objects, one object per sentence in exact order. No markdown code blocks, no commentary.
Example:
[
  {{"search_tags": ["person looking into distance", "longing expression", "motivated man standing cliff"], "callout_text": "PERSISTENCE IS EVERYTHING", "emphasis_word": "everything"}},
  {{"search_tags": ["crowd walking city subway", "tired worker rainy evening"], "callout_text": null, "emphasis_word": "never"}}
]

Sentences:
"""
    for i, s in enumerate(scenes):
        prompt += f"{i+1}. {s['text']}\n"

    content = None
    if groq_key:
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {"Authorization": f"Bearer {groq_key}", "Content-Type": "application/json"}
        for model_id in ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "mixtral-8x7b-32768", "gemma2-9b-it"]:
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
    elif openai_key:
        try:
            url = "https://api.openai.com/v1/chat/completions"
            headers = {"Authorization": f"Bearer {openai_key}", "Content-Type": "application/json"}
            payload = {
                "model": "gpt-4o-mini",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3
            }
            res = requests.post(url, headers=headers, json=payload, timeout=20)
            if res.status_code == 200:
                content = res.json()["choices"][0]["message"]["content"]
        except Exception:
            pass

    if not content:
        return []

    try:
        clean_json = re.sub(r'```(?:json)?\s*', '', content)
        clean_json = re.sub(r'```\s*', '', clean_json).strip()
        parsed = json.loads(clean_json)
        if not isinstance(parsed, list):
            return []

        results = []
        for item in parsed:
            if isinstance(item, list):
                # Legacy format: array of strings
                results.append({
                    "search_tags": [str(t).strip() for t in item if t],
                    "callout_text": None,
                    "emphasis_word": None
                })
            elif isinstance(item, dict):
                tags = item.get("search_tags", [])
                if not isinstance(tags, list):
                    tags = []
                callout = item.get("callout_text")
                if callout and isinstance(callout, str):
                    callout = callout.strip()
                    if len(callout.split()) > 7:
                        callout = " ".join(callout.split()[:5])
                else:
                    callout = None

                emp_word = item.get("emphasis_word")
                if emp_word and isinstance(emp_word, str):
                    emp_word = re.sub(r'[^a-zA-Z0-9]', '', emp_word.strip().lower())
                else:
                    emp_word = None

                results.append({
                    "search_tags": [str(t).strip() for t in tags if t],
                    "callout_text": callout,
                    "emphasis_word": emp_word
                })
            else:
                results.append({"search_tags": [], "callout_text": None, "emphasis_word": None})
        return results
    except Exception as e:
        print(f"[SceneAnalyzer] AI response parsing notice: {e}")
        return []


def _apply_callouts_prioritization(scenes: List[Dict[str, Any]]):
    """
    Limits callouts to roughly 1 out of every 4-5 scenes.
    Prioritizes any scene marked is_climax == True, strong statistics/claims,
    and spaces callouts out so they don't appear in adjacent scenes.
    """
    # Initialize all scenes with callout_text = None
    for sc in scenes:
        sc["callout_text"] = None

    if not scenes:
        return

    candidates = []
    for idx, sc in enumerate(scenes):
        raw_text = sc.get("raw_callout_text")
        if raw_text and isinstance(raw_text, str) and raw_text.strip():
            cleaned = raw_text.strip()
            # Calculate priority score
            score = 10
            if sc.get("is_climax"):
                score += 100
            # Boost if contains digits or percentages (stat/fact)
            if re.search(r'\d', cleaned):
                score += 25
            # Boost if contains high-impact markers
            if re.search(r'\b(key|rule|truth|secret|fact|never|always)\b', cleaned, re.IGNORECASE):
                score += 15
            # Prefer 3-5 words
            word_count = len(cleaned.split())
            if 3 <= word_count <= 5:
                score += 10

            candidates.append({
                "index": idx,
                "score": score,
                "text": cleaned
            })

    if not candidates:
        return

    # Max callouts allowed: roughly 1 out of every 4-5 scenes
    max_callouts = max(1, len(scenes) // 4)

    # Sort candidates by score descending
    candidates.sort(key=lambda c: c["score"], reverse=True)

    # Select candidates ensuring minimum distance of 2 scenes between callouts
    selected_indices = []
    for cand in candidates:
        if len(selected_indices) >= max_callouts:
            break
        cand_idx = cand["index"]
        # Check if adjacent to already selected
        if any(abs(cand_idx - s) <= 1 for s in selected_indices):
            continue
        selected_indices.append(cand_idx)

    # If climax was a candidate and didn't get selected due to spacing, force climax
    climax_candidates = [c for c in candidates if scenes[c["index"]].get("is_climax")]
    if climax_candidates:
        climax_idx = climax_candidates[0]["index"]
        if climax_idx not in selected_indices:
            if selected_indices:
                selected_indices.pop()
            selected_indices.append(climax_idx)

    for cand in candidates:
        if cand["index"] in selected_indices:
            scenes[cand["index"]]["callout_text"] = cand["text"]


def _match_emphasis_words_with_timestamps(scenes: List[Dict[str, Any]]):
    """
    Matches LLM-identified emphasis_word with Whisper word-level timestamps.
    Calculates relative timestamps within the scene clip timeline.
    Marks skip_emphasis_zoom = True if within 0.3s of scene boundaries.
    """
    for sc in scenes:
        sc.setdefault("emphasis_word", None)
        sc["emphasis_start"] = None
        sc["emphasis_end"] = None
        sc["emphasis_rel_start"] = None
        sc["emphasis_rel_end"] = None
        sc["skip_emphasis_zoom"] = True

        emp_word = sc.get("emphasis_word")
        words = sc.get("words", [])
        if not emp_word or not words:
            continue

        clean_target = re.sub(r'[^a-zA-Z0-9]', '', str(emp_word)).lower()
        if not clean_target:
            continue

        matched_w = None
        for w in words:
            clean_w = re.sub(r'[^a-zA-Z0-9]', '', str(w.get("word", ""))).lower()
            if clean_w == clean_target:
                matched_w = w
                break

        if matched_w:
            w_start = float(matched_w.get("start", 0))
            w_end = float(matched_w.get("end", 0))
            sc["emphasis_start"] = w_start
            sc["emphasis_end"] = w_end

            rel_start = round(w_start - float(sc.get("start", 0)), 2)
            rel_end = round(w_end - float(sc.get("start", 0)), 2)
            sc["emphasis_rel_start"] = rel_start
            sc["emphasis_rel_end"] = rel_end

            # Boundary conflict check: skip if within 0.3s of scene start or scene end
            dur = float(sc.get("duration", max(0.5, float(sc.get("end", 0)) - float(sc.get("start", 0)))))
            time_from_start = rel_start
            time_from_end = dur - rel_end

            if time_from_start >= 0.3 and time_from_end >= 0.3:
                sc["skip_emphasis_zoom"] = False
            else:
                sc["skip_emphasis_zoom"] = True


def analyze_script_editorial_direction(
    full_transcript_text: str,
    niche: str = "General",
    groq_key: str = "",
    openai_key: str = ""
) -> Dict[str, Any]:
    """
    Analyzes the full voiceover transcript with a single LLM call to establish
    overall editorial direction: energy level, pacing multiplier, climax scene, and tone.

    Returns:
        {
            "energy": "high" | "medium" | "calm",
            "pacing_multiplier": float (0.8 to 1.3),
            "climax_scene_index": int (0-based) or None,
            "tone": str
        }
    Falls back safely to neutral defaults on any failure or invalid response.
    """
    default_editorial = {
        "energy": "medium",
        "pacing_multiplier": 1.0,
        "climax_scene_index": None,
        "tone": "neutral"
    }

    if not full_transcript_text or not full_transcript_text.strip():
        return default_editorial

    # Automatically load API keys from config if not explicitly provided
    if not groq_key and not openai_key:
        try:
            settings = load_settings()
            groq_key = settings.get("groq_api_key", "").strip()
            openai_key = settings.get("openai_api_key", "").strip()
        except Exception:
            pass

    if not groq_key and not openai_key:
        return default_editorial

    # Number sentences for 0-based climax sentence identification
    raw_sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', full_transcript_text.strip()) if s.strip()]
    if not raw_sentences:
        raw_sentences = [full_transcript_text.strip()]

    numbered_script = "\n".join(f"[{i}] {s}" for i, s in enumerate(raw_sentences))

    prompt = f"""You are a master video director and pacing editor.
For the niche: "{niche}", analyze the voiceover script below.
Sentences with 0-based indices:
{numbered_script}

Evaluate the script's overall pacing, energy, and climax:
1. "energy": Must be exactly "high", "medium", or "calm".
2. "pacing_multiplier": Float from 0.8 to 1.3 (0.8 = fast-paced rapid cuts/high excitement, 1.0 = standard tempo, 1.3 = slow/calm holds).
3. "climax_scene_index": 0-based integer index of the single most emphatic/important/climactic sentence.
4. "tone": One or two words describing the overall tone (e.g., "inspiring", "urgent", "dark mystery", "educational").

Respond ONLY with a STRICT JSON object in this exact format. No markdown code blocks, no commentary:
{{"energy": "high", "pacing_multiplier": 0.9, "climax_scene_index": 0, "tone": "inspiring"}}
"""

    content = None
    try:
        if groq_key:
            url = "https://api.groq.com/openai/v1/chat/completions"
            headers = {"Authorization": f"Bearer {groq_key}", "Content-Type": "application/json"}
            for model_id in ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "mixtral-8x7b-32768", "gemma2-9b-it"]:
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
                return default_editorial
        elif openai_key:
            url = "https://api.openai.com/v1/chat/completions"
            headers = {"Authorization": f"Bearer {openai_key}", "Content-Type": "application/json"}
            payload = {
                "model": "gpt-4o-mini",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3
            }
            res = requests.post(url, headers=headers, json=payload, timeout=20)
            if res.status_code == 200:
                content = res.json()["choices"][0]["message"]["content"]
            else:
                return default_editorial
        else:
            return default_editorial

        if not content:
            return default_editorial

        clean_json = re.sub(r'```(?:json)?\s*', '', content)
        clean_json = re.sub(r'```\s*', '', clean_json).strip()
        parsed = json.loads(clean_json)
        if not isinstance(parsed, dict):
            return default_editorial

        # Validate energy
        energy = str(parsed.get("energy", "medium")).strip().lower()
        if energy not in ("high", "medium", "calm"):
            energy = "medium"

        # Validate & clamp pacing_multiplier
        try:
            pacing_mult = float(parsed.get("pacing_multiplier", 1.0))
            pacing_mult = max(0.8, min(1.3, round(pacing_mult, 2)))
        except (ValueError, TypeError):
            pacing_mult = 1.0

        # Validate climax_scene_index
        climax_idx = parsed.get("climax_scene_index")
        if climax_idx is not None:
            try:
                climax_idx = int(climax_idx)
                if climax_idx < 0 or climax_idx >= len(raw_sentences):
                    climax_idx = max(0, min(climax_idx, len(raw_sentences) - 1))
            except (ValueError, TypeError):
                climax_idx = None

        tone = str(parsed.get("tone", "neutral")).strip() or "neutral"

        return {
            "energy": energy,
            "pacing_multiplier": pacing_mult,
            "climax_scene_index": climax_idx,
            "tone": tone
        }
    except Exception as e:
        print(f"[SceneAnalyzer] Editorial direction fallback notice: {e}")
        return default_editorial

