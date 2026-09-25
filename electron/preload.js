const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('kemsinin', {
  isElectron: true,
  platform: process.platform,

  // Dialog & File APIs
  openVideoDialog: () => ipcRenderer.invoke('dialog:openVideo'),
  saveFileDialog: (defaultName) => ipcRenderer.invoke('dialog:saveFile', defaultName),

  // 🆕 Updater API
  updater: {
    getVersion: () => ipcRenderer.invoke('app:version'),
    check:      () => ipcRenderer.invoke('update:check'),
    download:   () => ipcRenderer.invoke('update:download'),
    install:    () => ipcRenderer.invoke('update:install'),

    onStatus:   cb => ipcRenderer.on('update:status',   (_, d) => cb(d)),
    onProgress: cb => ipcRenderer.on('update:progress', (_, d) => cb(d)),
  }
});

// Also expose electronAPI for backward compatibility
contextBridge.exposeInMainWorld('electronAPI', {
  openVideoDialog: () => ipcRenderer.invoke('dialog:openVideo'),
  saveFileDialog: (defaultName) => ipcRenderer.invoke('dialog:saveFile', defaultName),
  getAppVersion: () => ipcRenderer.invoke('app:version'),
  checkForUpdates: () => ipcRenderer.invoke('update:check'),
  downloadUpdate: () => ipcRenderer.invoke('update:download'),
  installUpdate: () => ipcRenderer.invoke('update:install'),
  onUpdateStatus: (callback) => ipcRenderer.on('update:status', (_, d) => callback(d)),
  onUpdateProgress: (callback) => ipcRenderer.on('update:progress', (_, d) => callback(d)),
  platform: process.platform
});
