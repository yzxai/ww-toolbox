const { app, BrowserWindow, ipcMain } = require("electron");
const path = require("path");
const http = require('http');
const { spawn, exec } = require('child_process');
const kill = require('tree-kill');
const isAdmin = require('is-admin');

let mainWindow;
let pythonProcess;

function createWindow() {
  const iconPath = !app.isPackaged
    ? path.join(__dirname, '..', 'assets', 'icon.png') 
    : path.join(process.resourcesPath, 'assets', 'icon.png');

  const preloadPath = !app.isPackaged
    ? path.join(__dirname, 'preload.js')
    : path.join(process.resourcesPath, 'preload.js');

  mainWindow = new BrowserWindow({
    width: 1920,
    height: 1080,
    webPreferences: {
      preload: preloadPath,
      nodeIntegration: false,
      contextIsolation: true
    },
    backgroundColor: '#1a1a1a',
    icon: iconPath,
    frame: false,
    titleBarStyle: 'hidden'
  });
  mainWindow.loadFile("index.html");
}

function startBackend() {
  let backendPath, backendArgs;

  if (!app.isPackaged) {
    const scriptPath = path.join(__dirname, '..', 'main.py');
    pythonProcess = spawn('python', [scriptPath], {
      cwd: path.join(__dirname, '..')
    });
  } else {
    backendPath = path.join(process.resourcesPath, 'backend', 'main.exe');
    backendArgs = [];
    pythonProcess = spawn(backendPath, backendArgs, {
      cwd: path.dirname(backendPath)
    });
  }

  pythonProcess.stdout.on('data', (data) => {
      console.log(`${data}`);
  });

  pythonProcess.stderr.on('data', (data) => {
      console.error(`${data}`);
  });

  pythonProcess.on('close', (code) => {
      console.log(`python process exited with code ${code}`);
  });
}

function startDebugServer() {
  const server = http.createServer((req, res) => {
    if (req.method !== 'POST' || req.url !== '/') {
      res.writeHead(404, { 'Content-Type': 'text/plain' });
      res.end('Not Found');
      return;
    }

    let body = '';
    req.on('data', chunk => {
      body += chunk.toString();
    });

    req.on('end', () => {
      try {
        const data = JSON.parse(body);
        if (data && data.content) {
          if (mainWindow && mainWindow.webContents) {
            mainWindow.webContents.send('debug-message', data.content, data.type || 'INFO');
          }
        }
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ status: 'ok' }));
      } catch (e) {
        console.error('Error processing debug message:', e);
        res.writeHead(500, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ status: 'error', message: 'Failed to parse JSON' }));
      }
    });

    req.on('error', (err) => {
      console.error('Request error:', err);
      res.writeHead(500, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ status: 'error', message: 'Request error' }));
    });
  });

  server.on('error', (err) => {
    console.error('Server error:', err);
  });

  server.listen(2590, '127.0.0.1', () => {
    console.log('Debug server listening on http://127.0.0.1:2590');
  });
}

function initializeApp() {
  createWindow();
  startDebugServer();
  startBackend();
}

app.whenReady().then(async () => {
  ipcMain.handle('get-env-vars', () => {
    return {
      isDev: !app.isPackaged,
      assetsPathInProd: app.isPackaged ? path.join(process.resourcesPath, 'assets') : ''
    };
  });

  const isElevated = await isAdmin();
  if (!isElevated) {
    const execPath = process.execPath;
    const appPath = app.getAppPath();
    exec(`powershell -Command "Start-Process -FilePath '${execPath}' -ArgumentList '${appPath}' -Verb RunAs"`, (err) => {
      if (err) {
        console.error('Failed to relaunch with admin rights:', err);
      }
      app.quit();
    });
    return;
  }

  initializeApp();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    if (pythonProcess) {
      kill(pythonProcess.pid);
    }
    app.quit();
  }
});

app.on('before-quit', () => {
  if (pythonProcess) {
    kill(pythonProcess.pid);
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