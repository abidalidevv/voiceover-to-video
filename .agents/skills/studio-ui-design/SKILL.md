---
name: studio-ui-design
description: Master UI/UX design skill for crafting world-class, premium dark-mode desktop applications (DaVinci Resolve, Linear, and Obsidian aesthetic) with glassmorphism, micro-animations, high-contrast readability, standardized button metrics, and zero-scroll studio layouts. Activate this skill whenever designing, building, or styling web apps, HTML, CSS, frontend components, or layouts.
---

# 🎨 Studio UI/UX Master Design System

A battle-tested design framework engineered to produce **$10,000-tier, jaw-dropping desktop and web applications**. Eliminates cheap-looking bootstrap templates and generic colors in favor of a sleek, dark obsidian aesthetic inspired by DaVinci Resolve, Linear, and Adobe Premiere Pro.

---

## 1. 🌌 Obsidian Color Palette (CSS Variables)

Never use raw black (`#000000`) or generic CSS colors. Always use curated, harmonious dark tokens with subtle elevation:

```css
:root {
  /* Surfaces & Elevation */
  --bg-dark: #090c10;          /* Deepest canvas background */
  --bg-surface: #0f131a;       /* Main panel surface */
  --bg-card: #151b26;          /* Elevated card container */
  --bg-card-sub: #1c2433;      /* Nested element / sub-card */
  --bg-glass: rgba(15, 19, 26, 0.75); /* Frosted glass with blur */

  /* Borders & Glows */
  --border-subtle: rgba(255, 255, 255, 0.08); /* Crisp separator */
  --border-focus: rgba(59, 130, 246, 0.40);   /* Active outline */
  --glow-cyan: 0 0 20px rgba(0, 240, 255, 0.25);
  --glow-blue: 0 0 20px rgba(59, 130, 246, 0.25);

  /* Curated Accent Colors */
  --accent-cyan: #00f0ff;      /* Electric Cyan (Tech, energy) */
  --accent-blue: #3b82f6;      /* Studio Blue (Primary actions) */
  --accent-purple: #8b5cf6;    /* Deep Violet (Creative, AI) */
  --accent-green: #10b981;     /* Emerald (Success, ready) */
  --accent-amber: #f59e0b;     /* Gold / Amber (Warning, pro) */
  --accent-rose: #f43f5e;      /* Punch Red (Destructive) */

  /* Razor-Sharp Text Contrast */
  --text-primary: #ffffff;     /* 100% Solid White (Titles, badges) */
  --text-secondary: #cbd5e1;   /* Crisp Silver Slate (Body, labels) */
  --text-muted: #64748b;       /* Muted Slate (Hints, shortcuts) */

  /* Radii & Shadows */
  --radius-xs: 6px;
  --radius-sm: 8px;
  --radius-md: 12px;
  --radius-lg: 16px;
  --shadow-card: 0 8px 32px rgba(0, 0, 0, 0.45);
}
```

---

## 2. 🔤 Modern Typography Hierarchy

Never rely on browser default fonts (Times, Arial). Always import and pair modern fonts:

* **Primary Interface Font**: `Inter` or `Plus Jakarta Sans` (ultra-clean, legible at micro-sizes).
* **Display / Brand Headers**: `Montserrat` (weight 800/900) or `Outfit`.
* **Metrics, Counters & Code**: `JetBrains Mono` or `Space Grotesk`.

### Text Readability Rules:
1. **No Muddy Grey Text**: Titles, card headers, and button labels must be **pure white (`#ffffff`)**.
2. **Text Stroke Fix**: When drawing text with outlines, always use `paint-order: stroke fill;` and `-webkit-text-stroke` to prevent stroke bleeding into letters.
3. **Leading & Tracking**: Use tight letter-spacing (`letter-spacing: -0.02em`) on large headings for an authoritative, modern feel.

---

## 3. 🔘 Standardized Button Metrics & Alignment

Buttons make or break a UI. Follow strict height metrics and centering:

| Button Class | Exact Height | Font Size | Padding | Use Case |
| :--- | :--- | :--- | :--- | :--- |
| `.btn-lg` (Hero) | `46px` | `15px / 700` | `0 24px` | Primary Export / Render buttons |
| `.btn-md` (Default) | `38px` | `13px / 600` | `0 18px` | Standard studio actions |
| `.btn-sm` (Compact) | `32px` | `12px / 600` | `0 14px` | Card actions, tab pills, swaps |
| `.btn-icon` (Square) | `36px × 36px` | `16px` | `0` | Header tool icons, close buttons |

### Universal Button CSS Rule:
```css
.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  border-radius: var(--radius-sm);
  font-family: 'Inter', sans-serif;
  line-height: 1;
  cursor: pointer;
  transition: all 0.18s cubic-bezier(0.4, 0, 0.2, 1);
  white-space: nowrap;
  user-select: none;
}

/* Active Click Feedback (Instant tactile feel) */
.btn:active {
  transform: scale(0.97);
}
```

---

## 4. ✨ Dynamic Micro-Animations & Glassmorphism

Static UIs feel cheap; dynamic UIs feel alive. Implement these subtle touches:

### 1. Tactile Card Hover
```css
.card {
  background: var(--bg-card);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-md);
  transition: transform 0.25s ease, border-color 0.25s ease, box-shadow 0.25s ease;
}

.card:hover {
  transform: translateY(-2px);
  border-color: rgba(59, 130, 246, 0.35);
  box-shadow: 0 12px 28px rgba(0, 0, 0, 0.5), 0 0 16px rgba(59, 130, 246, 0.15);
}
```

### 2. Live Pulsing Worker / Status Badges
```css
@keyframes pulseGlow {
  0% { box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.6); }
  70% { box-shadow: 0 0 0 8px rgba(16, 185, 129, 0); }
  100% { box-shadow: 0 0 0 0 rgba(16, 185, 129, 0); }
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--accent-green);
  animation: pulseGlow 2s infinite;
}
```

### 3. Glassmorphic Modal & Floating Dock
```css
.glass-dock {
  background: rgba(15, 19, 26, 0.82);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border: 1px solid rgba(255, 255, 255, 0.12);
  box-shadow: 0 20px 50px rgba(0, 0, 0, 0.6);
}
```

---

## 5. 🖥️ Zero-Scroll Studio Layout Rules

For professional editing and video studio tools:
1. **Fixed Viewport Height**: Target `height: calc(100vh - 64px)` with `overflow: hidden` on the main window.
2. **Contained 16:9 Video Player**: Use `aspect-ratio: 16/9; max-height: 100%; object-fit: contain;` so the player automatically scales down to fit laptop screens without vertical page scrolling.
3. **Sticky Inspector Footers**: Action buttons (`Export Video`, `Save Settings`) must be pinned with `position: sticky; bottom: 0;` so the user never has to scroll down to find the render button.

---

## 6. 🚫 Critical Design Don'ts (Anti-Patterns)
- ❌ **No Pure Red/Green/Blue**: Don't use `#ff0000` or `#00ff00`. Use tailored HSL hexes like `#f43f5e` (Rose) and `#10b981` (Emerald).
- ❌ **No Harsh 1px Black Borders**: In dark mode, black borders are invisible. Use translucent white borders: `rgba(255, 255, 255, 0.08)`.
- ❌ **No Unpadded Dropzones**: Always give file upload dropzones dashed glowing borders, smooth hover animations, and friendly micro-instructions.
- ❌ **No Flash of Unstyled Content (FOUC)**: Use smooth `@keyframes fadeIn` transitions when switching between studio tabs.
