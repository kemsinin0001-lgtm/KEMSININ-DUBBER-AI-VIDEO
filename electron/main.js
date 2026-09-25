const { app, BrowserWindow, ipcMain, dialog } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const {
  setupAutoUpdater,
  checkForUpdatesManually,
  downloadUpdate,
  installUpdate
} = require('./updater');

let mainWindow = null;
let pythonProcess = null;

const BACKEND_PORT = 8000;
const IS_DEV = process.env.NODE_ENV === 'development';

function startBackend() {
  const pythonExecutable = process.platform === 'win32'
    ? path.join(__dirname, '..', '.venv', 'Scripts', 'python.exe')
    : 'python';

  const backendScript = path.join(__dirname, '..', 'backend', 'app.py');

  try {
    pythonProcess = spawn(pythonExecutable, [backendScript], {
      cwd: path.join(__dirname, '..', 'backend'),
      env: { ...process.env, PYTHONUNBUFFERED: "1" }
    });

    pythonProcess.stdout.on('data', (data) => {
      console.log(`[Python backend]: ${data}`);
    });

    pythonProcess.stderr.on('data', (data) => {
      console.error(`[Python err]: ${data}`);
    });

    pythonProcess.on('close', (code) => {
      console.log(`Python process exited with code ${code}`);
    });
  } catch (err) {
    console.error("Failed to spawn Python backend:", err);
  }
}

function createWindow() {
  const iconPath = path.join(__dirname, 'build', 'icon.ico');

  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 1024,
    minHeight: 700,
    title: 'KEMSININ DUBBER - AI Studio',
    icon: iconPath,
    backgroundColor: '#0a0c14',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      nodeIntegration: false,
      contextIsolation: true
    }
  });

  // Load the web UI directly from the backend or local file
  const uiUrl = `http://127.0.0.1:${BACKEND_PORT}`;
  
  // Try loading backend URL with fallback
  mainWindow.loadURL(uiUrl).catch(() => {
    // If backend isn't ready yet, load local UI and let it connect
    const localHtml = path.join(__dirname, '..', 'ui', 'index.html');
    mainWindow.loadFile(localHtml);
  });

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

// IPC Handlers
ipcMain.handle('dialog:openVideo', async () => {
  const result = await dialog.showOpenDialog(mainWindow, {
    title: 'Select Video File',
    properties: ['openFile'],
    filters: [
      { name: 'Videos', extensions: ['mp4', 'mkv', 'avi', 'mov', 'webm'] }
    ]
  });
  if (!result.canceled && result.filePaths.length > 0) {
    return result.filePaths[0];
  }
  return null;
});

ipcMain.handle('dialog:saveFile', async (event, defaultName) => {
  const result = await dialog.showSaveDialog(mainWindow, {
    defaultPath: defaultName || 'dubbed_video.mp4',
    filters: [{ name: 'MP4 Video', extensions: ['mp4'] }]
  });
  return result.filePath || null;
});

ipcMain.handle('app:getVersion', () => app.getVersion());
ipcMain.handle('app:version', () => app.getVersion());
ipcMain.handle('updater:check', () => checkForUpdatesManually());
ipcMain.handle('update:check', () => checkForUpdatesManually());
ipcMain.handle('updater:download', () => downloadUpdate());
ipcMain.handle('update:download', () => downloadUpdate());
ipcMain.handle('updater:install', () => installUpdate());
ipcMain.handle('update:install', () => installUpdate());

app.whenReady().then(() => {
  startBackend();
  createWindow();
  setupAutoUpdater();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('will-quit', () => {
  if (pythonProcess) {
    pythonProcess.kill();
    pythonProcess = null;
  }
});
