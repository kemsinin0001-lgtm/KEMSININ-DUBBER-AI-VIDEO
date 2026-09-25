/**
 * Subtitle & Voice Track Timeline Editor Module
 * Allows fine-tuning translated text, timestamps, individual voice assignments, and single line re-voicing.
 */

class DubEditor {
  constructor(containerId, options = {}) {
    this.container = document.getElementById(containerId);
    this.segments = [];
    this.onSegmentChange = options.onSegmentChange || (() => {});
    this.onPreviewAudio = options.onPreviewAudio || (() => {});
    this.activeSegmentId = null;
    this.videoElement = options.videoElement || null;
  }

  loadSegments(segments) {
    this.segments = JSON.parse(JSON.stringify(segments));
    this.render();
  }

  getSegments() {
    return this.segments;
  }

  updateSegment(id, field, value) {
    const seg = this.segments.find(s => s.id === id);
    if (seg) {
      seg[field] = value;
      this.onSegmentChange(this.segments);
    }
  }

  addSegment(time = 0) {
    const newId = this.segments.length > 0 ? Math.max(...this.segments.map(s => s.id)) + 1 : 1;
    const newSeg = {
      id: newId,
      orig: "",
      kh: "ឃ្លាថ្មី...",
      start: parseFloat(time.toFixed(2)),
      end: parseFloat((time + 3).toFixed(2)),
      t0: this.formatTime(time),
      t1: this.formatTime(time + 3),
      voice: "female"
    };
    this.segments.push(newSeg);
    this.segments.sort((a, b) => (a.start || 0) - (b.start || 0));
    this.render();
    this.onSegmentChange(this.segments);
  }

  deleteSegment(id) {
    this.segments = this.segments.filter(s => s.id !== id);
    this.render();
    this.onSegmentChange(this.segments);
  }

  formatTime(sec) {
    if (isNaN(sec) || sec === null) return "00:00:00.000";
    const h = Math.floor(sec / 3600);
    const m = Math.floor((sec % 3600) / 60);
    const s = (sec % 60).toFixed(3);
    return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(6, '0')}`;
  }

  parseTime(ts) {
    if (typeof ts === 'number') return ts;
    const parts = (ts || "").split(':');
    if (parts.length === 3) {
      return parseFloat(parts[0]) * 3600 + parseFloat(parts[1]) * 60 + parseFloat(parts[2]);
    }
    return parseFloat(ts) || 0;
  }

  highlightAtTime(currentTime) {
    const active = this.segments.find(s => {
      const start = s.start !== undefined ? s.start : this.parseTime(s.t0);
      const end = s.end !== undefined ? s.end : this.parseTime(s.t1);
      return currentTime >= start && currentTime <= end;
    });

    if (active && active.id !== this.activeSegmentId) {
      this.activeSegmentId = active.id;
      const allCards = this.container.querySelectorAll('.editor-card');
      allCards.forEach(c => c.classList.remove('active-playing'));
      const activeCard = this.container.querySelector(`[data-id="${active.id}"]`);
      if (activeCard) {
        activeCard.classList.add('active-playing');
        activeCard.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      }
    }
  }

  render() {
    if (!this.container) return;
    if (!this.segments || this.segments.length === 0) {
      this.container.innerHTML = `
        <div class="empty-state">
          <div style="font-size: 2.5rem; margin-bottom: 8px;">📝</div>
          <p style="color: var(--text-muted); font-size: 0.95rem;">មិនទាន់មាន Segment Subtitle ទេ។ បន្ទាប់ពី Dubbing ឬ Transcribe វានឹងបង្ហាញនៅទីនេះ។</p>
        </div>
      `;
      return;
    }

    this.container.innerHTML = `
      <div class="editor-header-bar">
        <span>🎬 សម្រួលអត្ថបទ & សំឡេង (${this.segments.length} បន្ទាត់)</span>
        <button class="btn-sub-action" id="btnAddNewSeg">➕ បន្ថែមបន្ទាត់</button>
      </div>
      <div class="editor-card-list">
        ${this.segments.map((s, idx) => `
          <div class="editor-card ${this.activeSegmentId === s.id ? 'active-playing' : ''}" data-id="${s.id}">
            <div class="editor-card-header">
              <span class="badge-index">#${idx + 1}</span>
              <div class="time-range-inputs">
                <input type="number" step="0.1" class="time-input" data-field="start" data-id="${s.id}" value="${(s.start !== undefined ? s.start : this.parseTime(s.t0)).toFixed(2)}" />
                <span>➔</span>
                <input type="number" step="0.1" class="time-input" data-field="end" data-id="${s.id}" value="${(s.end !== undefined ? s.end : this.parseTime(s.t1)).toFixed(2)}" />
                <span>s</span>
              </div>
              <div class="voice-picker">
                <select class="voice-select-mini" data-field="voice" data-id="${s.id}">
                  <option value="female" ${s.voice === 'female' ? 'selected' : ''}>👩 ស្រី (Sreymom)</option>
                  <option value="male" ${s.voice === 'male' ? 'selected' : ''}>👨 ប្រុស (Piseth)</option>
                  <option value="gpt_sovits" ${s.voice === 'gpt_sovits' ? 'selected' : ''}>🧬 AI Cloned (GPT-SoVITS)</option>
                </select>
              </div>
              <button class="btn-icon btn-del" data-id="${s.id}" title="លុបបន្ទាត់នេះ">🗑️</button>
            </div>

            <div class="editor-body">
              ${s.orig ? `<div class="editor-orig-text" title="Original text">Original: "${s.orig}"</div>` : ''}
              <div class="editor-input-wrap">
                <textarea class="editor-textarea" data-id="${s.id}" rows="2" placeholder="បញ្ចូលអត្ថបទសំឡេង...">${s.kh || ''}</textarea>
                <div class="editor-card-actions">
                  <button class="btn-action-mini btn-preview-audio" data-id="${s.id}">🔊 ស្តាប់សាកល្បង</button>
                  <button class="btn-action-mini btn-seek-video" data-id="${s.id}">▶️ លោតទៅវីដេអូ</button>
                </div>
              </div>
            </div>
          </div>
        `).join('')}
      </div>
    `;

    this.bindEvents();
  }

  bindEvents() {
    // Add new segment
    const addBtn = this.container.querySelector('#btnAddNewSeg');
    if (addBtn) {
      addBtn.onclick = () => {
        const curTime = this.videoElement ? this.videoElement.currentTime : 0;
        this.addSegment(curTime);
      };
    }

    // Time input edits
    this.container.querySelectorAll('.time-input').forEach(inp => {
      inp.onchange = (e) => {
        const id = parseInt(e.target.dataset.id, 10);
        const field = e.target.dataset.field;
        const val = parseFloat(e.target.value) || 0;
        this.updateSegment(id, field, val);
      };
    });

    // Voice type dropdown
    this.container.querySelectorAll('.voice-select-mini').forEach(sel => {
      sel.onchange = (e) => {
        const id = parseInt(e.target.dataset.id, 10);
        this.updateSegment(id, 'voice', e.target.value);
      };
    });

    // Text area update
    this.container.querySelectorAll('.editor-textarea').forEach(ta => {
      ta.oninput = (e) => {
        const id = parseInt(e.target.dataset.id, 10);
        this.updateSegment(id, 'kh', e.target.value);
      };
    });

    // Delete button
    this.container.querySelectorAll('.btn-del').forEach(btn => {
      btn.onclick = (e) => {
        const id = parseInt(e.target.dataset.id, 10);
        this.deleteSegment(id);
      };
    });

    // Preview single audio line
    this.container.querySelectorAll('.btn-preview-audio').forEach(btn => {
      btn.onclick = (e) => {
        const id = parseInt(e.target.dataset.id, 10);
        const seg = this.segments.find(s => s.id === id);
        if (seg) this.onPreviewAudio(seg);
      };
    });

    // Seek video directly to segment start
    this.container.querySelectorAll('.btn-seek-video').forEach(btn => {
      btn.onclick = (e) => {
        const id = parseInt(e.target.dataset.id, 10);
        const seg = this.segments.find(s => s.id === id);
        if (seg && this.videoElement) {
          const start = seg.start !== undefined ? seg.start : this.parseTime(seg.t0);
          this.videoElement.currentTime = start;
          this.videoElement.play();
        }
      };
    });
  }
}

window.DubEditor = DubEditor;
