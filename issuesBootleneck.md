# 🛠️ Universal Video Generation Engine — 34-Point Audit & Optimization Checklist

> **How to Use This Checklist**:  
> Give this file to any developer or AI assistant working on an automated video/voiceover tool.  
> 1. **Audit**: Search the codebase for the patterns described in **"How to Audit / Grep"**.  
> 2. **Identify**: If the flaw exists in the tool, check the box under **"Issue Identified"**.  
> 3. **Fix**: Implement the code pattern specified in **"Prescribed Solution & Code Pattern"**.  
> 4. **Verify**: Run the check in **"Verification Metric"** and mark as `[x] Resolved`.

---

## 📋 Executive Summary Table

| # | Check Name | Primary Risk Area | Severity | Status |
|:---:|---|---|:---:|:---:|
| **1** | A/V Lipsync Drift on Long Timelines | Audio Sync | 🔴 Critical | `[ ]` |
| **2** | Whisper 25MB Limit & Word-Cutting | STT Transcription | 🔴 Critical | `[ ]` |
| **3** | Long Voiceover Sequential Transcription Lag | STT Speed | 🟡 High | `[ ]` |
| **4** | Delayed Transcription Trigger | UX / Latency | 🟡 Medium | `[ ]` |
| **5** | Redundant Audio Mixing Overhead | Render Speed | 🟢 Low | `[ ]` |
| **6** | Heavy Raw Audio Upload Network Lag | Network / STT | 🟡 Medium | `[ ]` |
| **7** | GPU Hardware Encoder Cascade Auto-Probe | Render Stability | 🔴 Critical | `[ ]` |
| **8** | Mixed-Resolution Decoder Stall & OOM Crash | Memory / Stability | 🔴 Critical | `[ ]` |
| **9** | FFmpeg Muxing Buffer Overflow Crash | Render Stability | 🔴 Critical | `[ ]` |
| **10** | Drone/Camera Data Track Concat Corruption | Render Stability | 🔴 Critical | `[ ]` |
| **11** | Redundant Framerate Resampling & Dropped Frames | Render Speed / Quality | 🟡 High | `[ ]` |
| **12** | Premature Video Cutoff on Long Timelines | Video Completeness | 🔴 Critical | `[ ]` |
| **13** | Multi-Thread Filter Memory Explosion | Memory Bloat | 🔴 Critical | `[ ]` |
| **14** | CPU-to-GPU Memory Bounce (Ping-Pong Filters) | Render Speed | 🟡 High | `[ ]` |
| **15** | Sequential Multi-Batch Transition Rendering | Render Speed | 🟡 High | `[ ]` |
| **16** | Stock Video Trimming Semaphore Bottleneck | Downloader Speed | 🟡 High | `[ ]` |
| **17** | Repeated Synchronous FFprobe Process Spawning | Disk / CPU Overhead | 🟡 Medium | `[ ]` |
| **18** | Cross-Project Stock Clip Repetition | Video Quality | 🟡 Medium | `[ ]` |
| **19** | Single Stock Provider Outage & Blank Scenes | Pipeline Reliability | 🔴 Critical | `[ ]` |
| **20** | Unpurged Raw Stock Footage Disk Exhaustion | Storage Stability | 🔴 Critical | `[ ]` |
| **21** | Short Clip Freeze on Long Voiceover Scenes | Video Quality | 🟡 High | `[ ]` |
| **22** | LLM 429 Fallback to Fake Content & Static Keys | AI Data Integrity | 🔴 Critical | `[ ]` |
| **23** | Sequential AI Scene Tagging Latency | Pipeline Speed | 🟡 High | `[ ]` |
| **24** | Mid-Render API Key Expiration Failure | Pipeline Reliability | 🔴 Critical | `[ ]` |
| **25** | Abstract Narration Resulting in Empty Stock B-Roll | Visual Relevance | 🟡 High | `[ ]` |
| **26** | Missing Automated YouTube SEO & Metadata | Creator Workflow | 🟢 Medium | `[ ]` |
| **27** | Machine-Dependent Hardcoded File Paths | Portability | 🔴 Critical | `[ ]` |
| **28** | Localhost Link Hijack on Remote/Shared Access | UI / Remote Sharing | 🟡 High | `[ ]` |
| **29** | Long Browser Session Memory Leaks from Video Blobs | Client Stability | 🟡 High | `[ ]` |
| **30** | Python 3.14 / Uvicorn Custom Logger Crash | Startup Crash | 🔴 Critical | `[ ]` |
| **31** | Safari & WebKit CSS Blur / Prefix Breakage | UI Aesthetics | 🟢 Low | `[ ]` |
| **32** | Missing Subtitle Fonts Fallback Degeneration | Caption Aesthetics | 🟡 Medium | `[ ]` |
| **33** | Browser Tab Confusion & Accidental Closure | Desktop UX | 🟢 Medium | `[ ]` |
| **34** | Terminal Closure Causing Loss of Diagnostic Logs | Debug Visibility | 🟡 High | `[ ]` |

---

## 🎙️ Category 1: Audio, Voiceover & STT Pipeline

### - [ ] 1. A/V Lipsync Drift on Long Timelines (`aresample=async=1000`)
* **Issue / Symptom:** In videos longer than 10–15 minutes (or 1–2 hours), audio and video gradually drift out of sync. By the end of the video, speech occurs seconds ahead or behind the visuals.
* **Root Cause:** FFmpeg audio filtergraphs default to `-af "aresample=async=1"` or lack sample clock synchronization. Fractional PTS timestamp rounding across 50–100+ stock clips accumulates clock drift over time.
* **How to Audit / Grep:** Search the rendering pipeline for audio filter definitions (`-af`, `amix`, `aresample`). If `aresample` is missing or set to `async=1`, the issue is present.
* **Prescribed Solution & Code Pattern:**  
  Upgrade all audio output chains and filtergraphs to use `aresample=async=1000`:
  ```bash
  -af "aresample=async=1000:min_hard_comp=0.100000:first_pts=0"
  ```
  This continuously stretches/trims audio sample micro-packets to hardware-lock with video frame timestamps.
* **Verification Metric:** Microsecond-exact audio/video synchronization maintained from minute 0 to hour 2.

---

### - [ ] 2. Whisper 25MB Limit & Word-Cutting (Smart Silence-Based Slicing)
* **Issue / Symptom:** Voiceovers longer than 15 minutes or high-bitrate files throw HTTP `413 Payload Too Large` on Groq or OpenAI Whisper. If fixed time-slicing is used (e.g., cutting every 10 mins), words are cut in half mid-syllable, corrupting word timestamps.
* **Root Cause:** Uploading raw audio files exceeding 25MB, or dividing audio by pure duration math (`i * 600`) without checking if the speaker is mid-sentence.
* **How to Audit / Grep:** Check the transcription module for how audio files $> 25\text{MB}$ are handled. If there is no chunking, or if chunking uses rigid duration multiplication without silence detection, the issue is present.
* **Prescribed Solution & Code Pattern:**  
  1. Detect natural pauses in the audio using FFmpeg `silencedetect`:
     ```python
     cmd = [ffmpeg_exe, "-i", audio_path, "-af", "silencedetect=noise=-30dB:d=0.3", "-f", "null", "-"]
     ```
  2. Parse silence intervals from stderr (`silence_end: X | silence_duration: Y`).
  3. Align all chunk cuts to the nearest natural silence window within the target slice duration (e.g., 10–12 minutes). Never cut while speech is active.
* **Verification Metric:** 0 dropped or mutilated words across 2-hour recordings; 100% valid Whisper API requests below 25MB.

---

### - [ ] 3. Long Voiceover Sequential Transcription Lag (Parallel Multi-Key STT)
* **Issue / Symptom:** A 1-to-2-hour voiceover takes 10–15 minutes just to transcribe before scene analysis even starts.
* **Root Cause:** Sliced audio chunks are processed in a sequential `for chunk in chunks:` loop against a single API key.
* **How to Audit / Grep:** Inspect chunk transcription execution. If chunks are processed in a single-threaded synchronous loop, the bottleneck is present.
* **Prescribed Solution & Code Pattern:**  
  Use `ThreadPoolExecutor` to dispatch audio chunks concurrently across a multi-key pool:
  ```python
  from concurrent.futures import ThreadPoolExecutor
  workers = min(len(chunks), len(api_keys) * 2)
  with ThreadPoolExecutor(max_workers=workers) as executor:
      results = list(executor.map(transcribe_chunk_worker, chunk_tasks))
  ```
* **Verification Metric:** 1-hour voiceover transcribed in under 60–90 seconds using 2–3 API keys.

---

### - [ ] 4. Delayed Transcription Trigger (Background Zero-Wait Pre-Transcription)
* **Issue / Symptom:** User uploads or drops an audio file, configures video settings for 1 minute, clicks "Generate", and is then forced to wait an additional 30–60 seconds for transcription.
* **Root Cause:** The backend delays transcription until the final "Generate" action is triggered.
* **How to Audit / Grep:** Check the frontend file drop/upload handler. If uploading an audio file only returns metadata (duration, filename) and does not kick off background transcription and caching, the issue is present.
* **Prescribed Solution & Code Pattern:**  
  Trigger an asynchronous background transcription request immediately when the user drops the audio file. Cache the transcript in memory/disk by audio hash. When "Generate" is clicked, retrieve the cached transcript instantly in 0.0 seconds.
* **Verification Metric:** 0 seconds wait time on "Generate" click if user spent $> 20$ seconds configuring settings.

---

### - [ ] 5. Redundant Audio Mixing Overhead (Dynamic BGM Bypass)
* **Issue / Symptom:** Rendering speed is 5–10% slower even when the user has disabled Background Music (BGM) or uploaded no audio track.
* **Root Cause:** The FFmpeg audio filtergraph unconditionally executes `amix=inputs=2:duration=first`, forcing FFmpeg to decode, resample, and mix an empty/silent secondary audio channel.
* **How to Audit / Grep:** Search the FFmpeg command builder for `amix`. Check if `amix` is always added regardless of whether a BGM file is attached.
* **Prescribed Solution & Code Pattern:**  
  Conditionally construct the audio filtergraph:
  ```python
  if bgm_path and os.path.exists(bgm_path) and bgm_volume > 0:
      audio_filter = f"[0:a][1:a]amix=inputs=2:duration=first,aresample=async=1000[aout]"
  else:
      # Bypass mixing completely — direct stream copy / single filter
      audio_filter = f"[0:a]aresample=async=1000[aout]"
  ```
* **Verification Metric:** 0 CPU mixing overhead when background music is inactive.

---

### - [ ] 6. Heavy Raw Audio Upload Network Lag (48kbps Pre-Compression)
* **Issue / Symptom:** User uploads a 150MB uncompressed WAV file (or 32-bit float audio), causing multi-minute network upload delays to cloud STT APIs.
* **Root Cause:** Raw uncompressed PCM WAV data sent directly over HTTP to remote APIs.
* **How to Audit / Grep:** Check whether audio is compressed before uploading to Whisper/Groq API. If raw `.wav` files $> 20\text{MB}$ are transmitted directly, the issue is present.
* **Prescribed Solution & Code Pattern:**  
  Before dispatching to the STT API, compress audio locally via FFmpeg to 48kbps 16kHz mono MP3:
  ```bash
  ffmpeg -i input.wav -ar 16000 -ac 1 -b:a 48k output_compact.mp3
  ```
  Reduces a 150MB WAV down to 3.8MB in 0.4 seconds with 0 loss in Whisper transcription accuracy.
* **Verification Metric:** Network upload payload reduced by 95%+.

---

## ⚡ Category 2: Video Rendering, FFmpeg & Hardware Encoding

### - [ ] 7. GPU Hardware Encoder Cascade Auto-Probe
* **Issue / Symptom:** Video export crashes on startup with `Unknown encoder 'h264_nvenc'` when run on a PC with an AMD GPU, Intel GPU, or no discrete graphics card.
* **Root Cause:** Hardcoded GPU encoder name (`h264_nvenc`) without runtime hardware probing.
* **How to Audit / Grep:** Search the codebase for `h264_nvenc`, `hevc_nvenc`, or `-c:v`. If an encoder is hardcoded without a runtime validation test, the issue is present.
* **Prescribed Solution & Code Pattern:**  
  Run a 1-second benchmark probe at startup testing candidates in priority order:
  `h264_nvenc` (NVIDIA) $\rightarrow$ `h264_qsv` (Intel) $\rightarrow$ `h264_amf` (AMD) $\rightarrow$ `h264_mf` (Windows Media Foundation) $\rightarrow$ `libx264` (CPU Fallback).
  Cache the winning encoder in settings.
* **Verification Metric:** 100% crash-free startup on any hardware configuration.

---

### - [ ] 8. Mixed-Resolution Decoder Stall & OOM Crash (1080p Normalization)
* **Issue / Symptom:** FFmpeg crashes midway through rendering with: `Error while filtering: Cannot allocate memory` (Exit code `-12` / `4294967284`).
* **Root Cause:** Concat demuxer receives clips of varying resolutions (e.g., Clip 1 is 720p, Clip 2 is 1080p, Clip 3 is 4K). When resolution changes dynamically across clips, FFmpeg decoder buffers fail to reallocate, leaking RAM until the OS terminates the process.
* **How to Audit / Grep:** Check how downloaded stock clips are stitched. If clips are passed directly into `concat` demuxer without pre-normalizing resolution and framerate, the issue is present.
* **Prescribed Solution & Code Pattern:**  
  Every clip MUST be pre-normalized before entering the concat pipeline:
  ```bash
  ffmpeg -i raw_clip.mp4 -vf "scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,setsar=1,fps=30" -c:v <encoder> -an -dn normalized_clip.mp4
  ```
* **Verification Metric:** Peak RAM during multi-clip concat remains $< 250\text{MB}$ instead of ballooning to 2.5GB+.

---

### - [ ] 9. FFmpeg Muxing Buffer Overflow Crash (`-max_muxing_queue_size 1024`)
* **Issue / Symptom:** Long renders with subtitles and audio tracks crash with: `Too many packets buffered for output stream`.
* **Root Cause:** Default muxing queue size in FFmpeg is 128 packets. Burst audio/video packet generation on multi-stream filtergraphs overruns this queue.
* **How to Audit / Grep:** Check final FFmpeg export command arguments. If `-max_muxing_queue_size 1024` is missing, the vulnerability exists.
* **Prescribed Solution & Code Pattern:**  
  Add `-max_muxing_queue_size 1024` to all final FFmpeg video generation commands.
* **Verification Metric:** 0 queue overflow errors on multi-hour timeline renders.

---

### - [ ] 10. Drone & Camera Telemetry/Data Track Concat Corruption (`-an -dn`)
* **Issue / Symptom:** Concat demuxer emits `Non-monotonous DTS in output stream` warnings, visual stuttering, or audio/video track mapping errors.
* **Root Cause:** Stock footage from GoPros, drones, or iPhones contains non-standard data tracks (`tmcd` timecode, GPS telemetry, extra metadata streams) and silent audio tracks that break container muxing.
* **How to Audit / Grep:** Check clip trimming and preparation commands. If they only strip audio with `-an` but omit `-dn` (data streams), the issue is present.
* **Prescribed Solution & Code Pattern:**  
  Always pass both `-an` and `-dn` when processing stock clips:
  ```bash
  -c:v copy -an -dn
  ```
* **Verification Metric:** 100% clean video-only containers with 0 non-monotonous DTS errors.

---

### - [ ] 11. Redundant Framerate Resampling & Dropped Frames (Single-Pass CFR)
* **Issue / Symptom:** Rendering logs report thousands of duplicate and dropped frames (`dup=1077 drop=278`), and rendering speed is cut in half.
* **Root Cause:** Applying framerate filters multiple times (e.g. `fps=30` in filtergraph AND `-r 30` in CLI arguments AND deprecated `-vsync 1`), forcing FFmpeg into recalculation loops.
* **How to Audit / Grep:** Check if both `fps=X` in filtergraph and `-r X` in output flags exist together. Check for deprecated `-vsync` flags.
* **Prescribed Solution & Code Pattern:**  
  Standardize on modern single-pass Constant Frame Rate (CFR) syntax:
  ```bash
  -fps_mode cfr -r 30
  ```
  Remove duplicate `fps=30` video filters from pre-normalized clips.
* **Verification Metric:** 0 dropped frames (`drop=0 dup=0`) during final rendering.

---

### - [ ] 12. Premature Video Cutoff on Long Timelines (No `-shortest`)
* **Issue / Symptom:** For an 18-minute voiceover, the tool exports only 2 minutes of video and terminates early without throwing an error.
* **Root Cause:** Presence of the `-shortest` flag in the FFmpeg command. If any stock video stream ends before the audio, `-shortest` cuts the entire output immediately.
* **How to Audit / Grep:** Search the rendering pipeline for `-shortest`. If present, the bug exists.
* **Prescribed Solution & Code Pattern:**  
  1. Remove `-shortest` completely from the final render command.
  2. Map stock footage with `-stream_loop -1` or ensure total visual duration matches audio duration with a 5–10s safety buffer.
* **Verification Metric:** Final exported video matches voiceover duration down to the exact millisecond.

---

### - [ ] 13. Multi-Thread Filter Memory Explosion (Adaptive CPU Threading)
* **Issue / Symptom:** System freezes, mouse lags, and low-RAM laptops (8GB–12GB) experience out-of-memory crashes during video export.
* **Root Cause:** FFmpeg defaulting to `-threads 0` (unbounded threads) across complex filtergraphs, causing dozens of video frames to buffer in system RAM simultaneously.
* **How to Audit / Grep:** Check thread configuration in FFmpeg commands. If unconstrained (`-threads 0` on filter complex without RAM awareness), the issue is present.
* **Prescribed Solution & Code Pattern:**  
  Scale threads dynamically based on available system RAM:
  ```python
  import psutil
  total_ram_gb = psutil.virtual_memory().total / (1024**3)
  threads = 2 if total_ram_gb <= 12 else (4 if total_ram_gb <= 24 else 8)
  cmd.extend(["-threads", str(threads)])
  ```
* **Verification Metric:** Stable memory footprint under 500MB on 8GB RAM machines.

---

### - [ ] 14. CPU-to-GPU Memory Bounce (Ping-Pong Filters)
* **Issue / Symptom:** Hardware encoder speed drops from 85 FPS down to 35 FPS despite having a fast dedicated GPU.
* **Root Cause:** Interleaving CPU filters (e.g. `boxblur`, complex software overlays) inside a hardware-accelerated pipeline forces frames to copy from GPU VRAM to CPU RAM and back to GPU VRAM for every frame.
* **How to Audit / Grep:** Check the filtergraph applied to video streams. If heavy CPU filters are used between hardware decode and encode stages, the bottleneck exists.
* **Prescribed Solution & Code Pattern:**  
  Use GPU-native filters or fast linear mathematical expressions (`zoompan` with linear interpolation). Set heavy blurs to 0 by default. Keep frame processing strictly in one memory domain.
* **Verification Metric:** GPU rendering throughput sustained at 80+ FPS on 1080p.

---

### - [ ] 15. Sequential Multi-Batch Transition Rendering (`xfade`)
* **Issue / Symptom:** Videos with 80–150 scenes spend 3–5 minutes solely applying xfade transitions between clips.
* **Root Cause:** Large timelines are divided into batches to prevent RAM crashes, but each batch is rendered sequentially in a single loop.
* **How to Audit / Grep:** Inspect the transition rendering function (e.g. `_render_xfade_batches`). If batches are rendered one-by-one in a `for` loop, the bottleneck is present.
* **Prescribed Solution & Code Pattern:**  
  Render independent batches concurrently using `ThreadPoolExecutor(max_workers=2)`:
  ```python
  with ThreadPoolExecutor(max_workers=2) as executor:
      rendered_batches = list(executor.map(render_single_batch, batches))
  ```
* **Verification Metric:** Transition rendering stage completed in $< 45$ seconds.

---

## 🌐 Category 3: Stock Footage & Asset Pipeline

### - [ ] 16. Stock Video Trimming Semaphore Bottleneck
* **Issue / Symptom:** 14 worker threads download stock videos rapidly, but the process halts at "Trimming Clips" taking 2–3 minutes.
* **Root Cause:** Trimming execution is throttled by a hardcoded `Semaphore(2)`, allowing only 2 parallel FFmpeg processes even on 16-core or 32-core CPUs.
* **How to Audit / Grep:** Search downloader files for `Semaphore`. If set to a static integer `2`, the bottleneck is present.
* **Prescribed Solution & Code Pattern:**  
  Scale semaphore dynamically based on available CPU cores:
  ```python
  import os
  max_trim_slots = min(6, max(2, (os.cpu_count() or 4) // 2))
  trim_semaphore = threading.Semaphore(max_trim_slots)
  ```
* **Verification Metric:** Trimming concurrency doubled (4–6 concurrent workers on 8+ core CPUs).

---

### - [ ] 17. Synchronous Disk FFprobe Process Spawning Lag
* **Issue / Symptom:** Before rendering starts, the tool freezes for 5–10 seconds inspecting 50–100 clips on disk.
* **Root Cause:** Invoking a new OS subprocess `ffprobe.exe` for every single clip repeatedly to read duration/dimensions without caching.
* **How to Audit / Grep:** Search for `ffprobe` calls across the codebase. Check if results are memoized in an in-memory dictionary.
* **Prescribed Solution & Code Pattern:**  
  Add an in-memory probe memoization dictionary with a thread lock:
  ```python
  _PROBE_CACHE: Dict[str, float] = {}
  # Check cache before spawning process
  if file_path in _PROBE_CACHE:
      return _PROBE_CACHE[file_path]
  ```
* **Verification Metric:** Subsequent clip metadata queries return in 0.0 milliseconds.

---

### - [ ] 18. Cross-Project Stock Clip Repetition
* **Issue / Symptom:** Multiple videos produced for the same YouTube channel repeatedly feature the exact same 3–4 stock clips.
* **Root Cause:** Stock footage candidate scoring only evaluates single-project suitability and has no memory of past video projects.
* **How to Audit / Grep:** Check clip selection scoring logic. If there is no persistent history file tracking used video IDs, the flaw exists.
* **Prescribed Solution & Code Pattern:**  
  Maintain a persistent JSON registry (`stock_usage_history.json`).
  Apply scoring penalties:
  - `-1000.0` points penalty if clip was already chosen in the *current* project.
  - `-75.0` points penalty if clip was used in a *prior* project within the last 14 days.
  - Rotate across top 3 highest-scoring candidate clips.
* **Verification Metric:** 0 repetitive clips within the same video; natural variety across different project videos.

---

### - [ ] 19. Single Stock Provider Dependency & Rate-Limit Blank Scenes
* **Issue / Symptom:** If Pexels API hits hourly rate limit (200 requests/hr) or lacks clips for a niche query, scenes are left blank or generation crashes.
* **Root Cause:** Hard dependency on a single stock video provider.
* **How to Audit / Grep:** Check stock downloader implementation. If it only queries Pexels or only queries Pixabay, the vulnerability exists.
* **Prescribed Solution & Code Pattern:**  
  Implement a dual-provider pool with multi-key rotation: Query Pexels primary pool; if results are fewer than 2 candidates, seamlessly fallback to Pixabay 4K engine.
* **Verification Metric:** 100% visual fulfillment across all scenes with 0 blank clips.

---

### - [ ] 20. Hard Drive Exhaustion from Unpurged Raw Stock Clips
* **Issue / Symptom:** After generating 5–10 videos, the user's hard drive runs out of disk space (each project leaves 2–5 GB of raw stock clips).
* **Root Cause:** Temporary raw downloaded videos are never cleaned up from cache directories.
* **How to Audit / Grep:** Check cache lifecycle management. If raw clips in `cache/` remain permanently on disk without retention policies, the issue is present.
* **Prescribed Solution & Code Pattern:**  
  Implement an automated background storage cleaner daemon:
  - Purge raw clips older than a configurable retention window (default: 3 hours).
  - Provide an option to immediately delete raw stock clips once final video export is confirmed (`clean_raw_after_render: true`).
* **Verification Metric:** Hard drive stays clean; zero disk bloat after renders.

---

### - [ ] 21. Short Clip Freeze on Long Voiceover Scenes (`-stream_loop -1`)
* **Issue / Symptom:** If a scene duration is 12 seconds but the best matching stock clip is only 4 seconds, the video freezes on the last frame for 8 seconds.
* **Root Cause:** Missing loop configuration on stock video input streams.
* **How to Audit / Grep:** Check how stock clips shorter than scene duration are handled. If not looped or extended, the freeze bug is present.
* **Prescribed Solution & Code Pattern:**  
  Apply seamless stream looping via FFmpeg `-stream_loop -1` before the input flag:
  ```bash
  ffmpeg -stream_loop -1 -i short_clip.mp4 -t <scene_duration> ...
  ```
* **Verification Metric:** Smooth continuous motion across all scenes regardless of raw clip duration.

---

## 🧠 Category 4: AI Director, Prompts & API Rate-Limit Resilience

### - [ ] 22. LLM 429 Fallback to Fake Content & Static Keys
* **Issue / Symptom:** When Groq or OpenAI returns HTTP 429 (rate limit), the tool fails, or fills subtitles with dummy placeholder quotes (`"You have power over your mind..."`). Entering a new API key in settings requires restarting the server.
* **Root Cause:** Hardcoded mock fallbacks in exception blocks, and loading settings only once on server boot.
* **How to Audit / Grep:** Search code for `429` and check exception blocks. If mock quotes are generated, or if `settings.json` is not re-read inside retry loops, the flaw exists.
* **Prescribed Solution & Code Pattern:**  
  1. Implement exponential backoff (`1s, 2s, 4s, 8s`) on HTTP 429 status codes.
  2. Re-read `settings.json` dynamically on each retry attempt so newly saved keys take effect immediately without server restart.
  3. Delete all dummy placeholder quote generators; raise clean errors instead.
* **Verification Metric:** Seamless recovery from rate limits with zero dummy content corruption.

---

### - [ ] 23. Sequential AI Scene Tagging Latency
* **Issue / Symptom:** A 150-scene video takes 35–45 seconds waiting for AI LLM to extract visual search queries for scenes.
* **Root Cause:** Batches of scenes are sent to the LLM sequentially one after another in a single-threaded loop.
* **How to Audit / Grep:** Inspect `enhance_scenes_with_ai` or equivalent function. If batches are processed in a sequential `for` loop, the bottleneck exists.
* **Prescribed Solution & Code Pattern:**  
  Dispatch scene batches concurrently across the multi-key LLM pool using `ThreadPoolExecutor`:
  ```python
  with ThreadPoolExecutor(max_workers=min(len(batches), len(keys) * 2)) as executor:
      results = list(executor.map(tag_batch_worker, batches))
  ```
* **Verification Metric:** AI scene analysis completed in $< 4$ seconds across 150+ scenes.

---

### - [ ] 24. Mid-Render API Key Expiration Failure
* **Issue / Symptom:** User waits 3 minutes into video generation, and the render suddenly aborts because an API key was expired or invalid.
* **Root Cause:** No pre-flight validation of API credentials before initiating the render pipeline.
* **How to Audit / Grep:** Check if the application performs lightweight health pings on configured API keys on startup or settings save.
* **Prescribed Solution & Code Pattern:**  
  Perform silent background health pings on startup and settings save. If the primary key fails, display a warning in the UI immediately and switch to the fallback key before video generation starts.
* **Verification Metric:** 0 mid-render aborts due to expired API keys.

---

### - [ ] 25. Abstract Narration Resulting in Empty Stock B-Roll
* **Issue / Symptom:** Script lines like *"Time is slipping away"* or *"Overcome mental resistance"* produce zero stock video matches because the AI searches for literal abstract phrases.
* **Root Cause:** Lack of physical entity translation in LLM system prompts.
* **How to Audit / Grep:** Review system prompts for scene tag extraction. If there is no instruction forcing abstract concepts into tangible physical visual entities, the flaw exists.
* **Prescribed Solution & Code Pattern:**  
  Mandate concrete physical entity mapping in the LLM prompt:
  - *"Translate abstract metaphors into concrete physical objects that exist in reality: e.g., 'time is slipping' -> hourglass sand, clock ticking; 'mental resistance' -> athlete exhausted gym, person looking mirror."*
* **Verification Metric:** 100% relevant stock footage returned for abstract philosophical scripts.

---

### - [ ] 26. Missing Automated YouTube SEO & Metadata
* **Issue / Symptom:** Creator has to manually write titles, tags, and timestamps after the video is finished.
* **Root Cause:** Video generator stops at video rendering without generating distribution metadata.
* **How to Audit / Grep:** Check if an automated SEO generator exists that outputs ranked tags, descriptions, and chapters.
* **Prescribed Solution & Code Pattern:**  
  Add an automated SEO generator utilizing Groq/Qwen: Outputs 5 viral high-CTR titles, formatted descriptions with scene timestamps, and 30+ ranked tags saved directly to `data/seo/`.
* **Verification Metric:** Complete YouTube-ready title, description, and tags generated in $< 2$ seconds.

---

## 🖥️ Category 5: System Portability, UI/UX & Reliability

### - [ ] 27. Machine-Dependent Hardcoded File Paths
* **Issue / Symptom:** Sharing the application folder or executable with a team member or another PC causes instant `FileNotFoundError` crashes on export.
* **Root Cause:** Paths like `C:\Users\Abid\...` saved in `settings.json` or scripts without checking whether that directory exists on the target machine.
* **How to Audit / Grep:** Search for hardcoded user paths or check how `output_dir` in `settings.json` is validated upon load.
* **Prescribed Solution & Code Pattern:**  
  Sanitize output directories on load:
  ```python
  raw_out = str(settings.get("output_dir", "")).strip()
  if not raw_out or not Path(raw_out).exists():
      settings["output_dir"] = str(DEFAULT_OUTPUT_DIR)
  ```
* **Verification Metric:** App runs flawlessly out-of-the-box on any drive, folder, or user account.

---

### - [ ] 28. Localhost Link Hijack on Remote/Shared Access
* **Issue / Symptom:** Accessing the tool over LAN or remote connection causes "Docs" or "Help" buttons to open a browser window on the *host* server machine instead of the client machine.
* **Root Cause:** Backend route invoking `webbrowser.open_new_tab("http://127.0.0.1:8765/docs.html")` on the server OS.
* **How to Audit / Grep:** Search backend routes for `webbrowser.open`. If triggered by API calls from the client, the bug exists.
* **Prescribed Solution & Code Pattern:**  
  1. Remove server-side `webbrowser.open` calls from API handlers.
  2. Display documentation inside an in-window responsive glassmorphic modal with an embedded iframe.
  3. External buttons must use client-side JavaScript `window.open('docs.html', '_blank')`.
* **Verification Metric:** Clean in-window modal display on any device, network port, or IP address.

---

### - [ ] 29. Long Browser Session Memory Leaks from Video Blobs
* **Issue / Symptom:** After previewing 10–20 videos in the web UI, browser RAM bloats to 3–5 GB, causing tab freezing and browser lag.
* **Root Cause:** Repeatedly generating `URL.createObjectURL(blob)` without calling `URL.revokeObjectURL()` when video previews change.
* **How to Audit / Grep:** Search frontend JavaScript for `URL.createObjectURL`. Check if `URL.revokeObjectURL` is invoked on previous preview URLs.
* **Prescribed Solution & Code Pattern:**  
  Revoke prior blob URLs before allocating new preview objects:
  ```javascript
  if (currentVideoUrl && currentVideoUrl.startsWith('blob:')) {
      URL.revokeObjectURL(currentVideoUrl);
  }
  currentVideoUrl = URL.createObjectURL(newBlob);
  ```
* **Verification Metric:** Browser RAM remains stable under 300MB after dozens of video previews.

---

### - [ ] 30. Python 3.14 / Uvicorn Custom Logger Crash (`LogTee.isatty`)
* **Issue / Symptom:** Application crashes immediately on startup on newer Python/Uvicorn versions with: `AttributeError: 'LogTee' object has no attribute 'isatty'`.
* **Root Cause:** Custom stdout/stderr tee logger class does not implement terminal query methods expected by modern Uvicorn color formatters.
* **How to Audit / Grep:** Inspect custom `LogTee` or stdout redirection classes in `config.py` or `server.py`.
* **Prescribed Solution & Code Pattern:**  
  Implement `isatty()` and `fileno()` delegation:
  ```python
  class LogTee:
      def isatty(self):
          return hasattr(self.terminal, "isatty") and self.terminal.isatty()
      def fileno(self):
          return getattr(self.terminal, "fileno", lambda: 1)()
  ```
* **Verification Metric:** Clean 1-second startup on Python 3.10 through Python 3.14+.

---

### - [ ] 31. Safari & WebKit CSS Blur / Prefix Breakage
* **Issue / Symptom:** Glassmorphism UI looks opaque or broken on macOS Safari, iOS, and WebKit-based desktop wrappers.
* **Root Cause:** Missing `-webkit-backdrop-filter` or placing `-webkit-backdrop-filter` *after* standard `backdrop-filter`.
* **How to Audit / Grep:** Search CSS stylesheets for `backdrop-filter`. Check if `-webkit-backdrop-filter` is missing or placed in reverse order.
* **Prescribed Solution & Code Pattern:**  
  Always specify the WebKit vendor prefix first:
  ```css
  -webkit-backdrop-filter: blur(16px);
  backdrop-filter: blur(16px);
  ```
* **Verification Metric:** 100% warning-free CSS and pristine glassmorphism across Chrome, Edge, Safari, and iOS.

---

### - [ ] 32. Missing Subtitle Fonts Fallback Degeneration
* **Issue / Symptom:** Subtitles render in basic Arial font instead of stylized viral typography (MrBeast, Hormozi, Bold Impact) on machines without those fonts installed.
* **Root Cause:** Relying on Windows system font installation instead of bundling TTF fonts with the application.
* **How to Audit / Grep:** Check if font files are bundled in the repository and passed directly to FFmpeg `libass` via `fontsdir`.
* **Prescribed Solution & Code Pattern:**  
  Embed viral font TTFs directly in `data/fonts/` and pass `fontsdir` to the subtitle filter:
  ```bash
  -vf "subtitles=subs.ass:fontsdir='data/fonts'"
  ```
* **Verification Metric:** Subtitle styling identical across all client machines without requiring font installation.

---

### - [ ] 33. Browser Tab Confusion & Accidental Closure
* **Issue / Symptom:** Users accidentally close the browser tab during a 40-minute render, aborting the process.
* **Root Cause:** Running the application exclusively in a standard web browser tab.
* **How to Audit / Grep:** Check if a standalone desktop wrapper exists.
* **Prescribed Solution & Code Pattern:**  
  Provide a dedicated desktop runner (`desktop_launcher.py`) that opens the tool in a standalone, frameless Windows WebView2 or Microsoft Edge App Mode window:
  ```python
  cmd = ["msedge.exe", f"--app=http://127.0.0.1:{port}", "--window-size=1400,900"]
  ```
* **Verification Metric:** Tool runs as an isolated desktop application with 60 FPS hardware acceleration.

---

### - [ ] 34. Terminal Closure Causing Loss of Diagnostic Logs
* **Issue / Symptom:** When a background CMD window is closed, all troubleshooting history is lost, making customer support impossible.
* **Root Cause:** Output printed strictly to stdout without persistent file redirection.
* **How to Audit / Grep:** Check if logs are written simultaneously to a persistent file in `data/logs/`.
* **Prescribed Solution & Code Pattern:**  
  Implement tee logging to `data/logs/app.log` and provide a 1-click "Open Log File" button in the Settings interface.
* **Verification Metric:** Complete runtime diagnostic trail available at all times.

---

## 🎯 Audit Scorecard
* **Total Checks:** 34
* **Passed / Implemented:** `___ / 34`
* **Audit Completed By:** `________________`
* **Date:** `________________`
