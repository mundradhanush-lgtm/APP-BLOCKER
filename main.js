const { app, BrowserWindow, ipcMain } = require("electron");
const { spawn } = require("child_process");

function createWindow() {
    const window = new BrowserWindow({
        width: 900,
        height: 700,
        webPreferences: {
            preload: __dirname + "/preload.js"
        }
    });

    window.loadFile("index.html");
}

function getApps() {
    const python = spawn("python3", ["app_blocker.py", "--list-apps"]);

    let output = "";

    python.stdout.on("data", (data) => {
        output += data.toString();
    });

    python.on("close", () => {
        const apps = JSON.parse(output);

        BrowserWindow.getAllWindows()[0].webContents.send("apps-found", apps);
    });
}

app.whenReady().then(() => {
    createWindow();
    getApps();
});
ipcMain.on("block-app", (event, data) => {
    console.log(data);

    const python = spawn("python3", ["app_blocker.py"]);

    python.stdin.write(JSON.stringify(data));
    python.stdin.end();

    python.stdout.on("data", (output) => {
        console.log(`Python: ${output}`);
    });

    python.stderr.on("data", (error) => {
        console.error(`Python Error: ${error}`);
    });
});