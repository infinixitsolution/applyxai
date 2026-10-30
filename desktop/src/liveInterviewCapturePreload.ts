import { contextBridge, ipcRenderer } from "electron";

contextBridge.exposeInMainWorld("captureBridge", {
  sendClip: (speaker: string, buffer: ArrayBuffer) => {
    ipcRenderer.send("live-capture:clip", speaker, new Uint8Array(buffer));
  },
});
