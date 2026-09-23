# VideoGen Studio — Architectural Review & System Blueprint for Claude

This document provides a comprehensive technical overview of **VideoGen Studio**, detailed post-mortems of recent engineering breakthroughs, architectural decisions, and current technical suggestions for collaborative review with Claude.

---

## 1. System Architecture Overview

VideoGen Studio is an automated AI-driven YouTube Full HD (1080p) / 4K UHD video generation engine. It transforms raw voiceover audio or text into a complete, synchronized YouTube video with dynamic kinetic subtitles, context-matched stock footage, sound effects, background music, AI image fallback, and viral YouTube thumbnails.

### End-to-End Pipeline Flow:
```
[Voiceover Audio / Text Script]
             │
             ▼
[Whisper Word-Level Transcription & Micro-Segmentation] (Groq Whisper Large v3)
             │
             ▼
[AI Scene Analyzer: Gemini Flash + Groq LLM + 80+ Keyword Map]
  ├─ 2-3 Word English Visual Stock Queries (Niche Anchored)
  ├─ 3-5 Word Callout Text Badges
  └─ High-Impact Emphasis Words for Timed Punch Zoom
             │
             ▼
[Stock Footage Downloader & Multi-Account Concurrency Pool]
  ├─ Pexels API (Multi-Key Pool, 8 Workers)
  ├─ Pixabay API (Multi-Key Pool)
  ├─ Thematic Clash Scoring (-200 pts penalty against off-topic footage)
  └─ [NEW] 1-Click Ultra HD 16:9 AI Image Generation (Missing Clips Fallback via Pollinations Flux/SDXL)
             │
             ▼
[FFmpeg Audio/Video Synchronization & Multi-Pass Concurrency Engine]
  ├─ Content-Aware Action Window Trimming (Exact Sentence Duration)
  ├─ Dynamic ASS Subtitle Generator (Word-by-word Kinetic Karaoke Highlighting)
  ├─ Dual-Layer Audio Engine (Voiceover + Ducked BGM + Transition SFX)
  ├─ Constant Frame Rate CFR Normalization (-vsync cfr, centered xfade offsets)
  └─ Hardware-Accelerated NVENC / AMF / CPU Encoding
             │
             ▼
[Export & Delivery Engine]
  ├─ Final YouTube MP4 (1080p/4K)
  ├─ Dual YouTube Thumbnails (Style 1: Bold Viral Punch, Style 2: Dark Cinematic Mystery)
  ├─ AI YouTube SEO Suite (High-CTR Titles, Timestamps, Tags)
  ├─ Native CapCut Desktop Draft Project Exporter (100+ Cuts & 400+ Subtitle Tracks)
  └─ Interactive In-App Docs Manual & Windows Explorer Integration
```

---

## 2. Recent Bug Post-Mortems & Breakthrough Fixes

### Challenge A: Voiceover Content Mismatch ("Snail Video on Ballistic Missile Sentence")
* **Symptom**: User fed a script about the Iran-Israel conflict with ballistic missile strikes (in Roman Urdu / with typos like *"blastoc misile"*), but the resulting video showed a nature clip of a **snail**.
* **Root Cause**:
  1. `backend/scene_analyzer.py` had decommissioned Groq model strings, causing silent fallback to `_extract_tags_rulebased()`.
  2. `KEYWORD_MAP` lacked defense/military keywords.
  3. The rule-based extractor appended generic nature tags (`"dense emerald forest mist"`). Pexels returned 0 results for long 4-word combined queries, falling back to forest/snail footage.
* **Resolution**:
  - Upgraded to active Groq endpoints (`groq/compound-mini`, `openai/gpt-oss-20b`, `groq/compound`).
  - Added Google Gemini 2.5/3.6 Flash with multi-key load balancing as the primary contextual intelligence engine.
  - Added 30+ military/defense terms into `KEYWORD_MAP`.
  - Added automatic query simplification fallback (simplifying queries to salient 2-word nouns).
  - Added negative clash penalties (`-100 pts`) against insects, flowers, and peaceful nature for action scenes.

---

### Challenge B: Space & Astronomy Thematic Clash ("Swimmers & Olympics on Astronomy Voiceover")
* **Symptom**: User provided a space/astronomy voiceover topic, but several scenes displayed stock clips of people swimming at the beach, sea waves, or Olympic runners.
* **Root Cause**:
  1. Words like *"fast"*, *"speed"*, *"waves"*, *"surface"* in astronomy scripts (e.g. gravitational waves, planetary surface, cosmic speed) matched athletic sprinting, ocean waves, or swimming clips on Pexels/Pixabay.
  2. The scoring algorithm did not penalize terrestrial human recreational footage when the chosen niche was **Sci-Fi & Space**.
* **Resolution**:
  - Added **60+ specialized space terms** into `KEYWORD_MAP` (`space`, `astronomy`, `galaxy`, `telescope`, `nebula`, `planet`, `orbit`, `black hole`, `spacewalk`, `cosmos`, `starlight`, `supernova`, `satellite`, etc.).
  - Implemented **Niche Query Anchoring**: For Space & Sci-Fi topics, every query is automatically anchored with `space astronomy` or `cinematic space`.
  - Implemented **Strict Thematic Penalty (-200 pts)**: In `backend/stock_downloader.py`, candidate videos with tags like `beach`, `swim`, `swimming`, `ocean`, `pool`, `athlete`, `olympics`, `fitness`, `sports`, `park`, `bikini`, `crowd` receive an instant **-200 point penalty** when the project niche is Space/Astronomy.

---

### Challenge C: Preview Player Stuttering & Static Image Bug
* **Symptom**: When playing video preview in the Studio, AI-swapped images displayed as flat, static pictures without video motion, and transitions between scenes had noticeable visual lag/stutter.
* **Root Cause**:
  1. When a clip had provider `ai_image`, the frontend showed a static `<img>` layer while hiding `<video>`, resulting in a jarring halt in visual pacing compared to 24fps stock video clips.
  2. Media elements did not preload the upcoming scene's media, causing network buffering hiccups on each scene cut.
* **Resolution**:
  - Implemented an animated **Ken Burns Motion Layer** in `frontend/styles.css` (`@keyframes kenBurnsZoomPan`) applied to the preview image layer.
  - Implemented asynchronous **Next-Scene Preloading** in `frontend/app.js` (`preloadNextSceneMedia()`), completely eliminating scene transition stutter.

---

### Challenge D: Subtitle & Audio-Video Drift in Final Render
* **Symptom**: Towards the middle/end of long 5–10 minute videos, subtitles and video cuts would drift out of sync with the voiceover by 1–3 seconds.
* **Root Cause**:
  1. Stock video clips downloaded from Pexels and Pixabay have variable frame rates (VFR) ranging from 23.976 to 60.0 fps.
  2. When concatenating VFR clips, FFmpeg accumulated fractional timestamp drift over hundreds of seconds.
  3. When `xfade` crossfade transitions were applied, transition overlap durations shifted the cumulative timeline offset relative to the absolute ASS subtitle timestamps.
* **Resolution**:
  - Forced **Constant Frame Rate (CFR)** normalization via `-vsync cfr -r {target_fps}` during scene normalization.
  - Balanced transition offsets by centering crossfade windows symmetrically around scene boundaries.
  - Clamped the final audio-video muxing strictly to `-t {audio_duration}` to ensure millisecond-perfect lip and subtitle sync.

---

### Challenge E: Windows Desktop App Mode Navigation & Explorer Focus
* **Symptom**: 
  1. Clicking `📖 Docs` in the top header did nothing.
  2. Clicking `📁 Outputs` or `📂 Show in Windows Folder` did not appear to open the folder.
  3. Server threw `FileExistsError: [WinError 183]` when attempting to open an exported video file.
* **Root Cause**:
  1. The app runs via Microsoft Edge in standalone desktop mode (`msedge.exe --app=http://127.0.0.1:8765`). Edge App mode runs without browser tabs or address bar, and silently suppresses `<a target="_blank">` navigation.
  2. Backend `open_folder` endpoint ran `target_path.mkdir(parents=True, exist_ok=True)` unconditionally. When passed a file path (`...mp4`), `mkdir()` raised `FileExistsError` and returned HTTP 500.
  3. `os.startfile()` on Windows opens the folder in the background behind full-screen Edge without bringing Explorer to the front.
* **Resolution**:
  - Replaced `📖 Docs` link with an interactive modal trigger: opens an in-app **Operational Manual & User Guide Modal** containing an embedded iframe of `docs.html`, and calls `/api/open-docs` to launch the user's default Windows browser via Python's `webbrowser.open_new_tab()`.
  - Refactored `open_folder` in `backend/server.py`:
    - If `target_path.is_file()`: runs `subprocess.Popen(['explorer.exe', '/select,', abs_path])`, which pops Windows Explorer directly in front of the app with the newly exported `.mp4` video highlighted!
    - If `target_path.is_dir()`: runs `subprocess.Popen(['explorer.exe', abs_path])`.
    - No `mkdir()` is called on existing files.

---

### Challenge F: Export Modal Thumbnail 404 & Direct YouTube Thumbnails
* **Symptom**: In the "Ultra HD Video Exported Successfully!" modal, the video preview box was pitch black (0:00), and thumbnails did not appear.
* **Root Cause**:
  1. `frontend/app.js` hardcoded the video poster to `/media/thumbnails/${id}_thumb1.jpg`. The actual files generated by `thumbnail_generator.py` are `{id}_thumb_1_viral.jpg` and `{id}_thumb_2_cinematic.jpg`, causing a 404 error and black player.
  2. Render progress job result did not pass `thumbnails` data to the frontend completion callback.
  3. The export modal lacked direct thumbnail preview cards.
* **Resolution**:
  - Bound video player poster to the verified thumbnail URL (`thumb_1_viral.jpg`).
  - Added direct side-by-side **YouTube Thumbnail Preview Cards** (Style 1: Bold Viral Punch & Style 2: Dark Cinematic Mystery) directly inside the Export Complete Modal with 1-click **Download (1280x720)** buttons.
  - Robustified `/api/thumbnails/{id}` to scan disk cache (`data/thumbnails/` and `data/output/`) so thumbnail loading never returns 404 even if in-memory project state was reset.

---

## 4. Video Overlay Engine (New)

* **Architecture**: A dedicated `backend/video_overlay.py` module handles overlay path resolution, FFmpeg filter generation, and position/opacity calculations.
* **FFmpeg Integration**: Overlays are applied in the `filter_complex` chain **before** ASS subtitles, so kinetic captions always render on top of the overlay layer.
* **Filter Pipeline**: `[overlay_input] → scale → format=rgba → colorchannelmixer(aa=opacity) → overlay(position) → [vovr]`
* **Position Presets**: `top_left`, `top_right`, `bottom_left`, `bottom_right`, `center` — each maps to exact FFmpeg overlay coordinates with 10px padding.
* **Opacity Control**: Uses `colorchannelmixer=aa=0.XX` (0.0 invisible → 1.0 fully opaque), default 30%.
* **Auto-Scaling**: Overlay auto-scales to a configurable percentage of the main frame width (default 20%), preserving aspect ratio.
* **Supported Formats**: Video overlays (`.mp4`, `.mov`, `.webm`) use `shortest=1` to match main video length. Image overlays (`.png`, `.jpg`, `.gif`) are static.

---

## 5. Free Voice Cloning — Kokoro-82M (New)

* **Engine**: Kokoro-82M, an Apache 2.0 licensed, CPU-friendly TTS model (~200MB).
* **Zero Cost**: Fully local inference, no API keys, no cloud dependency, no usage limits.
* **Integration**: Added as a new TTS provider (`kokoro_clone`) in `tts_generator.py`, alongside Edge-TTS, ElevenLabs, and OpenAI.
* **21 Voice Presets**: American English (male/female) and British English (male/female) presets.
* **Graceful Fallback**: If Kokoro is not installed (`pip install kokoro soundfile`), the system automatically falls back to Microsoft Edge-TTS Andrew V2.
* **Pipeline**: `KPipeline(lang_code='a') → generate segments → concatenate → WAV → FFmpeg MP3 conversion → pipeline-ready audio`
* **First-Run**: Model auto-downloads (~200MB) on first use, no manual setup required.

---

## 6. High-Value Architectural Suggestions for Claude & Next Steps

### Suggestion 1: Automated Multimodal Visual Relevance Validator (CLIP / Gemini Flash)
* **Concept**: While negative keyword clash penalties (-200 pts) catch obvious errors, an AI visual verification pass provides 100% guarantee.
* **Architecture**:
  1. When a stock clip or AI image is acquired for a scene, grab Frame 0.
  2. Send Frame 0 and the scene narration to Gemini 2.5 Flash with a binary check:
     `"Does this visual align with the context of: [Narration]? Reply YES or NO"`.
  3. If NO: immediately try the next stock candidate or invoke `backend/image_generator.py` for a tailored 16:9 cinematic render.

### Suggestion 2: In-App Scene Clip Playback Speed & Looping Controls
* **Concept**: When a sentence narration duration (e.g. 8.5s) exceeds the downloaded stock video clip duration (e.g. 5.2s), FFmpeg currently slows down the clip or loops.
* **Architecture**:
  - Add visual speed controls (0.8x, 1.0x, 1.25x) and a seamless ping-pong reverse loop option directly in the Scene Editor bar in the Studio tab.

---

## 7. Current File Structure & Module Responsibilities

```
VideoGen-Studio/
├── backend/
│   ├── server.py              # FastAPI endpoints, WebSocket progress, Explorer & Docs APIs
│   ├── scene_analyzer.py      # Gemini Flash / Groq LLM scene analyzer & 80+ keyword map
│   ├── stock_downloader.py    # Multi-worker Pexels/Pixabay downloader with -200pt clash scoring
│   ├── image_generator.py     # 1-Click 16:9 AI Image Generator & Ken Burns MP4 video synthesis
│   ├── video_renderer.py      # FFmpeg CFR normalization, transitions, BGM/SFX/Overlay mixing
│   ├── video_overlay.py       # [NEW] Video overlay engine (logo, watermark, facecam + opacity)
│   ├── voice_cloner.py        # [NEW] Free voice cloning via Kokoro-82M (Apache 2.0, CPU)
│   ├── subtitle_generator.py  # ASS kinetic subtitles & callout badge generator
│   ├── thumbnail_generator.py # YouTube Thumbnail Studio (Viral Punch & Cinematic Mystery)
│   ├── seo_generator.py       # AI YouTube SEO Suite (Titles, Description, Timestamps, Tags)
│   ├── tts_generator.py       # Edge-TTS Neural, ElevenLabs, OpenAI, Kokoro voice engines
│   ├── transcriber.py         # Groq Whisper speech-to-text with word micro-timestamps
│   ├── capcut_exporter.py     # Native CapCut desktop draft project generator
│   ├── templates.py           # Master templates, pools & variant resolution
│   └── config.py              # Global settings, paths, SFX library & defaults
├── frontend/
│   ├── index.html             # Studio, Preview, Thumbnail, Projects, Settings, Docs & Export modals
│   ├── styles.css             # Glassmorphic Obsidian UI, Ken Burns animations, responsive styles
│   ├── app.js                 # UI controllers, preview engine, overlay & clone handlers
│   ├── caption_engine.js      # Word-level kinetic subtitle animator & drag positioning
│   ├── docs.html              # Built-in User Guide & operational manual
│   ├── favicon.ico / png      # Application brand badges
├── data/                      # Persistent storage
│   ├── assets/bgm/            # Background music loops
│   ├── assets/overlays/       # [NEW] Uploaded video/image overlays
│   ├── models/                # [NEW] Kokoro-82M voice cloning model cache
│   ├── voice_samples/         # [NEW] User voice reference audio samples
│   ├── output/                # Rendered videos & thumbnails
│   ├── thumbnails/            # YouTube thumbnail JPEGs
│   ├── seo/                   # Generated SEO metadata JSON
│   └── sfx/                   # Sound effects & voice preview MP3s
├── 1_RUN_APP_Python_Source.bat # 1-Click launcher for Python source mode
├── 2_RUN_APP_Standalone_EXE.bat# 1-Click launcher for compiled executable
├── 3_BUILD_NEW_Standalone_EXE.bat # PyInstaller executable compiler
├── desktop_launcher.py        # Desktop app launcher with Edge App mode & port management
├── requirements.txt           # Python dependencies (including kokoro, soundfile, numpy)
└── CLAUDE_REVIEW.md           # Master architectural review document
```

---
*Maintained by Antigravity AI • VideoGen Studio 4K/8K UHD AI Video Engine*
