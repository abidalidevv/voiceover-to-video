# VideoGen — Master Build Document

Single reference file: project spec, architecture, decisions, risks, ground rules, and a ready-to-paste prompt for every build phase. This supersedes the earlier separate files for day-to-day use — keep those in the repo for history, but work from this one.

---

## 1. Project Summary

Desktop app (Electron) that turns **voiceover audio + niche** into a finished YouTube video: transcribes the audio, semantically matches stock footage (fetched live from Pexels/Pixabay) to what's being said, adds CapCut-style animated captions, gives a live editable preview before export, and renders Full HD in **both 16:9 and 9:16**. Built for a team, not a single user.

## 2. Final Architecture

```
Electron shell (React + TypeScript + Tailwind)
        │  HTTP/WebSocket
        ▼
FastAPI backend (Python)
├── Project service (SQLite)
├── Transcription (faster-whisper, word-level timestamps)
├── Scene planner (semantic segmentation + visual intent; LLM used only here — never for deterministic media steps)
├── Stock provider registry (Pexels / Pixabay adapters, normalized schema, license metadata)
├── Candidate scoring + fallback hierarchy + duplicate avoidance
├── asyncio worker pool (parallel download, bounded concurrency, retry w/ backoff)
├── Composition JSON (single source of truth for preview AND final render — resolution-aware: 1920x1080 and 1080x1920)
├── Caption engine (ASS/libass, JSON style template)
└── FFmpeg renderer (normalize clips → concat → caption burn-in → mux audio → GPU encode where available)
```

## 3. Key Decisions (locked in — don't relitigate these mid-build)

| Decision | Choice | Why |
|---|---|---|
| Desktop shell | Electron | Confirmed choice, despite the packaging overhead vs. a web app |
| Output formats | Both 16:9 and 9:16 | Confirmed requirement — composition engine must be resolution-aware from Phase 1, not bolted on later |
| Job queue | asyncio + bounded worker pool | Redis/Celery adds operational complexity not needed for an internal desktop tool at this scale; revisit only if team usage actually saturates it |
| Stock providers (v1) | Pexels + Pixabay only | Add more later through the same adapter interface; don't start with 5+ |
| Fallback footage | Last resort only, never default | Must be visibly logged as a fallback, never presented as if it were live stock footage |
| Caption rendering | ASS/libass burned in via ffmpeg | Native karaoke/word-highlight support, proven and fast |

## 4. Known Risks — keep these live throughout the build

- **YouTube monetization policy**: as of the July 15, 2025 policy update, "inauthentic content" (mass-produced/templated, little variation between videos) is ineligible for monetization — this is the exact profile this tool can produce if not careful. Mitigation built into the plan: duplicate/repetition avoidance at the project level, and scripts should stay substantively original — the tool automates assembly, not the writing.
- **Stock API licensing terms** for automated bulk fetch + monetized YouTube use — check Pexels' and Pixabay's current terms directly before production use; not yet verified.
- **Rate limits** on free API tiers under team-scale concurrent use — plan for key rotation/pooling if more than one or two people generate videos at once.
- **Antigravity's earlier build session claimed completion without real verification** — see Ground Rules below. Any code already scaffolded from that session (`stock_downloader.py` etc.) must be audited before reuse: confirm it calls real Pexels/Pixabay APIs and doesn't quietly default to the `studio_cinematic` fallback.
- **Clip normalization** (fps/resolution/codec) before concatenation is required or ffmpeg concat will produce artifacts.

## 5. Ground Rules — apply to every phase, every prompt

1. Never report a feature, phase, or test as "complete" or "verified" without direct, inspectable evidence (real API response logged, real rendered file checked via `ffprobe`, real screenshot of real output). If something hasn't been run end-to-end with real inputs, say so explicitly.
2. Stock footage must come from real, authenticated Pexels/Pixabay calls. No silent fallback to mock/placeholder content presented as live stock footage. Surface API failures clearly instead of papering over them.
3. Never state a specific software version (FFmpeg, Python, libraries) without having actually checked it on this machine. Say "unspecified" or run a check first — don't guess a plausible-sounding number.
4. This must end up a packaged, installable Electron app — not a local Python server opened via a `.bat` file in a browser. If a local dev server is used during development, say so explicitly and confirm Electron packaging is a separate, tracked step.
5. Finish phases in order. After each phase, stop and report exactly what was tested, with what real input, and what the actual output was — before starting the next phase. No batching multiple phases into one "done" report.
6. State assumptions out loud instead of silently proceeding on them.

---

## 6. Phase-by-Phase Prompts

Paste the Ground Rules (Section 5) once at the start of the Antigravity conversation, then use each phase prompt below in order. Don't move to the next phase until the current one's verification checklist is actually satisfied.

### Phase 1 — Foundation

> Build the foundation only: Electron shell, FastAPI skeleton, SQLite project store, a settings/API-key panel (Pexels, Pixabay), and FFmpeg + hardware encoder detection. Check and report the actual installed FFmpeg version — don't state one without checking. Stop after this phase.

**Verify before moving on:** app actually launches as a packaged/dev Electron window (not just a browser tab); settings panel actually saves and reloads a test API key; reported FFmpeg version matches what's actually installed (`ffmpeg -version`).

### Phase 2 — Audio Intelligence

> Implement audio upload, faster-whisper transcription with word-level timestamps, and a transcript viewer in the UI. Use a real voiceover file for testing — not a synthetic/short placeholder. Report the actual transcript output and timestamps.

**Verify:** upload a real voiceover, confirm the displayed transcript duration matches the audio file's actual duration (check with `ffprobe`), spot-check a few word timestamps against the audio by ear.

### Phase 3 — Stock Pipeline

> Implement Pexels and Pixabay adapters behind a common provider interface, normalized asset schema (id, url, width, height, duration, fps, orientation, license info), orientation filtering, local caching, and retry with backoff. Do not use or default to any mock/fallback provider in this phase.

**Verify:** show the actual raw API response from a real Pexels and a real Pixabay call for a test query, with real asset IDs and URLs — not `studio_cinematic` or any placeholder. Confirm license metadata is stored per downloaded asset.

### Phase 4 — Visual Intelligence

> Implement scene segmentation (semantic, not per-sentence), visual-intent/search-query generation, candidate scoring, the fallback hierarchy (exact → related → niche → generic → filler), and duplicate/repetition avoidance at the project level.

**Verify:** show the actual scene-plan JSON generated from a real transcript, with real generated search queries per scene. Demonstrate duplicate avoidance actually rejecting a repeated asset in one real run.

### Phase 5 — Timeline & Basic Render

> Build the composition JSON model and a basic renderer: normalize downloaded clips (scale/fps/pixel format), assemble to match audio duration, export plain HD video with no captions yet, for both 16:9 and 9:16.

**Verify:** produce two real exported files (16:9 and 9:16) from one real audio input. Confirm via `ffprobe` that duration matches the source audio and resolution is correct for each. Confirm the clips used are traceable back to real downloaded stock assets from Phase 3.

### Phase 6 — Captions

> Implement the ASS/libass caption engine with word-highlight timing, burned into the video via ffmpeg.

**Verify:** provide frame screenshots showing burned-in captions on a real render, and confirm word-highlight timing lines up with the audio at a few spot-checked timestamps.

### Phase 7 — Preview Editor

> Build the live preview: style controls (font, size, color, stroke, active-word color, animation, position) that update instantly without a re-render, plus scene/clip swap.

**Verify:** screenshots or a screen recording of a real style change reflected live in the preview. Confirm a scene swap actually changes that scene's clip in the underlying composition JSON, not just visually.

### Phase 8 — Final Rendering Hardening

> Add GPU-accelerated encoding with CPU fallback, cancel/resume for long jobs, autosave/project recovery, and quality gates (file exists, decodable, minimum duration/resolution, orientation correct).

**Verify:** demonstrate an actual cancelled-and-resumed job. Demonstrate a quality gate actually rejecting a deliberately bad/corrupt test file.

### Phase 9 — Team Production Features

> Add job history, per-user/per-key usage tracking, and niche/brand presets.

**Verify:** show real job history entries from more than one simulated run, and real per-key usage counts logged, not placeholder numbers.

---

## 7. If a phase report looks wrong

If a "complete" report doesn't include the specific evidence the verification checklist asks for, don't accept it — ask directly: *"Show me the actual [API response / ffprobe output / screenshot] for this, not a summary."* This is the same check that caught the Antigravity session's overclaiming the first time; apply it every phase, not just once.
