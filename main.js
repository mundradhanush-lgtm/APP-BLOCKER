const { app, BrowserWindow, ipcMain } = require("electron");
const path = require("path");
const fs = require("fs");
const { spawn, spawnSync } = require("child_process");
if (!app.requestSingleInstanceLock()) {
    app.quit();
} else {
    let mainWindow = null;
    let isQuitting = false;
    let developmentBlocker = null;
    let applicationScanProcess = null;
    let applicationScanId = 0;
    const home = app.getPath("home");
    const supportDirectory = path.join(
        home,
        "Library",
        "Application Support",
        "python-projects"
    );
    const schedulesFile = path.join(
        supportDirectory,
        "schedules.json"
    );
    const applicationsFile = path.join(
        app.getPath("userData"),
        "applications.json"
    );
    const launchAgentsDirectory = path.join(
        home,
        "Library",
        "LaunchAgents"
    );
    const logsDirectory = path.join(
        home,
        "Library",
        "Logs"
    );
    const launchAgentLabel = "com.appblocker.background";
    const launchAgentFile = path.join(
        launchAgentsDirectory,
        `${launchAgentLabel}.plist`
    );
    const backgroundLog = path.join(
        logsDirectory,
        "AppBlocker.log"
    );
    const backgroundErrorLog = path.join(
        logsDirectory,
        "AppBlocker-error.log"
    );
    const stableBlockerPath = path.join(
        supportDirectory,
        "app_blocker"
    );
    function sendToWindow(channel, data) {
        if (
            mainWindow &&
            !mainWindow.isDestroyed() &&
            !mainWindow.webContents.isDestroyed()
        ) {
            mainWindow.webContents.send(channel, data);
        }
    }
    function loadSchedules() {
        try {
            if (!fs.existsSync(schedulesFile)) {
                return [];
            }
            const schedules = JSON.parse(
                fs.readFileSync(schedulesFile, "utf8")
            );
            if (!Array.isArray(schedules)) {
                throw new Error("Schedules must be a JSON list.");
            }
            return schedules;
        } catch (error) {
            console.error("Could not load schedules:", error);
            sendToWindow(
                "blocker-error",
                "Could not load schedules. The saved file was not changed."
            );
            return [];
        }
    }
    function saveSchedules(schedules) {
        if (!Array.isArray(schedules)) {
            sendToWindow(
                "blocker-error",
                "Invalid schedule data."
            );
            return false;
        }
        let temporaryFile;
        try {
            fs.mkdirSync(supportDirectory, {
                recursive: true
            });
            temporaryFile =
                `${schedulesFile}.${process.pid}.tmp`;
            fs.writeFileSync(
                temporaryFile,
                JSON.stringify(schedules, null, 2),
                "utf8"
            );
            fs.renameSync(temporaryFile, schedulesFile);
            console.log(
                `Saved ${schedules.length} schedule(s).`
            );
            return true;
        } catch (error) {
            console.error("Could not save schedules:", error);
            if (temporaryFile) {
                try {
                    fs.unlinkSync(temporaryFile);
                } catch {
                }
            }
            sendToWindow(
                "blocker-error",
                "Could not save schedules."
            );
            return false;
        }
    }
    function sendSchedulesToWindow() {
        sendToWindow("schedules-loaded", loadSchedules());
    }
    function getPackagedBlockerPath() {
        const executable = path.join(
            process.resourcesPath,
            "app_blocker"
        );
        if (
            !fs.existsSync(executable) ||
            !fs.statSync(executable).isFile()
        ) {
            throw new Error(
                `Blocker executable not found: ${executable}`
            );
        }
        return executable;
    }
    function getDevelopmentBlocker() {
        const pythonFile = path.join(
            __dirname,
            "app_blocker.py"
        );
        if (!fs.existsSync(pythonFile)) {
            throw new Error(
                `Python blocker file not found: ${pythonFile}`
            );
        }
        return {
            command: "python3",
            args: [pythonFile]
        };
    }
    function getBlockerForApp() {
        if (app.isPackaged) {
            return {
                command: getPackagedBlockerPath(),
                args: []
            };
        }
        return getDevelopmentBlocker();
    }
    function startDevelopmentBlocker() {
        if (app.isPackaged) {
            return;
        }
        if (
            developmentBlocker &&
            developmentBlocker.exitCode === null
        ) {
            return;
        }
        let blocker;
        try {
            blocker = getDevelopmentBlocker();
            developmentBlocker = spawn(
                blocker.command,
                blocker.args,
                {
                    cwd: __dirname,
                    stdio: ["ignore", "pipe", "pipe"]
                }
            );
        } catch (error) {
            console.error("Could not start blocker:", error);
            sendToWindow(
                "blocker-error",
                error.message
            );
            return;
        }
        const child = developmentBlocker;
        child.stdout.on("data", (data) => {
            const message = data.toString().trim();
            if (message) {
                console.log(`[Blocker] ${message}`);
                sendToWindow("blocker-status", message);
            }
        });
        child.stderr.on("data", (data) => {
            const message = data.toString().trim();
            if (message) {
                console.error(`[Blocker] ${message}`);
                sendToWindow("blocker-error", message);
            }
        });
        child.on("error", (error) => {
            console.error("Blocker failed to start:", error);
            sendToWindow(
                "blocker-error",
                "The Python blocker could not start."
            );
        });
        child.on("close", (code, signal) => {
            console.log(
                `Blocker exited: code=${code}, signal=${signal}`
            );
            if (developmentBlocker === child) {
                developmentBlocker = null;
            }
            if (!isQuitting) {
                sendToWindow(
                    "blocker-error",
                    "The blocker stopped. Reopen the app to start it again."
                );
            }
        });
    }
    function xmlEscape(value) {
        return String(value)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&apos;");
    }
    function runLaunchctl(args) {
        return spawnSync(
            "/bin/launchctl",
            args,
            {
                encoding: "utf8",
                timeout: 10000
            }
        );
    }
    function installBackgroundAgent() {
        if (!app.isPackaged) {
            return;
        }
        const domain = `gui/${process.getuid()}`;
        const service = `${domain}/${launchAgentLabel}`;
        try {
            fs.mkdirSync(supportDirectory, {
                recursive: true
            });
            fs.mkdirSync(launchAgentsDirectory, {
                recursive: true
            });
            fs.mkdirSync(logsDirectory, {
                recursive: true
            });
            const packagedExecutable = getPackagedBlockerPath();
            runLaunchctl(["bootout", service]);
            fs.copyFileSync(
                packagedExecutable,
                stableBlockerPath
            );
            fs.chmodSync(stableBlockerPath, 0o755);
            fs.accessSync(
                stableBlockerPath,
                fs.constants.X_OK
            );
            const plist = `<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>${launchAgentLabel}</string>
    <key>ProgramArguments</key>
    <array>
        <string>${xmlEscape(stableBlockerPath)}</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>ProcessType</key>
    <string>Background</string>
    <key>StandardOutPath</key>
    <string>${xmlEscape(backgroundLog)}</string>
    <key>StandardErrorPath</key>
    <string>${xmlEscape(backgroundErrorLog)}</string>
</dict>
</plist>`;
            const temporaryPlist = `${launchAgentFile}.tmp`;
            fs.writeFileSync(
                temporaryPlist,
                plist,
                "utf8"
            );
            fs.renameSync(
                temporaryPlist,
                launchAgentFile
            );
            const result = runLaunchctl([
                "bootstrap",
                domain,
                launchAgentFile
            ]);
            if (result.error || result.status !== 0) {
                throw new Error(
                    result.error?.message ||
                    result.stderr ||
                    "launchctl bootstrap failed."
                );
            }
            console.log(
                "Background blocker installed and started."
            );
            sendToWindow(
                "blocker-status",
                "Background blocker installed and started."
            );
        } catch (error) {
            console.error(
                "Could not install background blocker:",
                error
            );
            sendToWindow(
                "blocker-error",
                `Could not start background blocker: ${error.message}`
            );
        }
    }
    function scanApplicationFolders() {
        const roots = [
            "/Applications",
            "/System/Applications",
            path.join(home, "Applications")
        ];
        const found = new Set();
        function walk(folder, depth = 0) {
            let entries;
            try {
                entries = fs.readdirSync(
                    folder,
                    { withFileTypes: true }
                );
            } catch {
                return;
            }
            for (const entry of entries) {
                if (
                    !entry.isDirectory() ||
                    entry.isSymbolicLink()
                ) {
                    continue;
                }
                const fullPath = path.join(
                    folder,
                    entry.name
                );
                if (entry.name.endsWith(".app")) {
                    found.add(fullPath);
                } else if (
                    depth < 4 &&
                    !entry.name.startsWith(".") &&
                    entry.name !== "Contents" &&
                    entry.name !== "Frameworks"
                ) {
                    walk(fullPath, depth + 1);
                }
            }
        }
        for (const root of roots) {
            walk(root);
        }
        const grouped = new Map();
        for (const appPath of found) {
            const name = path.basename(appPath, ".app");
            const parent = path.basename(path.dirname(appPath));
            if (!grouped.has(name)) {
                grouped.set(name, []);
            }
            grouped.get(name).push({
                name,
                parent,
                path: appPath
            });
        }
        const result = [];
        for (const [name, entries] of grouped) {
            entries.sort((a, b) =>
                a.path.localeCompare(b.path)
            );
            if (entries.length === 1) {
                result.push(name);
                continue;
            }
            for (const entry of entries) {
                result.push([name, entry.parent]);
            }
        }
        return result.sort((a, b) => {
            const nameA = Array.isArray(a) ? a[0] : a;
            const nameB = Array.isArray(b) ? b[0] : b;
            return nameA.localeCompare(nameB);
        });
    }
    function saveApplicationsCache(apps) {
        if (!Array.isArray(apps) || apps.length === 0) {
            return;
        }
        try {
            fs.mkdirSync(
                path.dirname(applicationsFile),
                { recursive: true }
            );
            const temporaryFile =
                `${applicationsFile}.${process.pid}.tmp`;
            fs.writeFileSync(
                temporaryFile,
                JSON.stringify(apps, null, 2),
                "utf8"
            );
            fs.renameSync(temporaryFile, applicationsFile);
        } catch (error) {
            console.error(
                "Could not save application cache:",
                error
            );
        }
    }
    function loadSavedApplications() {
        try {
            const apps = JSON.parse(
                fs.readFileSync(applicationsFile, "utf8")
            );
            if (Array.isArray(apps) && apps.length > 0) {
                sendToWindow("apps-found", apps);
            }
        } catch {
        }
    }
    function loadApplications() {
        const scanId = ++applicationScanId;
        if (
            applicationScanProcess &&
            applicationScanProcess.exitCode === null
        ) {
            applicationScanProcess.kill();
        }
        let blocker;
        try {
            blocker = getBlockerForApp();
        } catch (error) {
            console.error(error);
            const apps = scanApplicationFolders();
            saveApplicationsCache(apps);
            sendToWindow("apps-found", apps);
            return;
        }
        let child;
        try {
            child = spawn(
                blocker.command,
                [...blocker.args, "--list-apps"],
                {
                    cwd: __dirname,
                    stdio: ["ignore", "pipe", "pipe"]
                }
            );
        } catch (error) {
            console.error("Could not scan applications:", error);
            const apps = scanApplicationFolders();
            saveApplicationsCache(apps);
            sendToWindow("apps-found", apps);
            return;
        }
        applicationScanProcess = child;
        let output = "";
        let errorOutput = "";
        child.stdout.on("data", (data) => {
            output += data.toString();
        });
        child.stderr.on("data", (data) => {
            errorOutput += data.toString();
        });
        child.on("error", (error) => {
            if (scanId !== applicationScanId) {
                return;
            }
            console.error("Application scan failed:", error);
            const apps = scanApplicationFolders();
            saveApplicationsCache(apps);
            sendToWindow("apps-found", apps);
        });
        child.on("close", (code) => {
            if (scanId !== applicationScanId) {
                return;
            }
            if (applicationScanProcess === child) {
                applicationScanProcess = null;
            }
            let apps = [];
            try {
                if (code !== 0) {
                    throw new Error(
                        errorOutput ||
                        `Application scan exited with code ${code}.`
                    );
                }
                apps = JSON.parse(output);
                if (!Array.isArray(apps)) {
                    throw new Error("Invalid application list.");
                }
            } catch (error) {
                console.error(error);
            }
            if (apps.length === 0) {
                apps = scanApplicationFolders();
            }
            saveApplicationsCache(apps);
            sendToWindow("apps-found", apps);
        });
    }
    function createWindow() {
        if (mainWindow && !mainWindow.isDestroyed()) {
            mainWindow.show();
            mainWindow.focus();
            return;
        }
        mainWindow = new BrowserWindow({
            width: 1000,
            height: 700,
            minWidth: 850,
            minHeight: 600,
            show: false,
            webPreferences: {
                preload: path.join(__dirname, "preload.js"),
                contextIsolation: true,
                nodeIntegration: false
            }
        });
        mainWindow.loadFile(
            path.join(__dirname, "index.html")
        );
        mainWindow.once("ready-to-show", () => {
            if (mainWindow && !mainWindow.isDestroyed()) {
                mainWindow.show();
            }
        });
        mainWindow.webContents.once("did-finish-load", () => {
            sendSchedulesToWindow();
            loadSavedApplications();
            loadApplications();
        });
        mainWindow.on("close", (event) => {
            if (!isQuitting) {
                event.preventDefault();
                mainWindow.hide();
            }
        });
        mainWindow.on("closed", () => {
            mainWindow = null;
        });
    }
    ipcMain.on("load-schedules", () => {
        sendSchedulesToWindow();
    });
    ipcMain.on("block-app", (_event, data) => {
        if (!data || !Array.isArray(data.schedules)) {
            sendToWindow(
                "blocker-error",
                "Invalid schedule data was received."
            );
            return;
        }
        if (saveSchedules(data.schedules)) {
            sendSchedulesToWindow();
            console.log(
                "Schedules saved for the background blocker."
            );
        }
    });
    app.whenReady().then(() => {
        createWindow();
        if (app.isPackaged) {
            installBackgroundAgent();
        } else {
            startDevelopmentBlocker();
        }
    });
    app.on("second-instance", () => {
        if (!mainWindow || mainWindow.isDestroyed()) {
            return;
        }
        if (mainWindow.isMinimized()) {
            mainWindow.restore();
        }
        mainWindow.show();
        mainWindow.focus();
    });
    app.on("activate", () => {
        if (mainWindow && !mainWindow.isDestroyed()) {
            mainWindow.show();
            mainWindow.focus();
        } else {
            createWindow();
        }
    });
    app.on("before-quit", () => {
        isQuitting = true;
        if (
            applicationScanProcess &&
            applicationScanProcess.exitCode === null
        ) {
            applicationScanProcess.kill();
            applicationScanProcess = null;
        }
        if (
            !app.isPackaged &&
            developmentBlocker &&
            developmentBlocker.exitCode === null
        ) {
            developmentBlocker.kill();
            developmentBlocker = null;
        }
    });
    app.on("window-all-closed", () => {
    });
}