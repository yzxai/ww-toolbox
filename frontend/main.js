const { app, BrowserWindow, ipcMain } = require("electron");
const path = require("path");
const http = require('http');

let mainWindow;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 800,
    height: 600,
    webPreferences: {
      nodeIntegration: true,
      contextIsolation: false
    },
    backgroundColor: '#1a1a1a',
    frame: false,
    titleBarStyle: 'hidden'
  });

  mainWindow.loadFile("index.html");
}

function startDebugServer() {
  const server = http.createServer((req, res) => {
    if (req.method === 'POST' && req.url === '/') {
      let body = '';
      req.on('data', chunk => { body += chunk; });
      req.on('end', () => {
        try {
          const data = JSON.parse(body);
          if (data && data.content) {
            if (mainWindow && mainWindow.webContents) {
              console.log('Sending debug message:', data.content, data.type);
              mainWindow.webContents.send('debug-message', data.content, data.type || 'INFO');
            } else {
              console.error('Main window or webContents not available');
            }
          } else {
            console.error('Invalid message format:', data);
          }
        } catch (e) {
          console.error('Error processing debug message:', e);
        }
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ status: 'ok' }));
      });
    } else {
      res.writeHead(404);
      res.end();
    }
  });
  server.listen(2590, '127.0.0.1');
}

app.whenReady().then(() => {
  createWindow();
  startDebugServer();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

// 窗口控制事件处理
ipcMain.on('minimize-window', () => {
  mainWindow.minimize();
});

ipcMain.on('maximize-window', () => {
  if (mainWindow.isMaximized()) {
    mainWindow.unmaximize();
  } else {
    mainWindow.maximize();
  }
});

ipcMain.on('close-window', () => {
  mainWindow.close();
});