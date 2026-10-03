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

    python.stderr.on("data", (error) => {
        console.error(`Python Error: ${error}`);
    });

    python.on("error", (error) => {
        console.error(`Could not start Python: ${error}`);
    });

    python.on("close", (code) => {
        if (code !== 0) {
            console.error(`Python failed with exit code: ${code}`);
            return;
        }

        try {
            const apps = JSON.parse(output);
            BrowserWindow.getAllWindows()[0].webContents.send("apps-found", apps);
        }
        catch (error) {
            console.error("Could not read the app list from Python:", error);
        }
    });
}

app.whenReady().then(() => {
    createWindow();
    getApps();
});

ipcMain.on("block-app", (event, data) => {
    if (!data || typeof data !== "object") {
        console.error("Invalid data received from the GUI.");
        return;
    }

    if (!data.app || !data.start || !data.end) {
        console.error("Incomplete blocking information received from the GUI.");
        return;
    }

    const python = spawn("python3", ["app_blocker.py"]);

    python.stdout.on("data", (output) => {
        const message = output.toString().trim();

        if (message) {
            event.sender.send("blocker-status", message);
        }

        console.log(`Python: ${output}`);
    });

    python.stderr.on("data", (error) => {
        const message = error.toString().trim();

        if (message) {
            event.sender.send("blocker-error", message);
        }

        console.error(`Python Error: ${error}`);
    });

    python.stdin.on("error", (error) => {
        console.error(`Python input error: ${error}`);
    });

    python.on("error", (error) => {
        console.error(`Could not start Python: ${error}`);
        event.sender.send("blocker-error", "Could not start the application blocker.");
    });

    python.on("close", (code) => {
        if (code === 0) {
            event.sender.send("blocker-ended", "The blocking period has ended.");
        }
        else {
            console.error(`Python blocker failed with exit code: ${code}`);
        }
    });

    try {
        python.stdin.write(JSON.stringify(data));
        python.stdin.end();
    }
    catch (error) {
        console.error("Could not send data to Python:", error);
        event.sender.send("blocker-error", "Could not send the blocking information to Python.");
    }
});