import { contextBridge, ipcRenderer, type IpcRendererEvent } from "electron";
import type { LiveInterviewDesktopEvent, LiveInterviewStartOptions } from "./liveInterviewTypes";

/** Preload must not import main-process modules (config, fs, apiBackendStore). */

type ConnectionSettings = {
  apiBackendOrigin: string;
  presets: { local: string; production: string };
  packagedDefault: string;
  uiOrigin?: string;
  useLocalVite?: boolean;
};

const FALLBACK_CONNECTION: ConnectionSettings = {
  apiBackendOrigin: "http://127.0.0.1:8010",
  presets: { local: "http://127.0.0.1:8010", production: "https://applyxai.com" },
  packagedDefault: "http://127.0.0.1:8010",
  uiOrigin: "http://127.0.0.1:39218",
  useLocalVite: false,
};

function readConnectionSettings(): ConnectionSettings {
  try {
    const value = ipcRenderer.sendSync("desktop:connectionSettingsSync") as ConnectionSettings;
    if (value?.apiBackendOrigin) return { ...FALLBACK_CONNECTION, ...value };
  } catch {
    /* main not ready */
  }
  return FALLBACK_CONNECTION;
}

const connection = readConnectionSettings();

contextBridge.exposeInMainWorld("applyxaiDesktop", {
  isDesktop: true as const,
  apiBackendOrigin: connection.apiBackendOrigin,
  apiPresets: connection.presets,
  uiOrigin: connection.uiOrigin ?? FALLBACK_CONNECTION.uiOrigin,
  useLocalVite: connection.useLocalVite ?? false,
  connection: {
    getSettings: (): Promise<ConnectionSettings> => ipcRenderer.invoke("desktop:getConnectionSettings"),
    setApiBackend: (url: string): Promise<{ ok: true; apiBackendOrigin: string; needsRestart: boolean } | { ok: false; message: string }> =>
      ipcRenderer.invoke("desktop:setApiBackend", url),
    restart: (): Promise<void> => ipcRenderer.invoke("desktop:restart"),
  },
  versions: {
    electron: process.versions.electron,
    chrome: process.versions.chrome,
  },
  agent: {
    connect: (): Promise<{ name: string }> => ipcRenderer.invoke("agent:connect"),
    beginConnect: (): Promise<{ session_id: string; secret: string }> => ipcRenderer.invoke("agent:beginConnect"),
    completeConnect: (sessionId: string, secret: string): Promise<{ name: string }> =>
      ipcRenderer.invoke("agent:completeConnect", sessionId, secret),
    validateToken: (): Promise<boolean> => ipcRenderer.invoke("agent:validateToken"),
    status: (): Promise<{ workerRunning: boolean; connected: boolean; tokenValid?: boolean }> =>
      ipcRenderer.invoke("agent:status"),
    disconnect: (): Promise<void> => ipcRenderer.invoke("agent:disconnect"),
    readCredentials: (): Promise<{
      username: string;
      password: string;
      naukri_username: string;
      naukri_password: string;
    }> => ipcRenderer.invoke("agent:readCredentials"),
    saveCredentials: (body: {
      username?: string;
      password?: string;
      naukri_username?: string;
      naukri_password?: string;
    }): Promise<{
      username: string;
      password: string;
      naukri_username: string;
      naukri_password: string;
    }> => ipcRenderer.invoke("agent:saveCredentials", body),
  },
  liveInterview: {
    start: (options: LiveInterviewStartOptions): Promise<{ sessionId: string }> =>
      ipcRenderer.invoke("liveInterview:start", options),
    end: (sessionId: string): Promise<{ ok: boolean; message: string }> =>
      ipcRenderer.invoke("liveInterview:end", sessionId),
    endActive: (): Promise<{ ok: boolean; message: string }> => ipcRenderer.invoke("liveInterview:endActive"),
    probeAudio: (): Promise<{ ok: boolean; message: string }> => ipcRenderer.invoke("liveInterview:probeAudio"),
    status: (): Promise<{ active: boolean; sessionId: string | null }> => ipcRenderer.invoke("liveInterview:status"),
    sync: (): Promise<{ active: boolean; sessionId: string | null }> => ipcRenderer.invoke("liveInterview:sync"),
    concealCoach: (): Promise<void> => ipcRenderer.invoke("liveInterview:concealCoach"),
    showCoach: (): Promise<void> => ipcRenderer.invoke("liveInterview:showCoach"),
    reconnectAudio: (): Promise<{ active: boolean; sessionId: string | null }> =>
      ipcRenderer.invoke("liveInterview:reconnectAudio"),
    moveCoachWindow: (deltaX: number, deltaY: number): Promise<void> =>
      ipcRenderer.invoke("liveInterview:coachMoveBy", deltaX, deltaY),
    resizeCoachWindow: (deltaWidth: number): Promise<void> =>
      ipcRenderer.invoke("liveInterview:coachResizeBy", deltaWidth),
    onEvent: (listener: (event: LiveInterviewDesktopEvent) => void) => {
      const handler = (_event: IpcRendererEvent, payload: LiveInterviewDesktopEvent) => listener(payload);
      ipcRenderer.on("live-interview:event", handler);
      return () => ipcRenderer.removeListener("live-interview:event", handler);
    },
  },
});
