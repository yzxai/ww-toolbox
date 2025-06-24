const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  // Main to Renderer (one-way)
  onDebugMessage: (callback) => ipcRenderer.on('debug-message', (_event, ...args) => callback(...args)),
  
  // Renderer to Main (request/response)
  getEnvVars: () => ipcRenderer.invoke('get-env-vars'),
  
  // Renderer to Main (one-way)
  minimizeWindow: () => ipcRenderer.send('minimize-window'),
  maximizeWindow: () => ipcRenderer.send('maximize-window'),
  closeWindow: () => ipcRenderer.send('close-window')
}); 