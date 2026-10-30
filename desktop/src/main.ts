import {
  app,
  BrowserWindow,
  dialog,
  ipcMain,
  Menu,
  nativeImage,
  session,
  shell,
  Tray,
} from "electron";
import fs from "fs";
import path from "path";
import { connectionSettings, getApiBackendOrigin, loadApiBackendOrigin, saveApiBackendOrigin } from "./apiBackendStore";
import { DESKTOP_UI_PORT, desktopUiOrigin, useLocalVite } from "./config";
import {
  ensureAgentWorker,
  isAgentWorkerRunning,
  markAgentWorkerShuttingDown,
  readAgentConnected,
  stopAgentWorkerAsync,
} from "./agent-process";
import {
  beginConnectSession,
  completeConnectSession,
  disconnectDesktopAgent,
  runDesktopConnect,
  validateLocalAgentToken,
} from "./connect";
import { readLocalCredentials, writeLocalCredentials } from "./credentials";
import { ensureLocalApiRunning, stopLocalApiIfStarted } from "./api-process";
import { startLocalServer } from "./server";
import { hideLiveInterviewCoachWindow, moveLiveInterviewCoachWindow, resizeLiveInterviewCoachWindow } from "./liveInterviewCoachWindow";
import {
  concealLiveInterviewCoachOverlay,
  endActiveLiveInterviewSession,
  endLiveInterviewSession,
  liveInterviewStatus,
  probeLiveInterviewAudio,
  setLiveInterviewMainWindow,
  showLiveInterviewCoachOverlay,
  startLiveInterviewSession,
  syncLiveInterviewSession,
} from "./liveInterviewSession";
import { stopLiveCapture } from "./liveInterviewCapture";
import { checkDesktopUpdate } from "./autoUpdate";

let mainWindow: BrowserWindow | null = null;
let tray: Tray | null = null;
let appQuitting = false;

function isMainWindowLive(): boolean {
  return mainWindow != null && !mainWindow.isDestroyed();
}

function ensureMainWindow(): BrowserWindow {
  if (isMainWindowLive()) return mainWindow!;
  mainWindow = createWindow();
  setLiveInterviewMainWindow(() => mainWindow);
  return mainWindow;
}

function showMainWindow(): void {
  const win = ensureMainWindow();
  if (win.isMinimized()) win.restore();
  if (!win.isVisible()) win.show();
  win.focus();
}

const gotLock = app.requestSingleInstanceLock();
ipcMain.on("desktop:connectionSettingsSync", (event) => {
  try {
    event.returnValue = {
      ...connectionSettings(),
      uiOrigin: desktopUiOrigin(),
      useLocalVite: useLocalVite(),
    };
  } catch (error) {
    console.error("[ApplyXAI] connectionSettingsSync failed:", error);
    event.returnValue = {
      apiBackendOrigin: "http://127.0.0.1:8010",
      presets: { local: "http://127.0.0.1:8010", production: "https://applyxai.com" },
      packagedDefault: "http://127.0.0.1:8010",
      uiOrigin: `http://127.0.0.1:${DESKTOP_UI_PORT}`,
      useLocalVite: false,
    };
  }
});

ipcMain.handle("desktop:getConnectionSettings", () => ({
  ...connectionSettings(),
  uiOrigin: desktopUiOrigin(),
  useLocalVite: useLocalVite(),
}));

ipcMain.handle("desktop:setApiBackend", async (_event, url: string) => {
  try {
    const saved = saveApiBackendOrigin(String(url || ""));
    return { ok: true as const, apiBackendOrigin: saved, needsRestart: true };
  } catch (error) {
    return { ok: false as const, message: error instanceof Error ? error.message : String(error) };
  }
});

ipcMain.handle("desktop:restart", () => {
  app.relaunch();
  app.exit(0);
});

if (!gotLock) {
  app.quit();
} else {
  app.on("second-instance", () => {
    showMainWindow();
  });
}

function resolvePreload(): string {
  const candidates = [
    path.join(__dirname, "preload.js"),
    path.join(process.resourcesPath, "preload.js"),
  ];
  for (const candidate of candidates) {
    if (fs.existsSync(candidate)) return candidate;
  }
  return candidates[0]!;
}

function resolveIcon(): string {
  const iconPath = path.join(__dirname, "..", "..", "agent", "branding", "applyxai.ico");
  return iconPath;
}

function createWindow(): BrowserWindow {
  const win = new BrowserWindow({
    width: 1280,
    height: 840,
    minWidth: 1024,
    minHeight: 720,
    show: false,
    autoHideMenuBar: true,
    webPreferences: {
      preload: resolvePreload(),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
    },
  });

  win.webContents.setWindowOpenHandler(({ url }) => {
    if (url.startsWith("http://") || url.startsWith("https://")) {
      void shell.openExternal(url);
    }
    return { action: "deny" };
  });

  win.once("ready-to-show", () => win.show());
  win.on("close", () => {
    hideLiveInterviewCoachWindow();
  });
  win.on("closed", () => {
    if (mainWindow === win) mainWindow = null;
  });
  const preloadPath = resolvePreload();
  if (!fs.existsSync(preloadPath)) {
    console.error("[ApplyXAI] Preload script missing:", preloadPath);
  }
  win.webContents.on("did-finish-load", () => {
    if (win.isDestroyed()) return;
    void win.webContents
      .executeJavaScript("Boolean(window.applyxaiDesktop?.isDesktop)", true)
      .then((ok) => {
        if (!ok) console.error("[ApplyXAI] Preload bridge missing after load. preload=", preloadPath);
      })
      .catch(() => undefined);
  });
  void win.loadURL(`${desktopUiOrigin()}/login`);
  return win;
}

function navigateMainWindow(url: string): void {
  if (!isMainWindowLive()) return;
  void mainWindow!.loadURL(url);
}

function buildTray(): void {
  const icon = nativeImage.createFromPath(resolveIcon());
  tray = new Tray(icon.isEmpty() ? nativeImage.createEmpty() : icon);
  tray.setToolTip("ApplyXAI");
  const menu = Menu.buildFromTemplate([
    {
      label: "Open ApplyXAI",
      click: () => {
        showMainWindow();
      },
    },
    { type: "separator" },
    {
      label: "Quit",
      click: () => app.quit(),
    },
  ]);
  tray.setContextMenu(menu);
  tray.on("double-click", () => showMainWindow());
}

app.whenReady().then(async () => {
  loadApiBackendOrigin();

  session.defaultSession.setPermissionRequestHandler((_webContents, permission, callback) => {
    if (permission === "media") {
      callback(true);
      return;
    }
    callback(true);
  });

  const apiReady = await ensureLocalApiRunning();
  if (!apiReady.ok) {
    await dialog.showMessageBox({
      type: "warning",
      title: "ApplyXAI API",
      message: `Can't reach the ApplyXAI API at ${getApiBackendOrigin()}.`,
      detail: apiReady.detail,
    });
  }

  if (!useLocalVite()) {
    await startLocalServer(getApiBackendOrigin());
  } else {
    console.log("Desktop UI: %s (start: cd frontend && npm run dev, API via Vite proxy)", desktopUiOrigin());
  }
  await ensureAgentWorker();
  buildTray();
  mainWindow = createWindow();
  setLiveInterviewMainWindow(() => mainWindow);
  void checkDesktopUpdate();

  app.on("activate", () => {
    if (!isMainWindowLive()) ensureMainWindow();
  });
});

app.on("window-all-closed", () => {
  hideLiveInterviewCoachWindow();
  if (process.platform !== "darwin") app.quit();
});

app.on("before-quit", (event) => {
  const shutdown = () => {
    hideLiveInterviewCoachWindow();
    markAgentWorkerShuttingDown();
    stopLocalApiIfStarted();
    void stopLiveCapture();
    void stopAgentWorkerAsync();
  };
  if (appQuitting) {
    shutdown();
    return;
  }
  const live = liveInterviewStatus();
  if (live.active && live.sessionId) {
    event.preventDefault();
    void (async () => {
      await endLiveInterviewSession(live.sessionId!);
      appQuitting = true;
      app.quit();
    })();
    return;
  }
  shutdown();
});

ipcMain.handle("agent:connect", async () => runDesktopConnect(navigateMainWindow));

ipcMain.handle("agent:beginConnect", async () => beginConnectSession());

ipcMain.handle("agent:completeConnect", async (_event, sessionId: string, secret: string) =>
  completeConnectSession(sessionId, secret),
);

ipcMain.handle("agent:validateToken", async () => validateLocalAgentToken());

ipcMain.handle("agent:status", async () => ({
  workerRunning: await isAgentWorkerRunning(),
  connected: readAgentConnected(),
}));

ipcMain.handle("agent:disconnect", async () => {
  await disconnectDesktopAgent();
  await stopAgentWorkerAsync();
  await ensureAgentWorker();
});

ipcMain.handle("agent:readCredentials", async () => readLocalCredentials());

ipcMain.handle("agent:saveCredentials", async (_event, body: Record<string, string | undefined>) =>
  writeLocalCredentials({
    username: body.username,
    password: body.password,
    naukri_username: body.naukri_username,
    naukri_password: body.naukri_password,
  }),
);

ipcMain.handle(
  "liveInterview:start",
  async (_event, body: { token: string; applicationId?: string | null; resume?: boolean }) => {
    const token = String(body.token || "").replace(/\D/g, "");
    if (token.length !== 8) throw new Error("Enter the 8-digit token from Support.");
    return startLiveInterviewSession(token, body.applicationId ? String(body.applicationId) : null, {
      resume: body.resume === true,
    });
  },
);

ipcMain.handle("liveInterview:end", async (_event, sessionId: string) => endLiveInterviewSession(String(sessionId)));

ipcMain.handle("liveInterview:endActive", async () => endActiveLiveInterviewSession());

ipcMain.handle("liveInterview:probeAudio", async () => probeLiveInterviewAudio());

ipcMain.handle("liveInterview:status", async () => liveInterviewStatus());

ipcMain.handle("liveInterview:sync", async () => syncLiveInterviewSession());

ipcMain.handle("liveInterview:concealCoach", async () => {
  await concealLiveInterviewCoachOverlay();
});

ipcMain.handle("liveInterview:showCoach", async () => {
  await showLiveInterviewCoachOverlay();
});

ipcMain.handle("liveInterview:reconnectAudio", async () => syncLiveInterviewSession());

ipcMain.handle("liveInterview:coachMoveBy", async (_event, deltaX: number, deltaY: number) => {
  moveLiveInterviewCoachWindow(Number(deltaX) || 0, Number(deltaY) || 0);
});

ipcMain.handle("liveInterview:coachResizeBy", async (_event, deltaWidth: number) => {
  resizeLiveInterviewCoachWindow(Number(deltaWidth) || 0);
});
