/**
 * VideoGen Studio Desktop Application Logic
 */

let currentProject = null;
let activePipeline = 'Main';
let selectedAudioFile = null;
let uploadedAudioData = null;
let captionEngine = null;

// Multi-clip timeline playback manager
let isPlaying = false;
let currentPlaybackTime = 0.0;
let totalDuration = 0.0;
let playbackTimer = null;
let currentSceneIdx = -1;
let swapTargetSceneId = null;

document.addEventListener('DOMContentLoaded', async () => {
  captionEngine = new CaptionEngine('subtitle-overlay', 'subtitle-text');
  captionEngine.applyContainerStyles();

  setupDropzone();
  await loadSettings();
  await checkApiStatus();
  await loadProjectsLibrary();

  // If there is an existing project in library, auto-initialize it in preview editor
  try {
    const res = await fetch('/api/projects');
    const projects = await res.json();
    if (projects && projects.length > 0) {
      currentProject = projects[0];
      loadProjectIntoPreview(currentProject);
    }
  } catch (e) {}
});

// ==================== TAB MANAGEMENT ====================
function switchTab(tabId) {
  document.querySelectorAll('.tab-pane').forEach(el => el.classList.remove('active'));
  document.querySelectorAll('.nav-btn').forEach(el => el.classList.remove('active'));

  const targetPane = document.getElementById(`tab-${tabId}`);
  const targetBtn = document.getElementById(`tab-${tabId}-btn`);
  if (targetPane) targetPane.classList.add('active');
  if (targetBtn) targetBtn.classList.add('active');

  if (tabId === 'library') {
    loadProjectsLibrary();
  }
}

function selectPipeline(pipe) {
  activePipeline = pipe;
  document.querySelectorAll('.pipeline-btn').forEach(b => b.classList.remove('active'));
  const btn = document.getElementById(`pipe-${pipe.toLowerCase()}`);
  if (btn) btn.classList.add('active');
}

// ==================== SETTINGS & API STATUS ====================
function handleWorkerSliderChange(val) {
  const num = parseInt(val, 10);
  document.getElementById('workers-slider-val').textContent = num;
  const powerLabel = document.getElementById('workers-power-label');
  const descEl = document.getElementById('workers-recommend-desc');

  if (num <= 4) {
    if (powerLabel) { powerLabel.textContent = '🟢 Low CPU / Dual-Core'; powerLabel.style.color = '#10b981'; }
    if (descEl) descEl.textContent = 'Gentle resource usage for Dual/Quad Core CPUs and integrated Intel UHD graphics. Prevents system slowdown.';
  } else if (num <= 8) {
    if (powerLabel) { powerLabel.textContent = '⚡ Standard Multi-Core'; powerLabel.style.color = '#00f0ff'; }
    if (descEl) descEl.textContent = 'Recommended for 6-8 core CPUs (i5 / i7 / Ryzen 5/7) and GTX 1650 / RTX 3050. Fast concurrent downloads and smooth parallel normalization.';
  } else if (num <= 16) {
    if (powerLabel) { powerLabel.textContent = '🚀 High Performance GPU'; powerLabel.style.color = '#f59e0b'; }
    if (descEl) descEl.textContent = 'High-speed profile for 8-16 core CPUs and RTX 3060 / 3070 / 4060 GPUs. Parallel downloads across stock APIs complete in seconds.';
  } else {
    if (powerLabel) { powerLabel.textContent = '🔥 Extreme Beast Mode'; powerLabel.style.color = '#ef4444'; }
    if (descEl) descEl.textContent = 'Maximum throughput for 16+ core CPUs, AMD Threadripper, and RTX 3080 / 4080 / 4090 GPUs. Blazing parallel 1080p stream processing!';
  }
}

async function loadSettings() {
  try {
    const res = await fetch('/api/settings');
    const data = await res.json();

    // 10+ Stock Video APIs
    if (document.getElementById('input-pexels-key')) document.getElementById('input-pexels-key').value = data.pexels_api_key || '';
    if (document.getElementById('input-pixabay-key')) document.getElementById('input-pixabay-key').value = data.pixabay_api_key || '';
    if (document.getElementById('input-coverr-key')) document.getElementById('input-coverr-key').value = data.coverr_api_key || '';
    if (document.getElementById('input-videvo-key')) document.getElementById('input-videvo-key').value = data.videvo_api_key || '';
    if (document.getElementById('input-nasa-key')) document.getElementById('input-nasa-key').value = data.nasa_api_key || '';
    if (document.getElementById('input-wiki-enabled')) document.getElementById('input-wiki-enabled').checked = data.wikimedia_video_enabled !== false;
    if (document.getElementById('input-mixkit-key')) document.getElementById('input-mixkit-key').value = data.mixkit_api_key || '';
    if (document.getElementById('input-freepik-key')) document.getElementById('input-freepik-key').value = data.freepik_api_key || '';
    if (document.getElementById('input-rapidapi-key')) document.getElementById('input-rapidapi-key').value = data.rapidapi_stock_key || '';
    if (document.getElementById('input-custom-webhook')) document.getElementById('input-custom-webhook').value = data.custom_stock_webhook || '';

    // AI & Transcription
    if (document.getElementById('input-groq-key')) document.getElementById('input-groq-key').value = data.groq_api_key || '';
    if (document.getElementById('input-openai-key')) document.getElementById('input-openai-key').value = data.openai_api_key || '';

    // Tuner & Strategy
    if (document.getElementById('input-hardware-encoder')) document.getElementById('input-hardware-encoder').value = data.hardware_encoder || 'auto';
    if (document.getElementById('input-video-provider')) document.getElementById('input-video-provider').value = data.video_provider || 'all';
    
    const workers = data.workers || 8;
    if (document.getElementById('input-workers-slider')) {
      document.getElementById('input-workers-slider').value = workers;
      handleWorkerSliderChange(workers);
    }
    const badge = document.getElementById('worker-count-badge');
    if (badge) badge.textContent = `${workers} Workers Ready`;
  } catch (err) {
    console.error('Failed to load settings:', err);
  }
}

async function saveAppSettings() {
  const payload = {
    // 10+ Stock Video APIs
    pexels_api_key: document.getElementById('input-pexels-key')?.value.trim() || '',
    pixabay_api_key: document.getElementById('input-pixabay-key')?.value.trim() || '',
    coverr_api_key: document.getElementById('input-coverr-key')?.value.trim() || '',
    videvo_api_key: document.getElementById('input-videvo-key')?.value.trim() || '',
    nasa_api_key: document.getElementById('input-nasa-key')?.value.trim() || '',
    wikimedia_video_enabled: document.getElementById('input-wiki-enabled')?.checked ?? true,
    mixkit_api_key: document.getElementById('input-mixkit-key')?.value.trim() || '',
    freepik_api_key: document.getElementById('input-freepik-key')?.value.trim() || '',
    rapidapi_stock_key: document.getElementById('input-rapidapi-key')?.value.trim() || '',
    custom_stock_webhook: document.getElementById('input-custom-webhook')?.value.trim() || '',

    // AI & Transcription
    groq_api_key: document.getElementById('input-groq-key')?.value.trim() || '',
    openai_api_key: document.getElementById('input-openai-key')?.value.trim() || '',

    // Performance & Hardware
    hardware_encoder: document.getElementById('input-hardware-encoder')?.value || 'auto',
    video_provider: document.getElementById('input-video-provider')?.value || 'all',
    workers: parseInt(document.getElementById('input-workers-slider')?.value || '8', 10),
    gpu_acceleration: true
  };

  try {
    const res = await fetch('/api/settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    showToast(`💾 Settings and API keys saved successfully! (${payload.workers} Workers Active)`);
    const badge = document.getElementById('worker-count-badge');
    if (badge) badge.textContent = `${payload.workers} Workers Ready`;
  } catch (err) {
    alert('Error saving settings: ' + err.message);
  }
}

async function checkApiStatus() {
  try {
    const res = await fetch('/api/test-apis', { method: 'POST' });
    const data = await res.json();

    updateBadge('badge-pexels', data.pexels);
    updateBadge('badge-pixabay', data.pixabay);
    updateBadge('badge-groq', data.groq);
  } catch (e) {
    console.warn('API check notice:', e);
  }
}

function updateBadge(badgeId, res) {
  const el = document.getElementById(badgeId);
  if (!el) return;
  if (!res || res.status === 'unconfigured') {
    el.className = 'badge badge-warning';
    el.textContent = 'Not Configured';
  } else if (res.status === 'ok') {
    el.className = 'badge badge-success';
    el.textContent = 'Connected ✓';
  } else {
    el.className = 'badge badge-error';
    el.textContent = 'Error';
  }
}

async function testApiConnections() {
  await saveAppSettings();
  alert('Testing connections...');
  await checkApiStatus();
}

function showToast(message) {
  let container = document.getElementById('toast-container');
  if (!container) {
    container = document.createElement('div');
    container.id = 'toast-container';
    container.className = 'toast-container';
    document.body.appendChild(container);
  }
  const toast = document.createElement('div');
  toast.className = 'toast';
  toast.innerHTML = message;
  container.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transition = 'opacity 0.4s';
    setTimeout(() => toast.remove(), 400);
  }, 3500);
}

async function openOutputFolder(customPath = null) {
  try {
    const res = await fetch('/api/open-folder', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path: customPath })
    });
    const data = await res.json();
    const folderName = data.path.split(/[\\/]/).pop() || 'Output';
    showToast(`📂 Opened folder in Windows Explorer: <strong>${folderName}</strong>`);
  } catch (e) {
    console.error(e);
    alert('Could not open folder: ' + e.message);
  }
}

// ==================== AUDIO DROPZONE & UPLOAD ====================
function setupDropzone() {
  const dropzone = document.getElementById('audio-dropzone');

  ['dragenter', 'dragover'].forEach(name => {
    dropzone.addEventListener(name, (e) => {
      e.preventDefault();
      dropzone.classList.add('dragover');
    });
  });

  ['dragleave', 'drop'].forEach(name => {
    dropzone.addEventListener(name, (e) => {
      e.preventDefault();
      dropzone.classList.remove('dragover');
    });
  });

  dropzone.addEventListener('drop', (e) => {
    const files = e.dataTransfer.files;
    if (files.length > 0) {
      uploadAudioFile(files[0]);
    }
  });
}

function handleAudioSelect(event) {
  const files = event.target.files;
  if (files.length > 0) {
    uploadAudioFile(files[0]);
  }
}

async function uploadAudioFile(file) {
  selectedAudioFile = file;
  const formData = new FormData();
  formData.append('file', file);

  const promptEl = document.getElementById('dropzone-prompt');
  const infoEl = document.getElementById('dropzone-fileinfo');

  promptEl.innerHTML = '<div class="modal-spinner" style="width:28px;height:28px;margin-bottom:8px;"></div><h3>Uploading audio file...</h3>';

  try {
    const res = await fetch('/api/upload-audio', {
      method: 'POST',
      body: formData
    });
    uploadedAudioData = await res.json();

    promptEl.classList.add('hidden');
    infoEl.classList.remove('hidden');

    document.getElementById('audio-filename').textContent = uploadedAudioData.original_name;
    const mins = Math.floor(uploadedAudioData.duration / 60);
    const secs = Math.floor(uploadedAudioData.duration % 60);
    document.getElementById('audio-duration-stat').textContent = `⏱ ${mins}:${secs < 10 ? '0' : ''}${secs}`;
    document.getElementById('audio-filesize-stat').textContent = `${(file.size / (1024 * 1024)).toFixed(1)} MB`;
  } catch (err) {
    alert('Failed to upload audio: ' + err.message);
    resetAudioUpload();
  }
}

function resetAudioUpload() {
  selectedAudioFile = null;
  uploadedAudioData = null;
  document.getElementById('audio-input').value = '';
  document.getElementById('dropzone-prompt').classList.remove('hidden');
  document.getElementById('dropzone-fileinfo').classList.add('hidden');
  document.getElementById('dropzone-prompt').innerHTML = `
    <div class="dropzone-icon">🎵</div>
    <h3>Drop voiceover audio here or click to browse</h3>
    <p>Supports MP3, WAV, M4A, AAC (YouTube Full HD 16:9 output)</p>
  `;
}

// ==================== VIDEO GENERATION PIPELINE ====================
async function startGeneration() {
  if (!uploadedAudioData) {
    alert('Please upload a voiceover audio file first!');
    return;
  }

  const niche = document.getElementById('niche-select').value;
  const modal = document.getElementById('processing-modal');
  modal.classList.remove('hidden');

  const setStep = (stepId, active, completed = false) => {
    const el = document.getElementById(stepId);
    if (el) {
      el.className = `stepper-item ${active ? 'active' : ''} ${completed ? 'completed' : ''}`;
    }
  };

  // Reset modal elements
  document.getElementById('modal-status-title').textContent = 'Starting AI Video Pipeline...';
  document.getElementById('modal-status-desc').textContent = 'Preparing audio analysis and download worker pool...';
  document.getElementById('job-progress-bar').style.width = '5%';
  document.getElementById('job-progress-pct').textContent = '5%';
  document.getElementById('job-scene-counter').textContent = 'Initializing...';
  const currSceneEl = document.getElementById('job-current-scene');
  currSceneEl.classList.add('hidden');
  currSceneEl.textContent = '';

  setStep('step-transcribe', true);
  setStep('step-scenes', false);
  setStep('step-download', false);
  setStep('step-preview', false);

  try {
    const res = await fetch('/api/start-generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        audio_filename: uploadedAudioData.filename,
        niche: niche,
        pipeline: activePipeline
      })
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Failed to start generation');
    }

    const { job_id } = await res.json();

    // Poll job progress every 350ms
    const pollInterval = setInterval(async () => {
      try {
        const progRes = await fetch(`/api/job-progress/${job_id}`);
        if (!progRes.ok) return;
        const job = await progRes.json();

        // Update progress bar & text
        const pct = Math.min(100, Math.max(5, job.percent || 5));
        document.getElementById('job-progress-bar').style.width = `${pct}%`;
        document.getElementById('job-progress-pct').textContent = `${pct}%`;

        if (job.stage_title) {
          document.getElementById('modal-status-title').textContent = job.stage_title;
        }
        if (job.stage_desc) {
          document.getElementById('modal-status-desc').textContent = job.stage_desc;
        }

        if (job.total_scenes > 0) {
          document.getElementById('job-scene-counter').textContent = 
            `Worker Downloads: ${job.completed_scenes || 0} / ${job.total_scenes} scenes completed`;
        }

        if (job.current_scene_title) {
          currSceneEl.classList.remove('hidden');
          currSceneEl.textContent = `🎬 Downloading: "${job.current_scene_title}..."`;
        }

        // Stepper state updates
        if (job.stage === 'transcribing') {
          setStep('step-transcribe', true, false);
        } else if (job.stage === 'analyzing') {
          setStep('step-transcribe', false, true);
          setStep('step-scenes', true, false);
        } else if (job.stage === 'downloading') {
          setStep('step-transcribe', false, true);
          setStep('step-scenes', false, true);
          setStep('step-download', true, false);
        } else if (job.stage === 'finalizing' || job.status === 'completed') {
          setStep('step-download', false, true);
          setStep('step-preview', true, true);
        }

        // Completion check
        if (job.status === 'completed' && job.project) {
          clearInterval(pollInterval);
          currentProject = job.project;
          document.getElementById('job-progress-bar').style.width = '100%';
          document.getElementById('job-progress-pct').textContent = '100%';
          document.getElementById('modal-status-title').textContent = 'Video Ready!';

          setTimeout(() => {
            modal.classList.add('hidden');
            loadProjectIntoPreview(currentProject);
            switchTab('preview');
          }, 600);
        } else if (job.status === 'error') {
          clearInterval(pollInterval);
          modal.classList.add('hidden');
          alert('Error during generation: ' + (job.error || 'Unknown error'));
        }
      } catch (pollErr) {
        console.warn('Poll error:', pollErr);
      }
    }, 350);

  } catch (err) {
    modal.classList.add('hidden');
    alert('Error generating video: ' + err.message);
  }
}

// ==================== INTERACTIVE PREVIEW & TIMELINE ====================
function loadProjectIntoPreview(project) {
  if (!project || !project.scenes || project.scenes.length === 0) return;

  totalDuration = project.duration || 30.0;
  captionEngine.loadScenes(project.scenes);

  // Setup preview voiceover audio element
  const audioEl = document.getElementById('preview-audio');
  if (audioEl && project.audio_url) {
    audioEl.src = project.audio_url;
    audioEl.load();
  }
  const videoEl = document.getElementById('preview-video');
  if (videoEl) {
    videoEl.muted = true; // Always mute stock video so voiceover is 100% clean
  }

  // Setup scene markers on timeline
  renderTimelineMarkers(project.scenes);

  // Render Scene Director cards
  renderSceneCards(project.scenes);

  // Reset playback
  currentPlaybackTime = 0.0;
  currentSceneIdx = -1;
  updateTimeDisplay(0, totalDuration);

  // Load first scene clip
  loadSceneClip(0, false);
}

function renderTimelineMarkers(scenes) {
  const container = document.getElementById('timeline-scene-markers');
  container.innerHTML = '';
  scenes.forEach(sc => {
    const tick = document.createElement('div');
    tick.className = 'timeline-scene-tick';
    tick.style.left = `${(sc.start / totalDuration) * 100}%`;
    container.appendChild(tick);
  });
}

function renderSceneCards(scenes) {
  const strip = document.getElementById('scenes-strip');
  document.getElementById('scene-count-badge').textContent = scenes.length;
  strip.innerHTML = '';

  scenes.forEach((sc, idx) => {
    const card = document.createElement('div');
    card.className = `scene-card ${idx === currentSceneIdx ? 'active' : ''}`;
    card.id = `scene-card-${idx}`;
    card.onclick = () => seekToScene(idx);

    const clip = sc.video_clip || {};
    const thumbUrl = clip.thumbnail_url || '';
    const videoUrl = clip.web_url || '';
    const provider = clip.provider || 'stock';

    card.innerHTML = `
      <div class="scene-card-thumb">
        ${videoUrl ? `<video src="${videoUrl}" muted playsinline loop onmouseover="this.play()" onmouseout="this.pause()"></video>` : `<div style="padding:30px;color:#666;">No Clip</div>`}
        <span class="scene-time-badge">⏱ ${formatTime(sc.start)} - ${formatTime(sc.end)}</span>
        <span class="scene-provider-badge">${provider}</span>
      </div>
      <div class="scene-card-body">
        <p class="scene-text" title="${sc.text}">${sc.text}</p>
        <div class="scene-tags">
          ${(sc.search_tags || []).slice(0, 2).map(t => `<span class="tag-pill">#${t}</span>`).join('')}
        </div>
        <button class="btn btn-secondary btn-swap" onclick="event.stopPropagation(); openSwapModal(${sc.id})">
          🔄 Swap Clip
        </button>
      </div>
    `;
    strip.appendChild(card);
  });
}

function loadSceneClip(sceneIdx, autoPlay = true) {
  if (!currentProject || !currentProject.scenes[sceneIdx]) return;
  currentSceneIdx = sceneIdx;
  const sc = currentProject.scenes[sceneIdx];
  const videoEl = document.getElementById('preview-video');

  const clip = sc.video_clip;
  if (clip && clip.web_url) {
    videoEl.onloadedmetadata = () => {
      const container = document.getElementById('video-container');
      const resTag = container ? container.querySelector('.res-tag') : null;
      if (videoEl.videoWidth && videoEl.videoHeight) {
        const isVertical = videoEl.videoHeight > videoEl.videoWidth;
        if (container) {
          if (isVertical) {
            container.classList.add('aspect-9-16');
          } else {
            container.classList.remove('aspect-9-16');
          }
        }
        if (resTag) {
          resTag.textContent = isVertical
            ? `${videoEl.videoWidth}x${videoEl.videoHeight} 9:16 Vertical`
            : `${videoEl.videoWidth}x${videoEl.videoHeight} 16:9 Full HD`;
        }
      }
    };
    videoEl.muted = true;
    if (videoEl.src !== clip.web_url && !videoEl.src.endsWith(clip.web_url)) {
      videoEl.src = clip.web_url;
    }
    const offsetInScene = Math.max(0, currentPlaybackTime - sc.start);
    videoEl.currentTime = Math.min(offsetInScene, Math.max(0.1, (sc.duration || 4.0) - 0.05));
    if (autoPlay && isPlaying) {
      videoEl.play().catch(() => {});
    }
  }

  // Highlight active scene card
  document.querySelectorAll('.scene-card').forEach(c => c.classList.remove('active'));
  const activeCard = document.getElementById(`scene-card-${sceneIdx}`);
  if (activeCard) {
    activeCard.classList.add('active');
    activeCard.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'center' });
  }
}

function togglePlayPause() {
  if (isPlaying) {
    pausePlayback();
  } else {
    startPlayback();
  }
}

function startPlayback() {
  if (!currentProject) return;
  isPlaying = true;
  document.getElementById('play-pause-btn').textContent = '⏸';

  const audioEl = document.getElementById('preview-audio');
  const videoEl = document.getElementById('preview-video');

  if (audioEl && audioEl.src) {
    audioEl.currentTime = currentPlaybackTime;
    audioEl.play().catch(() => {});
  }
  if (videoEl) {
    videoEl.muted = true;
    videoEl.play().catch(() => {});
  }

  const startStamp = performance.now() - (currentPlaybackTime * 1000);

  clearInterval(playbackTimer);
  playbackTimer = setInterval(() => {
    if (audioEl && !audioEl.paused && !audioEl.ended && audioEl.currentTime > 0) {
      currentPlaybackTime = audioEl.currentTime;
    } else {
      currentPlaybackTime = (performance.now() - startStamp) / 1000;
    }

    if (currentPlaybackTime >= totalDuration) {
      pausePlayback();
      currentPlaybackTime = 0.0;
      seekVideoToTime(0);
      return;
    }

    updatePlaybackUI();
  }, 33); // 30 FPS update loop
}

function pausePlayback() {
  isPlaying = false;
  document.getElementById('play-pause-btn').textContent = '▶';
  clearInterval(playbackTimer);

  const audioEl = document.getElementById('preview-audio');
  if (audioEl) audioEl.pause();

  const videoEl = document.getElementById('preview-video');
  if (videoEl) videoEl.pause();
}

function updatePlaybackUI() {
  // Update progress bar
  const progressPct = (currentPlaybackTime / totalDuration) * 100;
  document.getElementById('timeline-progress').style.width = `${progressPct}%`;
  updateTimeDisplay(currentPlaybackTime, totalDuration);

  // Sync Subtitles
  captionEngine.renderAtTime(currentPlaybackTime);

  // Check if we need to switch scene video
  if (currentProject && currentProject.scenes) {
    const activeIdx = currentProject.scenes.findIndex(s => currentPlaybackTime >= s.start && currentPlaybackTime < s.end);
    if (activeIdx !== -1 && activeIdx !== currentSceneIdx) {
      loadSceneClip(activeIdx, true);
    }
  }
}

function seekVideo(event) {
  if (!totalDuration) return;
  const bar = document.getElementById('timeline-bar');
  const rect = bar.getBoundingClientRect();
  const clickX = event.clientX - rect.left;
  const pct = Math.max(0, Math.min(1, clickX / rect.width));
  seekVideoToTime(pct * totalDuration);
}

function seekToScene(sceneIdx) {
  if (!currentProject || !currentProject.scenes[sceneIdx]) return;
  seekVideoToTime(currentProject.scenes[sceneIdx].start);
}

function seekVideoToTime(targetTime) {
  currentPlaybackTime = targetTime;
  const audioEl = document.getElementById('preview-audio');
  if (audioEl) {
    audioEl.currentTime = targetTime;
  }
  updatePlaybackUI();

  if (currentProject && currentProject.scenes) {
    const scIdx = currentProject.scenes.findIndex(s => targetTime >= s.start && targetTime < s.end);
    if (scIdx !== -1) {
      loadSceneClip(scIdx, isPlaying);
    }
  }
}

function updateTimeDisplay(current, total) {
  document.getElementById('time-display').textContent = `${formatTime(current)} / ${formatTime(total)}`;
}

function formatTime(secs) {
  const m = Math.floor(secs / 60);
  const s = Math.floor(secs % 60);
  return `${m < 10 ? '0' : ''}${m}:${s < 10 ? '0' : ''}${s}`;
}

function changeVolume(val) {
  const audio = document.getElementById('preview-audio');
  if (audio) audio.volume = parseFloat(val);
}

function toggleFullscreen() {
  const container = document.getElementById('video-container');
  if (!document.fullscreenElement) {
    container.requestFullscreen().catch(err => alert(err.message));
  } else {
    document.exitFullscreen();
  }
}

// ==================== CAPCUT CAPTION CUSTOMIZATION ====================
function applyPreset(presetKey) {
  document.querySelectorAll('.preset-btn').forEach(b => b.classList.remove('active'));
  const btn = document.getElementById(`preset-${presetKey}`);
  if (btn) btn.classList.add('active');

  const presets = {
    capcut_yellow: {
      fontFamily: 'Montserrat',
      fontSize: 24,
      letterSpacing: 1,
      wordSpacing: 6,
      primaryColor: '#ffffff',
      highlightColor: '#ffe010',
      strokeColor: '#000000',
      strokeWidth: 4,
      uppercase: true,
      animation: 'word_bounce'
    },
    hormozi_green: {
      fontFamily: 'Impact',
      fontSize: 26,
      letterSpacing: 0.5,
      wordSpacing: 5,
      primaryColor: '#ffffff',
      highlightColor: '#39ff14',
      strokeColor: '#000000',
      strokeWidth: 4.5,
      uppercase: true,
      animation: 'word_bounce'
    },
    mrbeast_punch: {
      fontFamily: 'Bangers',
      fontSize: 28,
      letterSpacing: 1.5,
      wordSpacing: 7,
      primaryColor: '#ffe010',
      highlightColor: '#ff3333',
      strokeColor: '#000000',
      strokeWidth: 5.5,
      uppercase: true,
      animation: 'word_bounce'
    },
    ali_abdaal: {
      fontFamily: 'Poppins',
      fontSize: 22,
      letterSpacing: 0.5,
      wordSpacing: 5,
      primaryColor: '#ffffff',
      highlightColor: '#ffa94d',
      strokeColor: '#1a1a1a',
      strokeWidth: 2.5,
      uppercase: false,
      animation: 'word_bounce'
    },
    iman_gadzhi: {
      fontFamily: 'Cinzel',
      fontSize: 23,
      letterSpacing: 2,
      wordSpacing: 8,
      primaryColor: '#f4efea',
      highlightColor: '#d4af37',
      strokeColor: '#000000',
      strokeWidth: 3.5,
      uppercase: true,
      animation: 'word_bounce'
    },
    tiktok_violet: {
      fontFamily: 'Archivo Black',
      fontSize: 25,
      letterSpacing: 1,
      wordSpacing: 6,
      primaryColor: '#ff2a85',
      highlightColor: '#bd00ff',
      strokeColor: '#000000',
      strokeWidth: 4.5,
      uppercase: true,
      animation: 'word_glow'
    },
    podcast_pill: {
      fontFamily: 'Outfit',
      fontSize: 22,
      letterSpacing: 0.5,
      wordSpacing: 6,
      primaryColor: '#ffffff',
      highlightColor: '#ffe600',
      strokeColor: '#111111',
      strokeWidth: 3,
      uppercase: false,
      animation: 'word_box'
    },
    streamer_lime: {
      fontFamily: 'Luckiest Guy',
      fontSize: 26,
      letterSpacing: 1.5,
      wordSpacing: 7,
      primaryColor: '#a6ff00',
      highlightColor: '#00f0ff',
      strokeColor: '#000000',
      strokeWidth: 5,
      uppercase: true,
      animation: 'word_bounce'
    },
    neon_cyber: {
      fontFamily: 'Montserrat',
      fontSize: 24,
      letterSpacing: 2,
      wordSpacing: 8,
      primaryColor: '#ffffff',
      highlightColor: '#00f0ff',
      strokeColor: '#001040',
      strokeWidth: 3.5,
      uppercase: true,
      animation: 'word_glow'
    },
    red_fire: {
      fontFamily: 'Trebuchet MS',
      fontSize: 24,
      letterSpacing: 1.5,
      wordSpacing: 7,
      primaryColor: '#ffffff',
      highlightColor: '#ff3333',
      strokeColor: '#000000',
      strokeWidth: 4,
      uppercase: true,
      animation: 'word_bounce'
    },
    dark_stoic: {
      fontFamily: 'Oswald',
      fontSize: 26,
      letterSpacing: 1.5,
      wordSpacing: 7,
      primaryColor: '#ffffff',
      highlightColor: '#818cf8',
      strokeColor: '#0f0f14',
      strokeWidth: 4,
      uppercase: true,
      animation: 'word_bounce'
    },
    clean_minimal: {
      fontFamily: 'Inter',
      fontSize: 22,
      letterSpacing: 0,
      wordSpacing: 4,
      primaryColor: '#ffffff',
      highlightColor: '#e0e0e0',
      strokeColor: '#151515',
      strokeWidth: 2,
      uppercase: false,
      animation: 'fade_in'
    }
  };

  const p = presets[presetKey];
  if (p) {
    document.getElementById('font-family-select').value = p.fontFamily;
    document.getElementById('font-size-slider').value = p.fontSize;
    document.getElementById('font-size-val').textContent = p.fontSize;
    if (document.getElementById('letter-spacing-slider')) {
      document.getElementById('letter-spacing-slider').value = p.letterSpacing;
      document.getElementById('letter-spacing-val').textContent = p.letterSpacing;
    }
    if (document.getElementById('word-spacing-slider')) {
      document.getElementById('word-spacing-slider').value = p.wordSpacing;
      document.getElementById('word-spacing-val').textContent = p.wordSpacing;
    }
    document.getElementById('color-primary').value = p.primaryColor;
    document.getElementById('color-highlight').value = p.highlightColor;
    document.getElementById('color-stroke').value = p.strokeColor;
    document.getElementById('stroke-width-slider').value = p.strokeWidth;
    document.getElementById('stroke-width-val').textContent = p.strokeWidth;
    document.getElementById('uppercase-checkbox').checked = p.uppercase;
    document.getElementById('animation-style-select').value = p.animation;

    captionEngine.updateStyle({ preset: presetKey, ...p });
  }
}

function updateFontSize(val) {
  document.getElementById('font-size-val').textContent = val;
  updateCaptionStyle();
}

function updateLetterSpacing(val) {
  document.getElementById('letter-spacing-val').textContent = val;
  updateCaptionStyle();
}

function updateWordSpacing(val) {
  document.getElementById('word-spacing-val').textContent = val;
  updateCaptionStyle();
}

function updateStrokeWidth(val) {
  document.getElementById('stroke-width-val').textContent = val;
  updateCaptionStyle();
}

function updateMarginV(val) {
  document.getElementById('margin-v-val').textContent = val;
  updateCaptionStyle();
}

function updateCaptionStyle() {
  const newStyle = {
    fontFamily: document.getElementById('font-family-select').value,
    fontSize: parseInt(document.getElementById('font-size-slider').value, 10),
    letterSpacing: parseFloat(document.getElementById('letter-spacing-slider').value) || 1,
    wordSpacing: parseFloat(document.getElementById('word-spacing-slider').value) || 6,
    primaryColor: document.getElementById('color-primary').value,
    highlightColor: document.getElementById('color-highlight').value,
    strokeColor: document.getElementById('color-stroke').value,
    strokeWidth: parseFloat(document.getElementById('stroke-width-slider').value),
    marginV: parseInt(document.getElementById('margin-v-slider').value, 10),
    uppercase: document.getElementById('uppercase-checkbox').checked,
    animation: document.getElementById('animation-style-select').value
  };

  captionEngine.updateStyle(newStyle);
}

// ==================== SCENE CLIP SWAP MODAL ====================
function openSwapModal(sceneId) {
  swapTargetSceneId = sceneId;
  const sc = currentProject.scenes.find(s => s.id === sceneId);
  if (!sc) return;

  document.getElementById('swap-scene-number').textContent = `#${sc.scene_number}`;
  const query = sc.selected_tag || (sc.search_tags && sc.search_tags[0]) || 'cinematic';
  document.getElementById('swap-search-input').value = query;

  document.getElementById('swap-clip-modal').classList.remove('hidden');
  executeSwapSearch();
}

function closeSwapModal() {
  document.getElementById('swap-clip-modal').classList.add('hidden');
}

async function executeSwapSearch() {
  const query = document.getElementById('swap-search-input').value.trim();
  const grid = document.getElementById('swap-results-grid');
  grid.innerHTML = '<div style="padding:20px;text-align:center;">Searching stock clips...</div>';

  try {
    const res = await fetch(`/api/search-clips?query=${encodeURIComponent(query)}`);
    const data = await res.json();
    const results = data.results || [];

    if (results.length === 0) {
      grid.innerHTML = '<div style="padding:20px;text-align:center;color:#888;">No video clips found. Try another query or check API keys in Settings.</div>';
      return;
    }

    grid.innerHTML = '';
    results.forEach(item => {
      const el = document.createElement('div');
      el.className = 'swap-clip-item';
      el.onclick = () => selectSwapClip(item);
      el.innerHTML = `
        <img src="${item.thumbnail_url || 'https://images.pexels.com/photos/1181244/pexels-photo-1181244.jpeg?auto=compress&cs=tinysrgb&w=300'}" alt="clip">
        <div class="swap-clip-info">
          <span>${item.provider.toUpperCase()}</span>
          <span>⏱ ${item.duration}s</span>
        </div>
      `;
      grid.appendChild(el);
    });
  } catch (err) {
    grid.innerHTML = `<div style="padding:20px;color:red;">Error searching: ${err.message}</div>`;
  }
}

async function selectSwapClip(clipItem) {
  if (swapTargetSceneId === null || !currentProject) return;

  const modal = document.getElementById('swap-clip-modal');
  modal.classList.add('hidden');

  const pModal = document.getElementById('processing-modal');
  document.getElementById('modal-status-title').textContent = 'Downloading Selected Clip...';
  document.getElementById('modal-status-desc').textContent = 'Fetching Full HD clip and updating scene...';
  pModal.classList.remove('hidden');

  try {
    const res = await fetch('/api/swap-clip', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        project_id: currentProject.id,
        scene_id: swapTargetSceneId,
        download_url: clipItem.download_url,
        provider: clipItem.provider,
        thumbnail_url: clipItem.thumbnail_url
      })
    });

    const data = await res.json();
    currentProject.scenes = data.scenes;
    loadProjectIntoPreview(currentProject);
    pModal.classList.add('hidden');
  } catch (err) {
    pModal.classList.add('hidden');
    alert('Failed to swap clip: ' + err.message);
  }
}

// ==================== FINAL EXPORT & RENDER ====================
async function startExportRender() {
  if (!currentProject) {
    alert('No active project to export!');
    return;
  }

  pausePlayback();

  const fps = parseInt(document.getElementById('export-fps').value, 10);
  const activePresetBtn = document.querySelector('.preset-btn.active');
  const presetKey = activePresetBtn ? activePresetBtn.id.replace('preset-', '') : 'capcut_yellow';

  const customOptions = {
    font_name: document.getElementById('font-family-select').value,
    font_size: parseInt(document.getElementById('font-size-slider').value, 10),
    letter_spacing: parseFloat(document.getElementById('letter-spacing-slider').value) || 1,
    word_spacing: parseFloat(document.getElementById('word-spacing-slider').value) || 6,
    primary_color: document.getElementById('color-primary').value,
    highlight_color: document.getElementById('color-highlight').value,
    outline_color: document.getElementById('color-stroke').value,
    outline_width: parseFloat(document.getElementById('stroke-width-slider').value),
    margin_v: parseInt(document.getElementById('margin-v-slider').value, 10),
    uppercase: document.getElementById('uppercase-checkbox').checked,
    animation: document.getElementById('animation-style-select').value,
    bgm_track: document.getElementById('bgm-track-select')?.value || 'cinematic_ambient',
    bgm_volume: (parseInt(document.getElementById('bgm-volume-slider')?.value || '10', 10)) / 100.0,
    enable_motion: document.getElementById('kenburns-checkbox')?.checked ?? true,
    enable_vignette: document.getElementById('vignette-checkbox')?.checked ?? false,
    mute_stock_audio: document.getElementById('mute-stock-checkbox')?.checked ?? true,
    color_grade: document.getElementById('color-grade-select')?.value || 'clean',
    transition: document.getElementById('transition-select')?.value || 'none'
  };

  const modal = document.getElementById('processing-modal');
  document.getElementById('modal-status-title').textContent = 'Fast Multi-Worker Video Render...';
  document.getElementById('modal-status-desc').textContent = 'Normalizing segments in parallel, stitching timeline, and burning CapCut kinetic subtitles...';
  modal.classList.remove('hidden');

  try {
    const res = await fetch('/api/render', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        project_id: currentProject.id,
        preset_key: presetKey,
        custom_options: customOptions,
        fps: fps
      })
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Rendering failed');
    }

    const data = await res.json();
    modal.classList.add('hidden');

    // Show completion modal
    document.getElementById('export-success-filename').textContent = `File: ${data.output_file}`;
    const exportedPlayer = document.getElementById('exported-video-player');
    exportedPlayer.src = data.web_url;
    exportedPlayer.load();

    const dlLink = document.getElementById('export-download-link');
    dlLink.href = data.web_url;
    dlLink.setAttribute('download', data.output_file);

    document.getElementById('export-complete-modal').classList.remove('hidden');
    showToast(`🎉 Video exported successfully: <strong>${data.output_file}</strong>`);
    loadProjectsLibrary();
  } catch (err) {
    modal.classList.add('hidden');
    alert('Rendering error: ' + err.message);
  }
}

function closeExportModal() {
  document.getElementById('export-complete-modal').classList.add('hidden');
  const exportedPlayer = document.getElementById('exported-video-player');
  if (exportedPlayer) exportedPlayer.pause();
}

// ==================== CAPCUT TIMELINE EXPORT ====================
let lastCapCutDraftPath = null;

async function exportToCapCutTimeline() {
  if (!currentProject) {
    alert('No active project to open in CapCut!');
    return;
  }

  pausePlayback();

  const customOptions = {
    font_name: document.getElementById('font-family-select').value,
    font_size: parseInt(document.getElementById('font-size-slider').value, 10),
    letter_spacing: parseFloat(document.getElementById('letter-spacing-slider').value) || 1,
    word_spacing: parseFloat(document.getElementById('word-spacing-slider').value) || 6,
    primary_color: document.getElementById('color-primary').value,
    highlight_color: document.getElementById('color-highlight').value,
    outline_color: document.getElementById('color-stroke').value,
    outline_width: parseFloat(document.getElementById('stroke-width-slider').value),
    margin_v: parseInt(document.getElementById('margin-v-slider').value, 10),
    uppercase: document.getElementById('uppercase-checkbox').checked,
    animation: document.getElementById('animation-style-select').value
  };

  const pModal = document.getElementById('processing-modal');
  document.getElementById('modal-status-title').textContent = 'Generating CapCut Timeline Project...';
  document.getElementById('modal-status-desc').textContent = 'Structuring video cuts, voiceover timeline, and kinetic caption tracks...';
  pModal.classList.remove('hidden');

  try {
    const res = await fetch('/api/export-capcut', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        project_id: currentProject.id,
        custom_options: customOptions
      })
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'CapCut export failed');
    }

    const data = await res.json();
    pModal.classList.add('hidden');
    lastCapCutDraftPath = data.project_dir;

    document.getElementById('capcut-draft-path').textContent = data.project_dir;
    const msg = data.launched
      ? '🚀 CapCut.exe launched! Project template is ready on your timeline with all cuts, audio, and captions.'
      : '✅ CapCut draft generated and placed directly in your CapCut projects folder!';
    document.getElementById('capcut-status-msg').textContent = msg;

    document.getElementById('capcut-modal').classList.remove('hidden');
    showToast(`✂️ CapCut draft ready: <strong>${data.folder_name}</strong>`);
  } catch (err) {
    pModal.classList.add('hidden');
    alert('CapCut export failed: ' + err.message);
  }
}

async function exportProjectCardToCapCut(projectId) {
  try {
    const res = await fetch('/api/projects');
    const projects = await res.json();
    const proj = projects.find(p => p.id === projectId);
    if (proj) {
      currentProject = proj;
      loadProjectIntoPreview(proj);
      await exportToCapCutTimeline();
    }
  } catch (err) {
    alert('Failed to export to CapCut: ' + err.message);
  }
}

function openCapCutDraftFolder() {
  if (lastCapCutDraftPath) {
    openOutputFolder(lastCapCutDraftPath);
  } else {
    openOutputFolder();
  }
}

function closeCapCutModal() {
  document.getElementById('capcut-modal').classList.add('hidden');
}

// ==================== PROJECTS LIBRARY ====================
async function loadProjectsLibrary() {
  try {
    const res = await fetch('/api/projects');
    const projects = await res.json();
    const grid = document.getElementById('projects-grid');
    if (!grid) return;

    if (projects.length === 0) {
      grid.innerHTML = '<div style="grid-column:1/-1;padding:40px;text-align:center;color:#888;">No completed videos yet. Create your first video in Studio!</div>';
      return;
    }

    grid.innerHTML = '';
    projects.forEach(p => {
      const card = document.createElement('div');
      card.className = 'project-card';
      const rendered = p.rendered_video;
      const mediaUrl = rendered ? rendered.web_url : (p.scenes && p.scenes[0] && p.scenes[0].video_clip ? p.scenes[0].video_clip.web_url : '');

      card.innerHTML = `
        <div class="project-thumb">
          ${mediaUrl ? `<video src="${mediaUrl}" muted playsinline loop onmouseover="this.play()" onmouseout="this.pause()"></video>` : `<div style="padding:40px;text-align:center;color:#666;">Preview</div>`}
        </div>
        <div class="project-body">
          <div class="project-title">${p.name || 'Untitled Video'}</div>
          <div class="project-meta">
            <span>🏷️ ${p.niche || 'General'}</span>
            <span>⏱ ${formatTime(p.duration || 0)}</span>
          </div>
          <div class="project-actions" style="display:flex;gap:6px;flex-wrap:wrap;margin-top:10px;">
            <button class="btn btn-secondary btn-sm flex-1" onclick="openProjectInPreview('${p.id}')">
              🎬 Studio
            </button>
            <button class="btn btn-capcut btn-sm" onclick="exportProjectCardToCapCut('${p.id}')" title="Open in CapCut Timeline">
              ✂️ CapCut
            </button>
            <button class="btn btn-outline btn-sm" onclick="openOutputFolder()" title="Open Output Folder">
              📂
            </button>
            ${rendered ? `<a href="${rendered.web_url}" download class="btn btn-success btn-sm">💾 MP4</a>` : ''}
          </div>
        </div>
      `;
      grid.appendChild(card);
    });
  } catch (err) {
    console.error('Error loading library:', err);
  }
}

async function openProjectInPreview(projectId) {
  try {
    const res = await fetch('/api/projects');
    const projects = await res.json();
    const proj = projects.find(p => p.id === projectId);
    if (proj) {
      currentProject = proj;
      loadProjectIntoPreview(proj);
      switchTab('preview');
    }
  } catch (err) {
    alert('Failed to load project: ' + err.message);
  }
}

function updateBgmVolume(val) {
  const lbl = document.getElementById('bgm-volume-val');
  if (lbl) lbl.textContent = val;
}

function updateBgmSelection() {
  const sel = document.getElementById('bgm-track-select');
  console.log('BGM track selected:', sel ? sel.value : '');
}
