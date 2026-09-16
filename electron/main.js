const { app, BrowserWindow, dialog } = require('electron');
const path = require('path');
const http = require('http');
const { spawn } = require('child_process');

let mainWindow;
let pythonProcess = null;
const BACKEND_PORT = 9000;
const BACKEND_URL = `http://127.0.0.1:${BACKEND_PORT}`;

function isBackendRunning() {
    return new Promise((resolve) => {
        const req = http.get(`${BACKEND_URL}/api/system`, (res) => {
            resolve(res.statusCode === 200);
        });
        req.on('error', () => resolve(false));
        req.setTimeout(1500, () => {
            req.destroy();
            resolve(false);
        });
    });
}

function startBackend() {
    const pythonCmd = process.platform === 'win32' ? 'python' : 'python3';
    const mainPyPath = path.join(__dirname, '..', 'backend', 'main.py');
    console.log(`[Electron] Launching backend: ${pythonCmd} ${mainPyPath}`);
    
    pythonProcess = spawn(pythonCmd, [mainPyPath], {
        cwd: path.join(__dirname, '..'),
        detached: false,
        stdio: 'pipe'
    });

    pythonProcess.stdout.on('data', (data) => console.log(`[Python] ${data}`));
    pythonProcess.stderr.on('data', (data) => console.error(`[Python ERR] ${data}`));
    pythonProcess.on('close', (code) => console.log(`[Python] Exited with code ${code}`));
}

async function createWindow() {
    mainWindow = new BrowserWindow({
        width: 1440,
        height: 900,
        minWidth: 1080,
        minHeight: 700,
        title: 'VideoGen Studio — AI YouTube Full HD Video Generator',
        webPreferences: {
            nodeIntegration: false,
            contextIsolation: true
        },
        backgroundColor: '#0d1117',
        show: false
    });

    // Check if backend running, else start it
    let running = await isBackendRunning();
    if (!running) {
        startBackend();
        // Wait up to 10 seconds for backend to start
        for (let i = 0; i < 20; i++) {
            await new Promise((r) => setTimeout(r, 500));
            running = await isBackendRunning();
            if (running) break;
        }
    }

    mainWindow.loadURL(BACKEND_URL);

    mainWindow.once('ready-to-show', () => {
        mainWindow.show();
    });

    mainWindow.on('closed', () => {
        mainWindow = null;
    });
}

app.whenReady().then(createWindow);

app.on('window-all-closed', () => {
    if (pythonProcess) {
        console.log('[Electron] Terminating Python backend...');
        pythonProcess.kill();
    }
    if (process.platform !== 'darwin') {
        app.quit();
    }
});

app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
        createWindow();
    }
});
