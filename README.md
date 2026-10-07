# VideoGen Studio ⚡ (4K/8K UHD AI Video Engine)

> **All-In-One Automated AI Video Engine, Neural Voiceover Studio, YouTube Thumbnail Studio & CapCut PC Integration**.  
> Generates 1080p Full HD, 4K UHD, and 8K Ultra HD YouTube landscape videos (16:9) and viral vertical Shorts (9:16) from a single script or voiceover audio file.

---

## 🌟 Core Highlights

### 1. 🧠 High-Speed AI Visual Director (Groq Primary + Gemini Fallback)
- **Groq Primary Intelligence Engine**: Powered by `qwen/qwen3.8-27b` and `llama-3.1-8b-instant`. Analyzes entire voiceovers, performs dynamic topic classification across 1,000+ niches, and synthesizes concrete physical stock video search terms in **under 2.5 seconds**.
- **Multi-Key Pool & Automatic Key Rotation**: Supports multiple Groq API keys with seamless failover across accounts if rate limits are approached.
- **Automated Gemini Fallback**: Automatically cascades to Google Gemini (`gemini-2.5-flash` / `gemini-2.0-flash`) if primary LLM is unreachable, followed by intelligent rule-based keyword mapping for guaranteed 100% operational uptime.

### 2. 🛡️ Cross-Project Anti-Repetition Engine
- **Persistent Global Registry** (`data/stock_usage_history.json`): Tracks all downloaded stock video IDs, clip URLs, and scene associations across projects.
- **Cross-Project Deduplication**: Past-used clips receive a **-75 point penalty**, while repeated clips within the same video receive an instant **-1000 point veto**.
- **Dynamic Candidate Rotation**: Dynamically rotates top-tier candidate clips across videos in the same niche, ensuring fresh, high-retention visuals every time.

### 3. 🧹 Automated Storage & Disk Cleaner
- **Smart Background Cleaner** (`backend/storage_cleaner.py`): Automatically monitors disk space and prevents gigabytes of downloaded footage from cluttering user drives.
- **Configurable Retention**: Auto-purges temporary video clips and render caches after a configurable period (default: 3 hours) or immediately after export completes.
- **Zero Drive Bloat**: Users get their finished Full HD / 4K MP4 output while raw clip caches are cleanly purged.

### 4. 🎙️ In-App Neural AI Voiceover Studio (100% Free & Unlimited)
- **100% Free Microsoft Edge-TTS Engine**: Pre-configured with 16+ ultra-realistic human neural voices with natural breathing pauses, authentic emotional inflection, and zero API costs.
  - 🌟 **Andrew V2 & Ava V2**: Ultra-natural narration with human breathing and vocal pauses.
  - 🌟 **Brian V2 & Emma V2**: Conversational YouTube tech and crisp studio storytelling.
  - 🎬 **Christopher & Guy**: Deep cinematic documentary and high-retention creator voices.
  - 🇵🇰 **Asad & Uzma**: Authentic, polished Urdu (Pakistan) male and female voices.
  - 🇮🇳 **Madhur & Swara**: Engaging, dynamic Hindi (India) male and female voices.
  - 🇬🇧 **Ryan & Sonia**: Sophisticated British documentary narration.
  - 🇦🇺 **William**: Relaxed, positive Australian voiceover.
- **🔊 1-Click Instant Voice Sample Previews**: Pre-cached audio samples for all curated voices with 0ms instantaneous playback directly in the browser.
- **💎 ElevenLabs & OpenAI Speech Integration**: Optional user API keys for ElevenLabs and OpenAI TTS (`tts-1`), backed by automatic fallback to Microsoft Neural V2 to guarantee zero downtime.

### 5. 🖼️ YouTube Thumbnail Studio (Viral & Cinematic Mystery)
- **1-Click High-CTR YouTube Thumbnails (1280×720 HD)**:
  - **Option 1: Viral High-CTR Style** (*MrBeast / Alex Hormozi Impact*): Electric yellow and white bold typography, heavy 3D drop shadows, red/gold pill badge (`100% PROVEN`), and high-urgency callouts.
  - **Option 2: Cinematic Mystery Style** (*Magnates Media / Vox Documentary*): Luxury gold border framing, glowing cyan and white typography, cold teal vignette, and category header (`• SPECIAL REPORT •`).
- **Dynamic Auto-Fit Font Scaling**: Algorithmically scales font sizes down to prevent text overflow regardless of headline length.
- **Project Frame Extraction**: Intelligently extracts high-clarity frames across video scenes with micro-timestamps and random seed keys.

### 6. 🏷️ YouTube SEO Title, Description & Tags Suite
- **5 High-CTR YouTube Titles**: Generates viral curiosity-gap titles crafted for algorithmic click-through rate.
- **Full Video Description**: Auto-generates structured description with key takeaways, chapter timestamps, and channel hashtags.
- **Optimized Video Tags**: Formats ranked comma-separated tags ready for 1-click clipboard copying.

### 7. 🎨 Multi-Tier AI Image Generator & Ken Burns MP4 Synthesis
- **Automated Fallback & Manual Generation**:
  - **Tier 1: Google Gemini 2.0 Flash (`gemini-2.0-flash-exp`)**: Official multimodal generation.
  - **Tier 2: Google Imagen 3 (`imagen-3.0-generate-002`)**: Photorealistic studio quality.
  - **Tier 3: Pollinations Flux Engine**: High-fidelity photorealistic rendering (`enhance=true`, `safe=true`, curated negative prompts).
  - **Tier 4: Pollinations Turbo**: Rapid generation fallback with zero API key requirement.
- **Ken Burns Motion Synthesis**: Automatically converts 2D AI images into dynamic 16:9 MP4 video clips with cinematic pan/zoom movement.

### 8. 🎭 Full-Screen 16:9 Video & Image Overlay Studio
- **1-Click Overlay Upload**: Upload any video or image file (`.mp4`, `.mov`, `.png`, `.jpg`, `.gif`) as an overlay layer.
- **16:9 Full Screen Fit**: Seamlessly stretches and fits over the entire 16:9 player with perfect zero-leak containment (`overflow: hidden`).
- **Custom Positioning**: 5 Presets (Top-Left, Top-Right, Bottom-Left, Bottom-Right, Center) with interactive size scale.
- **Smart Muting & Transparency**: Overlays are muted by default to preserve crystal-clear voiceover audio, with an adjustable opacity slider (default 85%).
- **Non-Destructive Layering**: Renders cleanly beneath kinetic subtitles so captions always stay 100% readable.

### 9. 🎬 4K & 8K UHD Resolution Profiles & Hardware Acceleration
- **Ultra High Definition Profiles**: Supports Full HD (1080p), 4K UHD (3840×2160), and 8K Ultra HD (7680×4320).
- **Aspect Ratio Switching**: Seamlessly toggle between 16:9 Landscape (YouTube) and 9:16 Vertical (Shorts, TikTok, Reels).
- **FFmpeg 9+ Modern Engine**: Hardware-accelerated encoding using `-fps_mode cfr` (Intel QuickSync `h264_qsv`, NVIDIA NVENC `h264_nvenc`, AMD AMF `h264_amf`).

### 10. 💬 CapCut Kinetic Subtitles & Interactive Positioning
- **12 Viral Typography Presets**: CapCut Yellow, Hormozi Green, Neon Cyber, Red Fire, Clean Minimal, MrBeast Punch, Ali Abdaal, Iman Gadzhi, TikTok Glow, Podcast Box, Streamer Lime, Dark Stoic.
- **Mouse Drag-to-Positioning**: Drag subtitles directly on the video player to adjust vertical position in real time.
- **1-Click Subtitle Toggle**: Easily toggle captions on/off for video-only exports.

### 11. ✂️ CapCut PC Timeline Draft Integration
- **Native Desktop Project Generation**: Exports video cuts, voiceover timeline, and kinetic caption tracks directly into `%LOCALAPPDATA%\CapCut\User Data\Projects\com.lveditor.draft\`.
- **Auto-Launch**: Automatically opens the generated project inside CapCut PC for final polish.

### 12. 🧬 Free Voice Cloning (Zero API Cost)
- **Kokoro-82M Engine**: Apache 2.0 licensed, CPU-friendly (~200MB model), fully local inference.
- **21 Voice Presets**: American English and British English male/female voices.
- **Auto-Download & Fallback**: Model auto-downloads on first use; automatically falls back to Edge-TTS if absent.

### 13. ⚡ High-Stability Audio/Video Engine & Dynamic Multi-Core Scaling
- **🔒 Audio-Video Lipsync Lock (`aresample=async=1000`)**: Frame-locks voiceover, BGM, and SFX across 15–30+ minute long-form renders with microsecond precision, preventing audio drift across hundreds of stitched clips.
- **⚡ Dynamic Multi-Core Trimming Concurrency**: Trimming throughput auto-scales with CPU cores (`min(6, max(2, cpu_count // 2))`), upgrading from a static 2-process throttle to 4–6 parallel FFmpeg processes.
- **🛡️ Groq 429 Resilience & Hot-Reload**: Automatically applies exponential backoff retry on Groq rate limits while dynamically reloading updated API keys directly from `settings.json` without requiring a server restart. Eliminates dummy fallback quotes.
- **🧹 Buffer Overflow Safety & Clean Containers**: Configures `-max_muxing_queue_size 1024` on all complex audio-video interleaves and strips drone/action-cam telemetry data tracks (`-dn`) alongside audio (`-an`).

---

## 🚀 Quick Start

### 1. Run Python Source Code
Double-click:
```cmd
1_RUN_APP_Python_Source.bat
```
*(or run `python desktop_launcher.py` in terminal)*.

The app automatically starts on:
```
http://127.0.0.1:8765/
```

### 2. Run Standalone Executable (No Python Required)
Double-click:
```cmd
2_RUN_APP_Standalone_EXE.bat
```

### 3. Build Standalone Portable Executable & ZIP
Double-click:
```cmd
3_BUILD_NEW_Standalone_EXE.bat
```
This packages the entire application into `dist/VideoGenStudio/VideoGenStudio.exe` and `dist/VideoGenStudio-Windows-Portable.zip`.

---

## 🔑 Active API Keys & Configurations

All API keys are configured and stored persistently in [`data/settings.json`](file:///c:/Users/Abid/Desktop/vg/data/settings.json):

| Service | Primary Key | Role | Model / Endpoint |
|---|---|---|---|
| **Groq Cloud** | `gsk_9xOBIdq5...` (Pool: 3 Keys) | **PRIMARY** LLM Visual Director & Whisper Speech-to-Text | `qwen/qwen3.8-27b`, `whisper-large-v3` |
| **Pexels** | `ibxqJm3ADs...` (Pool: 2 Keys) | 1080p Landscape Stock Video Footage | `https://api.pexels.com/videos/search` |
| **Pixabay** | `57580975-a6f...` | HD & 4K Stock Video Footage | `https://pixabay.com/api/videos/` |
| **Google Gemini** | `AQ.Ab8RN6IV...` (Pool: 2 Keys) | Automated Fallback LLM & Image Synthesis | `gemini-2.5-flash`, `gemini-2.0-flash-exp` |

---

## 📁 Repository Structure

```
VideoGen-Studio/
├── 1_RUN_APP_Python_Source.bat       # 1-Click launcher for Python source code
├── 2_RUN_APP_Standalone_EXE.bat       # 1-Click launcher for compiled executable
├── 3_BUILD_NEW_Standalone_EXE.bat     # PyInstaller standalone executable compiler
├── desktop_launcher.py               # Desktop app launcher with Edge App mode & port cleanup
├── main.py                           # Root application entrypoint
├── requirements.txt                  # Python dependencies (FastAPI, Edge-TTS, Kokoro, Pillow)
├── README.md                         # Complete project documentation
│
├── backend/                          # Core Python engine modules
│   ├── server.py                     # FastAPI endpoints, WebSocket progress & file serving
│   ├── scene_analyzer.py             # Groq Primary LLM + Gemini Fallback scene analyzer
│   ├── stock_downloader.py           # Multi-worker Pexels/Pixabay downloader + Anti-repetition registry
│   ├── storage_cleaner.py            # Automated disk space monitor & cache auto-purging
│   ├── image_generator.py            # Gemini 2.0 & Pollinations Flux 16:9 AI Image & Ken Burns engine
│   ├── video_renderer.py             # FFmpeg modern CFR normalization & audio-video compositor
│   ├── video_overlay.py              # Full-screen 16:9 video/image overlay manager
│   ├── voice_cloner.py               # Free voice cloning via Kokoro-82M
│   ├── subtitle_generator.py         # ASS kinetic subtitles & callout badge generator
│   ├── thumbnail_generator.py        # YouTube Thumbnail Studio (Viral Punch & Cinematic Mystery)
│   ├── seo_generator.py              # Groq Primary YouTube SEO Suite (5 Titles, Description, Tags)
│   ├── tts_generator.py              # Edge-TTS Neural, ElevenLabs, OpenAI voice engines
│   ├── transcriber.py                # Groq Whisper speech-to-text with word micro-timestamps
│   ├── capcut_exporter.py            # Native CapCut desktop draft project generator
│   ├── templates.py                  # Master templates, pools & variant resolution
│   └── config.py                     # Global settings, paths, multi-key pools & defaults
│
├── frontend/                         # Glassmorphic Obsidian Web application
│   ├── index.html                    # Studio, Preview, Thumbnail, Projects & Settings modals
│   ├── styles.css                    # Dark mode UI, Ken Burns animations, responsive styles
│   ├── app.js                        # Frontend controllers & event handlers
│   ├── caption_engine.js             # Word-level kinetic subtitle animator & drag positioning
│   ├── docs.html                     # Built-in User Guide & operational manual
│   └── favicon.ico / png             # Application icon & brand badge
│
├── bin/                              # Bundled system binaries
│   ├── ffmpeg.exe                    # Hardware-accelerated FFmpeg binary
│   └── ffprobe.exe                   # Media analysis binary
│
├── data/                             # Persistent application data
│   ├── assets/bgm/                   # Background music loops (ambient, lofi, focus)
│   ├── assets/overlays/              # Uploaded video/image overlays
│   ├── output/                       # Rendered 1080p/4K MP4 videos
│   ├── thumbnails/                   # Generated YouTube thumbnail JPEGs
│   ├── seo/                          # Generated YouTube SEO metadata JSON
│   ├── sfx/                          # Sound effects & voice preview MP3s
│   ├── fonts/                        # Subtitle typography fonts
│   ├── settings.json                 # Persistent active API keys & preferences
│   └── stock_usage_history.json      # Cross-project anti-repetition registry
│
├── CleanTool/                        # Pristine, zero-clutter distribution copy
│   ├── Run_VideoGen_Studio.bat       # 1-Click execution script
│   ├── Build_Standalone_EXE.bat      # 1-Click standalone executable builder
│   └── README.txt                    # Single plain-text quick reference
│
└── extra/                            # Blueprints, specifications & API documentation
    ├── api.md                        # Active API keys registry & endpoints
    ├── BRAIN.md                      # Complete architectural memory & session logs
    ├── VIDEOGEN_MASTER_BLUEPRINT.md  # Master technical and operational blueprint
    └── CLAUDE_TODAY.md               # Daily engineering briefing & challenge documentation
```

---

## 📜 Interactive Documentation
Access the comprehensive user guide by clicking **📖 Docs** in the top navigation header inside the app or visiting:
`http://127.0.0.1:8765/docs.html`

---
*Maintained by Antigravity AI • VideoGen Studio 4K/8K UHD AI Video Engine*
