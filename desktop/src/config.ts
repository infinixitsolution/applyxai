import { app } from "electron";

import { getApiBackendOrigin } from "./apiBackendStore";

/**
 * Local Vite (127.0.0.1:5173) for unpackaged Electron dev.
 * Packaged app serves bundled SPA on DESKTOP_UI_PORT and proxies /api to the configured backend.
 */
export const LOCAL_VITE_ORIGIN = (process.env.APPLYXAI_VITE_URL || "http://127.0.0.1:5173").replace(/\/$/, "");

/** FastAPI backend (user-selectable; see apiBackendStore). */
export function apiBackendOrigin(): string {
  return getApiBackendOrigin();
}

export const DESKTOP_UI_PORT = Number(process.env.APPLYXAI_DESKTOP_PORT || 39218);

export const AGENT_WAKE_PORT = 39217;

function envOverride(): boolean | null {
  const v = process.env.APPLYXAI_DESKTOP_LOCAL;
  if (v === "0") return false;
  if (v === "1") return true;
  return null;
}

export function useLocalVite(): boolean {
  // Packaged builds always serve the desktop-only bundled SPA (never the public marketing Vite dev site).
  if (app.isPackaged) return false;
  const forced = envOverride();
  if (forced !== null) return forced;
  return true;
}

export function desktopUiOrigin(): string {
  if (useLocalVite()) return LOCAL_VITE_ORIGIN;
  return `http://127.0.0.1:${DESKTOP_UI_PORT}`;
}

/** Agent connect + device token API base. */
export function apiOriginForDesktop(): string {
  if (useLocalVite()) return LOCAL_VITE_ORIGIN;
  return apiBackendOrigin();
}
