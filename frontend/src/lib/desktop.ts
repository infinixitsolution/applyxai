import type { LiveInterviewDesktopApi } from "./liveInterviewDesktop";

declare global {
  interface Window {
    applyxaiDesktop?: {
      isDesktop: true;
      /** FastAPI origin the desktop shell proxies /api to (Electron main config). */
      apiBackendOrigin?: string;
      uiOrigin?: string;
      useLocalVite?: boolean;
      apiPresets?: { local: string; production: string };
      connection?: {
        getSettings: () => Promise<{ apiBackendOrigin: string; presets: { local: string; production: string } }>;
        setApiBackend: (url: string) => Promise<
          { ok: true; apiBackendOrigin: string; needsRestart: boolean } | { ok: false; message: string }
        >;
        restart: () => Promise<void>;
      };
      versions?: { electron?: string; chrome?: string };
      agent?: {
        connect: () => Promise<{ name: string }>;
        beginConnect: () => Promise<{ session_id: string; secret: string }>;
        completeConnect: (sessionId: string, secret: string) => Promise<{ name: string }>;
        validateToken: () => Promise<boolean>;
        status: () => Promise<{ workerRunning: boolean; connected: boolean; tokenValid?: boolean }>;
        disconnect: () => Promise<void>;
        readCredentials: () => Promise<AgentLocalCredentials>;
        saveCredentials: (body: Partial<AgentLocalCredentials>) => Promise<AgentLocalCredentials>;
      };
      liveInterview?: LiveInterviewDesktopApi;
    };
  }
}

export type AgentLocalCredentials = {
  username: string;
  password: string;
  naukri_username: string;
  naukri_password: string;
};

export const isDesktop =
  typeof window !== "undefined" &&
  (window.applyxaiDesktop?.isDesktop === true || Boolean(window.applyxaiDesktop?.versions?.electron));

/** Bundled desktop SPA (login-only shell) — true in Electron or VITE_DESKTOP_BUILD. */
export const isDesktopApp =
  isDesktop || (typeof import.meta !== "undefined" && import.meta.env.VITE_DESKTOP_BUILD === "1");

/** ApplyXAI Desktop UI (no installer / connect wizard). Same as {@link isDesktopApp}. */
export const isDesktopHost = isDesktopApp;

/** Electron agent IPC available for silent pairing on this machine. */
export function hasDesktopAgent(): boolean {
  return typeof window !== "undefined" && Boolean(window.applyxaiDesktop?.agent?.beginConnect);
}

export function hasLiveInterviewDesktop(): boolean {
  return typeof window !== "undefined" && Boolean(window.applyxaiDesktop?.liveInterview?.start);
}

/** True when the page runs inside Electron (even if preload failed). */
export function isElectronRenderer(): boolean {
  return typeof navigator !== "undefined" && /Electron/i.test(navigator.userAgent);
}

/** Electron preload bridge is active (not a bare browser tab on the local UI port). */
export function isDesktopBridgeReady(): boolean {
  if (typeof window === "undefined") return false;
  const desktop = window.applyxaiDesktop;
  return desktop?.isDesktop === true || Boolean(desktop?.versions?.electron);
}

export function waitForDesktopBridge(timeoutMs = 4000): Promise<boolean> {
  if (isDesktopBridgeReady()) return Promise.resolve(true);
  return new Promise((resolve) => {
    const start = Date.now();
    const tick = () => {
      if (isDesktopBridgeReady()) {
        resolve(true);
        return;
      }
      if (Date.now() - start >= timeoutMs) {
        resolve(false);
        return;
      }
      window.setTimeout(tick, 150);
    };
    tick();
  });
}

/** Desktop shell can offer live interview controls (API may attach after preload). */
export function canUseLiveInterviewShell(): boolean {
  return isDesktopBridgeReady();
}

export function liveInterviewUnavailableMessage(): string {
  if (isDesktopBridgeReady() && !hasLiveInterviewDesktop()) {
    return "Live interview API is missing. Install ApplyXAI Desktop v1.2.14 or newer.";
  }
  if (isDesktopHost && !isDesktopBridgeReady()) {
    if (isElectronRenderer()) {
      return "ApplyXAI Desktop could not load its integration layer. Fully quit the app (tray → Quit), install ApplyXAI Desktop v1.2.14 or newer, then open Live interviews again.";
    }
    return "You opened the local UI in a browser (127.0.0.1). Use the ApplyXAI Desktop app window instead — not Chrome or Edge.";
  }
  return "Live interview runs in ApplyXAI Desktop on Windows. Install the app, sign in, then return here.";
}

/** Signed-in user can run automation on this PC without manual Connect steps. */
export function isDesktopAutomationHost(): boolean {
  return isDesktop || (isDesktopHost && hasDesktopAgent());
}

export function desktopAgent() {
  return window.applyxaiDesktop?.agent;
}

/** Where API requests from this shell are routed (desktop proxy target or browser dev proxy). */
export function desktopApiBackendLabel(): string | null {
  if (!isDesktop) return null;
  return window.applyxaiDesktop?.apiBackendOrigin?.replace(/\/$/, "") ?? null;
}
