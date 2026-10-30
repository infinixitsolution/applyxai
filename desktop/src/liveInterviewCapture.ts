import { BrowserWindow, ipcMain, session } from "electron";
import path from "path";
import {
  isNativeCaptureRunning,
  probeNativeCapture,
  startNativeCapture,
  stopNativeCapture,
} from "./liveInterviewNativeCapture";

let captureWindow: BrowserWindow | null = null;
let clipHandler: ((speaker: string, wav: Buffer) => void) | null = null;
let clipListenerRegistered = false;
let captureMode: "native" | "browser" | null = null;

export function liveCaptureMode(): "native" | "browser" | null {
  return captureMode;
}

export function isLiveCaptureRunning(): boolean {
  return isNativeCaptureRunning() || (captureWindow !== null && !captureWindow.isDestroyed());
}

function captureHtmlPath(): string {
  return path.join(__dirname, "..", "static", "live-capture.html");
}

function capturePreloadPath(): string {
  return path.join(__dirname, "liveInterviewCapturePreload.js");
}

function ensureClipListener(): void {
  if (clipListenerRegistered) return;
  clipListenerRegistered = true;
  ipcMain.on("live-capture:clip", (_event, speaker: string, data: Buffer | Uint8Array) => {
    if (!clipHandler) return;
    const buf = Buffer.isBuffer(data) ? data : Buffer.from(data);
    clipHandler(speaker, buf);
  });
}

async function startBrowserCapture(onClip: (speaker: string, wav: Buffer) => void): Promise<void> {
  ensureClipListener();
  await stopBrowserCapture();

  session.defaultSession.setDisplayMediaRequestHandler(null);

  const picker = new BrowserWindow({
    width: 480,
    height: 360,
    show: true,
    alwaysOnTop: true,
    autoHideMenuBar: true,
    title: "ApplyXAI — share meeting audio",
    webPreferences: {
      preload: capturePreloadPath(),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
    },
  });

  captureWindow = picker;

  try {
    await picker.loadFile(captureHtmlPath(), { query: { picker: "1" } });
    clipHandler = onClip;
    await picker.webContents.executeJavaScript("window.startLiveCapture()", true);
    if (!picker.isDestroyed()) picker.hide();
  } catch (err) {
    await stopBrowserCapture();
    throw err;
  }
}

async function stopBrowserCapture(): Promise<void> {
  if (captureWindow && !captureWindow.isDestroyed()) {
    try {
      await captureWindow.webContents.executeJavaScript("window.stopLiveCapture()", true);
    } catch {
      /* closing */
    }
    captureWindow.destroy();
  }
  captureWindow = null;
}

export async function startLiveCapture(onClip: (speaker: string, wav: Buffer) => void): Promise<void> {
  await stopLiveCapture();
  clipHandler = onClip;

  if (process.platform === "win32") {
    try {
      await startNativeCapture(onClip);
      captureMode = "native";
      return;
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      console.warn(`Native loopback capture unavailable (${message}); trying screen-share audio.`);
    }
  }

  await startBrowserCapture(onClip);
  captureMode = "browser";
}

export async function stopLiveCapture(): Promise<void> {
  clipHandler = null;
  captureMode = null;
  await stopNativeCapture();
  await stopBrowserCapture();
}

export async function probeLiveCapture(): Promise<{ ok: boolean; message: string }> {
  if (process.platform === "win32") {
    const native = await probeNativeCapture();
    if (native.ok) return native;
  }
  try {
    await startBrowserCapture(() => undefined);
    await stopBrowserCapture();
    return {
      ok: true,
      message: "Screen-share audio capture is available (pick your meeting and enable Share audio).",
    };
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    return {
      ok: false,
      message: `Could not access call audio. On Windows, check your default speakers; otherwise pick a screen with Share audio enabled. ${message}`,
    };
  }
}
