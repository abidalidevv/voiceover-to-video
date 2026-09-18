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
    this.enabled = true; // Master toggle for captions (Default: ON)

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

    // Force initial render of first scene chunk
    this.lastRenderedChunkIdx = -1;
    this.lastRenderedWordIdx = -1;
    const curTime = (typeof currentPlaybackTime !== 'undefined') ? currentPlaybackTime : 0.0;
    this.renderAtTime(curTime);
  }

  updateStyle(newStyle) {
    this.style = { ...this.style, ...newStyle };
    this.applyContainerStyles();
    // Force re-render of current caption
    this.lastRenderedWordIdx = -1;
    this.lastRenderedChunkIdx = -1;
    // Force immediate live re-render at current playback time even when paused
    const curTime = (typeof currentPlaybackTime !== 'undefined') ? currentPlaybackTime : 0.0;
    this.renderAtTime(curTime);
  }

  setEnabled(enabled) {
    this.enabled = Boolean(enabled);
    if (!this.overlay) return;
    if (!this.enabled) {
      this.overlay.style.setProperty('display', 'none', 'important');
      this.overlay.classList.add('hidden');
    } else {
      this.overlay.classList.remove('hidden');
      this.overlay.style.setProperty('display', 'flex', 'important');
      this.overlay.style.justifyContent = 'center';
      this.overlay.style.alignItems = 'center';
      this.overlay.style.left = '0';
      this.overlay.style.right = '0';
      this.overlay.style.width = '100%';
      this.overlay.style.textAlign = 'center';
      if (this.captionEl) {
        const offX = this.style.offsetX || 0;
        this.captionEl.style.transform = offX ? `translateX(${offX}px)` : 'none';
      }
      const curTime = (typeof currentPlaybackTime !== 'undefined') ? currentPlaybackTime : 0.0;
      this.lastRenderedChunkIdx = -1;
      this.lastRenderedWordIdx = -1;
      this.renderAtTime(curTime);
    }
  }

  applyContainerStyles() {
    if (!this.overlay || !this.captionEl) return;

    if (!this.enabled) {
      this.overlay.style.setProperty('display', 'none', 'important');
      this.overlay.classList.add('hidden');
    } else {
      this.overlay.classList.remove('hidden');
      this.overlay.style.setProperty('display', 'flex', 'important');
      this.overlay.style.justifyContent = 'center';
      this.overlay.style.alignItems = 'center';
      this.overlay.style.left = '0';
      this.overlay.style.right = '0';
      this.overlay.style.width = '100%';
      this.overlay.style.textAlign = 'center';
    }

    const marginV = this.style.marginV !== undefined ? this.style.marginV : 24;
    this.overlay.style.setProperty('bottom', `${marginV}px`, 'important');
    this.overlay.style.setProperty('--caption-bottom', `${marginV}px`);

    const offX = this.style.offsetX || 0;
    this.captionEl.style.transform = offX ? `translateX(${offX}px)` : 'none';

    this.captionEl.style.setProperty('font-family', `'${this.style.fontFamily}', sans-serif`, 'important');
    const baseFontSize = this.style.fontSize || 24;
    this.captionEl.style.setProperty('font-size', `${baseFontSize}px`, 'important');
    this.captionEl.style.setProperty('--caption-font-size', `${baseFontSize}px`);
    this.captionEl.style.setProperty('color', this.style.primaryColor, 'important');
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
   * Enables interactive 2D mouse & touch drag on video player to adjust vertical and horizontal position
   */
  enableDrag(onPositionChange) {
    if (!this.overlay) return;
    this.overlay.classList.add('draggable');

    let isDragging = false;
    let startX = 0;
    let startY = 0;
    let startBottom = 0;
    let startOffsetX = 0;

    const onStart = (e) => {
      isDragging = true;
      this.overlay.classList.add('dragging');
      const clientX = e.touches ? e.touches[0].clientX : e.clientX;
      const clientY = e.touches ? e.touches[0].clientY : e.clientY;
      startX = clientX;
      startY = clientY;
      const parsed = parseInt(this.overlay.style.bottom || '', 10);
      startBottom = Number.isFinite(parsed) ? parsed : (this.style.marginV || 24);
      startOffsetX = this.style.offsetX || 0;
      e.stopPropagation();
      if (e.cancelable && e.type !== 'touchstart') {
        e.preventDefault();
      }
    };

    const onMove = (e) => {
      if (!isDragging) return;
      const clientX = e.touches ? e.touches[0].clientX : e.clientX;
      const clientY = e.touches ? e.touches[0].clientY : e.clientY;
      const deltaX = clientX - startX;
      const deltaY = startY - clientY; // dragging upward increases bottom offset

      const container = this.overlay.parentElement;
      const containerW = container ? container.clientWidth : 640;
      const containerH = container ? container.clientHeight : 368;
      const maxBottom = Math.max(80, containerH - 45);
      const newBottom = Math.max(10, Math.min(maxBottom, Math.round(startBottom + deltaY)));

      const maxOffsetX = Math.max(60, Math.floor(containerW / 2 - 40));
      const newOffsetX = Math.max(-maxOffsetX, Math.min(maxOffsetX, Math.round(startOffsetX + deltaX)));

      this.overlay.style.setProperty('bottom', `${newBottom}px`, 'important');
      this.overlay.style.setProperty('--caption-bottom', `${newBottom}px`);
      this.style.marginV = newBottom;

      this.style.offsetX = newOffsetX;
      if (this.captionEl) {
        this.captionEl.style.transform = `translateX(${newOffsetX}px)`;
      }

      if (onPositionChange) {
        onPositionChange(newBottom, newOffsetX);
      }
    };

    const onEnd = () => {
      if (isDragging) {
        isDragging = false;
        this.overlay.classList.remove('dragging');
      }
    };

    const onDoubleClick = (e) => {
      e.stopPropagation();
      this.style.offsetX = 0;
      if (this.captionEl) {
        this.captionEl.style.transform = 'none';
      }
      if (onPositionChange) {
        onPositionChange(this.style.marginV || 24, 0);
      }
      if (typeof showToast === 'function') {
        showToast('🎯 Subtitles re-centered horizontally');
      }
    };

    this.overlay.addEventListener('mousedown', onStart);
    this.overlay.addEventListener('dblclick', onDoubleClick);
    if (this.captionEl) {
      this.captionEl.addEventListener('mousedown', onStart);
      this.captionEl.addEventListener('dblclick', onDoubleClick);
    }
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onEnd);

    this.overlay.addEventListener('touchstart', onStart, { passive: true });
    if (this.captionEl) {
      this.captionEl.addEventListener('touchstart', onStart, { passive: true });
    }
    window.addEventListener('touchmove', onMove, { passive: true });
    window.addEventListener('touchend', onEnd);
  }

  /**
   * Called on every video timeupdate / animation frame
   */
  renderAtTime(currentTime) {
    if (!this.enabled) {
      if (this.overlay) {
        this.overlay.style.setProperty('display', 'none', 'important');
        this.overlay.classList.add('hidden');
      }
      return;
    }
    if (this.overlay && (this.overlay.style.display === 'none' || this.overlay.classList.contains('hidden'))) {
      this.overlay.classList.remove('hidden');
      this.overlay.style.setProperty('display', 'flex', 'important');
      this.overlay.style.justifyContent = 'center';
      this.overlay.style.alignItems = 'center';
      this.overlay.style.left = '0';
      this.overlay.style.right = '0';
      this.overlay.style.width = '100%';
    }
    if (!this.captionEl) return;

    if (this.wordChunks.length === 0) {
      // Fallback: If scenes are loaded but wordChunks empty, check current scene
      if (this.currentScenes && this.currentScenes.length > 0 && typeof currentSceneIdx !== 'undefined' && currentSceneIdx >= 0) {
        const sc = this.currentScenes[currentSceneIdx];
        if (sc && sc.text) {
          this.captionEl.textContent = this.style.uppercase ? sc.text.toUpperCase() : sc.text;
        }
      }
      return;
    }

    // Find active chunk
    let chunkIdx = this.wordChunks.findIndex(c => currentTime >= c.start && currentTime <= c.end);
    if (chunkIdx === -1) {
      // When paused or seeking between words, find closest chunk so preview is NEVER empty
      let minDiff = Infinity;
      let closestIdx = 0;
      for (let i = 0; i < this.wordChunks.length; i++) {
        const c = this.wordChunks[i];
        const diff = Math.min(Math.abs(currentTime - c.start), Math.abs(currentTime - c.end));
        if (diff < minDiff) {
          minDiff = diff;
          closestIdx = i;
        }
      }
      chunkIdx = closestIdx;
    }

    const chunk = this.wordChunks[chunkIdx];
    if (!chunk) return;

    // If chunk has no word timestamps, display plain text
    if (!chunk.words || chunk.words.length === 0) {
      const raw = chunk.text || '';
      this.captionEl.textContent = this.style.uppercase ? raw.toUpperCase() : raw;
      this.lastRenderedChunkIdx = chunkIdx;
      return;
    }

    // Find active word in this chunk
    let activeWordIdx = chunk.words.findIndex(w => currentTime >= w.start && currentTime <= w.end);
    if (activeWordIdx === -1) {
      // Pick closest word before or first word of chunk
      activeWordIdx = chunk.words.reduce((closest, w, i) => (w.start <= currentTime ? i : closest), 0);
    }

    // Only redraw DOM if active word or chunk changed, OR if forced (-1)
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
      let rawText = w.word || '';
      if (this.style.uppercase) {
        rawText = rawText.toUpperCase();
      }

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
