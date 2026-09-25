const { autoUpdater } = require('electron-updater');
const log = require('electron-log');
const { dialog, BrowserWindow } = require('electron');

// ============ Configure logging ============
autoUpdater.logger = log;
autoUpdater.logger.transports.file.level = 'info';

// Disable auto-download (we control via UI)
autoUpdater.autoDownload = false;
autoUpdater.autoInstallOnAppQuit = true;

// ============ State Broadcast ============
function broadcast(channel, payload) {
  BrowserWindow.getAllWindows().forEach(w => {
    if (!w.isDestroyed()) w.webContents.send(channel, payload);
  });
}

// ============ Event Handlers ============
autoUpdater.on('checking-for-update', () => {
  log.info('[UPDATE] Checking for updates...');
  broadcast('update:status', { status: 'checking' });
});

autoUpdater.on('update-available', info => {
  log.info('[UPDATE] Available:', info.version);
  broadcast('update:status', {
    status: 'available',
    version: info.version,
    releaseDate: info.releaseDate,
    releaseNotes: info.releaseNotes
  });
});

autoUpdater.on('update-not-available', info => {
  log.info('[UPDATE] Not available. Current:', info.version);
  broadcast('update:status', {
    status: 'not-available',
    version: info.version
  });
});

autoUpdater.on('download-progress', progress => {
  log.info(`[UPDATE] ${progress.percent.toFixed(1)}%`);
  broadcast('update:progress', {
    percent: progress.percent,
    transferred: progress.transferred,
    total: progress.total,
    bytesPerSecond: progress.bytesPerSecond
  });
});

autoUpdater.on('update-downloaded', info => {
  log.info('[UPDATE] Downloaded:', info.version);
  broadcast('update:status', {
    status: 'downloaded',
    version: info.version
  });
  // Auto-prompt after 3s
  setTimeout(() => promptInstall(info), 3000);
});

autoUpdater.on('error', err => {
  log.error('[UPDATE] Error:', err);
  broadcast('update:status', {
    status: 'error',
    message: err.message
  });
});

// ============ Prompt Install ============
async function promptInstall(info) {
  const r = await dialog.showMessageBox({
    type: 'info',
    title: '🎉 ការអាប់ដេតថ្មី',
    message: `KEMSININ DUBBER v${info.version} បានទាញយករួចរាល់`,
    detail: 'ចុច "ដំឡើងឥឡូវ" ដើម្បីបិទកម្មវិធីហើយដំឡើងកំណែថ្មី',
    buttons: ['🔁 ដំឡើងឥឡូវ', '⏰ ពេលក្រោយ'],
    defaultId: 0,
    cancelId: 1,
    noLink: true
  });

  if (r.response === 0) {
    setImmediate(() => autoUpdater.quitAndInstall(false, true));
  }
}

// ============ Public API ============
function setupAutoUpdater() {
  // Check every 4 hours
  setTimeout(() => autoUpdater.checkForUpdates().catch(handleErr), 30_000);
  setInterval(
    () => autoUpdater.checkForUpdates().catch(handleErr),
    4 * 60 * 60 * 1000
  );
}

function handleErr(e) {
  log.warn('[UPDATE] Check failed:', e.message);
}

async function checkForUpdatesManually() {
  try {
    const result = await autoUpdater.checkForUpdates();
    return { ok: true, version: result?.updateInfo?.version };
  } catch (e) {
    return { ok: false, error: e.message };
  }
}

function downloadUpdate() {
  return autoUpdater.downloadUpdate().catch(err => {
    log.error('[UPDATE] Download failed:', err);
    return { ok: false, error: err.message };
  });
}

function installUpdate() {
  autoUpdater.quitAndInstall(false, true);
}

module.exports = {
  setupAutoUpdater,
  checkForUpdatesManually,
  downloadUpdate,
  installUpdate,
  autoUpdater
};
