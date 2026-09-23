# ATS Video ⚡ (4K/8K UHD AI Video Engine)

> **All-In-One Automated AI Video Engine, Neural Voiceover Studio, YouTube Thumbnail Studio & CapCut PC Integration**.
> Generates 1080p Full HD, 4K UHD, and 8K Ultra HD YouTube landscape videos (16:9) and viral vertical Shorts (9:16) from a single script or voiceover audio file.

---

## 🌟 Core Highlights

### 1. 🎙️ In-App Neural AI Voiceover Studio (100% Free & Unlimited)
- **100% Free Microsoft Edge-TTS Engine**: Pre-configured with 16+ ultra-realistic human neural voices with natural breathing pauses, authentic emotional inflection, and zero API costs.
  - 🌟 **Andrew V2 & Ava V2**: Ultra-natural narration with human breathing and vocal pauses.
  - 🌟 **Brian V2 & Emma V2**: Conversational YouTube tech and crisp studio storytelling.
  - 🎬 **Christopher & Guy**: Deep cinematic documentary and high-retention creator voices.
  - 🇵🇰 **Asad & Uzma**: Authentic, polished Urdu (Pakistan) male and female voices.
  - 🇮🇳 **Madhur & Swara**: Engaging, dynamic Hindi (India) male and female voices.
  - 🇬🇧 **Ryan & Sonia**: Sophisticated British documentary narration.
  - 🇦🇺 **William**: Relaxed, positive Australian voiceover.
- **🔊 1-Click Instant Voice Sample Previews**: Pre-cached 3-second audio samples for all curated voices with 0ms instantaneous playback directly in the browser.
- **💎 ElevenLabs & OpenAI Speech Integration**: Optional user API keys for ElevenLabs (10k chars/mo free tier) and OpenAI TTS (`tts-1`), backed by automatic fallback to Microsoft Neural V2 to guarantee zero downtime.

### 2. 🖼️ YouTube Thumbnail Studio (Viral & Cinematic Mystery)
- **1-Click High-CTR YouTube Thumbnails (1280×720 HD)**:
  - **Option 1: Viral High-CTR Style** (*MrBeast / Alex Hormozi Impact*): Electric yellow and white bold typography, heavy 3D drop shadows, red/gold pill badge (`100% PROVEN`), and high-urgency callouts.
  - **Option 2: Cinematic Mystery Style** (*Magnates Media / Vox Documentary*): Luxury gold border framing, glowing cyan and white typography, cold teal vignette, and category header (`• SPECIAL REPORT •`).
- **Dynamic Auto-Fit Font Scaling**: Algorithmically scales font sizes down to prevent text overflow regardless of headline length.

### 3. 🏷️ YouTube SEO Title, Description & Tags Suite
- **High-CTR YouTube Titles**: Generates 3 curiosity-gap titles crafted for algorithmic click-through rate.
- **Full Video Description**: Auto-generates structured description with key takeaways, chapter markers, and channel hashtags.
- **Optimized Video Tags**: Formats ranked comma-separated tags ready for 1-click clipboard copying.

### 4. 🎬 4K & 8K UHD Resolution Profiles
- **Ultra High Definition Profiles**: Supports Full HD (1080p), 4K UHD (3840×2160), and 8K Ultra HD (7680×4320) output for high-res displays and TVs.
- **Aspect Ratio Switching**: Seamlessly toggle between 16:9 Landscape (YouTube) and 9:16 Vertical (Shorts, TikTok, Reels).

### 5. 🔊 Scene Transitions & Auto SFX Stings
- **Royalty-Free Sound Effects**: Automatic insertion of transition stings (`whoosh_soft.mp3`, `pop_punch.mp3`, `click_modern.mp3`, `ding_bell.mp3`) with FFmpeg `adelay` time-alignment.
- **Custom Background Music (BGM)**: 1-click upload of custom audio with automatic looping and volume ducking under speech.

### 6. 💬 CapCut Kinetic Subtitles & Interactive Positioning
- **12 Viral Typography Presets**: CapCut Yellow, Hormozi Green, Neon Cyber, Red Fire, Clean Minimal, MrBeast Punch, Ali Abdaal, Iman Gadzhi, TikTok Glow, Podcast Box, Streamer Lime, Dark Stoic.
- **Mouse Drag-to-Positioning**: Drag subtitles directly on the video player to adjust vertical position in real time.
- **1-Click Subtitle Toggle**: Easily toggle captions on/off for video-only exports.

### 7. ✂️ CapCut PC Timeline Draft Integration
- **Native Desktop Project Generation**: Exports video cuts, voiceover timeline, and kinetic caption tracks directly into `%LOCALAPPDATA%\CapCut\User Data\Projects\com.lveditor.draft\`.
- **Auto-Launch**: Automatically opens the generated project inside CapCut PC for final polish.

### 8. ⚡ High-Speed Concurrency & GPU Acceleration
- **2 to 32 Parallel Workers**: Hardware power slider tuned for dual-core CPUs up to multi-core Threadrippers.
- **Hardware Acceleration**: Auto-detects NVIDIA NVENC (`h264_nvenc`), AMD AMF (`h264_amf`), and Intel QuickSync (`h264_qsv`).

---

## 🚀 Quick Start

### Standalone Executable (Zero Setup)
Double-click:
```cmd
2_RUN_APP_Standalone_EXE.bat
```
*(No Python, Git, or FFmpeg installation required. Everything is self-contained in the portable package).*

### Developer / Source Code Mode
Run:
```cmd
1_RUN_APP_Python_Source.bat
```
Or start via Python:
```bash
python main.py
```
Open your browser at:
```
http://127.0.0.1:8765/
```

---

## 📁 Clean Repository Structure

```
ATS-Video/
├── backend/                  # Core Python modules
│   ├── server.py             # Active FastAPI backend endpoints, WebSocket progress & Explorer launchers
│   ├── scene_analyzer.py     # Gemini Flash + Groq LLM scene analyzer & 80+ keyword map
│   ├── stock_downloader.py   # Multi-worker Pexels/Pixabay downloader with -200pt clash scoring
│   ├── image_generator.py    # 1-Click 16:9 AI Image Generator & Ken Burns MP4 video synthesis
│   ├── video_renderer.py     # FFmpeg CFR normalization, centered transitions, BGM/SFX mixing
│   ├── subtitle_generator.py # ASS kinetic subtitles & callout badge generator
│   ├── thumbnail_generator.py# YouTube Thumbnail Studio (Viral Punch & Cinematic Mystery)
│   ├── seo_generator.py      # AI YouTube SEO Suite (Titles, Description, Timestamps, Tags)
│   ├── tts_generator.py      # Edge-TTS Neural, ElevenLabs, OpenAI voice engines
│   ├── transcriber.py        # Groq Whisper speech-to-text with word micro-timestamps
│   ├── capcut_exporter.py    # Native CapCut desktop draft project generator
│   ├── templates.py          # Master templates, pools & variant resolution
│   └── config.py             # Global settings, paths, SFX library & defaults
├── frontend/                 # Glassmorphic Obsidian Web application
│   ├── index.html            # Studio, Preview, Thumbnail, Projects, Settings, Docs & Export modals
│   ├── styles.css            # Dark mode UI, Ken Burns animations, responsive styles
│   ├── app.js                # Frontend controllers, live preview, folder & CapCut handlers
│   ├── caption_engine.js     # Word-level kinetic subtitle animator & drag positioning
│   ├── docs.html             # Built-in User Guide & operational manual
│   ├── favicon.ico / png     # Application icon & brand badge
├── data/                     # Persistent application data
│   ├── assets/bgm/           # Background music loops (ambient, lofi, focus)
│   ├── output/               # Rendered 1080p/4K MP4 videos & YouTube thumbnails
│   ├── thumbnails/           # Auto-generated YouTube clickbait thumbnail JPEGs
│   ├── seo/                  # Generated YouTube titles, descriptions, and tags JSON
│   └── sfx/                  # Sound effects & pre-cached voice preview MP3s
├── 1_RUN_APP_Python_Source.bat       # 1-Click launcher for Python source code (fast & live)
├── 2_RUN_APP_Standalone_EXE.bat       # 1-Click launcher for compiled executable (standalone)
├── 3_BUILD_NEW_Standalone_EXE.bat     # PyInstaller standalone executable compiler
├── desktop_launcher.py       # Desktop app launcher with Edge App mode & port management
├── main.py                   # Root application entrypoint
├── CLAUDE_REVIEW.md          # Master architectural review & post-mortem blueprint
└── requirements.txt          # Python dependencies
```

---

## 📜 Interactive Documentation
Access the comprehensive user guide by clicking **📖 Docs** in the top navigation header inside the app or visiting:
`http://127.0.0.1:8765/docs.html`

---
*Maintained by Antigravity AI • ATS Video 4K/8K UHD AI Video Engine*
