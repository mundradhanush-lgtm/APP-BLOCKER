const { app, BrowserWindow, ipcMain } = require("electron");
const path = require("path");
const fs = require("fs");
const { spawn, spawnSync } = require("child_process");

const gotSingleInstanceLock = app.requestSingleInstanceLock();

if (!gotSingleInstanceLock) {
    app.quit();
} else {
    let main_window = null;
    let is_quitting = false;

    const schedules_file = path.join(
        app.getPath("home"),
        "Library",
        "Application Support",
        "python-projects",
        "schedules.json"
    );

    const applications_file = path.join(
        app.getPath("userData"),
        "applications.json"
    );

    const launch_agents_directory = path.join(
        app.getPath("home"),
        "Library",
        "LaunchAgents"
    );

    const logs_directory = path.join(
        app.getPath("home"),
        "Library",
        "Logs"
    );

    const launch_agent_label = "com.appblocker.background";

    const launch_agent_file = path.join(
        launch_agents_directory,
        `${launch_agent_label}.plist`
    );

    app.on("second-instance", () => {
        if (!main_window || main_window.isDestroyed()) {
            return;
        }

        if (main_window.isMinimized()) {
            main_window.restore();
        }

        main_window.show();
        main_window.focus();
    });

    function sendToWindow(channel, data) {
        if (main_window && !main_window.isDestroyed()) {
            main_window.webContents.send(channel, data);
        }
    }

    function createWindow() {
        if (main_window && !main_window.isDestroyed()) {
            main_window.show();
            main_window.focus();
            return;
        }

        main_window = new BrowserWindow({
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

        main_window.loadFile(
            path.join(__dirname, "index.html")
        );

        main_window.once("ready-to-show", () => {
            if (main_window && !main_window.isDestroyed()) {
                main_window.show();
            }
        });

        main_window.webContents.once("did-finish-load", () => {
            sendSchedulesToWindow();

            // Show a previously saved app list immediately, if available.
            loadSavedApplications();

            // Refresh the list using the current application discovery logic.
            loadApplications();
        });

        main_window.on("close", (event) => {
            if (!is_quitting) {
                event.preventDefault();
                main_window.hide();
            }
        });

        main_window.on("closed", () => {
            main_window = null;
        });
    }

    function saveSchedules(schedules) {
        try {
            fs.mkdirSync(
                path.dirname(schedules_file),
                { recursive: true }
            );

            fs.writeFileSync(
                schedules_file,
                JSON.stringify(schedules, null, 2),
                "utf8"
            );

            console.log(
                `Saved ${schedules.length} schedule(s).`
            );
        } catch (error) {
            console.error("Could not save schedules:", error);
            sendToWindow(
                "blocker-error",
                "Could not save schedules."
            );
        }
    }

    function loadSchedules() {
        try {
            if (!fs.existsSync(schedules_file)) {
                return [];
            }

            const saved = JSON.parse(
                fs.readFileSync(schedules_file, "utf8")
            );

            return Array.isArray(saved) ? saved : [];
        } catch (error) {
            console.error("Could not load schedules:", error);
            return [];
        }
    }

    
    function getBlockerPath() {
        if (app.isPackaged) {
            const packagedPath = path.join(
                process.resourcesPath,
                "app_blocker",
                "app_blocker"
            );

            if (!fs.existsSync(packagedPath)) {
                throw new Error(
                    "The Python blocker executable was not found: " +
                    packagedPath
                );
            }

            return {
                command: packagedPath,
                args: []
            };
        }

        return {
            command: "python3",
            args: [
                path.join(__dirname, "app_blocker.py")
            ]
        };
    }


    function getApplicationParentLabel(app_path) {
        const parent = path.basename(path.dirname(app_path));

        if (app_path.startsWith("/System/Applications/")) {
            if (parent === "Applications") {
                return "System Applications";
            }
        }

        if (
            app_path.startsWith(
                path.join(app.getPath("home"), "Applications") + path.sep
            ) &&
            parent === "Applications"
        ) {
            return "User Applications";
        }

        return parent;
    }

    function scanApplicationFolders() {
        const roots = [
            "/Applications",
            "/System/Applications",
            path.join(app.getPath("home"), "Applications")
        ];

        const found_paths = new Set();

        function walk(folder, depth) {
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

                const full_path = path.join(
                    folder,
                    entry.name
                );

                if (entry.name.endsWith(".app")) {
                    found_paths.add(full_path);
                    continue;
                }

                if (
                    depth < 5 &&
                    entry.name !== "Contents" &&
                    entry.name !== "Frameworks" &&
                    !entry.name.startsWith(".")
                ) {
                    walk(full_path, depth + 1);
                }
            }
        }

        for (const root of roots) {
            walk(root, 0);
        }

        const grouped = new Map();

        for (const app_path of found_paths) {
            const name = path.basename(app_path, ".app");
            const parent = getApplicationParentLabel(app_path);

            if (!grouped.has(name)) {
                grouped.set(name, []);
            }

            grouped.get(name).push({
                name,
                parent,
                path: app_path
            });
        }

        const result = [];

        for (const [name, entries] of grouped.entries()) {
            entries.sort((a, b) =>
                a.path.localeCompare(b.path)
            );

            if (entries.length === 1) {
                result.push(name);
                continue;
            }

            const used_labels = new Set();

            for (const entry of entries) {
                let label = entry.parent;

                if (used_labels.has(label)) {
                    label = path.basename(
                        path.dirname(
                            path.dirname(entry.path)
                        )
                    ) + " / " + label;
                }

                used_labels.add(label);
                result.push([name, label]);
            }
        }

        return result.sort((a, b) => {
            const name_a = Array.isArray(a) ? a[0] : a;
            const name_b = Array.isArray(b) ? b[0] : b;

            return name_a.localeCompare(
                name_b,
                undefined,
                { sensitivity: "base" }
            );
        });
    }

    function saveApplicationsCache(apps) {
        if (!Array.isArray(apps) || apps.length === 0) {
            return;
        }

        try {
            fs.mkdirSync(
                path.dirname(applications_file),
                { recursive: true }
            );

            fs.writeFileSync(
                applications_file,
                JSON.stringify(apps, null, 2),
                "utf8"
            );
        } catch (error) {
            console.error(
                "Could not cache applications:",
                error
            );
        }
    }

    function loadSavedApplications() {
        try {
            if (!fs.existsSync(applications_file)) {
                return;
            }

            const cached = JSON.parse(
                fs.readFileSync(applications_file, "utf8")
            );

            // An empty cache must not prevent a fresh scan.
            if (Array.isArray(cached) && cached.length > 0) {
                sendToWindow("apps-found", cached);
            }
        } catch (error) {
            console.error(
                "Could not load saved applications:",
                error
            );
        }
    }

    function loadApplications() {
        let blocker;

        try {
            blocker = getBlockerPath();
        } catch (error) {
            console.error(error.message);
            useApplicationFolderFallback();
            return;
        }

        let child;

        try {
            child = spawn(
                blocker.command,
                [...blocker.args, "--list-apps"],
                {
                    stdio: ["ignore", "pipe", "pipe"]
                }
            );
        } catch (error) {
            console.error(
                "Could not start application discovery:",
                error
            );

            useApplicationFolderFallback();
            return;
        }

        let output = "";
        let error_output = "";
        let fallback_used = false;

        function useFallbackOnce() {
            if (fallback_used) {
                return;
            }

            fallback_used = true;
            useApplicationFolderFallback();
        }

        child.stdout.on("data", (data) => {
            output += data.toString();
        });

        child.stderr.on("data", (data) => {
            error_output += data.toString();
        });

        child.on("error", (error) => {
            console.error(
                "Application discovery failed:",
                error
            );

            useFallbackOnce();
        });

        child.on("close", (code) => {
            if (fallback_used) {
                return;
            }

            let apps = [];

            try {
                if (code !== 0) {
                    throw new Error(
                        error_output ||
                        `Application discovery exited with code ${code}.`
                    );
                }

                apps = JSON.parse(output);

                if (!Array.isArray(apps)) {
                    throw new Error(
                        "Application discovery returned invalid data."
                    );
                }
            } catch (error) {
                console.error(
                    "Could not read the application list:",
                    error
                );
            }

            if (apps.length === 0) {
                apps = scanApplicationFolders();
            }

            if (apps.length > 0) {
                saveApplicationsCache(apps);
                sendToWindow("apps-found", apps);
                return;
            }

            try {
                const cached = JSON.parse(
                    fs.readFileSync(applications_file, "utf8")
                );

                if (Array.isArray(cached) && cached.length > 0) {
                    sendToWindow("apps-found", cached);
                    return;
                }
            } catch {

            }

            sendToWindow("apps-found", []);
            sendToWindow(
                "blocker-error",
                "No applications were found. Check that your Applications folders are accessible."
            );
        });
    }

    function useApplicationFolderFallback() {
        const apps = scanApplicationFolders();

        if (apps.length > 0) {
            saveApplicationsCache(apps);
            sendToWindow("apps-found", apps);
            return;
        }

        try {
            const cached = JSON.parse(
                fs.readFileSync(applications_file, "utf8")
            );

            if (Array.isArray(cached) && cached.length > 0) {
                sendToWindow("apps-found", cached);
                return;
            }
        } catch {
            // No cache available.
        }

        sendToWindow("apps-found", []);
        sendToWindow(
            "blocker-error",
            "Application discovery failed. No cached application list is available."
        );
    }

    function xmlEscape(value) {
        return String(value)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&apos;");
    }

    function installBackgroundAgent(){
        if (!app.isPackaged) {
            console.log(
                "Development mode: leaving the installed background service unchanged."
            );
            return;
        }

        const blocker_path = path.join(
            process.resourcesPath,
            "app_blocker",
            "app_blocker"
        );

        if (!fs.existsSync(blocker_path)) {
            console.error(
                "Background blocker executable is missing:",
                blocker_path
            );
            return;
        }

        try {
            fs.mkdirSync(
                launch_agents_directory,
                { recursive: true }
            );

            fs.mkdirSync(
                logs_directory,
                { recursive: true }
            );

            const arguments_xml = `
        <array>
            <string>${xmlEscape(blocker_path)}</string>
        </array>`;

            const plist_contents = `<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>${launch_agent_label}</string>
    <key>ProgramArguments</key>
    ${arguments_xml}
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>ProcessType</key>
    <string>Background</string>
    <key>StandardOutPath</key>
    <string>${xmlEscape(path.join(logs_directory, "AppBlocker.log"))}</string>
    <key>StandardErrorPath</key>
    <string>${xmlEscape(path.join(logs_directory, "AppBlocker-error.log"))}</string>
</dict>
</plist>`;

            fs.writeFileSync(
                launch_agent_file,
                plist_contents,
                "utf8"
            );

            const domain = `gui/${process.getuid()}`;

            // It is okay if the service was not loaded yet.
            spawnSync(
                "/bin/launchctl",
                ["bootout", `${domain}/${launch_agent_label}`],
                { stdio: "ignore" }
            );

            const result = spawnSync(
                "/bin/launchctl",
                [
                    "bootstrap",
                    domain,
                    launch_agent_file
                ],
                { encoding: "utf8" }
            );

            if (result.error || result.status !== 0) {
                console.error(
                    "Could not start the background service:",
                    result.error || result.stderr
                );

                const retry = spawnSync(
                    "/bin/launchctl",
                    [
                        "kickstart",
                        "-k",
                        `${domain}/${launch_agent_label}`
                    ],
                    { encoding: "utf8" }
                );

                if (retry.error || retry.status !== 0) {
                    console.error(
                        "Could not restart the background service:",
                        retry.error || retry.stderr
                    );
                }
            } else {
                console.log(
                    "Background service installed and started."
                );
            }
        } catch (error) {
            console.error(
                "Could not configure the background service:",
                error
            );
        }
    }

    function sendSchedulesToWindow() {
        sendToWindow(
            "schedules-loaded",
            loadSchedules()
        );
    }

    ipcMain.on("load-schedules", () => {
        sendSchedulesToWindow();
    });

    ipcMain.on("block-app", (_event, data) => {
        if (!data || !Array.isArray(data.schedules)) {
            console.error("Received invalid schedule data.");
            return;
        }

        saveSchedules(data.schedules);
        sendSchedulesToWindow();
    });

    app.whenReady().then(() => {
        installBackgroundAgent();
        createWindow();
    });

    app.on("before-quit", () => {
        is_quitting = true;
    });

    app.on("window-all-closed", () => {
        // Keep the app running in the background on macOS.
    });

    app.on("activate", () => {
        if (main_window && !main_window.isDestroyed()) {
            main_window.show();
            main_window.focus();
        } else {
            createWindow();
        }
    });
}