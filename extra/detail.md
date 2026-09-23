[VIDEOGEN_MASTER_BUILD_DOCUMENT.md](file;file:///c%3A/Users/Abid/Desktop/vg/VIDEOGEN_MASTER_BUILD_DOCUMENT.md)  You are building "VideoGen" — a desktop application that turns a voiceover audio file + niche selection into a finished YouTube video, using stock footage fetched live from multiple stock-video APIs (Pexels, Pixabay), with CapCut-style animated captions, an editable live preview, and Full HD export in both 16:9 and 9:16.

Full specification and architecture decisions are in the attached files — read both fully before writing any code:

1. [VIDEOGEN_FINAL_CONSOLIDATED_PLAN.md]
2. [the second file]

GROUND RULES — these override any default behavior:

1. Never report a feature, phase, or test as "complete" or "verified" unless you have direct, inspectable evidence (actual API response logged, actual rendered file with real duration/resolution checked via ffprobe, actual screenshot of the real output). If you have not run something end-to-end with real inputs, say so explicitly instead of implying it works.

2. Stock footage must come from real, authenticated Pexels/Pixabay API calls. Do not build or silently fall back to a placeholder/mock provider (e.g. a "studio" or "cinematic" internal asset set) and present its output as if it were live stock footage. If real API calls fail, surface the failure clearly — do not paper over it with fallback content.

3. Do not state specific software version numbers (FFmpeg, Python, libraries) unless you have actually checked the installed version on this machine. If you haven't checked, say "unspecified" or check it first with a command, don't guess a plausible-sounding number.

4. This must end up as an actual installable/packaged Electron desktop application — not a Python server that a user starts via a batch file and accesses through a browser tab. If you build the backend as a local server for development convenience, say so explicitly, and confirm packaging into Electron is a separate, not-yet-done step.

5. Follow the build phases in the plan file in order. After finishing each phase, stop and report: what was actually tested, with what real input, and what the output was — before starting the next phase. Do not batch multiple phases into one "done" report.

6. If you are uncertain whether something works, or you're making an assumption to keep moving, state the assumption out loud rather than silently proceeding as if it were confirmed.

FIRST TASK: Start with Phase 1 (Foundation) only — Electron shell, FastAPI skeleton, SQLite project store, settings/API-key panel, and FFmpeg + hardware encoder detection (check and report the actual installed FFmpeg version). Stop after this phase and report status before continuing to Phase 2.

<https://github.com/abidalidevv/VideoGen>

ye repo dekh o is main kuch research hy
Groq Api
YOUR_GROQ_API_KEY

pexel api
YOUR_PEXELS_API_KEY

pixabay
YOUR_PIXABAY_API_KEY

