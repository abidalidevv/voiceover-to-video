# VideoGen Studio ⚡

> **Automated 1080p Full HD & 9:16 YouTube Video Generator** with Intelligent Sentence-Level Segmentation, AI Editorial Direction, Dynamic Clip Trimming, Modern Creator Transitions, 3 Optional Editing Effects (Text Callouts, Sound Stings, Emphasis Zoom), Dual-Track BGM Mixing, and CapCut PC Timeline Integration.

---

## 🌟 Key Capabilities

### 1. Intelligent Sentence-Level Segmentation & AI Editorial Direction
- **Word-Level Micro Timestamps**: Powered by Whisper AI (`whisper-large-v3` via Groq) with punctuation parsing (`.`, `!`, `?`, `;`) and speech pause detection (`> 0.45s`).
- **One Sentence, One Scene**: Every spoken sentence receives its own dedicated scene and visual context tags rather than grouping multiple sentences into clumsy paragraphs.
- **AI Script Editorial Direction**: Performs a single script-level analysis evaluating tone, energy (`"high" | "medium" | "calm"`), dynamic pacing multipliers (`0.8` to `1.3`), and tags the single most emphatic line (`is_climax = True`).
- **Dynamic Pacing Splitter**: Long sentences (`> 6s`) are dynamically split at natural pauses into 3–5 second visual cuts to maintain viral creator pacing.

### 2. Three Optional Pro Editing Effects
- **Phase 1 — Text Callouts**:
  - Automatically identifies strong claims, key statistics, and list-points via single-pass AI.
  - Rate-limited to ~1 in every 4–5 scenes, prioritizing climax scenes and numeric stats.
  - Injects ASS `Style: Callout` badges positioned in the top third of the frame (`badge_yellow`, `badge_cyan`, `badge_dark`) with pop and fade-in/out animations, strictly avoiding bottom caption overlap.
- **Phase 2 — Sound Stings (SFX)**:
  - Royalty-free short transition sound effects (`whoosh_soft.mp3`, `pop_punch.mp3`, `click_modern.mp3`, `ding_bell.mp3`) located in `data/sfx/`.
  - Automatically time-shifted via FFmpeg `adelay` to each exact scene-transition timestamp and mixed natively into voiceover and BGM via `amix`.
  - Fully optional: skips filter graph completely if `transition_sfx` is null.
- **Phase 3 — Emphasis Punch Zoom**:
  - Correlates LLM-identified `emphasis_word` (superlatives, numbers, pivotal nouns) with exact Whisper word micro-timestamps.
  - Sharp punch-zoom keyframe (fast 0.15s zoom-in, 0.25s hold, 0.20s fall) timed to the clip's local timeline.
  - **Boundary Conflict Guard**: Automatically skips punch zoom if the emphasis word falls within 0.3s of scene boundaries to prevent visual collision with transition crossfades.

### 3. Stock Clip Trimming & Extra Video Removal
- **Strict Target Trimming**: Downloaded stock videos (10s–30s) are automatically trimmed and normalized to match the exact duration of each sentence (`sc.duration`).
- **Content-Aware 40% Action Window**: Trims clips into the most active 40% motion window rather than static clip beginnings.
- **No Sentence Bleed**: Clips never spill over or leak across subsequent sentences, ensuring 100% video-to-caption correspondence.
- **Seamless Auto-Looping**: Clips shorter than a scene are seamlessly looped with `-stream_loop -1` to prevent black frames or audio drift.

### 4. Modern Creator Transitions & Randomization
- **Smooth Whip Pan (Left & Right)** (`smoothleft`, `smoothright`): Creator-style dynamic slide.
- **Dynamic Zoom Punch** (`zoomin`): Dramatic visual punch on sentence transitions.
- **Cinematic Crossfade** (`fade`): Atmospheric dissolve.
- **Fast Flash Fade** (`fadefast`): 0.22s punchy flash cut.
- **Circle Focus** (`circlecrop`): Iris reveal.
- **Dynamic Non-Repeating Random Mode**: When set to `"random"`, transitions vary dynamically across scenes without picking the same transition twice in a row.

### 5. Dual-Track Audio Mixing & BGM Ducking
- **Audio Muxing Guarantee**: Strict stream mapping (`-map 0:v:0 -map 1:a:0` or `[aout]`) ensures voiceover audio is 100% present in exported videos.
- **Royalty-Free Ambient Tracks**: Built-in loops (*Cinematic Ambient*, *Lofi Chill*, *Deep Focus*).
- **Template Pools**: Templates support pools (`bgm_track_pool`, `caption_style_pool`) ensuring video variety in bulk batch exports.
- **Smart Volume Mixing**: Automatic volume attenuation under voiceover speech.

### 6. CapCut Kinetic Subtitles & Dual Export
- **12 Viral Caption Presets**: CapCut Yellow, Hormozi Green, Neon Cyber, Red Fire, Clean Minimal, MrBeast Punch, Ali Abdaal, Iman Gadzhi, TikTok Glow, Podcast Box, Streamer Lime, Dark Stoic.
- **Interactive Formatting**: Live letter spacing, word spacing, font size, stroke color, and active word glow highlights.
- **Dual Export Options**:
  - **🚀 Export Video**: Directly renders Full HD 1080p MP4 via FFmpeg with burned-in ASS subtitles and sound stings.
  - **✂️ CapCut Timeline**: Generates a native CapCut desktop draft project with separate video and audio tracks for granular editing inside CapCut PC.

### 7. Multi-Threading & Concurrency Architecture
- **Multi-Worker Downloads**: 6–8 parallel threads download stock footage simultaneously.
- **Cascading Stock Fallback**: Pexels queried first; cascades to Pixabay only on 0 results or 429 rate limits, reducing API calls by 85%+.
- **Render Serialization Lock (`RENDER_LOCK`)**: Strictly serializes FFmpeg GPU renders, eliminating NVENC hardware exhaustion and silent CPU slowdowns.
- **Cross-Batch Lock (`GLOBAL_BATCH_LOCK`)**: Rejects concurrent batch triggers with HTTP 409 Conflict.
- **Batch State Persistence**: Saved to `data/batch_jobs.json`, persisting across server restarts with live cancellation support.

---

## 🎬 Master Video Editing Templates

| Template ID | Target Format | Cut Pacing | Transition & Mode | Caption Style | Callout | SFX Sting | Emphasis Zoom |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **`shorts_viral`** | 9:16 Vertical | Snappy 3.2s | Whip Pan (Random/Fixed) | CapCut Yellow | ✅ `badge_yellow` | `whoosh_soft.mp3` | ✅ 1.15x |
| **`documentary_cinematic`** | 16:9 1080p | Cinematic 5.0s | Crossfade (Fixed) | Luxury Serif | ✅ `badge_dark` | None | ❌ Off |
| **`tech_explainer`** | 16:9 1080p | Punchy 3.5s | Zoom Punch (Fixed) | Neon Cyber | ✅ `badge_cyan` | `whoosh_soft.mp3` | ✅ 1.15x |
| **`stoic_motivation`** | 9:16 / 16:9 | Snappy 3.2s | Flash Fade (Fixed) | Dark Stoic | ✅ `badge_dark` | `whoosh_soft.mp3` | ✅ 1.15x |
| **`podcast_pill`** | 16:9 1080p | Natural 4.2s | Clean Cut (Fixed) | Vox Pill Box | ❌ Off | None | ❌ Off |

---

## 🚀 Getting Started

### Prerequisites
- Python 3.10+
- FFmpeg 6.0+ (FFmpeg with NVENC/QSV/AMF hardware encoder support detected)
- Windows / macOS / Linux

### Quick Launch
Run the automated launcher:
```cmd
start.bat
```
Or start the Python server directly:
```bash
python main.py
```
Open your browser at:
```
http://127.0.0.1:8765/
```

---

## 📁 Repository Structure

```
VideoGen/
├── backend/                  # Core Python modules
│   ├── server.py             # Active FastAPI backend endpoints & WebSocket progress
│   ├── transcriber.py        # Groq Whisper speech-to-text with word timestamps
│   ├── scene_analyzer.py     # Sentence segmentation, editorial direction & tag enhancement
│   ├── stock_downloader.py   # Multi-worker concurrent Pexels/Pixabay downloader
│   ├── video_renderer.py     # FFmpeg normalization, xfade, SFX mixing & punch zoom
│   ├── subtitle_generator.py # ASS kinetic subtitles & callout badge generator
│   ├── templates.py          # Master templates, pools & variant resolution
│   ├── capcut_exporter.py    # Native CapCut desktop draft project generator
│   └── config.py             # Global settings, paths, SFX library & defaults
├── frontend/                 # Web application interface
│   ├── index.html            # Studio, Preview Editor, Batch Queue, and Settings tabs
│   ├── styles.css            # Dark mode UI, responsive rules, 100% wide player
│   ├── app.js                # Frontend controllers, preview audio sync, WebSockets
│   ├── caption_engine.js     # Word-level kinetic subtitle animator
│   └── docs.html             # Built-in User Guide & operational manual
├── test/                     # Dedicated test scripts and verification artifacts
│   ├── test_editing_effects.py      # Unit tests for Callouts, SFX & Emphasis Zoom
│   ├── test_18s_sample_voiceover.py # 18s sample voiceover end-to-end render test
│   ├── test_editorial_direction.py  # Script tone, energy, and climax tagging tests
│   ├── test_template_pools.py       # BGM & caption variant pool distribution tests
│   ├── test_random_transitions.py   # Non-repeating transition tests
│   └── test_bottlenecks_and_fixes.py # Concurrency locks & ranking tests
├── data/                     # Local SQLite DB, media cache, and exported videos
│   ├── sfx/                  # Royalty-free sound effects (whoosh, pop, click, ding)
│   ├── assets/bgm/           # Background music loops (lofi, ambient, focus)
│   ├── settings.json         # Local on-device JSON API credentials (unshared)
│   ├── batch_jobs.json       # Persistent batch queue state
│   ├── cache/                # Downloaded stock videos and audio clips
│   └── output/               # Rendered 1080p MP4 videos and CapCut drafts
├── main.py                   # Server entrypoint (port 8765)
├── start.bat                 # 1-Click launcher script
└── requirements.txt          # Python dependencies
```

---

## 🔑 API Configuration

Configure your API keys in the **Settings & APIs** tab in the UI or directly in `data/settings.json`:
- **Groq API Key**: `gsk_...` (Ultra-fast Whisper transcription in ~1.5s & LLM tag enhancement)
- **Pexels API Key**: For 1080p Full HD landscape stock footage
- **Pixabay API Key**: For secondary high-resolution video candidates
*(All keys remain strictly stored on your local disk in data/settings.json and are never transmitted to third-party telemetry).*

---

## 📜 Documentation & User Guide
- Open the interactive **User Guide** by clicking **📖 Guide** in the top navigation header or visiting:
  `http://127.0.0.1:8765/docs.html`
- Technical task and walkthrough records are persisted in `walkthrough.md` and `task.md`.
