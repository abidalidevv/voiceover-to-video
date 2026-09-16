# VideoGen Studio ⚡

> **Automated 1080p Full HD & 9:16 YouTube Video Generator** with Intelligent Sentence-Level Segmentation, Dynamic Clip Trimming, Modern Creator Transitions, Dual-Track BGM Mixing, and CapCut PC Timeline Integration.

---

## 🌟 Key Capabilities

### 1. Intelligent Sentence-Level Segmentation & Word Pacing
- **Word-Level Micro Timestamps**: Powered by Whisper AI (`whisper-large-v3` via Groq) with punctuation parsing (`.`, `!`, `?`, `;`) and speech pause detection (`> 0.45s`).
- **One Sentence, One Scene**: Every spoken sentence receives its own dedicated scene and visual context tags rather than grouping multiple sentences into clumsy paragraphs.
- **Dynamic Pacing Splitter**: Long sentences (`> 6s`) are dynamically split at commas or breathing pauses into 3–5 second visual cuts to maintain viral YouTube retention pacing.

### 2. Stock Clip Trimming & Extra Video Removal
- **Strict Target Trimming**: Downloaded stock videos (10s–30s) are automatically trimmed and normalized to match the exact duration of each sentence (`sc.duration`).
- **No Sentence Bleed**: Clips never spill over or leak across subsequent sentences, ensuring 100% video-to-caption correspondence.
- **Seamless Auto-Looping**: Clips shorter than a scene are seamlessly looped with `-stream_loop -1` to prevent black frames or audio drift.

### 3. Modern Creator Transitions (FFmpeg `xfade`)
- **Smooth Whip Pan (Left & Right)** (`smoothleft`, `smoothright`): Creator-style dynamic slide.
- **Dynamic Zoom Punch** (`zoomin`): Dramatic visual punch on sentence transitions.
- **Cinematic Crossfade** (`fade`): 0.35s atmospheric dissolve.
- **Fast Flash Fade** (`fadefast`): 0.25s punchy flash cut.
- **Circle Focus** (`circlecrop`): Iris reveal.
- **Clean Hard Cut** (`none`): Instant YouTube jump cut standard.

### 4. Dual-Track Audio Mixing & BGM Ducking
- **Audio Muxing Guarantee**: Strict `-map 0:v:0 -map 1:a:0` (or `[aout]`) stream mapping ensures voiceover audio is 100% present in exported videos.
- **Royalty-Free Ambient Tracks**: Built-in loops (*Cinematic Ambient*, *Lofi Chill*, *Deep Focus*).
- **Custom BGM Upload**: Drop in any `.mp3` background music file.
- **Smart Volume Mixing**: Automatic 10% volume attenuation under voiceover speech.

### 5. CapCut Kinetic Subtitles & Typography
- **12 Viral Caption Presets**: CapCut Yellow, Hormozi Green, Neon Cyber, Red Fire, Clean Minimal, MrBeast Punch, Ali Abdaal, Iman Gadzhi, TikTok Glow, Podcast Box, Streamer Lime, Dark Stoic.
- **Interactive Formatting**: Live letter spacing, word spacing, font size, stroke color, and active word glow highlights.
- **Dual Export Options**:
  - **🚀 Export Video**: Directly renders Full HD 1080p MP4 via FFmpeg with burned-in ASS subtitles.
  - **✂️ CapCut Timeline**: Generates a native CapCut desktop draft project with separate video and audio tracks for granular editing inside CapCut PC.

---

## 🚀 Getting Started

### Prerequisites
- Python 3.10+
- FFmpeg 6.0+ (FFmpeg 9.0.1 with hardware encoder support detected)
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
│   ├── server.py             # FastAPI backend endpoints & WebSocket progress
│   ├── transcriber.py        # Groq Whisper speech-to-text with word timestamps
│   ├── scene_analyzer.py     # Sentence segmentation & visual search intent
│   ├── stock_downloader.py   # Multi-worker concurrent Pexels/Pixabay downloader
│   ├── video_renderer.py     # FFmpeg normalization, xfade transitions, audio muxing
│   ├── capcut_exporter.py    # Native CapCut desktop draft project generator
│   └── config.py             # Global settings, paths, and defaults
├── frontend/                 # Web application interface
│   ├── index.html            # Studio, Preview Editor, Library, and Settings tabs
│   ├── styles.css            # Dark mode UI, responsive rules, 100% wide player
│   ├── app.js                # Frontend controllers, preview audio sync, WebSockets
│   ├── caption_engine.js     # Word-level kinetic subtitle animator
│   └── docs.html             # Built-in User Guide & operational manual
├── test/                     # Dedicated test scripts and verification artifacts
│   ├── test_pipeline_e2e.py  # End-to-end segmentation, trimming, and transition test
│   ├── test_live_workflow.py # Full workflow test with live API authentication
│   └── test_xfade.py         # FFmpeg transition matrix test
├── data/                     # Local SQLite DB, media cache, and exported videos
│   ├── videogen.db           # Projects and stock assets database
│   ├── settings.json         # Encrypted local API credentials
│   ├── cache/                # Downloaded stock videos and audio clips
│   └── output/               # Rendered 1080p MP4 videos and CapCut drafts
├── main.py                   # Server entrypoint (port 8765)
├── start.bat                 # 1-Click launcher script
└── requirements.txt          # Python dependencies
```

---

## 🔑 API Configuration

Configure your API keys in the **Settings & APIs** tab in the UI or in `data/settings.json`:
- **Groq API Key**: `gsk_...` (Ultra-fast Whisper transcription in ~1.5s)
- **Pexels API Key**: For 1080p Full HD landscape stock footage
- **Pixabay API Key**: For secondary high-resolution video candidates
*(All keys remain strictly stored on your local disk).*

---

## 📜 Documentation & Guides
- Open the interactive **User Guide** by clicking **📖 Guide** in the top navigation header or visiting:
  `http://127.0.0.1:8765/docs.html`
- Technical task and walkthrough records are persisted in `walkthrough.md` and `task.md`.
