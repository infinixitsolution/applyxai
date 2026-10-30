"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const electron_1 = require("electron");
const FALLBACK_CONNECTION = {
    apiBackendOrigin: "http://127.0.0.1:8010",
    presets: { local: "http://127.0.0.1:8010", production: "https://applyxai.com" },
    packagedDefault: "http://127.0.0.1:8010",
    uiOrigin: "http://127.0.0.1:39218",
    useLocalVite: false,
};
function readConnectionSettings() {
    try {
        const value = electron_1.ipcRenderer.sendSync("desktop:connectionSettingsSync");
        if (value?.apiBackendOrigin)
            return { ...FALLBACK_CONNECTION, ...value };
    }
    catch {
        /* main not ready */
    }
    return FALLBACK_CONNECTION;
}
const connection = readConnectionSettings();
electron_1.contextBridge.exposeInMainWorld("applyxaiDesktop", {
    isDesktop: true,
    apiBackendOrigin: connection.apiBackendOrigin,
    apiPresets: connection.presets,
    uiOrigin: connection.uiOrigin ?? FALLBACK_CONNECTION.uiOrigin,
    useLocalVite: connection.useLocalVite ?? false,
    connection: {
        getSettings: () => electron_1.ipcRenderer.invoke("desktop:getConnectionSettings"),
        setApiBackend: (url) => electron_1.ipcRenderer.invoke("desktop:setApiBackend", url),
        restart: () => electron_1.ipcRenderer.invoke("desktop:restart"),
    },
    versions: {
        electron: process.versions.electron,
        chrome: process.versions.chrome,
    },
    agent: {
        connect: () => electron_1.ipcRenderer.invoke("agent:connect"),
        beginConnect: () => electron_1.ipcRenderer.invoke("agent:beginConnect"),
        completeConnect: (sessionId, secret) => electron_1.ipcRenderer.invoke("agent:completeConnect", sessionId, secret),
        validateToken: () => electron_1.ipcRenderer.invoke("agent:validateToken"),
        status: () => electron_1.ipcRenderer.invoke("agent:status"),
        disconnect: () => electron_1.ipcRenderer.invoke("agent:disconnect"),
        readCredentials: () => electron_1.ipcRenderer.invoke("agent:readCredentials"),
        saveCredentials: (body) => electron_1.ipcRenderer.invoke("agent:saveCredentials", body),
    },
    liveInterview: {
        start: (options) => electron_1.ipcRenderer.invoke("liveInterview:start", options),
        end: (sessionId) => electron_1.ipcRenderer.invoke("liveInterview:end", sessionId),
        endActive: () => electron_1.ipcRenderer.invoke("liveInterview:endActive"),
        probeAudio: () => electron_1.ipcRenderer.invoke("liveInterview:probeAudio"),
        status: () => electron_1.ipcRenderer.invoke("liveInterview:status"),
        sync: () => electron_1.ipcRenderer.invoke("liveInterview:sync"),
        concealCoach: () => electron_1.ipcRenderer.invoke("liveInterview:concealCoach"),
        showCoach: () => electron_1.ipcRenderer.invoke("liveInterview:showCoach"),
        reconnectAudio: () => electron_1.ipcRenderer.invoke("liveInterview:reconnectAudio"),
        moveCoachWindow: (deltaX, deltaY) => electron_1.ipcRenderer.invoke("liveInterview:coachMoveBy", deltaX, deltaY),
        resizeCoachWindow: (deltaWidth) => electron_1.ipcRenderer.invoke("liveInterview:coachResizeBy", deltaWidth),
        onEvent: (listener) => {
            const handler = (_event, payload) => listener(payload);
            electron_1.ipcRenderer.on("live-interview:event", handler);
            return () => electron_1.ipcRenderer.removeListener("live-interview:event", handler);
        },
    },
});
