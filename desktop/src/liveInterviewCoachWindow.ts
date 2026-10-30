import { app, BrowserWindow, screen } from "electron";
import fs from "fs";
import path from "path";
import { desktopUiOrigin } from "./config";

let coachWindow: BrowserWindow | null = null;

const DEFAULT_COACH_WIDTH = 420;
const DEFAULT_COACH_HEIGHT = 560;
const MIN_COACH_WIDTH = 300;
const MAX_COACH_WIDTH = 720;

type CoachBounds = { x: number; y: number; width: number; height: number };

function coachBoundsFile(): string {
  return path.join(app.getPath("userData"), "live-interview-coach-bounds.json");
}

function readSavedCoachBounds(): CoachBounds | null {
  try {
    const raw = fs.readFileSync(coachBoundsFile(), "utf8");
    const parsed = JSON.parse(raw) as CoachBounds;
    if (
      typeof parsed.x === "number" &&
      typeof parsed.y === "number" &&
      typeof parsed.width === "number" &&
      typeof parsed.height === "number"
    ) {
      return parsed;
    }
  } catch {
    /* first run */
  }
  return null;
}

function writeSavedCoachBounds(bounds: CoachBounds): void {
  try {
    fs.mkdirSync(path.dirname(coachBoundsFile()), { recursive: true });
    fs.writeFileSync(coachBoundsFile(), JSON.stringify(bounds), "utf8");
  } catch {
    /* best effort */
  }
}

function clampCoachBounds(bounds: CoachBounds): CoachBounds {
  const display = screen.getDisplayMatching(bounds);
  const { workArea } = display;
  const width = Math.max(MIN_COACH_WIDTH, Math.min(bounds.width, Math.min(MAX_COACH_WIDTH, workArea.width)));
  const height = Math.max(120, Math.min(bounds.height, workArea.height));
  const x = Math.max(workArea.x, Math.min(bounds.x, workArea.x + workArea.width - width));
  const y = Math.max(workArea.y, Math.min(bounds.y, workArea.y + workArea.height - height));
  return { x, y, width, height };
}

function defaultCoachBounds(): CoachBounds {
  const { workArea } = screen.getPrimaryDisplay();
  const margin = 12;
  return clampCoachBounds({
    x: workArea.x + workArea.width - DEFAULT_COACH_WIDTH - margin,
    y: workArea.y + workArea.height - DEFAULT_COACH_HEIGHT - margin,
    width: DEFAULT_COACH_WIDTH,
    height: DEFAULT_COACH_HEIGHT,
  });
}

function initialCoachBounds(): CoachBounds {
  const saved = readSavedCoachBounds();
  return clampCoachBounds(saved ?? defaultCoachBounds());
}

function trackCoachBounds(win: BrowserWindow): void {
  const persist = () => {
    if (win.isDestroyed()) return;
    writeSavedCoachBounds(win.getBounds());
  };
  win.on("moved", persist);
  win.on("resized", persist);
}

/** Move the floating coach window (drag the mic icon or panel header). */
export function moveLiveInterviewCoachWindow(deltaX: number, deltaY: number): void {
  const win = getLiveInterviewCoachWindow();
  if (!win || win.isDestroyed()) return;
  const current = win.getBounds();
  const next = clampCoachBounds({
    x: current.x + Math.round(deltaX),
    y: current.y + Math.round(deltaY),
    width: current.width,
    height: current.height,
  });
  win.setBounds(next);
  writeSavedCoachBounds(next);
}

function coachPreloadPath(): string {
  return path.join(__dirname, "preload.js");
}

export function getLiveInterviewCoachWindow(): BrowserWindow | null {
  if (coachWindow && !coachWindow.isDestroyed()) return coachWindow;
  return null;
}

/**
 * Keep the coach visible locally but omit it from screen capture (full desktop share, etc.).
 * Windows 10 2004+ uses WDA_EXCLUDEFROMCAPTURE; macOS uses NSWindowSharingNone.
 */
function applyCoachScreenCaptureProtection(win: BrowserWindow): void {
  if (process.platform !== "win32" && process.platform !== "darwin") return;
  if (win.isDestroyed()) return;
  try {
    // Transparent frameless windows need explicit opacity before content protection on some Electron/Win builds.
    if (win.getOpacity() < 1) win.setOpacity(1);
    win.setContentProtection(true);
  } catch {
    /* best effort */
  }
}

/** Floating coach UI on the Windows desktop (outside the main ApplyXAI window). */
export async function ensureLiveInterviewCoachWindow(): Promise<BrowserWindow> {
  const existing = getLiveInterviewCoachWindow();
  if (existing) {
    applyCoachScreenCaptureProtection(existing);
    existing.show();
    return existing;
  }

  const bounds = initialCoachBounds();

  const win = new BrowserWindow({
    x: bounds.x,
    y: bounds.y,
    width: bounds.width,
    height: bounds.height,
    minWidth: MIN_COACH_WIDTH,
    maxWidth: MAX_COACH_WIDTH,
    minHeight: 120,
    frame: false,
    transparent: true,
    show: false,
    alwaysOnTop: true,
    skipTaskbar: true,
    resizable: true,
    maximizable: false,
    minimizable: false,
    fullscreenable: false,
    title: "ApplyXAI Interview Coach",
    autoHideMenuBar: true,
    backgroundColor: "#00000000",
    webPreferences: {
      preload: coachPreloadPath(),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
    },
  });

  coachWindow = win;
  trackCoachBounds(win);
  win.on("closed", () => {
    if (coachWindow === win) coachWindow = null;
  });

  const ready = new Promise<void>((resolve) => {
    win.webContents.once("did-finish-load", () => resolve());
  });
  await win.loadURL(`${desktopUiOrigin()}/app/live-interview-coach`);
  await ready;
  applyCoachScreenCaptureProtection(win);
  win.show();
  void import("./liveInterviewSession").then((mod) => mod.replayLiveInterviewUiState());
  return win;
}

/** Widen or narrow the coach panel (persisted with other bounds). */
export function resizeLiveInterviewCoachWindow(deltaWidth: number): void {
  const win = getLiveInterviewCoachWindow();
  if (!win || win.isDestroyed()) return;
  const current = win.getBounds();
  const next = clampCoachBounds({
    x: current.x,
    y: current.y,
    width: current.width + Math.round(deltaWidth),
    height: current.height,
  });
  win.setBounds(next);
  writeSavedCoachBounds(next);
}

/** Hide the overlay while the interview session keeps running in the main process. */
export function concealLiveInterviewCoachWindow(): void {
  const win = getLiveInterviewCoachWindow();
  if (win) win.hide();
}

export async function revealLiveInterviewCoachWindow(): Promise<void> {
  await ensureLiveInterviewCoachWindow();
}

export function hideLiveInterviewCoachWindow(): void {
  const win = getLiveInterviewCoachWindow();
  if (win) {
    win.close();
  }
  coachWindow = null;
}
