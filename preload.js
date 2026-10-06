const { contextBridge, ipcRenderer } = require("electron");
contextBridge.exposeInMainWorld("electronAPI", {
    sendAppData: (data) => ipcRenderer.send("block-app", data),
    receiveApps: (callback) => ipcRenderer.on("apps-found", (event, apps) => {
        callback(apps);
    }),
    receiveBlockerStatus: (callback) => ipcRenderer.on("blocker-status", (event, message) => {
        callback(message);
    }),
    receiveBlockerError: (callback) => ipcRenderer.on("blocker-error", (event, message) => {
        callback(message);
    }),
    receiveBlockerEnded: (callback) => ipcRenderer.on("blocker-ended", (event, message) => {
        callback(message);
    })
});