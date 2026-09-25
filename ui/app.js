/**
 * KEMSININ DUBBER - Main Client Application Logic
 * Integrates:
 * - Real-time WebSocket connectivity for progress / stage reporting
 * - File upload & drag and drop
 * - Full automatic dubbing & interactive timeline editor
 * - Re-rendering custom edited subtitles and voices
 * - Electron IPC communication hooks when running in desktop mode
 */

const SAVED_API_BASE = localStorage.getItem('kemsinin_server_url');
const API_BASE = SAVED_API_BASE && SAVED_API_BASE.trim() !== ''
  ? SAVED_API_BASE.trim().replace(/\/+$/, '')
  : (window.location.port === "8000" || window.location.port === "3000"
      ? window.location.origin
      : "http://127.0.0.1:8000");

let socket = null;
let currentVideoPath = null;
let currentSegments = [];
let dubEditor = null;
let previewAudio = new Audio();

document.addEventListener('DOMContentLoaded', () => {
  initWebSocket();
  initEditor();
  initUIEvents();
  checkGptSovits();
});

// ---------- 1. WebSocket Management ----------
function initWebSocket() {
  let wsUrl;
  try {
    const parsed = new URL(API_BASE);
    const wsProto = parsed.protocol === 'https:' ? 'wss:' : 'ws:';
    wsUrl = `${wsProto}//${parsed.host}/ws`;
  } catch (e) {
    wsUrl = `ws://127.0.0.1:8000/ws`;
  }

  const wsIndicator = document.getElementById('wsStatus');

  try {
    socket = new WebSocket(wsUrl);

    socket.onopen = () => {
      console.log("[WS] Connected to KEMSININ Dubber Engine");
      if (wsIndicator) {
        wsIndicator.innerHTML = '<span class="status-dot online"></span> WebSocket Online';
        wsIndicator.className = "status-pill online";
      }
    };

    socket.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        handleSocketMessage(msg);
      } catch (err) {
        console.log("[WS msg]", event.data);
      }
    };

    socket.onclose = () => {
      console.warn("[WS] Connection lost. Retrying in 3s...");
      if (wsIndicator) {
        wsIndicator.innerHTML = '<span class="status-dot offline"></span> Reconnecting...';
        wsIndicator.className = "status-pill offline";
      }
      setTimeout(initWebSocket, 3000);
    };

    socket.onerror = (err) => {
      console.error("[WS Error]", err);
    };
  } catch (e) {
    console.error("[WS Setup Exception]", e);
  }
}

function handleSocketMessage(msg) {
  const progressBox = document.getElementById('progressBox');
  const progressBarFill = document.getElementById('progressBarFill');
  const progressPercent = document.getElementById('progressPercent');
  const progressStatusText = document.getElementById('progressStatusText');

  if (msg.type === "progress") {
    if (progressBox) progressBox.style.display = 'block';
    if (progressBarFill) progressBarFill.style.width = `${msg.percent}%`;
    if (progressPercent) progressPercent.textContent = `${msg.percent}%`;
    if (progressStatusText) progressStatusText.textContent = `[${msg.stage.toUpperCase()}] ${msg.detail}`;
  } else if (msg.type === "status") {
    if (progressStatusText && msg.detail) {
      progressStatusText.textContent = msg.detail;
    }
  } else if (msg.type === "error") {
    alert(`បញ្ហាដំណើរការ: ${msg.message}`);
    const startDubBtn = document.getElementById('startDubBtn');
    if (startDubBtn) startDubBtn.disabled = false;
  }
}


// ---------- 2. Editor Initialization ----------
function initEditor() {
  const player = document.getElementById('player');
  dubEditor = new DubEditor('editorContainer', {
    videoElement: player,
    onSegmentChange: (segments) => {
      currentSegments = segments;
      const countEl = document.getElementById('segmentCount');
      if (countEl) countEl.textContent = `${segments.length} segments`;
    },
    onPreviewAudio: async (seg) => {
      try {
        const resp = await fetch(`${API_BASE}/tts`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            text: seg.kh,
            voice: seg.voice || 'female',
            lang: document.getElementById('targetLang').value || 'km'
          })
        });
        if (resp.ok) {
          const blob = await resp.blob();
          const url = URL.createObjectURL(blob);
          previewAudio.src = url;
          previewAudio.play();
        }
      } catch (err) {
        console.error("Audio preview failed:", err);
      }
    }
  });

  // Track video time to highlight active subtitle line
  if (player) {
    player.addEventListener('timeupdate', () => {
      if (dubEditor) {
        dubEditor.highlightAtTime(player.currentTime);
      }
    });
  }
}


// ---------- 3. UI Events & Flow ----------
function initUIEvents() {
  const dropZone = document.getElementById('dropZone');
  const fileInput = document.getElementById('fileInput');
  const startDubBtn = document.getElementById('startDubBtn');
  const renderEditedBtn = document.getElementById('renderEditedBtn');
  const transcribeOnlyBtn = document.getElementById('transcribeOnlyBtn');

  // Drag & drop
  if (dropZone && fileInput) {
    dropZone.addEventListener('click', () => fileInput.click());
    dropZone.addEventListener('dragover', (e) => {
      e.preventDefault();
      dropZone.classList.add('dragover');
    });
    dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragover'));
    dropZone.addEventListener('drop', (e) => {
      e.preventDefault();
      dropZone.classList.remove('dragover');
      if (e.dataTransfer.files.length) handleFileUpload(e.dataTransfer.files[0]);
    });
    fileInput.addEventListener('change', () => {
      if (fileInput.files.length) handleFileUpload(fileInput.files[0]);
    });
  }

  // Full Dubbing
  if (startDubBtn) {
    startDubBtn.addEventListener('click', startFullDubbing);
  }

  // Transcribe Only (For editor mode)
  if (transcribeOnlyBtn) {
    transcribeOnlyBtn.addEventListener('click', startTranscribeOnly);
  }

  // Re-Render from Timeline Editor
  if (renderEditedBtn) {
    renderEditedBtn.addEventListener('click', renderEditedPipeline);
  }

  // Native Electron Open File Dialog bridge if available
  if (window.electronAPI) {
    const nativeFileBtn = document.getElementById('btnNativePick');
    if (nativeFileBtn) {
      nativeFileBtn.style.display = 'inline-flex';
      nativeFileBtn.addEventListener('click', async () => {
        const filePath = await window.electronAPI.openVideoDialog();
        if (filePath) {
          currentVideoPath = filePath;
          const fileInfo = document.getElementById('fileInfo');
          fileInfo.textContent = `📁 ជ្រើសរើសឯកសារ: ${filePath}`;
          startDubBtn.disabled = false;
          if (transcribeOnlyBtn) transcribeOnlyBtn.disabled = false;
        }
      });
    }
  }
}

async function handleFileUpload(file) {
  const fileInfo = document.getElementById('fileInfo');
  const startDubBtn = document.getElementById('startDubBtn');
  const transcribeOnlyBtn = document.getElementById('transcribeOnlyBtn');

  fileInfo.textContent = `⏳ កំពុង Upload: ${file.name}...`;

  const formData = new FormData();
  formData.append('file', file);

  try {
    const resp = await fetch(`${API_BASE}/upload`, {
      method: 'POST',
      body: formData
    });
    const data = await resp.json();
    if (resp.ok && data.path) {
      currentVideoPath = data.path;
      fileInfo.textContent = `✅ បាន Upload ជោគជ័យ: ${file.name}`;
      startDubBtn.disabled = false;
      if (transcribeOnlyBtn) transcribeOnlyBtn.disabled = false;
    } else {
      fileInfo.textContent = `❌ Upload បរាជ័យ: ${data.detail || 'កំហុសមិនស្គាល់'}`;
    }
  } catch (err) {
    fileInfo.textContent = `❌ Network Error: ${err.message}`;
  }
}

async function startFullDubbing() {
  if (!currentVideoPath) return;

  const startDubBtn = document.getElementById('startDubBtn');
  startDubBtn.disabled = true;

  const voiceSelect = document.getElementById('voiceSelect');
  const targetLang = document.getElementById('targetLang');
  const sourceLang = document.getElementById('sourceLang');

  let voiceParam = 'female';
  if (voiceSelect.value.includes('Piseth') || voiceSelect.value.includes('male') || voiceSelect.value.includes('Guy')) {
    voiceParam = 'male';
  } else if (voiceSelect.value.includes('gpt_sovits') || voiceSelect.value.includes('clone')) {
    voiceParam = 'gpt_sovits';
  }

  const payload = {
    video: currentVideoPath,
    src_lang: sourceLang ? sourceLang.value : 'auto',
    tgt_lang: targetLang ? targetLang.value : 'km',
    voice: voiceParam
  };

  try {
    const resp = await fetch(`${API_BASE}/dub`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const data = await resp.json();
    if (resp.ok && data.output) {
      startDubBtn.disabled = false;
      displayResults(data);
    } else {
      alert(`Dubbing បរាជ័យ: ${data.detail || 'បរាជ័យ'}`);
      startDubBtn.disabled = false;
    }
  } catch (err) {
    alert(`កំហុសបណ្តាញ: ${err.message}`);
    startDubBtn.disabled = false;
  }
}

async function startTranscribeOnly() {
  if (!currentVideoPath) return;
  const transcribeOnlyBtn = document.getElementById('transcribeOnlyBtn');
  transcribeOnlyBtn.disabled = true;

  try {
    const resp = await fetch(`${API_BASE}/transcribe?video=${encodeURIComponent(currentVideoPath)}`, {
      method: 'POST'
    });
    const data = await resp.json();
    if (resp.ok && data.segments) {
      currentSegments = data.segments;
      dubEditor.loadSegments(currentSegments);
      document.getElementById('editorSection').style.display = 'block';
      document.getElementById('editorSection').scrollIntoView({ behavior: 'smooth' });
    }
  } catch (err) {
    alert(`Transcribe Error: ${err.message}`);
  } finally {
    transcribeOnlyBtn.disabled = false;
  }
}

async function renderEditedPipeline() {
  if (!currentVideoPath || !dubEditor) return;
  const segments = dubEditor.getSegments();
  if (!segments || segments.length === 0) {
    alert("សូមបញ្ចូល ឬ បង្កើតអត្ថបទ Subtitle យ៉ាងហោចណាស់ 1 បន្ទាត់!");
    return;
  }

  const renderBtn = document.getElementById('renderEditedBtn');
  renderBtn.disabled = true;

  const payload = {
    video: currentVideoPath,
    segments: segments,
    tgt_lang: document.getElementById('targetLang').value || 'km',
    voice: document.getElementById('voiceSelect').value.includes('Piseth') ? 'male' : 'female'
  };

  try {
    const resp = await fetch(`${API_BASE}/dub_custom_segments`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const data = await resp.json();
    if (resp.ok && data.output) {
      displayResults({ output: data.output, subtitles: segments });
      alert("✅ វីដេអូត្រូវបាន Mix សំឡេងកែប្រែដោយជោគជ័យ!");
    } else {
      alert(`បរាជ័យ: ${data.detail || 'កំហុសបច្ចេកទេស'}`);
    }
  } catch (err) {
    alert(`Render Error: ${err.message}`);
  } finally {
    renderBtn.disabled = false;
  }
}

function displayResults(data) {
  const player = document.getElementById('player');
  const dlVideo = document.getElementById('dlVideo');
  const downloadGroup = document.getElementById('downloadGroup');
  const editorSection = document.getElementById('editorSection');

  const videoUrl = `${API_BASE}/${data.output.replace(/\\/g, '/')}`;
  player.src = videoUrl;
  player.play();
  
  if (dlVideo) {
    dlVideo.href = videoUrl;
    dlVideo.setAttribute('download', 'kemsinin_dubbed.mp4');
  }
  if (downloadGroup) downloadGroup.style.display = 'flex';

  if (data.subtitles && data.subtitles.length) {
    currentSegments = data.subtitles;
    dubEditor.loadSegments(currentSegments);
    if (editorSection) editorSection.style.display = 'block';
  }
}

async function checkGptSovits() {
  const sovitsBadge = document.getElementById('sovitsBadge');
  if (!sovitsBadge) return;
  try {
    const r = await fetch(`${API_BASE}/gpt_sovits/status`);
    const res = await r.json();
    if (res.available) {
      sovitsBadge.innerHTML = '🧬 GPT-SoVITS: សកម្ម';
      sovitsBadge.style.color = '#10b981';
    } else {
      sovitsBadge.innerHTML = '🧬 GPT-SoVITS: មិនទាន់បើក (Edge-TTS Backup)';
      sovitsBadge.style.color = '#94a3b8';
    }
  } catch (e) {
    sovitsBadge.innerHTML = '🧬 GPT-SoVITS: មិនមានការឆ្លើយតប';
  }
}

window.app = {
  initWebSocket,
  startFullDubbing,
  renderEditedPipeline
};
