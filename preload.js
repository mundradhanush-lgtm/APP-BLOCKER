const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("electronAPI", {
    sendAppData: (data) => ipcRenderer.send("block-app", data),

    receiveApps: (callback) => ipcRenderer.on("apps-found", (event, apps) => {
        callback(apps);
    })
});