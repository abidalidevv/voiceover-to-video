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

// Bulk / Batch & Templates System State
let studioMode = 'single';
let allEditingTemplates = {};
let selectedBulkTemplateId = 'shorts_viral';
let batchFilesData = [];
let activeBatchPollInterval = null;

document.addEventListener('DOMContentLoaded', async () => {
  captionEngine = new CaptionEngine('subtitle-overlay', 'subtitle-text');
  captionEngine.applyContainerStyles();

  // Connect interactive drag-to-position on video player to bottom margin controls
  captionEngine.enableDrag((newBottom) => {
    const slider = document.getElementById('margin-v-slider');
    const label = document.getElementById('margin-v-val');
    if (slider) slider.value = newBottom;
    if (label) label.textContent = newBottom;
  });

  setupDropzone();
  setupBatchDropzone();
  await loadBgmTracks();
  await loadEditingTemplates();
  await loadTTSVoices();
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
  } else if (tabId === 'thumbnails') {
    loadProjectThumbnails(currentProject);
  }
}

function switchStudioMode(mode) {
  studioMode = mode;
  const singleGrid = document.getElementById('single-studio-grid');
  const bulkGrid = document.getElementById('bulk-studio-grid');
  const singleBtn = document.getElementById('mode-single-btn');
  const bulkBtn = document.getElementById('mode-bulk-btn');

  if (mode === 'single') {
    if (singleGrid) singleGrid.classList.remove('hidden');
    if (bulkGrid) bulkGrid.classList.add('hidden');
    if (singleBtn) singleBtn.classList.add('active');
    if (bulkBtn) bulkBtn.classList.remove('active');
  } else {
    if (singleGrid) singleGrid.classList.add('hidden');
    if (bulkGrid) bulkGrid.classList.remove('hidden');
    if (singleBtn) singleBtn.classList.remove('active');
    if (bulkBtn) bulkBtn.classList.add('active');
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

    // 10+ Stock Video APIs - Multi-Account Pools
    const pKeys = data.pexels_api_keys || (data.pexels_api_key ? [data.pexels_api_key] : []);
    if (document.getElementById('input-pexels-key')) document.getElementById('input-pexels-key').value = pKeys[0] || '';
    if (document.getElementById('input-pexels-key-2')) document.getElementById('input-pexels-key-2').value = pKeys[1] || '';
    if (document.getElementById('input-pexels-key-3')) document.getElementById('input-pexels-key-3').value = pKeys[2] || '';
    if (document.getElementById('input-pexels-key-4')) document.getElementById('input-pexels-key-4').value = pKeys[3] || '';
    if (document.getElementById('input-pexels-key-5')) document.getElementById('input-pexels-key-5').value = pKeys[4] || '';
    if (pKeys.length > 1 && document.getElementById('pexels-extra-keys')) {
      document.getElementById('pexels-extra-keys').style.display = 'block';
    }

    const pbKeys = data.pixabay_api_keys || (data.pixabay_api_key ? [data.pixabay_api_key] : []);
    if (document.getElementById('input-pixabay-key')) document.getElementById('input-pixabay-key').value = pbKeys[0] || '';
    if (document.getElementById('input-pixabay-key-2')) document.getElementById('input-pixabay-key-2').value = pbKeys[1] || '';
    if (document.getElementById('input-pixabay-key-3')) document.getElementById('input-pixabay-key-3').value = pbKeys[2] || '';
    if (document.getElementById('input-pixabay-key-4')) document.getElementById('input-pixabay-key-4').value = pbKeys[3] || '';
    if (document.getElementById('input-pixabay-key-5')) document.getElementById('input-pixabay-key-5').value = pbKeys[4] || '';
    if (pbKeys.length > 1 && document.getElementById('pixabay-extra-keys')) {
      document.getElementById('pixabay-extra-keys').style.display = 'block';
    }

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
    if (document.getElementById('input-elevenlabs-key')) document.getElementById('input-elevenlabs-key').value = data.elevenlabs_api_key || '';

    // Google Gemini 5-Key Pool
    const gKeys = data.gemini_api_keys || (data.gemini_api_key ? [data.gemini_api_key] : []);
    for (let i = 1; i <= 5; i++) {
      const gEl = document.getElementById(`input-gemini-key-${i}`);
      if (gEl) gEl.value = gKeys[i - 1] || '';
    }

    // Tuner & Strategy
    if (document.getElementById('input-hardware-encoder')) document.getElementById('input-hardware-encoder').value = data.hardware_encoder || 'auto';
    if (document.getElementById('input-video-provider')) document.getElementById('input-video-provider').value = data.video_provider || 'all';
    
    // Output Directories
    if (document.getElementById('input-output-dir')) {
      document.getElementById('input-output-dir').value = data.output_dir || '';
    }
    if (document.getElementById('input-thumbnail-output-dir')) {
      document.getElementById('input-thumbnail-output-dir').value = data.thumbnail_output_dir || '';
    }

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
  // Gather all non-empty Pexels keys
  const rawPexels = [
    document.getElementById('input-pexels-key')?.value || '',
    document.getElementById('input-pexels-key-2')?.value || '',
    document.getElementById('input-pexels-key-3')?.value || '',
    document.getElementById('input-pexels-key-4')?.value || '',
    document.getElementById('input-pexels-key-5')?.value || '',
  ];
  const pexelsKeys = [];
  rawPexels.forEach(val => {
    val.split(/[\r\n,;]+/).map(k => k.trim()).filter(Boolean).forEach(k => {
      if (!pexelsKeys.includes(k)) pexelsKeys.push(k);
    });
  });

  // Gather all non-empty Pixabay keys
  const rawPixabay = [
    document.getElementById('input-pixabay-key')?.value || '',
    document.getElementById('input-pixabay-key-2')?.value || '',
    document.getElementById('input-pixabay-key-3')?.value || '',
    document.getElementById('input-pixabay-key-4')?.value || '',
    document.getElementById('input-pixabay-key-5')?.value || '',
  ];
  const pixabayKeys = [];
  rawPixabay.forEach(val => {
    val.split(/[\r\n,;]+/).map(k => k.trim()).filter(Boolean).forEach(k => {
      if (!pixabayKeys.includes(k)) pixabayKeys.push(k);
    });
  });

  // Gather all non-empty Gemini keys
  const rawGemini = [
    document.getElementById('input-gemini-key-1')?.value || '',
    document.getElementById('input-gemini-key-2')?.value || '',
    document.getElementById('input-gemini-key-3')?.value || '',
    document.getElementById('input-gemini-key-4')?.value || '',
    document.getElementById('input-gemini-key-5')?.value || '',
  ];
  const geminiKeys = [];
  rawGemini.forEach(val => {
    val.split(/[\r\n,;]+/).map(k => k.trim()).filter(Boolean).forEach(k => {
      if (!geminiKeys.includes(k)) geminiKeys.push(k);
    });
  });

  const payload = {
    // 10+ Stock Video APIs - Multi-Account Pool
    pexels_api_key: pexelsKeys[0] || '',
    pexels_api_keys: pexelsKeys,
    pixabay_api_key: pixabayKeys[0] || '',
    pixabay_api_keys: pixabayKeys,
    coverr_api_key: document.getElementById('input-coverr-key')?.value.trim() || '',
    videvo_api_key: document.getElementById('input-videvo-key')?.value.trim() || '',
    nasa_api_key: document.getElementById('input-nasa-key')?.value.trim() || '',
    wikimedia_video_enabled: document.getElementById('input-wiki-enabled')?.checked ?? true,
    mixkit_api_key: document.getElementById('input-mixkit-key')?.value.trim() || '',
    freepik_api_key: document.getElementById('input-freepik-key')?.value.trim() || '',
    rapidapi_stock_key: document.getElementById('input-rapidapi-key')?.value.trim() || '',
    custom_stock_webhook: document.getElementById('input-custom-webhook')?.value.trim() || '',

    // Google Gemini 5-Key Pool
    gemini_api_key: geminiKeys[0] || '',
    gemini_api_keys: geminiKeys,

    // AI & Transcription
    groq_api_key: document.getElementById('input-groq-key')?.value.trim() || '',
    openai_api_key: document.getElementById('input-openai-key')?.value.trim() || '',
    elevenlabs_api_key: document.getElementById('input-elevenlabs-key')?.value.trim() || '',

    // Output Directories
    output_dir: document.getElementById('input-output-dir')?.value.trim() || '',
    thumbnail_output_dir: document.getElementById('input-thumbnail-output-dir')?.value.trim() || '',

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
    const poolInfo = `Pexels: ${pexelsKeys.length} keys, Pixabay: ${pixabayKeys.length} keys`;
    showToast(`💾 Settings and API keys saved! (${poolInfo}, ${payload.workers} Workers Active)`);
    const badge = document.getElementById('worker-count-badge');
    if (badge) badge.textContent = `${payload.workers} Workers Ready`;
  } catch (err) {
    alert('Error saving settings: ' + err.message);
  }
}

async function browseFolderFor(inputId) {
  const currentVal = document.getElementById(inputId)?.value || '';
  try {
    const res = await fetch('/api/browse-directory', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ initial_dir: currentVal })
    });
    const data = await res.json();
    if (data.path) {
      document.getElementById(inputId).value = data.path;
      showToast(`📁 Selected: <strong>${data.path}</strong>`);
    }
  } catch (e) {
    console.warn('Browse directory failed:', e);
  }
}

async function openOutputFolderCustom(type = 'videos') {
  try {
    const res = await fetch('/api/open-folder', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path: type })
    });
    const data = await res.json();
    const folderName = (data.path || '').split(/[\\/]/).pop() || type;
    showToast(`📂 Opened folder in Windows Explorer: <strong>${folderName}</strong><br><span style="font-size:11px;color:#94a3b8;word-break:break-all;">${data.path}</span>`, 4000);
  } catch (e) {
    showToast(`⚠️ Could not open folder: ${e.message}`);
  }
}

async function checkApiStatus() {
  try {
    const res = await fetch('/api/test-apis', { method: 'POST' });
    const data = await res.json();

    updateBadge('badge-pexels', data.pexels);
    updateBadge('badge-pixabay', data.pixabay);
    updateBadge('badge-groq', data.groq);
    updateBadge('badge-gemini', data.gemini);

    return data;
  } catch (e) {
    console.warn('API check notice:', e);
    return null;
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
    if (res.active_keys !== undefined && res.total_keys !== undefined) {
      el.textContent = `Connected (${res.active_keys}/${res.total_keys} Keys) ✓`;
    } else {
      el.textContent = 'Connected ✓';
    }
  } else {
    el.className = 'badge badge-error';
    el.textContent = res.error ? `Error: ${res.error}` : 'Error';
  }
}

async function testApiConnections() {
  await saveAppSettings();
  showToast('🔄 Testing API connections in parallel...', 2500);
  const data = await checkApiStatus();
  if (!data) {
    showToast('⚠️ Could not connect to API test endpoint.');
    return;
  }

  const connected = [];
  if (data.pexels?.status === 'ok') connected.push(`📷 Pexels: Active (${data.pexels.active_keys}/${data.pexels.total_keys} keys)`);
  if (data.pixabay?.status === 'ok') connected.push(`🎥 Pixabay: Active (${data.pixabay.active_keys}/${data.pixabay.total_keys} keys)`);
  if (data.gemini?.status === 'ok') connected.push(`✨ Google Gemini: Active (${data.gemini.active_keys}/${data.gemini.total_keys} keys)`);
  if (data.groq?.status === 'ok') connected.push('🎙️ Groq Whisper: Active');
  if (data.openai?.status === 'ok') connected.push('🤖 OpenAI: Active');
  if (data.nasa?.status === 'ok') connected.push('🚀 NASA Open Media: Active');
  if (data.coverr?.status === 'ok') connected.push('🎬 Coverr: Active');

  if (connected.length > 0) {
    showToast(`✅ <strong>API Verification Succeeded!</strong><br>${connected.join('<br>')}`, 6000);
  } else {
    showToast('⚠️ No active API keys configured or all connections timed out. Check your keys.');
  }
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

let lastExportedVideoPath = null;
let lastExportedVideoName = null;
let lastExportedThumbnails = null;

async function openOutputFolder(customPath = null) {
  const btn = document.getElementById('header-btn-outputs');
  if (btn) {
    btn.style.opacity = '0.7';
    btn.style.transform = 'scale(0.96)';
  }
  try {
    let res;
    try {
      res = await fetch('/api/open-folder', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: customPath || null })
      });
    } catch (netErr) {
      // Fallback: try GET /api/open-output-folder
      res = await fetch('/api/open-output-folder');
    }

    if (!res || !res.ok) {
      res = await fetch('/api/open-output-folder');
    }

    if (!res.ok) {
      throw new Error(`Server returned HTTP ${res.status}`);
    }
    const data = await res.json();
    const folderPath = data.path || 'data/output';
    const folderName = (folderPath.split(/[\\/]/).pop()) || 'Output';
    const isFile = data.type === 'file' || /\.(mp4|mkv|mov|avi|jpg|png)$/i.test(folderPath);
    const actionMsg = isFile ? `Selected file in Explorer: <strong>${folderName}</strong>` : `Opened folder in Windows Explorer: <strong>${folderName}</strong>`;
    showToast(`📂 ${actionMsg}<br><span style="font-size:11px;color:#94a3b8;word-break:break-all;">${folderPath}</span>`, 4500);
  } catch (e) {
    console.error('Error opening output folder:', e);
    showToast(`⚠️ Could not open folder: ${e.message}`);
  } finally {
    if (btn) {
      setTimeout(() => {
        btn.style.opacity = '1';
        btn.style.transform = 'scale(1)';
      }, 250);
    }
  }
}

function openExportedVideoFolder() {
  const path = lastExportedVideoPath || lastExportedVideoName;
  openOutputFolder(path);
}

// ==================== OPERATIONAL MANUAL & DOCS VIEWER ====================
async function openDocsManual() {
  const modal = document.getElementById('docs-modal');
  if (modal) {
    modal.classList.remove('hidden');
  }
  try {
    fetch('/api/open-docs');
  } catch (e) {}
}

function closeDocsModal() {
  const modal = document.getElementById('docs-modal');
  if (modal) {
    modal.classList.add('hidden');
  }
}

async function openDocsInBrowser() {
  try {
    const res = await fetch('/api/open-docs');
    if (res.ok) {
      showToast('📖 User manual opened in your default Windows browser', 3500);
      return;
    }
  } catch (e) {}
  window.open('docs.html', '_blank');
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
        pipeline: activePipeline,
        target_resolution: document.getElementById('target-resolution-select')?.value || '1080p'
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
        updateFloatingDock('⚡ Generating Video Draft...', job.stage_title || 'Analyzing scenes...', pct);

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

          const dock = document.getElementById('floating-task-dock');
          if (dock) dock.classList.add('hidden');
          activeMinimizedModal = null;

          setTimeout(() => {
            modal.classList.add('hidden');
            loadProjectIntoPreview(currentProject);
            switchTab('preview');
            showToast('🎉 Interactive video preview ready in Studio!', 4000);
          }, 600);
        } else if (job.status === 'error') {
          clearInterval(pollInterval);
          modal.classList.add('hidden');
          const dock = document.getElementById('floating-task-dock');
          if (dock) dock.classList.add('hidden');
          activeMinimizedModal = null;
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
    audioEl.volume = parseFloat(document.getElementById('volume-slider')?.value || '1');
    audioEl.load();
    audioEl.onerror = () => {
      console.warn("[VideoGen] Notice: voiceover audio could not load from", project.audio_url);
    };
  }
  const videoEl = document.getElementById('preview-video');
  if (videoEl) {
    videoEl.muted = true; // Always mute stock video so voiceover is 100% clean
  }

  // Setup scene markers on timeline
  renderTimelineMarkers(project.scenes);

  // Render Scene Director cards
  renderSceneCards(project.scenes);

  // Check for missing stock footage and show alert if needed
  checkMissingClipsAlert(project.scenes);

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
    const isFallback = Boolean(sc.fallback_used || clip.is_fallback || !clip.file_path);

    const isImage = Boolean(videoUrl && /\.(jpg|jpeg|png|webp)($|\?)/i.test(videoUrl));
    const thumbHtml = (videoUrl && !isImage)
      ? `<video src="${videoUrl}#t=0.5" poster="${thumbUrl}" preload="metadata" muted playsinline loop onmouseover="this.play()" onmouseout="this.pause()"></video>`
      : ((thumbUrl || videoUrl) 
          ? `<img src="${thumbUrl || videoUrl}" alt="Scene thumbnail" style="width:100%;height:100%;object-fit:cover;">` 
          : `<div style="padding:30px;color:#666;">No Clip</div>`);

    const fallbackBadge = isFallback
      ? `<span class="scene-fallback-badge">⚠️ AI Image Needed</span>`
      : '';

    card.innerHTML = `
      <div class="scene-card-thumb">
        ${thumbHtml}
        ${fallbackBadge}
        <span class="scene-time-badge">⏱ ${formatTime(sc.start)} - ${formatTime(sc.end)}</span>
        <span class="scene-provider-badge">${provider}</span>
      </div>
      <div class="scene-card-body">
        <p class="scene-text" title="${sc.text}">${sc.text}</p>
        <div class="scene-tags">
          ${(sc.search_tags || []).slice(0, 2).map(t => `<span class="tag-pill">#${t}</span>`).join('')}
        </div>
        <div class="scene-card-actions">
          <button class="btn btn-secondary btn-swap" onclick="event.stopPropagation(); openSwapModal(${sc.id})">
            🔄 Swap
          </button>
          <button class="btn btn-ai-img" onclick="event.stopPropagation(); generateSingleSceneAIImage(${sc.id})" title="Generate Ultra HD 16:9 AI Image for this scene">
            🎨 AI Image
          </button>
        </div>
      </div>
    `;
    strip.appendChild(card);
  });
}

function preloadNextSceneClip(sceneIdx) {
  if (!currentProject || !currentProject.scenes) return;
  const nextIdx = sceneIdx + 1;
  if (nextIdx < currentProject.scenes.length) {
    const nextClip = currentProject.scenes[nextIdx].video_clip;
    if (nextClip && nextClip.web_url && !/\.(jpg|jpeg|png|webp)($|\?)/i.test(nextClip.web_url)) {
      const link = document.createElement('link');
      link.rel = 'preload';
      link.as = 'video';
      link.href = nextClip.web_url;
      document.head.appendChild(link);
    }
  }
}

function loadSceneClip(sceneIdx, autoPlay = true) {
  if (!currentProject || !currentProject.scenes[sceneIdx]) return;
  currentSceneIdx = sceneIdx;
  const sc = currentProject.scenes[sceneIdx];
  const videoEl = document.getElementById('preview-video');
  const container = document.getElementById('video-container');
  if (!videoEl || !container) return;

  // Preload next scene in background for zero-latency cutover
  preloadNextSceneClip(sceneIdx);

  // Get or create smooth image animation layer for photo/fallback scenes
  let imgLayer = document.getElementById('preview-image-layer');
  if (!imgLayer) {
    imgLayer = document.createElement('div');
    imgLayer.id = 'preview-image-layer';
    imgLayer.className = 'preview-image-kenburns';
    container.insertBefore(imgLayer, videoEl);
  }

  const clip = sc.video_clip;
  const mediaUrl = clip ? (clip.web_url || clip.thumbnail_url || '') : '';
  const isImageMedia = Boolean(mediaUrl && /\.(jpg|jpeg|png|webp)($|\?)/i.test(mediaUrl));

  if (isImageMedia || (!clip || !clip.file_path)) {
    // Scene is an AI photo or image: render with smooth cinematic Ken Burns motion!
    const displayImg = mediaUrl || (clip && clip.thumbnail_url) || '';
    if (displayImg) {
      imgLayer.style.backgroundImage = `url('${displayImg}')`;
      imgLayer.style.display = 'block';
    } else {
      imgLayer.style.display = 'none';
    }
    videoEl.style.display = 'none';
    try { videoEl.pause(); } catch (e) {}
  } else if (clip && clip.web_url) {
    // Scene is an active MP4 video
    imgLayer.style.display = 'none';
    videoEl.style.display = 'block';

    if (clip.thumbnail_url) {
      videoEl.poster = clip.thumbnail_url;
    }

    const targetOffset = Math.max(0, currentPlaybackTime - sc.start);
    const safeOffset = Math.min(targetOffset, Math.max(0.1, (sc.duration || 4.0) - 0.05));

    const applySeekAndPlay = () => {
      try {
        if (videoEl.duration && safeOffset < videoEl.duration) {
          videoEl.currentTime = safeOffset;
        } else if (videoEl.readyState >= 1) {
          videoEl.currentTime = safeOffset;
        }
      } catch (e) {}
      if (autoPlay && isPlaying) {
        videoEl.play().catch(() => {});
      }
    };

    videoEl.onloadedmetadata = () => {
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
      applySeekAndPlay();
    };

    videoEl.muted = true;
    videoEl.onerror = () => {
      console.warn("[VideoGen] Warning: Could not load scene clip from", clip.web_url);
    };
    videoEl.onplaying = () => {
      videoEl.removeAttribute('poster');
    };

    const currentSrc = videoEl.getAttribute('src') || videoEl.src || '';
    if (currentSrc === clip.web_url || currentSrc.endsWith(clip.web_url)) {
      videoEl.removeAttribute('poster');
      applySeekAndPlay();
    } else {
      videoEl.src = clip.web_url;
      videoEl.load();
      videoEl.onloadeddata = () => {
        videoEl.removeAttribute('poster');
        applySeekAndPlay();
      };
    }
  }

  // Highlight active scene card and smoothly scroll horizontal strip without moving page viewport
  document.querySelectorAll('.scene-card').forEach(c => c.classList.remove('active'));
  const activeCard = document.getElementById(`scene-card-${sceneIdx}`);
  if (activeCard) {
    activeCard.classList.add('active');
    const strip = document.getElementById('scenes-strip');
    if (strip) {
      const cardLeft = activeCard.offsetLeft;
      const cardWidth = activeCard.offsetWidth;
      const stripWidth = strip.clientWidth;
      strip.scrollTo({
        left: cardLeft - (stripWidth / 2) + (cardWidth / 2),
        behavior: 'smooth'
      });
    }
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
    try {
      if (audioEl.readyState >= 1) {
        audioEl.currentTime = currentPlaybackTime;
      }
    } catch (e) {}
    audioEl.volume = parseFloat(document.getElementById('volume-slider')?.value || '1');
    const playPromise = audioEl.play();
    if (playPromise !== undefined) {
      playPromise.catch(err => {
        console.warn("[VideoGen] Voiceover audio autoplay warning:", err);
      });
    }
  }
  if (videoEl) {
    videoEl.muted = true;
    videoEl.removeAttribute('poster');
    const playPromise = videoEl.play();
    if (playPromise !== undefined) {
      playPromise.catch(() => {});
    }
  }

  // Synchronize live overlay video if visible
  const ovrVideo = document.getElementById('preview-overlay-video');
  if (ovrVideo && ovrVideo.style.display !== 'none' && ovrVideo.src) {
    ovrVideo.muted = document.getElementById('overlay-mute-checkbox')?.checked ?? true;
    ovrVideo.play().catch(() => {});
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

  const ovrVideo = document.getElementById('preview-overlay-video');
  if (ovrVideo) ovrVideo.pause();
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
  currentPlaybackTime = Math.max(0, Math.min(targetTime, totalDuration || 9999));
  const audioEl = document.getElementById('preview-audio');
  if (audioEl) {
    try {
      if (audioEl.readyState >= 1) {
        audioEl.currentTime = currentPlaybackTime;
      }
    } catch (e) {}
  }

  const ovrVideo = document.getElementById('preview-overlay-video');
  if (ovrVideo && ovrVideo.style.display !== 'none' && ovrVideo.duration) {
    try {
      ovrVideo.currentTime = currentPlaybackTime % ovrVideo.duration;
    } catch (e) {}
  }

  updatePlaybackUI();

  if (currentProject && currentProject.scenes) {
    const scIdx = currentProject.scenes.findIndex(s => currentPlaybackTime >= s.start && currentPlaybackTime < s.end);
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
    captionEngine.renderAtTime(currentPlaybackTime);
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
  captionEngine.renderAtTime(currentPlaybackTime);
}

// ==================== BGM TRACKS & CUSTOM UPLOAD ====================
async function loadBgmTracks() {
  try {
    const res = await fetch('/api/bgm-tracks');
    if (!res.ok) return;
    const tracks = await res.json();
    const select = document.getElementById('bgm-track-select');
    if (!select || !Array.isArray(tracks)) return;

    const currentVal = select.value;
    select.innerHTML = '';
    tracks.forEach(tr => {
      const opt = document.createElement('option');
      opt.value = tr.id;
      opt.textContent = tr.name;
      if (tr.id === currentVal) opt.selected = true;
      select.appendChild(opt);
    });
    if (!select.value && tracks.length > 0) {
      select.value = tracks[0].id;
    }
    updateBgmSelection();
  } catch (e) {
    console.warn("[VideoGen] Could not load BGM tracks:", e);
  }
}

function updateBgmSelection() {
  const select = document.getElementById('bgm-track-select');
  const badge = document.getElementById('custom-bgm-badge');
  const fname = document.getElementById('custom-bgm-filename');
  if (select && badge && fname) {
    const selectedOption = select.options[select.selectedIndex];
    const val = select.value;
    if (val && (val.startsWith('custom_') || val.endsWith('.mp3') || val.endsWith('.wav') || val.endsWith('.aac') || val.endsWith('.m4a') || val.endsWith('.ogg'))) {
      fname.textContent = selectedOption ? selectedOption.text.replace('🎵 ', '') : val;
      badge.classList.remove('hidden');
    } else {
      badge.classList.add('hidden');
    }
  }
}

function updateBgmVolume(val) {
  const el = document.getElementById('bgm-volume-val');
  if (el) el.textContent = val;
}

async function handleBgmUpload(event) {
  const file = event.target.files && event.target.files[0];
  if (!file) return;

  const btn = document.getElementById('upload-bgm-btn');
  const originalText = btn ? btn.innerHTML : '➕ Upload BGM';
  if (btn) btn.innerHTML = '⏳ Uploading...';

  try {
    const formData = new FormData();
    formData.append('file', file);

    const res = await fetch('/api/upload-bgm', {
      method: 'POST',
      body: formData
    });
    if (!res.ok) throw new Error('Upload failed with HTTP status ' + res.status);
    const data = await res.json();

    await loadBgmTracks();

    const select = document.getElementById('bgm-track-select');
    if (select && data.bgm_key) {
      select.value = data.bgm_key;
      updateBgmSelection();
    }

    const badge = document.getElementById('custom-bgm-badge');
    const fname = document.getElementById('custom-bgm-filename');
    if (badge && fname) {
      fname.textContent = data.filename || file.name;
      badge.classList.remove('hidden');
    }

    showToast(`🎵 Custom BGM uploaded & selected: <strong>${data.filename || file.name}</strong>`);
  } catch (e) {
    console.error(e);
    alert('Failed to upload custom background music: ' + e.message);
  } finally {
    if (btn) btn.innerHTML = originalText;
    event.target.value = '';
  }
}

// ==================== VIDEO OVERLAY HANDLERS ====================

let currentOverlayPath = null;
let currentOverlayUrl = null;

async function handleOverlayUpload(event) {
  const file = event.target.files && event.target.files[0];
  if (!file) return;

  const btn = document.getElementById('upload-overlay-btn');
  const originalText = btn ? btn.innerHTML : '➕ Upload Overlay';
  if (btn) btn.innerHTML = '⏳ Uploading...';

  try {
    const formData = new FormData();
    formData.append('file', file);

    const res = await fetch('/api/upload-overlay', {
      method: 'POST',
      body: formData
    });
    if (!res.ok) throw new Error('Upload failed with HTTP status ' + res.status);
    const data = await res.json();

    currentOverlayPath = data.overlay_key || data.path;
    currentOverlayUrl = data.web_url || ('/media/' + currentOverlayPath.replace(/^data[\\/]/, '').replace(/\\/g, '/'));

    const badge = document.getElementById('overlay-active-badge');
    const fname = document.getElementById('overlay-filename');
    if (badge && fname) {
      fname.textContent = data.filename || file.name;
      badge.classList.remove('hidden');
    }

    updateLiveOverlayPreview();
    showToast(`🎭 Overlay active in preview: <strong>${data.filename || file.name}</strong> (${data.type})`);
  } catch (e) {
    console.error(e);
    alert('Failed to upload overlay: ' + e.message);
  } finally {
    if (btn) btn.innerHTML = originalText;
    event.target.value = '';
  }
}

function removeOverlay() {
  currentOverlayPath = null;
  currentOverlayUrl = null;
  const badge = document.getElementById('overlay-active-badge');
  if (badge) badge.classList.add('hidden');
  updateLiveOverlayPreview();
  showToast('🎭 Overlay removed');
}

function updateLiveOverlayPreview() {
  const ovrVideo = document.getElementById('preview-overlay-video');
  const ovrImg = document.getElementById('preview-overlay-img');
  if (!ovrVideo || !ovrImg) return;

  if (!currentOverlayPath) {
    ovrVideo.style.display = 'none';
    ovrVideo.pause();
    ovrVideo.removeAttribute('src');
    ovrImg.style.display = 'none';
    ovrImg.removeAttribute('src');
    return;
  }

  const opacity = (parseFloat(document.getElementById('overlay-opacity-slider')?.value || 30)) / 100;
  const scalePercent = parseFloat(document.getElementById('overlay-scale-slider')?.value || 20);
  const position = document.getElementById('overlay-position-select')?.value || 'bottom_right';
  const isMuted = document.getElementById('overlay-mute-checkbox')?.checked ?? true;

  const isVideo = /\.(mp4|mov|webm|avi)($|\?)/i.test(currentOverlayPath);
  const activeEl = isVideo ? ovrVideo : ovrImg;
  const inactiveEl = isVideo ? ovrImg : ovrVideo;

  inactiveEl.style.display = 'none';
  inactiveEl.removeAttribute('src');
  if (inactiveEl.tagName === 'VIDEO') inactiveEl.pause();

  activeEl.style.display = 'block';
  activeEl.style.opacity = opacity;
  activeEl.style.position = 'absolute';
  activeEl.style.zIndex = '12';
  activeEl.style.pointerEvents = 'none';

  if (position === 'full_screen') {
    activeEl.style.top = '0';
    activeEl.style.left = '0';
    activeEl.style.right = '0';
    activeEl.style.bottom = '0';
    activeEl.style.width = '100%';
    activeEl.style.height = '100%';
    activeEl.style.transform = 'none';
    activeEl.style.objectFit = 'cover';
  } else {
    activeEl.style.width = `${scalePercent}%`;
    activeEl.style.maxHeight = `${scalePercent}%`;
    activeEl.style.objectFit = 'contain';

    activeEl.style.top = '';
    activeEl.style.bottom = '';
    activeEl.style.left = '';
    activeEl.style.right = '';
    activeEl.style.transform = 'none';

    if (position === 'bottom_right') {
      activeEl.style.bottom = '16px';
      activeEl.style.right = '16px';
    } else if (position === 'bottom_left') {
      activeEl.style.bottom = '16px';
      activeEl.style.left = '16px';
    } else if (position === 'top_right') {
      activeEl.style.top = '16px';
      activeEl.style.right = '16px';
    } else if (position === 'top_left') {
      activeEl.style.top = '16px';
      activeEl.style.left = '16px';
    } else if (position === 'center') {
      activeEl.style.top = '50%';
      activeEl.style.left = '50%';
      activeEl.style.transform = 'translate(-50%, -50%)';
    }
  }

  const resolvedUrl = currentOverlayUrl || ('/media/' + currentOverlayPath.replace(/^data[\\/]/, '').replace(/\\/g, '/'));
  if (activeEl.getAttribute('src') !== resolvedUrl) {
    activeEl.src = resolvedUrl;
    if (isVideo) {
      ovrVideo.muted = isMuted;
      ovrVideo.load();
      if (isPlaying) {
        ovrVideo.play().catch(() => {});
      }
    }
  }

  if (isVideo) {
    ovrVideo.muted = isMuted;
  }
}

function updateOverlayPosition() {
  updateLiveOverlayPreview();
}

function updateOverlayOpacity(val) {
  const el = document.getElementById('overlay-opacity-val');
  if (el) el.textContent = val;
  updateLiveOverlayPreview();
}

function updateOverlayScale(val) {
  const el = document.getElementById('overlay-scale-val');
  if (el) el.textContent = val;
  updateLiveOverlayPreview();
}

function updateOverlayMute(isMuted) {
  const ovrVideo = document.getElementById('preview-overlay-video');
  if (ovrVideo) {
    ovrVideo.muted = Boolean(isMuted);
  }
}

function getOverlaySettings() {
  if (!currentOverlayPath) return {};
  return {
    overlay_video: currentOverlayPath,
    overlay_opacity: parseFloat(document.getElementById('overlay-opacity-slider')?.value || 30) / 100,
    overlay_position: document.getElementById('overlay-position-select')?.value || 'bottom_right',
    overlay_scale: parseFloat(document.getElementById('overlay-scale-slider')?.value || 20),
    overlay_muted: document.getElementById('overlay-mute-checkbox')?.checked ?? true
  };
}

// ==================== KOKORO VOICE CLONING HANDLERS ====================

function onTTSVoiceChange() {
  const select = document.getElementById('tts-voice-select');
  const panel = document.getElementById('kokoro-clone-panel');
  if (select && panel) {
    if (select.value === 'clone_custom') {
      panel.classList.remove('hidden');
      checkKokoroStatus();
      return;
    } else {
      panel.classList.add('hidden');
    }
  }
  if (typeof previewSelectedVoice === 'function') {
    previewSelectedVoice();
  }
}

async function checkKokoroStatus() {
  const badges = [
    document.getElementById('kokoro-status-badge'),
    document.getElementById('clone-tab-status-badge')
  ].filter(Boolean);
  if (badges.length === 0) return;
  
  try {
    const res = await fetch('/api/clone-status');
    const data = await res.json();
    
    badges.forEach(badge => {
      if (data.available) {
        badge.textContent = '✅ Ready';
        badge.style.background = 'rgba(34,197,94,0.2)';
        badge.style.color = '#86efac';
      } else {
        badge.textContent = '⚠️ Not Installed (pip install kokoro soundfile numpy)';
        badge.style.background = 'rgba(234,179,8,0.2)';
        badge.style.color = '#fde047';
      }
    });
  } catch (e) {
    badges.forEach(badge => {
      badge.textContent = '❌ Error';
      badge.style.background = 'rgba(239,68,68,0.2)';
      badge.style.color = '#fca5a5';
    });
  }
}

function updateKokoroVoice() {
  // Voice preset selection stored in the dropdown, read on generation
}

function getSelectedTTSVoice() {
  const mainSelect = document.getElementById('tts-voice-select');
  if (!mainSelect) return 'en-US-ChristopherNeural';
  
  if (mainSelect.value === 'clone_custom') {
    const kokoroPreset = document.getElementById('kokoro-voice-preset');
    if (kokoroPreset) {
      return 'kokoro_' + kokoroPreset.value;
    }
    return 'clone_custom';
  }
  
  return mainSelect.value;
}

// ==================== MISSING CLIPS ALERT & 1-CLICK AI IMAGE GENERATION ====================
function checkMissingClipsAlert(scenes) {
  const alertEl = document.getElementById('missing-clips-alert');
  if (!alertEl || !scenes) return;

  const missingScenes = scenes.filter(sc => 
    Boolean(sc.fallback_used) || 
    Boolean(sc.video_clip && sc.video_clip.is_fallback) || 
    !sc.video_clip || 
    !sc.video_clip.file_path
  );

  if (missingScenes.length > 0) {
    const titleEl = document.getElementById('missing-clips-count-title');
    const descEl = document.getElementById('missing-clips-desc');
    if (titleEl) {
      titleEl.textContent = `⚠️ ${missingScenes.length} Scene${missingScenes.length > 1 ? 's' : ''} Missing Matching Video Footage`;
    }
    if (descEl) {
      descEl.textContent = `Scenes are using fallback placeholders. Generate 16:9 Ultra HD AI Images to complete the video.`;
    }
    alertEl.classList.remove('hidden');
  } else {
    alertEl.classList.add('hidden');
  }
}

async function fixMissingClipsWithAI() {
  if (!currentProject || !currentProject.id) return;
  const btn = document.getElementById('btn-fix-missing-clips');
  const originalHtml = btn ? btn.innerHTML : '✨ Generate Ultra HD 16:9 AI Images (1-Click)';
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = '⏳ Generating Ultra HD 16:9 AI Images...';
  }

  showToast('🎨 Generating Ultra HD 16:9 cinematic AI images for missing scenes...', 3500);

  try {
    const res = await fetch('/api/generate-missing-scene-images', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ project_id: currentProject.id })
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Image generation failed');
    }
    const data = await res.json();
    if (data.scenes) {
      currentProject.scenes = data.scenes;
      captionEngine.loadScenes(currentProject.scenes);
      renderTimelineMarkers(currentProject.scenes);
      renderSceneCards(currentProject.scenes);
      checkMissingClipsAlert(currentProject.scenes);
      if (currentSceneIdx >= 0 && currentSceneIdx < currentProject.scenes.length) {
        loadSceneClip(currentSceneIdx, isPlaying);
      }
    }
    showToast(`🎉 Generated & applied <strong>${data.fixed_count}</strong> Ultra HD 16:9 AI Images with exact sentence durations!`, 5500);
  } catch (e) {
    console.error(e);
    alert('Failed to generate AI images: ' + e.message);
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = originalHtml;
    }
  }
}

async function generateSingleSceneAIImage(sceneId) {
  if (!currentProject || !currentProject.id) return;
  const sc = currentProject.scenes.find(s => s.id === sceneId);
  if (!sc) return;

  const scIdx = currentProject.scenes.findIndex(s => s.id === sceneId);
  const cardEl = document.getElementById('scene-card-' + scIdx);

  // Attach interactive loader directly over scene card
  let loaderEl = null;
  if (cardEl) {
    loaderEl = document.createElement('div');
    loaderEl.className = 'scene-card-generating-overlay';
    loaderEl.id = `card-loader-${sceneId}`;
    loaderEl.innerHTML = `
      <div class="card-loader-spinner"></div>
      <div style="font-size:11px;font-weight:700;color:var(--accent-cyan);text-align:center;margin-top:8px;">🎨 Generating AI Image...</div>
      <div style="font-size:10px;color:#94a3b8;text-align:center;margin-top:2px;">Ultra HD Photorealistic</div>
    `;
    cardEl.style.position = 'relative';
    cardEl.appendChild(loaderEl);

    // Temporarily disable action buttons on card
    cardEl.querySelectorAll('button').forEach(b => b.disabled = true);
  }

  const defaultPrompt = sc.selected_tag || (sc.search_tags && sc.search_tags[0]) || sc.text;
  const aspectRatio = document.getElementById('export-aspect-ratio')?.value || '16:9';

  showToast(`🎨 Generating Ultra HD ${aspectRatio} AI Image for Scene #${sc.scene_number}...`, 4000);

  try {
    const res = await fetch('/api/generate-single-scene-image', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        project_id: currentProject.id,
        scene_id: sceneId,
        custom_prompt: defaultPrompt,
        aspect_ratio: aspectRatio
      })
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Failed to generate image');
    }

    const data = await res.json();
    if (data.scenes) {
      currentProject.scenes = data.scenes;
      captionEngine.loadScenes(currentProject.scenes);
      renderTimelineMarkers(currentProject.scenes);
      renderSceneCards(currentProject.scenes);
      checkMissingClipsAlert(currentProject.scenes);

      if (currentSceneIdx === scIdx) {
        loadSceneClip(scIdx, isPlaying);
      }
    }
    showToast(`✨ Scene #${sc.scene_number} replaced with Ultra HD AI Image!`, 4500);
  } catch (err) {
    console.error(err);
    if (loaderEl && loaderEl.parentNode) {
      loaderEl.parentNode.removeChild(loaderEl);
    }
    if (cardEl) {
      cardEl.querySelectorAll('button').forEach(b => b.disabled = false);
    }
    alert('Error generating AI image: ' + err.message);
  }
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

// ==================== MASTER EFFECT TOGGLES ====================

function onToggleAnimation(enabled) {
  const wrapper = document.getElementById('animation-controls-wrapper');
  if (wrapper) {
    if (enabled) {
      wrapper.classList.remove('controls-disabled');
    } else {
      wrapper.classList.add('controls-disabled');
    }
  }
  updateCaptionStyle();
  showToast(enabled ? '⚡ Kinetic Animation enabled' : '⚡ Kinetic Animation disabled');
}

function onToggleBgm(enabled) {
  const wrapper = document.getElementById('bgm-controls-wrapper');
  if (wrapper) {
    if (enabled) {
      wrapper.classList.remove('controls-disabled');
    } else {
      wrapper.classList.add('controls-disabled');
    }
  }
  showToast(enabled ? '🎵 Background Music (BGM) enabled' : '🔇 Background Music (BGM) disabled');
}

function onToggleSfx(enabled) {
  const wrapper = document.getElementById('sfx-controls-wrapper');
  if (wrapper) {
    if (enabled) {
      wrapper.classList.remove('controls-disabled');
    } else {
      wrapper.classList.add('controls-disabled');
    }
  }
  showToast(enabled ? '🔊 Transition SFX enabled' : '🚫 Transition SFX disabled');
}

function onTogglePolish(enabled) {
  const wrapper = document.getElementById('polish-controls-wrapper');
  if (wrapper) {
    if (enabled) {
      wrapper.classList.remove('controls-disabled');
    } else {
      wrapper.classList.add('controls-disabled');
    }
  }
  showToast(enabled ? '🎬 Video Polish & Cinematic FX enabled' : '🎬 Video Polish & Cinematic FX disabled');
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

  const captionsEnabled = document.getElementById('enable-captions-toggle')?.checked ?? true;
  const animationEnabled = document.getElementById('enable-animation-toggle')?.checked ?? true;
  const bgmEnabled = document.getElementById('enable-bgm-toggle')?.checked ?? true;
  const sfxEnabled = document.getElementById('enable-sfx-toggle')?.checked ?? true;
  const polishEnabled = document.getElementById('enable-polish-toggle')?.checked ?? true;

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
    enable_captions: captionsEnabled,
    enable_animation: animationEnabled,
    animation: animationEnabled ? (document.getElementById('animation-style-select')?.value || 'word_bounce') : 'none',
    enable_bgm: bgmEnabled,
    bgm_track: bgmEnabled ? (document.getElementById('bgm-track-select')?.value || 'cinematic_ambient') : 'none',
    bgm_volume: bgmEnabled ? ((parseInt(document.getElementById('bgm-volume-slider')?.value || '10', 10)) / 100.0) : 0.0,
    enable_sfx: sfxEnabled,
    transition_sfx: sfxEnabled ? (document.getElementById('sfx-track-select')?.value || 'whoosh_soft') : 'none',
    transition_sfx_volume: sfxEnabled ? (parseFloat(document.getElementById('sfx-volume-slider')?.value || '40') / 100) : 0.0,
    enable_polish: polishEnabled,
    enable_motion: polishEnabled && (document.getElementById('kenburns-checkbox')?.checked ?? false),
    enable_vignette: polishEnabled && (document.getElementById('vignette-checkbox')?.checked ?? false),
    mute_stock_audio: document.getElementById('mute-stock-checkbox')?.checked ?? true,
    color_grade: polishEnabled ? (document.getElementById('color-grade-select')?.value || 'clean') : 'clean',
    transition: polishEnabled ? (document.getElementById('transition-select')?.value || 'none') : 'none',
    transition_mode: document.getElementById('transition-select')?.value === 'random' ? 'random' : 'fixed',
    transition_duration: parseFloat(document.getElementById('transition-speed-slider')?.value || '0.30'),
    target_resolution: document.getElementById('export-resolution')?.value || '1080p',
    aspect_ratio: document.getElementById('export-aspect-ratio')?.value || '16:9',
    ...getOverlaySettings()
  };

  const renderModal = document.getElementById('render-progress-modal');
  const progressBar = document.getElementById('render-progress-bar');
  const progressPct = document.getElementById('render-progress-pct');
  const statusMsg = document.getElementById('render-scene-status');
  const elapsedEl = document.getElementById('render-elapsed-time');
  const etaEl = document.getElementById('render-eta-time');

  // Reset progress state
  if (progressBar) progressBar.style.width = '3%';
  if (progressPct) progressPct.textContent = '3%';
  if (statusMsg) statusMsg.textContent = 'Initializing background render pipeline...';
  if (elapsedEl) elapsedEl.textContent = '00:00';
  if (etaEl) etaEl.textContent = 'Calculating...';

  const updateRenderSteppers = (pct) => {
    const s1 = document.getElementById('render-step-ass');
    const s2 = document.getElementById('render-step-filter');
    const s3 = document.getElementById('render-step-encode');
    const s4 = document.getElementById('render-step-finalize');
    if (!s1 || !s2 || !s3 || !s4) return;

    [s1, s2, s3, s4].forEach(s => s.classList.remove('active', 'completed'));

    if (pct < 15) {
      s1.classList.add('active');
    } else if (pct < 35) {
      s1.classList.add('completed');
      s2.classList.add('active');
    } else if (pct < 85) {
      s1.classList.add('completed');
      s2.classList.add('completed');
      s3.classList.add('active');
    } else if (pct < 100) {
      s1.classList.add('completed');
      s2.classList.add('completed');
      s3.classList.add('completed');
      s4.classList.add('active');
    } else {
      [s1, s2, s3, s4].forEach(s => s.classList.add('completed'));
    }
  };

  updateRenderSteppers(3);
  if (renderModal) renderModal.classList.remove('hidden');

  const formatSecs = (sec) => {
    if (sec === null || sec === undefined || isNaN(sec)) return '--:--';
    const m = Math.floor(sec / 60);
    const s = Math.floor(sec % 60);
    return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
  };

  try {
    const res = await fetch('/api/start-render', {
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
      throw new Error(err.detail || 'Rendering initiation failed');
    }

    const startData = await res.json();
    const jobId = startData.job_id;

    // Poll live render status every 500ms
    const result = await new Promise((resolve, reject) => {
      const pollTimer = setInterval(async () => {
        try {
          const pollRes = await fetch(`/api/render-progress/${jobId}`);
          if (!pollRes.ok) return;
          const job = await pollRes.json();

          const pct = Math.max(3, Math.min(100, job.progress || 0));
          if (progressBar) progressBar.style.width = `${pct}%`;
          if (progressPct) progressPct.textContent = `${pct}%`;
          if (statusMsg) statusMsg.textContent = job.stage_desc || job.stage || 'Rendering in progress...';
          updateFloatingDock('🎬 Rendering Final Video...', job.stage_desc || 'Encoding...', pct);
          if (elapsedEl) elapsedEl.textContent = formatSecs(job.elapsed_seconds);
          if (etaEl) {
            etaEl.textContent = job.eta_seconds !== null ? `~${formatSecs(job.eta_seconds)}` : 'Calculating...';
          }
          updateRenderSteppers(pct);

          if (job.status === 'completed') {
            clearInterval(pollTimer);
            const dock = document.getElementById('floating-task-dock');
            if (dock) dock.classList.add('hidden');
            activeMinimizedModal = null;
            resolve(job.result);
          } else if (job.status === 'error') {
            clearInterval(pollTimer);
            const dock = document.getElementById('floating-task-dock');
            if (dock) dock.classList.add('hidden');
            activeMinimizedModal = null;
            reject(new Error(job.error || 'Rendering job failed'));
          }
        } catch (pollErr) {
          // Keep polling through transient errors
        }
      }, 500);
    });

    if (renderModal) renderModal.classList.add('hidden');
    const dock = document.getElementById('floating-task-dock');
    if (dock) dock.classList.add('hidden');

    // Populate & open export complete modal
    const outputFileName = result.output_file || 'rendered_video.mp4';
    const webUrl = result.web_url || '';
    lastExportedVideoPath = result.output_path || outputFileName;
    lastExportedVideoName = outputFileName;
    lastExportedThumbnails = result.thumbnails || (currentProject && currentProject.thumbnails);

    document.getElementById('export-success-filename').textContent = `File: ${outputFileName}`;
    const exportedPlayer = document.getElementById('exported-video-player');
    
    // Resolve thumbnail URLs
    const projId = (currentProject && currentProject.id) || result.project_id || '';
    const t1Url = (lastExportedThumbnails && lastExportedThumbnails.thumb1_url)
      || (projId ? `/media/thumbnails/${projId}_thumb_1_viral.jpg` : '');
    const t2Url = (lastExportedThumbnails && lastExportedThumbnails.thumb2_url)
      || (projId ? `/media/thumbnails/${projId}_thumb_2_cinematic.jpg` : '');

    if (exportedPlayer) {
      exportedPlayer.src = webUrl;
      if (t1Url) {
        exportedPlayer.poster = `${t1Url}?v=${Date.now()}`;
      }
      exportedPlayer.load();
      exportedPlayer.addEventListener('loadedmetadata', () => {
        try { exportedPlayer.currentTime = 0.1; } catch (e) {}
      }, { once: true });
    }

    // Populate Thumbnail Preview Cards in Export Modal
    const mThumb1 = document.getElementById('export-modal-thumb-1');
    const mThumb2 = document.getElementById('export-modal-thumb-2');
    const mDl1 = document.getElementById('export-modal-dl-1');
    const mDl2 = document.getElementById('export-modal-dl-2');
    const baseCleanName = outputFileName.replace(/\.mp4$/i, '');

    if (mThumb1 && t1Url) {
      mThumb1.src = `${t1Url}?v=${Date.now()}`;
      mThumb1.style.display = 'block';
      if (mDl1) {
        mDl1.href = t1Url;
        mDl1.setAttribute('download', `${baseCleanName}_Thumb_Viral.jpg`);
        mDl1.classList.remove('disabled');
      }
    }
    if (mThumb2 && t2Url) {
      mThumb2.src = `${t2Url}?v=${Date.now()}`;
      mThumb2.style.display = 'block';
      if (mDl2) {
        mDl2.href = t2Url;
        mDl2.setAttribute('download', `${baseCleanName}_Thumb_Cinematic.jpg`);
        mDl2.classList.remove('disabled');
      }
    }

    const dlLink = document.getElementById('export-download-link');
    if (dlLink) {
      dlLink.href = webUrl;
      dlLink.setAttribute('download', outputFileName);
    }

    document.getElementById('export-complete-modal').classList.remove('hidden');
    showToast(`🎉 Video exported successfully: <strong>${outputFileName}</strong>`);
    loadProjectsLibrary();

    // Auto-open output folder in Windows Explorer with newly exported video selected
    openOutputFolder(lastExportedVideoPath);

    // Update active project thumbnails and sync Thumbnail Studio
    if (currentProject) {
      if (lastExportedThumbnails) {
        currentProject.thumbnails = lastExportedThumbnails;
      }
      loadProjectThumbnails(currentProject);
    }

  } catch (err) {
    if (renderModal) renderModal.classList.add('hidden');
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
    try {
      const pRes = await fetch('/api/projects');
      if (pRes.ok) {
        const projs = await pRes.json();
        if (projs && projs.length > 0) {
          currentProject = projs[0];
        }
      }
    } catch (e) {}
  }

  if (!currentProject) {
    alert('No active project found to export to CapCut! Please create or select a project first.');
    return;
  }

  pausePlayback();

  const fontEl = document.getElementById('font-family-select');
  const sizeEl = document.getElementById('font-size-slider');
  const letEl = document.getElementById('letter-spacing-slider');
  const wordEl = document.getElementById('word-spacing-slider');
  const primEl = document.getElementById('color-primary');
  const hiEl = document.getElementById('color-highlight');
  const strEl = document.getElementById('color-stroke');
  const strWEl = document.getElementById('stroke-width-slider');
  const marEl = document.getElementById('margin-v-slider');
  const upEl = document.getElementById('uppercase-checkbox');
  const animEl = document.getElementById('animation-style-select');

  const customOptions = {
    font_name: fontEl ? fontEl.value : 'Inter',
    font_size: sizeEl ? parseInt(sizeEl.value, 10) : 48,
    letter_spacing: letEl ? parseFloat(letEl.value) || 1 : 1,
    word_spacing: wordEl ? parseFloat(wordEl.value) || 6 : 6,
    primary_color: primEl ? primEl.value : '#FFFFFF',
    highlight_color: hiEl ? hiEl.value : '#FFE600',
    outline_color: strEl ? strEl.value : '#000000',
    outline_width: strWEl ? parseFloat(strWEl.value) : 2.5,
    margin_v: marEl ? parseInt(marEl.value, 10) : 60,
    uppercase: upEl ? upEl.checked : true,
    animation: animEl ? animEl.value : 'pop_up'
  };

  const pModal = document.getElementById('processing-modal');
  if (pModal) {
    document.getElementById('modal-status-title').textContent = 'Generating CapCut Timeline Project...';
    document.getElementById('modal-status-desc').textContent = 'Structuring video cuts, voiceover timeline, and kinetic caption tracks...';
    pModal.classList.remove('hidden');
  }

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
    if (pModal) pModal.classList.add('hidden');
    lastCapCutDraftPath = data.project_dir;

    const pathEl = document.getElementById('capcut-draft-path');
    if (pathEl) pathEl.textContent = data.project_dir;
    const msg = data.launched
      ? '🚀 CapCut.exe launched! Project template is ready on your timeline with all cuts, audio, and captions.'
      : '✅ CapCut draft generated and placed directly in your CapCut projects folder!';
    const statusEl = document.getElementById('capcut-status-msg');
    if (statusEl) statusEl.textContent = msg;

    const capcutModal = document.getElementById('capcut-modal');
    if (capcutModal) capcutModal.classList.remove('hidden');
    showToast(`✂️ CapCut draft ready: <strong>${data.folder_name}</strong>`);
  } catch (err) {
    if (pModal) pModal.classList.add('hidden');
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
            <button class="btn btn-warning btn-sm" onclick="openProjectThumbnails('${p.id}', event)" title="View YouTube Thumbnails">
              🖼️
            </button>
            <button class="btn btn-capcut btn-sm" onclick="exportProjectCardToCapCut('${p.id}')" title="Open in CapCut Timeline">
              ✂️ CapCut
            </button>
            <button class="btn btn-outline btn-sm" onclick="openOutputFolder()" title="Open Output Folder">
              📂
            </button>
            <button class="btn btn-danger btn-sm" onclick="deleteProject('${p.id}', event)" title="Delete Project">
              🗑️
            </button>
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

async function deleteProject(projectId, event) {
  if (event) event.stopPropagation();
  if (!confirm('Are you sure you want to delete this project?')) return;
  try {
    const res = await fetch(`/api/projects/${projectId}`, { method: 'DELETE' });
    if (!res.ok) throw new Error('Failed to delete project');
    showToast('🗑️ Project deleted successfully');
    await loadProjectsLibrary();
    if (currentProject && currentProject.id === projectId) {
      currentProject = null;
    }
  } catch (err) {
    alert('Error deleting project: ' + err.message);
  }
}

async function clearAllProjects() {
  if (!confirm('⚠️ Are you sure you want to delete ALL projects from your library? This action cannot be undone.')) return;
  try {
    const res = await fetch('/api/projects/all', { method: 'DELETE' });
    if (!res.ok) throw new Error('Failed to delete all projects');
    showToast('🗑️ All projects cleared successfully');
    currentProject = null;
    await loadProjectsLibrary();
  } catch (err) {
    alert('Error deleting projects: ' + err.message);
  }
}

// ==================== CAPTIONS TOGGLE & RESOLUTION HELPERS ====================

function onToggleCaptions(enabled) {
  if (captionEngine) {
    captionEngine.setEnabled(enabled);
  }
  const controls = document.getElementById('caption-customizer-controls');
  if (controls) {
    if (enabled) {
      controls.classList.remove('disabled');
    } else {
      controls.classList.add('disabled');
    }
  }
  if (currentProject) {
    currentProject.enable_captions = enabled;
  }
  showToast(enabled ? '💬 Subtitles Enabled for preview and export' : '🔇 Subtitles Disabled (Video only)');
}

function onTargetResolutionChange(val) {
  const badge = document.getElementById('studio-res-badge');
  if (badge) {
    if (val === '8k') {
      badge.textContent = '8K Ultra HD (7680x4320)';
      badge.className = 'badge badge-warning';
    } else if (val === '4k') {
      badge.textContent = '4K Ultra HD (3840x2160)';
      badge.className = 'badge badge-success';
    } else {
      badge.textContent = 'Full HD 1080p';
      badge.className = 'badge badge-info';
    }
  }
  const exportSel = document.getElementById('export-resolution');
  if (exportSel && exportSel.value !== val) {
    exportSel.value = val;
  }
}

function onExportResolutionChange(val) {
  const studioSel = document.getElementById('target-resolution-select');
  if (studioSel && studioSel.value !== val) {
    studioSel.value = val;
  }
  onTargetResolutionChange(val);
}

// ==================== YOUTUBE THUMBNAILS STUDIO ====================

async function switchToThumbnails() {
  closeExportModal();
  switchTab('thumbnails');
  if (!currentProject) {
    try {
      const res = await fetch('/api/projects');
      const projects = await res.json();
      if (projects && projects.length > 0) {
        currentProject = projects[0];
      }
    } catch (e) {}
  }
  if (currentProject) {
    await loadProjectThumbnails(currentProject);
  }
}

async function openProjectThumbnails(projectId, event) {
  if (event) event.stopPropagation();
  try {
    const res = await fetch('/api/projects');
    const projects = await res.json();
    const proj = projects.find(p => p.id === projectId);
    if (proj) {
      currentProject = proj;
      switchTab('thumbnails');
    }
  } catch (e) {
    console.error(e);
  }
}

async function loadProjectThumbnails(project) {
  const nameEl = document.getElementById('thumb-active-project-name');
  const nicheEl = document.getElementById('thumb-active-niche');
  const img1 = document.getElementById('thumb-img-1');
  const img2 = document.getElementById('thumb-img-2');
  const skel1 = document.getElementById('thumb-skeleton-1');
  const skel2 = document.getElementById('thumb-skeleton-2');
  const dl1 = document.getElementById('thumb-download-1');
  const dl2 = document.getElementById('thumb-download-2');
  const headlineInput = document.getElementById('thumb-custom-headline');

  // Fallback to active project if null
  if (!project) {
    try {
      const pRes = await fetch('/api/projects');
      if (pRes.ok) {
        const projs = await pRes.json();
        if (projs && projs.length > 0) {
          project = projs[0];
          currentProject = projs[0];
        }
      }
    } catch (e) {}
  }

  if (!project) {
    if (nameEl) nameEl.textContent = 'No Project Loaded';
    if (nicheEl) nicheEl.textContent = 'None';
    if (img1) img1.style.display = 'none';
    if (img2) img2.style.display = 'none';
    if (skel1) { skel1.style.display = 'flex'; skel1.querySelector('span').textContent = 'Render a video to generate thumbnails...'; }
    if (skel2) { skel2.style.display = 'flex'; skel2.querySelector('span').textContent = 'Render a video to generate thumbnails...'; }
    if (dl1) dl1.classList.add('disabled');
    if (dl2) dl2.classList.add('disabled');
    return;
  }

  if (nameEl) nameEl.textContent = project.name || project.id || 'Active Video';
  if (nicheEl) nicheEl.textContent = project.niche || 'General';

  // Helper to render thumbnails onto the DOM
  function applyThumbs(thumbs) {
    if (!thumbs) return;
    if (img1 && thumbs.thumb1_url) {
      img1.src = `${thumbs.thumb1_url}?v=${Date.now()}`;
      img1.style.display = 'block';
      if (skel1) skel1.style.display = 'none';
      if (dl1) {
        dl1.href = thumbs.thumb1_url;
        dl1.setAttribute('download', `${project.name || 'Video'}_Thumb_Viral.jpg`);
        dl1.classList.remove('disabled');
      }
    }
    if (img2 && thumbs.thumb2_url) {
      img2.src = `${thumbs.thumb2_url}?v=${Date.now()}`;
      img2.style.display = 'block';
      if (skel2) skel2.style.display = 'none';
      if (dl2) {
        dl2.href = thumbs.thumb2_url;
        dl2.setAttribute('download', `${project.name || 'Video'}_Thumb_Cinematic.jpg`);
        dl2.classList.remove('disabled');
      }
    }
    if (headlineInput && thumbs.headline_line1) {
      headlineInput.value = `${thumbs.headline_line1} ${thumbs.headline_line2 || ''}`.trim();
    }
  }

  // 1. Immediately render if already present in project object
  if (project.thumbnails && (project.thumbnails.thumb1_url || project.thumbnails.thumb2_url)) {
    applyThumbs(project.thumbnails);
  }

  // 2. Fetch fresh thumbnails from server
  try {
    const res = await fetch(`/api/thumbnails/${project.id}`);
    if (res.ok) {
      const data = await res.json();
      const thumbs = data.thumbnails;
      if (thumbs) {
        project.thumbnails = thumbs;
        applyThumbs(thumbs);
      }
    }
    // Also load SEO metadata for this project
    loadProjectSEO(project);
  } catch (err) {
    console.error('Error loading thumbnails:', err);
  }
}

async function regenerateThumbnails() {
  if (!currentProject) {
    alert('Please select or create a project first!');
    return;
  }
  const btn = document.getElementById('regen-thumb-btn');
  const origText = btn ? btn.innerHTML : '';
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = '⏳ Generating...';
  }

  try {
    const res = await fetch('/api/generate-thumbnails', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ project_id: currentProject.id })
    });
    if (!res.ok) throw new Error('Thumbnail generation failed');
    const data = await res.json();
    currentProject.thumbnails = data.thumbnails;
    await loadProjectThumbnails(currentProject);
    showToast('✨ 2 YouTube Thumbnails re-generated successfully!');
  } catch (err) {
    alert('Failed to re-generate thumbnails: ' + err.message);
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = origText;
    }
  }
}

async function applyCustomThumbnailHeadline() {
  if (!currentProject) {
    alert('Please select or create a project first!');
    return;
  }
  const input = document.getElementById('thumb-custom-headline');
  const headline = input ? input.value.trim() : '';
  if (!headline) {
    alert('Please enter a headline hook first!');
    return;
  }

  showToast('⚡ Generating custom thumbnails...');
  try {
    const res = await fetch('/api/generate-thumbnails', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        project_id: currentProject.id,
        custom_headline: headline
      })
    });
    if (!res.ok) throw new Error('Failed to generate with custom headline');
    const data = await res.json();
    currentProject.thumbnails = data.thumbnails;
    await loadProjectThumbnails(currentProject);
    showToast('🎉 Thumbnails updated with your custom headline!');
  } catch (err) {
    alert('Error: ' + err.message);
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

// ==================== EDITING TEMPLATES & PRESETS ====================
async function loadEditingTemplates() {
  try {
    const res = await fetch('/api/templates');
    if (!res.ok) return;
    const list = await res.json();
    allEditingTemplates = {};
    list.forEach(t => { allEditingTemplates[t.id] = t; });
  } catch (e) {
    console.error('Failed to load editing templates:', e);
  }
}

function selectBulkTemplate(tmplId) {
  selectedBulkTemplateId = tmplId;
  document.querySelectorAll('.template-card').forEach(c => c.classList.remove('active'));
  const card = document.getElementById(`tmpl-card-${tmplId}`);
  if (card) card.classList.add('active');

  const tmpl = allEditingTemplates[tmplId];
  if (tmpl && tmpl.niche) {
    const nicheSel = document.getElementById('batch-niche-select');
    if (nicheSel) {
      for (let i = 0; i < nicheSel.options.length; i++) {
        if (nicheSel.options[i].value === tmpl.niche || nicheSel.options[i].text.includes(tmpl.niche)) {
          nicheSel.selectedIndex = i;
          break;
        }
      }
    }
  }
  showToast(`⚡ Selected Template: <strong>${tmpl ? tmpl.name : tmplId}</strong>`);
}

function onSingleTemplateChange(tmplId) {
  const tmpl = allEditingTemplates[tmplId];
  if (!tmpl) return;
  const nicheSel = document.getElementById('niche-select');
  if (nicheSel && tmpl.niche) {
    for (let i = 0; i < nicheSel.options.length; i++) {
      if (nicheSel.options[i].value === tmpl.niche || nicheSel.options[i].text.includes(tmpl.niche)) {
        nicheSel.selectedIndex = i;
        break;
      }
    }
  }
  showToast(`📱 Set Template: <strong>${tmpl.name}</strong>`);
}

function applyEditingTemplate(tmplId) {
  const tmpl = allEditingTemplates[tmplId];
  if (!tmpl) return;

  // 1. Transition & Speed
  if (document.getElementById('transition-select')) {
    if (tmpl.transition_mode === 'random') {
      document.getElementById('transition-select').value = 'random';
    } else if (tmpl.transition) {
      document.getElementById('transition-select').value = tmpl.transition;
    }
  }
  if (tmpl.transition_duration !== undefined && document.getElementById('transition-speed-slider')) {
    document.getElementById('transition-speed-slider').value = tmpl.transition_duration;
    const speedLbl = document.getElementById('transition-speed-val');
    if (speedLbl) speedLbl.textContent = parseFloat(tmpl.transition_duration).toFixed(2);
  }

  // 2. BGM
  if (tmpl.bgm_track && document.getElementById('bgm-track-select')) {
    const key = tmpl.bgm_track.replace('.mp3', '');
    document.getElementById('bgm-track-select').value = key;
  }
  if (tmpl.bgm_volume !== undefined && document.getElementById('bgm-volume-slider')) {
    const volPct = Math.round(tmpl.bgm_volume * 100);
    document.getElementById('bgm-volume-slider').value = volPct;
    const volLbl = document.getElementById('bgm-volume-val');
    if (volLbl) volLbl.textContent = volPct;
  }

  // 3. Kinetic Caption Style
  if (tmpl.caption_style) {
    const presetKey = tmpl.caption_style.replace('-', '_');
    applyPreset(presetKey);
  }

  // 4. Aspect Ratio visual
  const container = document.getElementById('video-container');
  if (container) {
    if (tmpl.aspect_ratio === '9:16') {
      container.classList.add('aspect-9-16');
    } else {
      container.classList.remove('aspect-9-16');
    }
  }

  showToast(`✨ Applied Master Template: <strong>${tmpl.name}</strong>`);
}

function updateTransitionSpeed(val) {
  const lbl = document.getElementById('transition-speed-val');
  if (lbl) lbl.textContent = parseFloat(val).toFixed(2);
}

// ==================== BATCH MULTI-AUDIO UPLOAD & QUEUE ====================
function setupBatchDropzone() {
  const dropzone = document.getElementById('batch-dropzone');
  if (!dropzone) return;

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
      uploadBatchFiles(Array.from(files));
    }
  });
}

function handleBatchAudioSelect(event) {
  const files = event.target.files;
  if (files.length > 0) {
    uploadBatchFiles(Array.from(files));
  }
}

async function uploadBatchFiles(files) {
  const promptEl = document.getElementById('batch-dropzone-prompt');
  promptEl.innerHTML = '<div class="modal-spinner" style="width:28px;height:28px;margin-bottom:8px;"></div><h3>Uploading and analyzing audio clips in parallel...</h3>';

  const formData = new FormData();
  files.forEach(f => formData.append('files', f));

  try {
    const res = await fetch('/api/batch-upload-audio', {
      method: 'POST',
      body: formData
    });
    const data = await res.json();
    if (data.files && data.files.length > 0) {
      batchFilesData.push(...data.files);
    }
    renderBatchFilesPreview();
    showToast(`🎵 Added <strong>${data.files.length}</strong> audio files to queue!`);
  } catch (err) {
    alert('Failed to upload audio files: ' + err.message);
  } finally {
    promptEl.innerHTML = `
      <div class="dropzone-icon">📁⚡</div>
      <h3>Drop multiple voiceover audio files here or click to browse</h3>
      <p>Select 2, 5, 10 or more MP3/WAV files to process in parallel</p>
    `;
    const inp = document.getElementById('batch-audio-input');
    if (inp) inp.value = '';
  }
}

function renderBatchFilesPreview() {
  const box = document.getElementById('batch-files-preview-box');
  const listEl = document.getElementById('batch-files-list');
  const countNum = document.getElementById('batch-count-num');
  const btnCount = document.getElementById('batch-btn-count');
  const startBtn = document.getElementById('batch-start-btn');

  if (batchFilesData.length === 0) {
    box.classList.add('hidden');
    startBtn.disabled = true;
    if (countNum) countNum.textContent = '0';
    if (btnCount) btnCount.textContent = '0';
    return;
  }

  box.classList.remove('hidden');
  startBtn.disabled = false;
  if (countNum) countNum.textContent = batchFilesData.length;
  if (btnCount) btnCount.textContent = batchFilesData.length;

  listEl.innerHTML = '';
  batchFilesData.forEach((f, idx) => {
    const chip = document.createElement('div');
    chip.className = 'batch-file-chip';
    const mins = Math.floor(f.duration / 60);
    const secs = Math.floor(f.duration % 60);
    chip.innerHTML = `
      <div class="batch-file-chip-info">
        <span class="batch-file-chip-name">${f.original_name}</span>
        <span class="batch-file-chip-meta">⏱ ${mins}:${secs < 10 ? '0' : ''}${secs}</span>
      </div>
      <button class="batch-file-remove-btn" onclick="removeBatchFile(${idx})" title="Remove">✕</button>
    `;
    listEl.appendChild(chip);
  });
}

function removeBatchFile(idx) {
  batchFilesData.splice(idx, 1);
  renderBatchFilesPreview();
}

function resetBatchUpload() {
  batchFilesData = [];
  renderBatchFilesPreview();
}

// ==================== BATCH GENERATION EXECUTION & POLLING ====================
let currentActiveBatchId = null;

async function cancelActiveBatch() {
  if (!currentActiveBatchId) {
    showToast('No active batch to cancel');
    return;
  }
  const btn = document.getElementById('btn-cancel-batch');
  if (btn) {
    btn.disabled = true;
    btn.textContent = '⏳ Cancelling...';
  }
  try {
    const res = await fetch(`/api/batch-cancel/${currentActiveBatchId}`, { method: 'POST' });
    if (res.ok) {
      showToast('🛑 Batch cancellation requested. Active videos will wrap up, remaining queued items will stop.');
      const statusEl = document.getElementById('batch-overall-status');
      if (statusEl) statusEl.textContent = 'Cancelling remaining queued videos...';
    } else {
      showToast('Failed to cancel batch.');
    }
  } catch (err) {
    console.error('Failed to cancel batch:', err);
    showToast('Network error while cancelling batch.');
  }
}

async function startBatchGeneration() {
  if (batchFilesData.length === 0) {
    alert('Please upload voiceover audio files first!');
    return;
  }

  const niche = document.getElementById('batch-niche-select').value;
  const autoRender = document.getElementById('batch-autorender-checkbox').checked;
  const filenames = batchFilesData.map(f => f.filename);

  const dashCard = document.getElementById('batch-dashboard-card');
  dashCard.classList.remove('hidden');
  dashCard.scrollIntoView({ behavior: 'smooth' });

  document.getElementById('batch-start-btn').disabled = true;
  document.getElementById('batch-overall-status').textContent = 'Starting multi-worker batch pipeline...';
  document.getElementById('batch-overall-progress-bar').style.width = '2%';
  document.getElementById('batch-overall-pct').textContent = '2%';
  document.getElementById('batch-completed-counter').textContent = `0 / ${filenames.length} Completed`;

  const cancelBtn = document.getElementById('btn-cancel-batch');
  if (cancelBtn) {
    cancelBtn.disabled = false;
    cancelBtn.textContent = '⏹️ Cancel Batch';
  }

  const container = document.getElementById('batch-items-container');
  container.innerHTML = '';
  batchFilesData.forEach((f, idx) => {
    const card = document.createElement('div');
    card.className = 'batch-item-card';
    card.id = `batch-item-card-${idx}`;
    card.innerHTML = `
      <div class="batch-item-top">
        <span class="batch-item-title">${f.original_name}</span>
        <span class="batch-item-status-badge queued" id="batch-item-badge-${idx}">Queued</span>
      </div>
      <div class="progress-bar-wrap" style="height:6px;">
        <div class="progress-bar" id="batch-item-bar-${idx}" style="width: 0%;"></div>
      </div>
      <div class="batch-item-desc" id="batch-item-desc-${idx}">Waiting in worker queue...</div>
      <div class="batch-item-actions hidden" id="batch-item-actions-${idx}"></div>
    `;
    container.appendChild(card);
  });

  try {
    const res = await fetch('/api/start-batch-generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        audio_filenames: filenames,
        template_id: selectedBulkTemplateId,
        niche: niche,
        pipeline: activePipeline,
        auto_render: autoRender
      })
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Failed to start batch');
    }

    const { batch_id } = await res.json();
    currentActiveBatchId = batch_id;

    if (activeBatchPollInterval) clearInterval(activeBatchPollInterval);

    activeBatchPollInterval = setInterval(async () => {
      try {
        const pRes = await fetch(`/api/batch-progress/${batch_id}`);
        if (!pRes.ok) return;
        const job = await pRes.json();

        // Update overall batch bar
        const total = job.total || filenames.length;
        const completed = job.completed || 0;
        const overallPct = job.percent || Math.round((completed / total) * 100);

        document.getElementById('batch-overall-progress-bar').style.width = `${overallPct}%`;
        document.getElementById('batch-overall-pct').textContent = `${overallPct}%`;
        document.getElementById('batch-completed-counter').textContent = `${completed} / ${total} Completed`;
        
        if (job.status === 'cancelled') {
          document.getElementById('batch-overall-status').textContent = '⏹️ Batch stopped / cancelled by user.';
        } else if (job.status === 'completed') {
          document.getElementById('batch-overall-status').textContent = '✅ All batch videos finished successfully!';
        } else {
          document.getElementById('batch-overall-status').textContent = `Processing ${total - completed} videos concurrently across 6-8 worker threads...`;
        }

        // Update individual cards
        if (job.items) {
          job.items.forEach((item, i) => {
            const badge = document.getElementById(`batch-item-badge-${i}`);
            const bar = document.getElementById(`batch-item-bar-${i}`);
            const desc = document.getElementById(`batch-item-desc-${i}`);
            const act = document.getElementById(`batch-item-actions-${i}`);
            const card = document.getElementById(`batch-item-card-${i}`);

            if (badge) {
              badge.className = `batch-item-status-badge ${item.status}`;
              badge.textContent = item.status.toUpperCase();
            }
            if (bar) {
              bar.style.width = `${item.percent || 0}%`;
            }
            if (desc) {
              let msg = item.error ? `❌ Error: ${item.error}` : (item.stage_desc || 'Processing...');
              if (item.fallback_scenes_count > 0 && !msg.includes('gradient')) {
                msg += ` <span style="color:#f59e0b;font-size:11px;font-weight:600;">(⚠️ ${item.fallback_scenes_count} gradient fallback)</span>`;
              }
              desc.innerHTML = msg;
            }
            if (card) {
              if (item.status === 'completed') card.className = 'batch-item-card completed';
              if (item.status === 'error') card.className = 'batch-item-card error';
              if (item.status === 'cancelled') card.className = 'batch-item-card error';
            }

            if (item.status === 'completed' && act && act.classList.contains('hidden')) {
              act.classList.remove('hidden');
              act.innerHTML = `
                ${item.project_id ? `<button class="btn btn-secondary btn-sm" onclick="openProjectInPreview('${item.project_id}')">🎬 Studio</button>` : ''}
                ${item.project_id ? `<button class="btn btn-capcut btn-sm" onclick="exportProjectCardToCapCut('${item.project_id}')">✂️ CapCut</button>` : ''}
                ${item.rendered_url ? `<a href="${item.rendered_url}" download class="btn btn-success btn-sm">💾 MP4</a>` : ''}
              `;
            }
          });
        }

        if (job.status === 'completed' || job.status === 'cancelled') {
          clearInterval(activeBatchPollInterval);
          activeBatchPollInterval = null;
          document.getElementById('batch-start-btn').disabled = false;
          const cancelBtn = document.getElementById('btn-cancel-batch');
          if (cancelBtn) {
            cancelBtn.disabled = true;
            cancelBtn.textContent = job.status === 'cancelled' ? 'Cancelled' : '⏹️ Cancel Batch';
          }
          if (job.status === 'completed') {
            showToast('🎉 All batch videos processed & rendered successfully!');
          } else {
            showToast('⏹️ Batch cancelled.');
          }
          loadProjectsLibrary();
        }
      } catch (err) {
        console.error('Error polling batch progress:', err);
      }
    }, 600);

  } catch (err) {
    alert('Failed to start batch generation: ' + err.message);
    document.getElementById('batch-start-btn').disabled = false;
  }
}

// ==================== AUDIO INPUT MODE SWITCHER & TTS ====================

function switchAudioMode(mode) {
  const uploadBtn = document.getElementById('mode-btn-upload');
  const ttsBtn = document.getElementById('mode-btn-tts');
  const cloneBtn = document.getElementById('mode-btn-clone');
  const uploadPanel = document.getElementById('audio-upload-panel');
  const ttsPanel = document.getElementById('audio-tts-panel');
  const clonePanel = document.getElementById('audio-clone-panel');

  [uploadBtn, ttsBtn, cloneBtn].forEach(b => b?.classList.remove('active'));
  [uploadPanel, ttsPanel, clonePanel].forEach(p => p?.classList.add('hidden'));

  if (mode === 'upload') {
    uploadBtn?.classList.add('active');
    uploadPanel?.classList.remove('hidden');
  } else if (mode === 'clone') {
    cloneBtn?.classList.add('active');
    clonePanel?.classList.remove('hidden');
    checkKokoroStatus();
  } else {
    ttsBtn?.classList.add('active');
    ttsPanel?.classList.remove('hidden');
  }
}

// ==================== ASPECT RATIO SWITCHER ====================
function onAspectRatioChange(val) {
  const container = document.getElementById('video-container');
  const sel = document.getElementById('export-aspect-ratio');
  if (sel && sel.value !== val) sel.value = val;

  if (container) {
    if (val === '9:16') {
      container.classList.add('aspect-9-16');
      showToast('📱 Switched to <strong>9:16 Vertical</strong> (Shorts, TikTok, Reels)');
    } else {
      container.classList.remove('aspect-9-16');
      showToast('📺 Switched to <strong>16:9 Landscape</strong> (YouTube Full HD)');
    }
  }
}

// ==================== FLOATING BACKGROUND TASK DOCK & MINIMIZE ====================
let activeMinimizedModal = null; // 'processing' or 'render'

function updateFloatingDock(title, desc, pct) {
  const tEl = document.getElementById('dock-task-title');
  const dEl = document.getElementById('dock-task-desc');
  const pEl = document.getElementById('dock-task-pct');
  if (tEl && title) tEl.textContent = title;
  if (dEl && desc) dEl.textContent = `${desc} (${pct}%)`;
  if (pEl && pct !== undefined) pEl.textContent = `${pct}%`;
}

function minimizeProcessingModal() {
  const modal = document.getElementById('processing-modal');
  const dock = document.getElementById('floating-task-dock');
  if (modal) modal.classList.add('hidden');
  if (dock) dock.classList.remove('hidden');
  activeMinimizedModal = 'processing';
  showToast('⚡ Generating draft in background. Click floating dock to restore anytime.', 3500);
}

function minimizeRenderModal() {
  const modal = document.getElementById('render-progress-modal');
  const dock = document.getElementById('floating-task-dock');
  if (modal) modal.classList.add('hidden');
  if (dock) dock.classList.remove('hidden');
  activeMinimizedModal = 'render';
  showToast('🎬 Rendering video in background. Click floating dock to restore anytime.', 3500);
}

function restoreActiveModal() {
  const dock = document.getElementById('floating-task-dock');
  if (dock) dock.classList.add('hidden');
  if (activeMinimizedModal === 'render') {
    const modal = document.getElementById('render-progress-modal');
    if (modal) modal.classList.remove('hidden');
  } else {
    const modal = document.getElementById('processing-modal');
    if (modal) modal.classList.remove('hidden');
  }
  activeMinimizedModal = null;
}

// ==================== DEDICATED VOICE CLONING HANDLERS ====================
let uploadedVoiceSamplePath = null;

async function handleVoiceSampleUpload(event) {
  const file = event.target.files && event.target.files[0];
  if (!file) return;

  const infoEl = document.getElementById('clone-sample-active-info');
  const nameEl = document.getElementById('clone-sample-name');

  try {
    const formData = new FormData();
    formData.append('file', file);
    const res = await fetch('/api/upload-voice-sample', { method: 'POST', body: formData });
    if (!res.ok) throw new Error('Upload failed');
    const data = await res.json();
    uploadedVoiceSamplePath = data.path;
    if (nameEl) nameEl.textContent = data.filename || file.name;
    if (infoEl) infoEl.classList.remove('hidden');
    showToast(`🎤 Voice reference sample uploaded: <strong>${data.filename || file.name}</strong>`);
  } catch (e) {
    alert('Voice sample upload failed: ' + e.message);
  }
}

function clearVoiceSample() {
  uploadedVoiceSamplePath = null;
  const infoEl = document.getElementById('clone-sample-active-info');
  if (infoEl) infoEl.classList.add('hidden');
  const inputEl = document.getElementById('clone-sample-input');
  if (inputEl) inputEl.value = '';
  showToast('Voice reference cleared. Synthesizing with preset voice.');
}

function onCloneScriptInput() {
  const text = document.getElementById('clone-script-input')?.value || '';
  const words = text.trim() ? text.trim().split(/\s+/).length : 0;
  const estSec = Math.round(words / 2.5);
  const wcEl = document.getElementById('clone-word-count');
  const durEl = document.getElementById('clone-est-dur');
  if (wcEl) wcEl.textContent = words;
  if (durEl) durEl.textContent = `~${estSec}s`;
}

function loadCloneSampleScript() {
  const sample = "The future of automated video creation is here. With local voice cloning and AI scene synthesis, anyone can produce studio-quality videos in seconds.";
  const input = document.getElementById('clone-script-input');
  if (input) {
    input.value = sample;
    onCloneScriptInput();
  }
}

function onCloneRateChange(val) {
  const el = document.getElementById('clone-rate-val');
  if (el) {
    const num = parseFloat(val);
    el.textContent = num === 1.0 ? 'Normal' : `${num.toFixed(2)}x`;
  }
}

async function generateClonedVoiceover() {
  const script = document.getElementById('clone-script-input')?.value.trim();
  if (!script) {
    alert('Please enter a script text to synthesize.');
    return;
  }

  const preset = document.getElementById('clone-tab-preset-select')?.value || 'af_heart';
  const voice = 'kokoro_' + preset;
  const btn = document.getElementById('btn-gen-clone');
  const originalText = btn ? btn.innerHTML : '🧬 Generate Voice';
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = '⏳ Synthesizing Voice...';
  }

  try {
    const res = await fetch('/api/generate-voiceover', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        text: script,
        voice: voice,
        rate: '+0%',
        pitch: '+0Hz'
      })
    });
    if (!res.ok) {
      const errData = await res.json();
      throw new Error(errData.detail || 'Voice generation failed');
    }
    const data = await res.json();
    uploadedAudioData = {
      filename: data.filename,
      duration: data.duration,
      url: data.audio_url
    };

    const box = document.getElementById('clone-preview-box');
    const player = document.getElementById('clone-audio-player');
    const durEl = document.getElementById('clone-audio-dur');

    if (player) {
      player.src = data.audio_url;
      player.load();
    }
    if (durEl) {
      const m = Math.floor(data.duration / 60);
      const s = Math.floor(data.duration % 60).toString().padStart(2, '0');
      durEl.textContent = `${m}:${s}`;
    }
    if (box) box.classList.remove('hidden');

    // Also update main audio fileinfo state
    const prompt = document.getElementById('dropzone-prompt');
    const fileinfo = document.getElementById('dropzone-fileinfo');
    const fn = document.getElementById('audio-filename');
    const durStat = document.getElementById('audio-duration-stat');
    if (prompt) prompt.classList.add('hidden');
    if (fileinfo) fileinfo.classList.remove('hidden');
    if (fn) fn.textContent = `🧬 Cloned Voice (${data.filename})`;
    uploadedAudioFilename = data.filename;
    const startBtn = document.getElementById('start-generate-btn');
    if (startBtn) startBtn.disabled = false;

    showToast(`🧬 Voice synthesized successfully! Ready to generate video.`);
  } catch (e) {
    console.error(e);
    alert('Voice generation notice: ' + e.message + '\n\nNote: If Kokoro is not installed, the app falls back to Microsoft Edge-TTS.');
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = originalText;
    }
  }
}

function onTTSScriptInput() {
  const text = document.getElementById('tts-script-input')?.value || '';
  const words = text.trim() ? text.trim().split(/\s+/).length : 0;
  const estSec = Math.round(words / 2.5);
  const wcEl = document.getElementById('tts-word-count');
  const durEl = document.getElementById('tts-est-dur');
  if (wcEl) wcEl.textContent = words;
  if (durEl) durEl.textContent = `~${estSec}s`;
}

let activeSampleAudio = null;

async function loadTTSVoices() {
  try {
    const res = await fetch('/api/tts-voices');
    if (!res.ok) return;
    const data = await res.json();
    const voices = data.voices || [];
    const select = document.getElementById('tts-voice-select');
    if (!select || voices.length === 0) return;

    select.innerHTML = '';

    const edgeVoices = voices.filter(v => v.provider === 'edge');
    const kokoroVoices = voices.filter(v => v.provider === 'kokoro_clone');
    const elevenVoices = voices.filter(v => v.provider === 'elevenlabs');
    const openaiVoices = voices.filter(v => v.provider === 'openai');

    if (kokoroVoices.length > 0) {
      const group = document.createElement('optgroup');
      group.label = '🧬 Local AI Voice Cloning (Kokoro-82M / Free)';
      kokoroVoices.forEach(v => {
        const opt = document.createElement('option');
        opt.value = v.id;
        opt.textContent = `${v.flag || '🧬'} ${v.name} - ${v.style}`;
        group.appendChild(opt);
      });
      select.appendChild(group);
    }

    if (edgeVoices.length > 0) {
      const group = document.createElement('optgroup');
      group.label = '🌟 100% Free Human Neural Voices (Zero Setup / Unlimited)';
      edgeVoices.forEach(v => {
        const opt = document.createElement('option');
        opt.value = v.id;
        opt.textContent = `${v.flag || '🎙️'} ${v.name} - ${v.style}`;
        opt.dataset.sampleUrl = v.sample_url;
        if (v.id === 'en-US-AndrewMultilingualNeural') opt.selected = true;
        group.appendChild(opt);
      });
      select.appendChild(group);
    }

    if (elevenVoices.length > 0) {
      const group = document.createElement('optgroup');
      group.label = '💎 ElevenLabs Voices (Free Tier Supported in Settings)';
      elevenVoices.forEach(v => {
        const opt = document.createElement('option');
        opt.value = v.id;
        opt.textContent = `${v.flag || '💎'} ${v.name} - ${v.style}`;
        opt.dataset.sampleUrl = v.sample_url;
        group.appendChild(opt);
      });
      select.appendChild(group);
    }

    if (openaiVoices.length > 0) {
      const group = document.createElement('optgroup');
      group.label = '🤖 OpenAI Speech Voices (API Key in Settings)';
      openaiVoices.forEach(v => {
        const opt = document.createElement('option');
        opt.value = v.id;
        opt.textContent = `${v.flag || '🤖'} ${v.name} - ${v.style}`;
        opt.dataset.sampleUrl = v.sample_url;
        group.appendChild(opt);
      });
      select.appendChild(group);
    }
  } catch (e) {
    console.warn('Could not load dynamic TTS voices:', e);
  }
}

function previewSelectedVoice() {
  const select = document.getElementById('tts-voice-select');
  const selectedOption = select?.options[select.selectedIndex];
  const voiceId = select?.value || 'en-US-AndrewMultilingualNeural';
  const sampleUrl = selectedOption?.dataset?.sampleUrl || `/media/sfx/tts_samples/${voiceId}.mp3`;
  const btn = document.getElementById('btn-preview-voice');

  if (activeSampleAudio) {
    activeSampleAudio.pause();
    activeSampleAudio.currentTime = 0;
  }

  if (btn) {
    btn.innerHTML = '🔊 Playing...';
    btn.classList.add('btn-primary');
    btn.classList.remove('btn-secondary');
  }

  activeSampleAudio = new Audio(sampleUrl);

  activeSampleAudio.onended = () => {
    if (btn) {
      btn.innerHTML = '🔊 Listen Sample';
      btn.classList.remove('btn-primary');
      btn.classList.add('btn-secondary');
    }
  };

  activeSampleAudio.onerror = () => {
    if (btn) {
      btn.innerHTML = '🔊 Listen Sample';
      btn.classList.remove('btn-primary');
      btn.classList.add('btn-secondary');
    }
  };

  activeSampleAudio.play().catch(e => {
    console.warn('Voice preview error:', e);
    if (btn) {
      btn.innerHTML = '🔊 Listen Sample';
      btn.classList.remove('btn-primary');
      btn.classList.add('btn-secondary');
    }
  });
}


function onTTSRateChange(val) {
  const el = document.getElementById('tts-rate-val');
  if (el) {
    const num = parseInt(val, 10);
    el.textContent = num === 0 ? 'Normal' : (num > 0 ? `+${num}%` : `${num}%`);
  }
}

function loadSampleScript() {
  const sample = "Artificial intelligence is quietly revolutionizing how YouTube videos are created in 2026. Creators who leverage automated video pipelines are publishing high-retention content in minutes rather than days. In this video, we reveal the top three strategies used by modern cash-cow channels to dominate the algorithm.";
  const input = document.getElementById('tts-script-input');
  if (input) {
    input.value = sample;
    onTTSScriptInput();
  }
}

async function generateAIVoiceover() {
  const text = document.getElementById('tts-script-input')?.value.trim();
  if (!text) {
    alert('Please enter or paste your video script first!');
    return;
  }

  const voice = getSelectedTTSVoice();
  const rateVal = parseInt(document.getElementById('tts-rate-slider')?.value || '0', 10);
  const rate = rateVal >= 0 ? `+${rateVal}%` : `${rateVal}%`;

  const btn = document.getElementById('btn-gen-tts');
  const origText = btn ? btn.innerHTML : '';
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = '⏳ Generating Voiceover...';
  }

  try {
    const res = await fetch('/api/generate-voiceover', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text, voice, rate })
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'TTS generation failed');
    }

    const data = await res.json();
    uploadedAudioFilename = data.filename;

    // Show preview audio player
    const previewBox = document.getElementById('tts-preview-box');
    const player = document.getElementById('tts-audio-player');
    const durEl = document.getElementById('tts-audio-dur');

    if (previewBox) previewBox.classList.remove('hidden');
    if (durEl) durEl.textContent = `${Math.floor(data.duration / 60)}:${Math.floor(data.duration % 60).toString().padStart(2, '0')}`;
    if (player) {
      player.src = data.url;
      player.load();
    }

    // Enable Start Generation button in Single Studio
    const startBtn = document.getElementById('start-generate-btn');
    if (startBtn) startBtn.disabled = false;

    showToast(`🎉 AI Voiceover ready (${data.duration}s)! You can now click <strong>Generate Complete Video</strong>.`);
  } catch (err) {
    alert('AI Voiceover Error: ' + err.message);
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = origText;
    }
  }
}

// ==================== TRANSITION SFX ====================

function updateSfxSelection() {
  const select = document.getElementById('sfx-track-select');
  if (currentProject && select) {
    currentProject.transition_sfx = select.value;
  }
}

function updateSfxVolume(val) {
  const el = document.getElementById('sfx-volume-val');
  if (el) el.textContent = val;
  if (currentProject) {
    currentProject.transition_sfx_volume = parseFloat(val) / 100;
  }
}

// ==================== YOUTUBE SEO SUITE ====================

async function loadProjectSEO(project) {
  if (!project || !project.id) return;
  try {
    const res = await fetch(`/api/seo/${project.id}`);
    if (res.ok) {
      const data = await res.json();
      if (data && data.status === 'success') {
        populateSEOUi(data);
        return;
      }
    }
    // Auto-generate if not present
    regenerateSEO();
  } catch (e) {
    console.error('Error loading SEO metadata:', e);
  }
}

async function regenerateSEO() {
  if (!currentProject) {
    alert('Please select or create a project first!');
    return;
  }
  const btn = document.getElementById('btn-regen-seo');
  const origText = btn ? btn.innerHTML : '';
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = '⏳ Generating SEO...';
  }

  try {
    const res = await fetch('/api/generate-seo', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ project_id: currentProject.id })
    });

    if (!res.ok) {
      throw new Error(`Server returned HTTP ${res.status}`);
    }

    const data = await res.json();
    populateSEOUi(data);
    showToast('🚀 YouTube SEO titles, description & tags generated!');
  } catch (err) {
    console.error(err);
    showToast('⚠️ Could not generate SEO: ' + err.message);
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = origText;
    }
  }
}

function populateSEOUi(data) {
  if (!data) return;
  const titles = data.titles || [];
  for (let i = 1; i <= 3; i++) {
    const tEl = document.getElementById(`seo-title-${i}`);
    if (tEl) {
      tEl.textContent = titles[i - 1] || 'No title generated';
    }
  }

  const descEl = document.getElementById('seo-description-text');
  if (descEl) {
    descEl.value = data.description || '';
  }

  const tagsEl = document.getElementById('seo-tags-text');
  if (tagsEl) {
    tagsEl.value = data.tags_string || (data.tags_list || []).join(', ');
  }
}

function copyTitleText(idx) {
  const tEl = document.getElementById(`seo-title-${idx}`);
  if (tEl && tEl.textContent) {
    copyText(tEl.textContent, 'Title copied to clipboard!');
  }
}

function copyElementText(elemId, toastMsg) {
  const el = document.getElementById(elemId);
  if (el) {
    const val = el.value || el.textContent;
    copyText(val, toastMsg || 'Copied to clipboard!');
  }
}

function copyText(text, toastMsg) {
  if (!text) return;
  navigator.clipboard.writeText(text).then(() => {
    showToast(`📋 ${toastMsg || 'Copied to clipboard!'}`);
  }).catch(() => {
    const ta = document.createElement('textarea');
    ta.value = text;
    document.body.appendChild(ta);
    ta.select();
    document.execCommand('copy');
    document.body.removeChild(ta);
    showToast(`📋 ${toastMsg || 'Copied to clipboard!'}`);
  });
}
