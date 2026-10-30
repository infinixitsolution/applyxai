import fs from "fs";
import path from "path";

import { app } from "electron";

import { PACKAGED_API_ORIGIN } from "./productVersion";

export const API_BACKEND_PRESETS = {
  local: "http://127.0.0.1:8010",
  production: "https://applyxai.com",
} as const;

let cached = "";

function storePath(): string {
  return path.join(app.getPath("userData"), "api-backend.txt");
}

export function normalizeApiOrigin(raw: string): string {
  const trimmed = (raw || "").trim().replace(/\/$/, "");
  if (!trimmed) return API_BACKEND_PRESETS.local;
  const withScheme = /^https?:\/\//i.test(trimmed) ? trimmed : `http://${trimmed}`;
  const url = new URL(withScheme);
  if (url.protocol !== "http:" && url.protocol !== "https:") {
    throw new Error("API URL must use http or https.");
  }
  return `${url.protocol}//${url.host}`;
}

export function loadApiBackendOrigin(): string {
  if (process.env.APPLYXAI_CLOUD_API || process.env.APPLYXAI_API_URL) {
    cached = normalizeApiOrigin(process.env.APPLYXAI_CLOUD_API || process.env.APPLYXAI_API_URL || "");
    return cached;
  }
  try {
    const saved = fs.readFileSync(storePath(), "utf8").trim();
    if (saved) {
      cached = normalizeApiOrigin(saved);
      return cached;
    }
  } catch {
    /* first run */
  }
  cached = normalizeApiOrigin(PACKAGED_API_ORIGIN || API_BACKEND_PRESETS.local);
  return cached;
}

export function getApiBackendOrigin(): string {
  if (!cached) return loadApiBackendOrigin();
  return cached;
}

export function saveApiBackendOrigin(raw: string): string {
  cached = normalizeApiOrigin(raw);
  fs.mkdirSync(app.getPath("userData"), { recursive: true });
  fs.writeFileSync(storePath(), cached, "utf8");
  return cached;
}

export function connectionSettings() {
  return {
    apiBackendOrigin: getApiBackendOrigin(),
    presets: { ...API_BACKEND_PRESETS },
    packagedDefault: PACKAGED_API_ORIGIN,
  };
}
