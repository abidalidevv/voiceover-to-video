# 🧠 VideoGen Studio — Master Project Brain & Knowledge Repository

> **Project Mission**: Completely automated, production-grade 1080p Full HD (16:9 Landscape) YouTube video generator designed for content creators, faceless YouTube automation channels, and video editors. Takes a **single Voiceover Audio file + Niche**, transcribes micro-timestamps, contextually selects cinematic B-roll via an AI visual director, downloads stock footage across parallel multi-worker threads, burns CapCut-style kinetic typography subtitles, and exports directly into **CapCut PC** as an editable timeline project.

---

## 📑 Table of Contents
1. [Chronological Conversation & Requirements History](#1-chronological-conversation--requirements-history)
2. [High-Level Architecture & Pipeline Workflow](#2-high-level-architecture--pipeline-workflow)
3. [Project Directory & Core Modules Map](#3-project-directory--core-modules-map)
4. [CapCut PC Draft Timeline Integration Protocol](#4-capcut-pc-draft-timeline-integration-protocol)
5. [Kinetic Subtitles, Typography & 12 Viral Presets](#5-kinetic-subtitles-typography--12-viral-presets)
6. [10+ Stock Video Providers & Free API Registry](#6-10-stock-video-providers--free-api-registry)
7. [GPU & CPU Hardware Concurrency Tuning Guide](#7-gpu--cpu-hardware-concurrency-tuning-guide)
8. [Backend API Reference & Route Matrix](#8-backend-api-reference--route-matrix)
9. [Operational Guide & Troubleshooting](#9-operational-guide--troubleshooting)

---

## 1. Chronological Conversation & Requirements History

### Phase 1: Core Foundation & Requirements Alignment
- **User Prompt**: The user requested a desktop web tool to generate full HD (16:9) YouTube videos automatically using stock footage based on a single Voiceover input and a selected Niche. The tool needed to handle kinetic CapCut-style animated subtitles, multi-worker parallel downloads, and ultra-fast video rendering.
- **Architectural Decision**: Selected a lightweight, blazingly fast stack: **FastAPI + Uvicorn** backend with **Whisper AI** for word timestamps, asynchronous **Pexels/Pixabay** connection-pooled querying, **FFmpeg** for hardware-accelerated video rendering, and a glassmorphic **Vanilla JS/CSS** frontend.

### Phase 2: Bug Fixes & UX Optimization
- **Issues Reported**:
  - Preview was oversized and required scrolling.
  - Subtitle font appeared blurry with broken letter outlines.
  - Worker download progress was not visible to the user.
- **Solutions Implemented**:
  - Built a compact fixed-height 16:9 viewport with CSS aspect-ratio containment.
  - Re-engineered font rendering with distinct `-webkit-text-stroke` and `paint-order: stroke fill` to prevent double-stroking.
  - Created a real-time progress modal with scene-by-scene counter and dynamic progress bar.

### Phase 3: High-Speed Parallel Rendering & CapCut PC Draft Export
- **User Prompt**: 
  - "Some buttons not working like open output folder"
  - "I want to make it fast, download videos from multiple resources, multiple threads at a time and merge video in segments"
  - "Can I add letter spacing and word spacing in caption settings?"
  - "Can I add an option or button of CapCut if I click that it will open same project in CapCut exe as template in timelines?"
- **Solutions Implemented**:
  - Replaced non-native shell calls with Windows-native `os.startfile(target_path)`.
  - Upgraded video renderer to a **Parallel Segmented Pipeline**: 8 workers normalize clips to 1080p 30fps `.ts` files in parallel, followed by a **0.5-second lossless concat demuxer** (`-f concat -c copy`) and single-pass ASS subtitle burn. (22s 1080p video rendered in **24.5s**).
  - Added real-time **Letter Spacing** (`-2px` to `16px`) and **Word Spacing** (`0px` to `30px`) sliders in UI and mapped to ASS parameter 14.
  - Built `backend/capcut_exporter.py` generating standard `draft_content.json` and `draft_meta_info.json` directly into `%LOCALAPPDATA%\CapCut\User Data\Projects\com.lveditor.draft\`. Pre-arranges Video, Audio, and Text tracks.

### Phase 4: Expanded Presets, 10+ Stock Video APIs, GPU Tuner & Documentation
- **User Prompt**:
  - "Preset Style Templates or dal skty ho? mazeed templete or mazeed fonts dalny hain popular waly"
  - "bg worker 6 hain i think, inki tadad main GPU power ko dekh kr manually change kr sku setting sa"
  - "is main APIS or add kro stock videos k lye, main at least 10 apis dunga tum fields bnao jo stock videos wali website totally free main api provide krti ho"
  - "ik brain md file bnao us main sb chat, imp data or brain data save kro sb usk andr"
- **Solutions Implemented**:
  - Added 7 new viral presets (MrBeast, Ali Abdaal, Iman Gadzhi, TikTok Violet, Vox Podcast Box, Streamer Lime, Stoic Slate) and 7 popular Google Fonts (Anton, Archivo Black, Bangers, Cinzel, Luckiest Guy, Outfit, Poppins).
  - Upgraded worker slider to **2–32 threads** with dynamic GPU/CPU performance profiles.
  - Built 10+ Stock Video API configuration cards covering Pexels, Pixabay, Coverr, Videvo, NASA Open Media, Wikimedia Commons, Mixkit, Freepik, RapidAPI, and Custom Webhook.
  - Authored this master `BRAIN.md` file and the user-facing `frontend/docs.html`.

### Phase 5: Studio Pro Redesign, Micro-Animations & Button Standardization
- **User Prompt**:
  - "is main animations lgao"
  - "buttons ki height same kro text arrange kro"
  - "baki blusish ai feel dy rha h"
  - "Viewablity of text ko thk kro white krdo"
  - "isy professional bnao"
- **Solutions Implemented**:
  - **Aesthetic Overhaul**: Eliminated electric/neon cyan backdrops in favor of a sleek **Obsidian Dark Theme** (`#0c0e12`, `#13171f`, `#1b202a`), mirroring professional editing suites like DaVinci Resolve and Adobe Premiere Pro.
  - **Text Readability & Contrast**: Elevated all titles, labels, card headers, slider values, and status badges to **pure white (`#ffffff`)** and crisp silver (`#f1f5f9` / `#cbd5e1`), eliminating dark/muddy text completely.
  - **Strict Button Height Standardization**: Defined universal pixel-exact heights:
    - Standard action buttons: `38px`
    - Small buttons / Header buttons / Card actions: `34px`
    - Header utility buttons & workers pill: `36px`
    - Large primary export buttons: `46px`
    - Extra small badge buttons / Swap buttons: `28px`
    - Applied `display: inline-flex; align-items: center; justify-content: center; line-height: 1;` for 100% vertical and horizontal alignment across all browser viewports.
  - **Interactive Micro-Animations**:
    - Smooth tab transitions with `@keyframes tabFadeIn`
    - Spring-like modal entrance with `@keyframes modalPop`
    - Subtle pulsing glow ripple on the active worker indicator with `@keyframes pulseGlow`
    - Active click scale feedback (`transform: scale(0.97)`) on all interactive buttons
    - Card hover elevation (`transform: translateY(-2px) / translateY(-3px)`) with diffused shadows.

### Phase 6: Expanded Niche Suite (22 Categories) & 100vh Caption Customizer
- **User Prompt**:
  - "niches or add kro"
  - "🎨 CapCut Caption Customizer is panel ki height 100vh krdo"
- **Solutions Implemented**:
  - **Expanded Niches Catalogue (22 Categories)**:
    - Added 14 high-volume viral YouTube niches to `backend/scene_analyzer.py`, `backend/transcriber.py`, and `frontend/index.html`:
      1. 🛸 *Sci-Fi & Space* (Galaxies, Astrophotography, NASA footage)
      2. 🕵️ *Crime & Mystery* (Dark Noir, Investigations, True Crime suspense)
      3. 🧘 *Meditation & Lofi* (Zen garden, Rain on window, Chill ambient)
      4. 🧠 *Brain & Human Facts* (Mind science, Optical illusions, Psychology)
      5. 📜 *History & Empires* (Ancient Rome, Pyramids, Medieval castles)
      6. 🚀 *Business & Hustle* (Startups, Pitching, Executive leadership)
      7. 🚗 *Automotive & Supercars* (F1, Drift, Hypercars, Mechanical engines)
      8. 🎮 *Gaming & Esports* (RGB battlestations, Tournaments, High-voltage streamers)
      9. ✈️ *Travel & Adventure* (Swiss Alps, Tropical beaches, World exploration)
      10. 🧪 *Science & Engineering* (Chemistry labs, Robotics, Quantum physics)
      11. 💡 *Productivity & Self-Growth* (Deep work, Morning routines, Desk setups)
      12. 👻 *Horror & Paranormal* (Creepy forests, Abandoned structures, Eerie shadows)
      13. 🍲 *Food & Culinary* (Artisanal coffee, Gourmet steaks, Kitchen craft)
      14. 🦁 *Wildlife Predators & Oceans* (Savannah lions, Sharks, Coral reefs)
      15. Plus existing 8 core niches (*Motivation Psychology, Nature & Wildlife, Tech & AI, Finance & Wealth, Luxury & Lifestyle, Fitness & Health, Stoicism & Philosophy, General Inspiring*).
  - **100vh CapCut Caption Customizer & Sticky Footer**:
    - Reconfigured `.caption-inspector` with `height: 100vh; max-height: calc(100vh - 88px);` spanning the entire vertical viewport.
    - Added `position: sticky; bottom: -18px;` with subtle shadow to `.inspector-footer`, keeping the `#export-render-btn` and `#export-capcut-btn` always visible and instantly clickable while scrolling through presets and typography settings.

### Phase 7: UI Aesthetic Restoration & Compact Balanced Layout
- **User Prompt**:
  - "ye tum ny wide kr dya hy . phly thk lgta tha"
  - "or ye ui mjhy kuch acha nahi lhg rha phly wala thk tha bs kuch ui thk krna tha modern ui"
- **Solutions Implemented**:
  - **Balanced Container Width**: Fixed the over-stretched `1540px` width back to a compact, comfortable, and centered **`max-width: 1280px`**.
  - **Restored Cyber-Dark Theme**: Restored the beloved deep rich surfaces (`#0a0d14` background, `#111726` glass cards), vibrant electric cyan accents (`#00f0ff`), and gradient brand logo.
  - **Crisp White Text Readability**: Ensured 100% text readability with pure `#ffffff` titles/labels and silver `#e2e8f0` descriptions.
  - **Standardized Button Heights**: Universal pixel-exact button heights with centered text alignment and active click scale feedback.

---

## 2. High-Level Architecture & Pipeline Workflow

```
[Voiceover Audio (.mp3/.wav)] + [Target Niche]
                     │
                     ▼
      [1. Whisper Micro-Transcription]
      (Word-level & sentence timestamps)
                     │
                     ▼
       [2. Semantic Scene Analyzer]
       (Contextual tags matching sentence emotion)
                     │
                     ▼
   [3. Multi-Worker Stock Downloader (2-32 Threads)]
   ├── Pexels API (1080p Landscape)
   ├── Pixabay API (HD/4K)
   ├── Coverr / Videvo APIs
   ├── NASA & Wikimedia Open Media
   └── Custom Webhook / Fallback Engine
                     │
                     ▼
      [4. Interactive Preview & Studio]
      ├── 16:9 Video Player Overlay
      ├── Real-Time Kinetic Subtitles (12 Presets)
      └── Scene Clip Swapper (8 alternatives)
                     │
        ┌────────────┴────────────┐
        ▼                         ▼
 [5A. Fast Render Pipeline]   [5B. CapCut PC Draft Exporter]
 ├── Parallel .ts normalize   ├── draft_content.json (Tracks)
 ├── 0.5s Stream Copy Concat  ├── draft_meta_info.json
 └── Single-Pass ASS Burn     └── Auto-launches CapCut.exe
        │                         │
        ▼                         ▼
[Final 1080p MP4 Video]     [CapCut Timeline Project]
```

---

## 3. Project Directory & Core Modules Map

```
c:\Users\Abid\Desktop\vg\
├── 1_RUN_APP_Python_Source.bat       # 1-Click launcher for Python source code
├── 2_RUN_APP_Standalone_EXE.bat       # 1-Click launcher for compiled executable
├── 3_BUILD_NEW_Standalone_EXE.bat     # PyInstaller standalone executable compiler
├── desktop_launcher.py               # Desktop app launcher with Edge App mode & port management
├── main.py                           # Root application entrypoint
├── package.json                      # Desktop shell package configuration
├── requirements.txt                  # Python dependencies
├── README.md                         # Clean master user documentation
│
├── backend\
│   ├── __init__.py
│   ├── config.py             # Global constants, paths, default settings, ffmpeg detector
│   ├── server.py             # FastAPI server with all endpoints, WebSocket & background jobs
│   ├── transcriber.py        # Groq/OpenAI Whisper audio transcription & word timestamps
│   ├── scene_analyzer.py     # Gemini Flash + Groq LLM scene analyzer & 80+ keyword map
│   ├── stock_downloader.py   # Multi-provider concurrent download engine & clash scoring
│   ├── image_generator.py    # Gemini 2.0 & Pollinations Flux 16:9 AI Image & Ken Burns engine
│   ├── video_renderer.py     # Parallel segmented normalization & lossless concat render pipeline
│   ├── video_overlay.py      # Video & image overlay engine (16:9 full-fit, watermark, opacity)
│   ├── voice_cloner.py       # Free voice cloning via Kokoro-82M (Apache 2.0, CPU)
│   ├── subtitle_generator.py # Advanced ASS subtitle engine with 12 kinetic styles & kerning
│   ├── thumbnail_generator.py# YouTube Thumbnail Studio (Viral Punch & Cinematic Mystery)
│   ├── seo_generator.py      # AI YouTube SEO Suite (5 Titles, Description, Timestamps, Tags)
│   ├── tts_generator.py      # Edge-TTS Neural, ElevenLabs, OpenAI, Kokoro voice engines
│   ├── capcut_exporter.py    # Native CapCut PC draft JSON builder & timeline organizer
│   └── templates.py          # Master templates, pools & variant resolution
│
├── frontend\
│   ├── index.html            # Main Studio, Preview, Thumbnail, Projects, Settings UI
│   ├── styles.css            # Dark glassmorphic design system & micro-animations
│   ├── app.js                # Core frontend controller & API client
│   ├── caption_engine.js     # Real-time player caption renderer with kinetic animations
│   ├── docs.html             # Rich User Guide & Documentation manual
│   └── favicon.ico / png     # Application icon & brand badge
│
├── bin\
│   ├── ffmpeg.exe            # Bundled hardware-accelerated FFmpeg binary
│   └── ffprobe.exe           # Bundled media analysis binary
│
├── data\
│   ├── assets\bgm\           # Background music loops (ambient, lofi, focus)
│   ├── assets\overlays\      # Uploaded video/image overlays
│   ├── models\               # Kokoro-82M voice cloning model cache
│   ├── voice_samples\        # User voice reference audio samples
│   ├── output\               # Exported full HD 1080p/4K MP4 videos
│   ├── thumbnails\           # Auto-generated YouTube clickbait thumbnail JPEGs
│   ├── seo\                  # Generated YouTube titles, descriptions, and tags JSON
│   ├── sfx\                  # Sound effects & pre-cached voice preview MP3s
│   ├── settings.json         # Persisted user API keys and performance settings
│   └── projects_history.json # Project library metadata & history
│
├── electron\
│   └── main.js               # Electron window lifecycle manager
│
└── extra\                    # Archived blueprints, dev scratch, tests & specifications
    ├── BRAIN.md              # This master architectural brain & chronological memory
    ├── VIDEOGEN_MASTER_BLUEPRINT.md  # Master technical and operational blueprint
    ├── VIDEOGEN_MASTER_BUILD_DOCUMENT.md # Original build specifications and ground rules
    ├── NEW_AVATAR_VIDEO_ENGINE_PLAN.md # Future Avatar Storyteller engine specifications
    ├── CLAUDE_REVIEW.md      # Technical audit & post-mortem review
    ├── detail.md             # Initial research notes & API keys documentation
    ├── package_release.py    # Automated portable release packager
    ├── test_scripts\         # Automated verification test suite
    └── scratch_dev\          # Temporary developer scratch scripts
```

---

## 4. CapCut PC Draft Timeline Integration Protocol

### Draft Location on Windows:
```
%LOCALAPPDATA%\CapCut\User Data\Projects\com.lveditor.draft\<Project_Name>\
```

### Essential Draft Files:
1. `draft_content.json`: Defines the timeline hierarchy, materials (videos, audios, texts), and multi-track arrangement.
2. `draft_meta_info.json`: Contains project title, duration, aspect ratio (`16:9`), and cover image.

### Microsecond Precision Math:
CapCut internal timeline uses **microseconds** ($1 \text{ second} = 1,000,000 \mu s$):
$$\text{Offset}_{\mu s} = \text{round}(\text{timestamp}_{\text{seconds}} \times 1,000,000)$$

### Multi-Track Hierarchy:
- **Track 1 (Video):** Sequential B-roll video clips. Each clip has its audio volume set to `0.0` to avoid clashing with the narrator.
- **Track 2 (Audio):** Spoken voiceover audio file placed from offset `0.0s`.
- **Track 3 (Text/Subtitles):** Kinetic subtitle cues with font family, colors, and outline strokes synchronized with spoken words.

---

## 5. Kinetic Subtitles, Typography & 12 Viral Presets

### Subtitle Kerning & Spacing Formula (ASS Specification):
- **Letter Spacing:** Configured via ASS Header Style attribute `Spacing` (parameter 14).
  $$\text{ASS Spacing} = \text{round}(\text{LetterSpacing}_{\text{px}} \times 2)$$
- **Word Spacing:** Configured by calculating space characters between tokens:
  $$\text{Trailing Space} = \text{max}(1, \text{round}(\text{WordSpacing}_{\text{px}} / 6))$$

### 12 Viral Preset Style Catalogue:

| Preset Key | Display Name | Font Family | Primary Color | Highlight Word Color | Outline Width | Mood / Style |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `capcut_yellow` | CapCut Viral | Montserrat | `#FFFFFF` | `#FFE010` (Warm Gold) | 4px Black | Standard viral YouTube style |
| `hormozi_green` | Hormozi Punch | Impact | `#FFFFFF` | `#39FF14` (Neon Green) | 4.5px Black | High-energy business & motivation |
| `mrbeast_punch` | MrBeast Gold | Bangers | `#FFE010` | `#FF3333` (Punch Red) | 5.5px Black | Comic punchy retention style |
| `ali_abdaal` | Ali Abdaal | Poppins | `#FFFFFF` | `#FFA94D` (Amber Orange) | 2.5px Dark | Aesthetic productivity & study |
| `iman_gadzhi` | Luxury | Cinzel | `#F4EFEA` | `#D4AF37` (Champagne Gold) | 3.5px Black | High-ticket agency & wealth |
| `tiktok_violet` | TikTok Glow | Archivo Black | `#FF2A85` | `#BD00FF` (Electric Violet) | 4.5px Black | Viral TikTok & Shorts aesthetic |
| `podcast_pill` | Podcast Box | Outfit | `#FFFFFF` | `#FFE600` (Sharp Yellow) | 3px Pill Box | Vox / Lex Fridman podcast style |
| `streamer_lime` | Streamer | Luckiest Guy | `#A6FF00` | `#00F0FF` (Electric Cyan) | 5px Black | Gaming, streaming & reaction |
| `neon_cyber` | Neon Cyber | Montserrat | `#FFFFFF` | `#00F0FF` (Electric Cyan) | 3.5px Navy | Tech, crypto, future & AI |
| `red_fire` | Red Fire | Trebuchet MS | `#FFFFFF` | `#FF3333` (Punch Red) | 4px Black | Urgent warnings & breaking news |
| `dark_stoic` | Stoic Slate | Oswald | `#FFFFFF` | `#818CF8` (Slate Indigo) | 4px Dark | Stoicism, philosophy & deep thought |
| `clean_minimal` | Clean Minimal | Inter | `#FFFFFF` | `#E0E0E0` (Soft Gray) | 2px Slate | Documentary, corporate & education |

---

## 6. 10+ Stock Video Providers & Free API Registry

| # | Provider | Free Tier / Limits | Search URL / Endpoint | Integration Status |
| :--- | :--- | :--- | :--- | :--- |
| 1 | **Pexels Video API** | 20,000 req/month (100% Free) | `https://api.pexels.com/videos/search` | Direct Native Integration |
| 2 | **Pixabay Video API** | Unlimited (100% Free) | `https://pixabay.com/api/videos/` | Direct Native Integration |
| 3 | **Coverr Video** | Commercial Free B-Roll | `https://api.coverr.co/videos` | Direct Native Integration |
| 4 | **Videvo Stock** | Free HD Stock Footage | `https://api.videvo.net/v1/videos` | Direct Native Integration |
| 5 | **NASA Open Media** | 100% Free Public Domain | `https://images-api.nasa.gov/search` | Direct Native Integration |
| 6 | **Wikimedia Commons** | 100% Free Open Access | `https://commons.wikimedia.org/w/api.php` | Direct Native Integration |
| 7 | **Mixkit Video** | Free Envato B-Roll | `https://mixkit.co` | Native Web Adapter |
| 8 | **Freepik / Storyblocks** | Subscription / Key | `https://www.freepik.com/api` | API Key Field Ready |
| 9 | **RapidAPI Stock Hub** | Universal Stock API | `https://rapidapi.com` | API Header Key Ready |
| 10 | **Custom Webhook** | Private Proxy / Custom API | Custom URL | POST Webhook Dispatcher |
| 11 | **Groq Whisper AI** | 100% Free Speech (1.5s) | `https://api.groq.com/openai/v1` | Primary High-Speed Transcriber |
| 12 | **OpenAI Whisper** | Pay-as-you-go | `https://api.openai.com/v1` | Secondary Fallback Engine |

### Phase 7: Responsive Viewport Breakpoints & Mouse-Drag Subtitle Positioning
- **User Prompt**:
  - "tool responsive nhi h full screen pr ok hy, screen size chot kro tu mza ni ata"
  - "video player main caption ki position change krny k lye main mouse ssy location set krna chhta hu"
- **Solutions Implemented**:
  - **Responsive CSS Layout Engine**: Implemented fluid breakpoints (`1100px`, `1024px`, `768px`, `480px`) with compact headers, wrapping studio action grids, and flexible video player scaling.
  - **Interactive Drag-to-Position Subtitles**: Enabled mouse drag functionality directly on the video player overlay. Dragging updates vertical position in real time and automatically synchronizes with the vertical margin slider.

### Phase 8: 9:16 Shorts Mode, 4K/8K UHD Profiles & Dual BGM/SFX Engine
- **User Prompt**:
  - "stock videos 1080p mostly, there should be an option 4k or 8k"
  - "kya background music ko user khud say upload ni kr skta"
  - "Scene Transitions & Auto SFX (Sound Effects - Whooshes & Pops)"
- **Solutions Implemented**:
  - **4K & 8K UHD Profiles**: Added UHD resolution targeting across stock video downloads and FFmpeg encoding.
  - **Custom BGM Upload**: Added 1-click custom background music file upload (`/api/upload-bgm`) with automatic loop detection and volume ducking under speech.
  - **Scene Transition SFX Suite**: Integrated royalty-free transition sound stings (Cinematic Whoosh, Punchy Pop, Modern Shutter, Ding Bell) with volume sliders and FFmpeg `adelay` time-alignment.

### Phase 9: In-App Neural AI Voiceover Generator & 1-Click Voice Previews
- **User Prompt**:
  - "In-App AI Voiceover Generator (Text to Speech - Free)"
  - "voice suno kesy jis k gnerste kr rha hu uska ancent tu suno 1 1 line sb ki sunu sample phr hu genertekruga"
  - "totally freee api, free main real humen ki trah voice or kon kon dyta hy wo b lga do"
- **Solutions Implemented**:
  - **100% Free Edge-TTS V2 Multilingual Neural Voices**: Pre-configured 16+ ultra-natural human voices (Andrew V2, Ava V2, Brian V2, Emma V2, Christopher, Guy, Jenny, Ryan, Sonia, William, Asad/Uzma Urdu, Madhur/Swara Hindi) with natural breathing pauses and realistic human intonation.
  - **1-Click Live Audio Voice Previews**: Pre-cached 3-second natural audio sample MP3s in `data/sfx/tts_samples/`. Clicking `🔊 Listen Sample` plays the voice sample with 0ms delay.
  - **ElevenLabs Free Tier & OpenAI Speech Integration**: Added fields in Settings for optional user keys with zero-interruption auto-fallback to Microsoft Neural V2 if keys are empty.

### Phase 10: YouTube Thumbnail Studio, YouTube SEO Suite & ATS Video Rebranding
- **User Prompt**:
  - "there should be an extra page for Thumbnail"
  - "AI SEO Title, Description & Tags Generator"
  - "header fix kro us main itna bra logo h usy krdo ATS Video, ncy sologan 4K/8K UHD Engine"
  - "generate a test thumbnail of last rendered project"
- **Solutions Implemented**:
  - **ATS Video Branding**: Renamed application to **ATS Video**, slogan **4K/8K UHD Engine**, with sleek nano gradient badge. Compact nav buttons with emojis (`🎙️ Studio`, `🎬 Preview`, `🖼️ Thumbnail`, `📁 Projects`, `⚙️ Settings`, `⚡ 8 Workers`, `📖 Docs`, `📂 Outputs`).
  - **YouTube Thumbnail Studio (`/api/generate-thumbnails`)**: Generates 2 high-CTR 1280×720 thumbnails from video frames:
    1. *Viral High-CTR Style*: Bold drop shadow, electric yellow and white typography, red/gold pill badge.
    2. *Cinematic Mystery Style*: Luxury gold framing, cyan and white typography, cold teal vignette.
    - Added `_fit_font()` dynamic font auto-scaling to prevent text overflow.
  - **YouTube SEO Suite (`/api/generate-seo`)**: Automatically analyzes video script and scenes to output 5 high-CTR titles, structured description with chapters, and ranked comma-separated tags with 1-click clipboard copying.

### Phase 11: Background Overlay Video Studio & 16:9 Screen Fit
- **User Prompt**:
  - "bg overlay video lgai h wo isi video pr show honi chahye 16:9 fiully fit to this generated video with default perfect opacity, rest user will update it , overlay video by default muted . its currently showing at top center and some part of it outside of video player too"
- **Solutions Implemented**:
  - **16:9 Full Screen Fit**: Added full-screen fit option to `backend/video_overlay.py` and `frontend/app.js`. Overlay video/image stretches and covers the entire 16:9 player with zero leak-out via `.video-viewport { overflow: hidden; }`.
  - **Default Opacity & Muting**: Set default overlay opacity to 85% with an interactive slider (5% to 100%). Overlay audio is muted by default so it never interferes with the narrator's voiceover.
  - **Non-Destructive Layering**: Positioned overlay layer below kinetic subtitles (`z-index: 5`) so subtitles (`z-index: 10`) always remain crystal-clear and legible.

### Phase 12: Gemini 2.0 Flash & Pollinations Flux Multi-Tier AI Image Generator
- **User Prompt**:
  - "lkin grmini say image generate nahi hota .. images sai ni generate hoti aeeb c ati hain"
- **Solutions Implemented**:
  - **Decommissioned Invalid Model Names**: Removed non-existent names (`gemini-2.5-flash-image`, `nano-banana-pro-preview`) that caused API errors.
  - **Native Gemini 2.0 Flash Integration**: Configured `gemini-2.0-flash-exp` with correct `responseModalities: ["IMAGE"]` using official Google Generative Language endpoints.
  - **Imagen 3 Fallback**: Tier 2 fallback to `imagen-3.0-generate-002`.
  - **Enhanced Pollinations Flux Engine**: Tier 3 fallback with photorealistic parameters (`enhance=true`, `safe=true`, and curated negative prompts against low-quality artifacts).
  - **Niche-Aware Prompt Enrichment**:
    - *Motivation*: Golden hour backlight silhouettes, dramatic atmospheric sky.
    - *Finance & Luxury*: Rich dark tones, luxury high-rises, gold reflections, clean studio depth.
    - *Tech & AI*: Cyberpunk neon, clean laboratory macro, holographic server glows.
    - *Nature*: National Geographic 8K macro lens, golden hour aerial vista.
  - **Ken Burns Motion Synthesis**: Generates 16:9 pan/zoom MP4 clips directly from synthesized AI images.

### Phase 13: Repository Cleanup, Documentation & Test Verification
- **User Prompt**:
  - "push krdo , is kk bad hum file main sytax error thk krain gy... or itni sari files hain root main 26 files hain , actual tool ki files or folder kon c hain . Extra file kon c hain usy extra main dal do test fole test folder main dal do"
  - "md files upate kro, documents bi"
- **Solutions Implemented**:
  - **Clean Root Architecture**: Retained only production launchers (`1_RUN_APP_Python_Source.bat`, `2_RUN_APP_Standalone_EXE.bat`, `3_BUILD_NEW_Standalone_EXE.bat`), core entrypoint (`main.py`), desktop launcher, `package.json`, and `requirements.txt`.
  - **Organized `extra/` Directory**: Moved all development scratch, test scripts (`extra/test_scripts/`), internal notes, blueprints, and packaging scripts into `extra/`.
  - **Automated Verification**: Ran all 7 smoke tests (`test_transcriber`, `test_scene_analyzer`, `test_stock_downloader`, `test_subtitle_generator`, `test_capcut_exporter`, `test_video_renderer`, `test_api_endpoints`) with 100% pass rate.
  - **Updated All Master Documents**: Synchronized `README.md`, `extra/BRAIN.md`, `extra/VIDEOGEN_MASTER_BLUEPRINT.md`, `extra/VIDEOGEN_MASTER_BUILD_DOCUMENT.md`, and in-app `frontend/docs.html`.

---

## 7. GPU & CPU Hardware Concurrency Tuning Guide

The Settings tab features a **2 to 32 worker slider** with dynamic profile detection:

### Worker Power Allocation Matrix:
- **2 to 4 Workers (Low CPU / Dual-Core):** Designed for Dual/Quad Core CPUs. Prevents system slowdown.
- **5 to 8 Workers (Standard Multi-Core - Default):** Designed for 6–8 Core CPUs and GTX 1650 / RTX 3050 GPUs.
- **9 to 16 Workers (High-Performance GPU):** Designed for 8–16 Core CPUs and RTX 3060 / 4060 GPUs. Parallel downloads in seconds.
- **17 to 32 Workers (Extreme Beast Mode):** Designed for 16+ Core CPUs (Ryzen 9, Threadripper, i9) and RTX 4080 / 4090.

---

## 8. Backend API Reference & Route Matrix

| Route | Method | Payload / Params | Purpose |
| :--- | :--- | :--- | :--- |
| `/api/settings` | `GET` | None | Retrieves persisted settings and API keys. |
| `/api/settings` | `POST` | `JSON (settings)` | Updates and saves all user keys, worker counts, and encoder options. |
| `/api/test-apis` | `POST` | None | Tests connectivity against all configured stock video and AI APIs. |
| `/api/upload-audio` | `POST` | `multipart/form-data (file)` | Uploads voiceover file and returns duration, filename, and stream URL. |
| `/api/tts-voices` | `GET` | None | Lists curated neural voices with sample audio URLs. |
| `/api/generate-voiceover`| `POST` | `text, voice, rate, pitch` | Generates speech via Edge-TTS, ElevenLabs, or OpenAI. |
| `/api/clone-voice` | `POST` | `audio, text, voice_name` | Local Kokoro-82M zero-cost CPU voice cloner. |
| `/api/upload-bgm` | `POST` | `multipart/form-data (file)` | Uploads custom background music. |
| `/api/bgm-tracks` | `GET` | None | Lists available background music tracks. |
| `/api/upload-overlay` | `POST` | `multipart/form-data (file)` | Uploads video/image overlay (MP4, MOV, PNG, JPG). |
| `/api/generate-image` | `POST` | `prompt, niche, style` | Generates 16:9 AI image via Gemini 2.0 / Imagen 3 / Pollinations. |
| `/api/start-generate`| `POST` | `audio_filename, niche, pipeline, resolution` | Launches background worker video pipeline. |
| `/api/job-progress/{id}`| `GET`| `job_id` | Streams live percentage and stage details. |
| `/api/search-clips` | `GET` | `query (string)` | Queries stock APIs for replacement clips. |
| `/api/swap-clip` | `POST` | `project_id, scene_id, download_url` | Hot-swaps clip in project timeline. |
| `/api/start-render` | `POST` | `project_id, preset_key, custom_options` | Executes parallel segmented render to 1080p/4K MP4. |
| `/api/generate-thumbnails`| `POST`| `project_id, custom_headline` | Generates 2 high-CTR YouTube thumbnails. |
| `/api/thumbnails/{id}`| `GET` | `project_id` | Retrieves generated thumbnails for project. |
| `/api/generate-seo` | `POST` | `project_id` | Generates YouTube titles, description, and tags. |
| `/api/seo/{id}` | `GET` | `project_id` | Retrieves generated SEO metadata. |
| `/api/export-capcut` | `POST` | `project_id, custom_options` | Assembles native CapCut draft project. |
| `/api/open-folder` | `POST` | `path (optional)` | Opens Windows Explorer to specified directory. |
| `/api/open-output-folder`| `POST` | None | Guaranteed open of `data/output/` folder even if empty. |
| `/api/projects` | `GET` | None | Returns historical projects list. |
| `/api/projects/{id}` | `DELETE` | `project_id` | Deletes single project. |
| `/api/projects/all` | `DELETE` | None | Deletes all projects. |

---

## 9. Operational Guide & Troubleshooting

### How to Run VideoGen Studio / ATS Video:

1. **Standalone Portable EXE (Zero Setup)**:
   Double-click [**`2_RUN_APP_Standalone_EXE.bat`**](file:///c:/Users/Abid/Desktop/vg/2_RUN_APP_Standalone_EXE.bat).
   No Python, Git, or FFmpeg required.

2. **Source Code Developer Mode**:
   Double-click [**`1_RUN_APP_Python_Source.bat`**](file:///c:/Users/Abid/Desktop/vg/1_RUN_APP_Python_Source.bat) or run `python main.py`.

3. **Build Standalone Executable**:
   Double-click [**`3_BUILD_NEW_Standalone_EXE.bat`**](file:///c:/Users/Abid/Desktop/vg/3_BUILD_NEW_Standalone_EXE.bat).

4. **Web Browser Access**:
   The engine opens automatically at: [**`http://127.0.0.1:8765/`**](http://127.0.0.1:8765/)

5. **In-App User Manual**:
   Click **📖 Docs** in the navigation header or open: [**`http://127.0.0.1:8765/docs.html`**](http://127.0.0.1:8765/docs.html)

---

*Document version: 3.2.0 • ATS Video / VideoGen Studio 4K/8K UHD Engine • Maintained by Antigravity AI*
