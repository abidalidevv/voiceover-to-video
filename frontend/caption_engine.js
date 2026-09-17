/**
 * CaptionEngine: Synchronizes and renders CapCut-style animated kinetic subtitles
 * in real-time over the preview video player.
 */

class CaptionEngine {
  constructor(overlayContainerId, textElementId) {
    this.overlay = document.getElementById(overlayContainerId);
    this.captionEl = document.getElementById(textElementId);
    
    this.currentScenes = [];
    this.wordChunks = []; // Precomputed chunks with word timestamps

    // Active style state
    this.style = {
      preset: 'capcut_yellow',
      fontFamily: 'Montserrat',
      fontSize: 24,
      primaryColor: '#ffffff',
      highlightColor: '#ffe010',
      strokeColor: '#000000',
      strokeWidth: 4,
      marginV: 24,
      letterSpacing: 1,
      wordSpacing: 6,
      uppercase: true,
      animation: 'word_bounce'
    };

    this.lastRenderedChunkIdx = -1;
    this.lastRenderedWordIdx = -1;
  }

  loadScenes(scenes) {
    this.currentScenes = scenes || [];
    this.wordChunks = [];

    // Pre-calculate chunks of 3-5 words across all scenes
    for (const sc of this.currentScenes) {
      const words = sc.words || [];
      if (words.length === 0) {
        // Scene without words - use whole text
        this.wordChunks.push({
          start: sc.start,
          end: sc.end,
          text: sc.text,
          words: []
        });
        continue;
      }

      let currentChunk = [];
      for (const w of words) {
        currentChunk.push(w);
        const txt = w.word || '';
        if (currentChunk.length >= 4 || /[.!?,;]/.test(txt)) {
          this.wordChunks.push({
            start: currentChunk[0].start,
            end: currentChunk[currentChunk.length - 1].end,
            words: [...currentChunk]
          });
          currentChunk = [];
        }
      }
      if (currentChunk.length > 0) {
        this.wordChunks.push({
          start: currentChunk[0].start,
          end: currentChunk[currentChunk.length - 1].end,
          words: [...currentChunk]
        });
      }
    }
  }

  updateStyle(newStyle) {
    this.style = { ...this.style, ...newStyle };
    this.applyContainerStyles();
    // Force re-render of current caption
    this.lastRenderedWordIdx = -1;
    this.lastRenderedChunkIdx = -1;
  }

  applyContainerStyles() {
    if (!this.overlay || !this.captionEl) return;

    const marginV = this.style.marginV !== undefined ? this.style.marginV : 26;
    this.overlay.style.bottom = `${marginV}px`;
    this.captionEl.style.fontFamily = `'${this.style.fontFamily}', sans-serif`;
    const baseFontSize = this.style.fontSize || 24;
    this.captionEl.style.fontSize = `${baseFontSize}px`;
    this.captionEl.style.setProperty('--caption-font-size', `${baseFontSize}px`);
    this.captionEl.style.color = this.style.primaryColor;
    // Do NOT apply stroke to the container, as it double-strokes child words
    this.captionEl.style.webkitTextStroke = '0px transparent';

    const lSpacing = this.style.letterSpacing !== undefined ? this.style.letterSpacing : 1;
    const wSpacing = this.style.wordSpacing !== undefined ? this.style.wordSpacing : 6;
    this.captionEl.style.setProperty('--caption-letter-spacing', `${lSpacing}px`);
    this.captionEl.style.setProperty('--caption-word-spacing', `${wSpacing}px`);
    this.captionEl.style.letterSpacing = `${lSpacing}px`;
    this.captionEl.style.wordSpacing = `${wSpacing}px`;

    if (this.style.uppercase) {
      this.captionEl.style.textTransform = 'uppercase';
    } else {
      this.captionEl.style.textTransform = 'none';
    }
  }

  /**
   * Enables interactive mouse & touch drag on video player to adjust vertical position
   */
  enableDrag(onPositionChange) {
    if (!this.overlay) return;
    this.overlay.classList.add('draggable');

    let isDragging = false;
    let startY = 0;
    let startBottom = 0;

    const onStart = (e) => {
      // Allow clicking buttons if any, otherwise start dragging
      isDragging = true;
      this.overlay.classList.add('dragging');
      const clientY = e.touches ? e.touches[0].clientY : e.clientY;
      startY = clientY;
      startBottom = parseInt(this.overlay.style.bottom || '24', 10);
      e.stopPropagation();
    };

    const onMove = (e) => {
      if (!isDragging) return;
      const clientY = e.touches ? e.touches[0].clientY : e.clientY;
      const deltaY = startY - clientY; // dragging upward increases bottom offset
      const container = this.overlay.parentElement;
      const containerH = container ? container.clientHeight : 400;
      const maxBottom = Math.max(120, containerH - 60);
      const newBottom = Math.max(10, Math.min(maxBottom, Math.round(startBottom + deltaY)));

      this.overlay.style.bottom = `${newBottom}px`;
      this.style.marginV = newBottom;

      if (onPositionChange) {
        onPositionChange(newBottom);
      }
    };

    const onEnd = () => {
      if (isDragging) {
        isDragging = false;
        this.overlay.classList.remove('dragging');
      }
    };

    this.overlay.addEventListener('mousedown', onStart);
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onEnd);

    this.overlay.addEventListener('touchstart', onStart, { passive: true });
    window.addEventListener('touchmove', onMove, { passive: true });
    window.addEventListener('touchend', onEnd);
  }

  /**
   * Called on every video timeupdate / animation frame
   */
  renderAtTime(currentTime) {
    if (!this.captionEl || this.wordChunks.length === 0) return;

    // Find active chunk
    const chunkIdx = this.wordChunks.findIndex(c => currentTime >= c.start && currentTime <= c.end);
    if (chunkIdx === -1) {
      this.captionEl.innerHTML = '';
      this.lastRenderedChunkIdx = -1;
      return;
    }

    const chunk = this.wordChunks[chunkIdx];

    // If chunk has no word timestamps, display plain text
    if (chunk.words.length === 0) {
      if (this.lastRenderedChunkIdx !== chunkIdx) {
        this.captionEl.textContent = chunk.text || '';
        this.lastRenderedChunkIdx = chunkIdx;
      }
      return;
    }

    // Find active word in this chunk
    let activeWordIdx = chunk.words.findIndex(w => currentTime >= w.start && currentTime <= w.end);
    if (activeWordIdx === -1) {
      // Pick closest before or first
      activeWordIdx = chunk.words.reduce((closest, w, i) => (w.start <= currentTime ? i : closest), 0);
    }

    // Only redraw DOM if active word or chunk changed
    if (this.lastRenderedChunkIdx === chunkIdx && this.lastRenderedWordIdx === activeWordIdx) {
      return;
    }

    this.lastRenderedChunkIdx = chunkIdx;
    this.lastRenderedWordIdx = activeWordIdx;

    const strokeStyle = this.style.strokeWidth > 0 
      ? `-webkit-text-stroke: ${this.style.strokeWidth}px ${this.style.strokeColor}; paint-order: stroke fill;`
      : `-webkit-text-stroke: 0px transparent;`;

    // Render HTML words with kinetic styling & CSS keyframe animation classes
    const htmlParts = chunk.words.map((w, idx) => {
      const isActive = idx === activeWordIdx;
      const rawText = w.word || '';

      if (isActive) {
        if (this.style.animation === 'word_box') {
          return `<span class="caption-word active box-style anim-box" style="background:${this.style.highlightColor}; color:#000000 !important; -webkit-text-fill-color:#000000 !important; -webkit-text-stroke: 0px !important;">${rawText}</span>`;
        } else if (this.style.animation === 'word_glow') {
          return `<span class="caption-word active anim-glow" style="color:${this.style.highlightColor}; -webkit-text-fill-color:${this.style.highlightColor}; ${strokeStyle} text-shadow: 0 0 16px ${this.style.highlightColor};">${rawText}</span>`;
        } else if (this.style.animation === 'fade_in') {
          return `<span class="caption-word active anim-fade" style="color:${this.style.highlightColor}; -webkit-text-fill-color:${this.style.highlightColor}; ${strokeStyle}">${rawText}</span>`;
        } else {
          // Default: CapCut kinetic pop & bounce
          return `<span class="caption-word active anim-bounce" style="color:${this.style.highlightColor}; -webkit-text-fill-color:${this.style.highlightColor}; ${strokeStyle}">${rawText}</span>`;
        }
      } else {
        return `<span class="caption-word" style="color:${this.style.primaryColor}; -webkit-text-fill-color:${this.style.primaryColor}; ${strokeStyle}">${rawText}</span>`;
      }
    });

    this.captionEl.innerHTML = htmlParts.join(' ');
  }
}

// Attach to window
window.CaptionEngine = CaptionEngine;
