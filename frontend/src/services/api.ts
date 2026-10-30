/**
 * The only place the app talks to the backend.
 *
 * - Cookies carry the session (HttpOnly; JavaScript never sees the tokens).
 * - Every mutating request sends X-CSRF-Token, copied from the readable applyxai_csrf cookie.
 * - Responses use the {success, data | error} envelope; errors become ApiError.
 * - A 401 triggers one shared POST /auth/refresh, then the request is retried once.
 */

import { isDesktop } from "../lib/desktop";

export const API_BASE = "/api";

const DESKTOP_API_HINT =
  "Start the API: venv\\Scripts\\python -m uvicorn backend.app.main:app --reload --port 8010 " +
  "(and for dev mode, also run npm run dev in frontend on port 5173).";
const CSRF_COOKIE = "applyxai_csrf";
const CSRF_HEADER = "X-CSRF-Token";
const SAFE_METHODS = new Set(["GET", "HEAD", "OPTIONS"]);
// Endpoints where a 401 means "wrong credentials / no session", not "access token expired".
const NO_REFRESH = ["/auth/login", "/auth/login/2fa", "/auth/refresh", "/auth/register", "/auth/logout"];
/** HTTP 401 with these error codes means the ApplyXAI session died — not third-party API key checks. */
const SESSION_EXPIRED_CODES = new Set(["UNAUTHORIZED", "SESSION_EXPIRED"]);

export interface FieldError {
  field: string;
  message: string;
}

export class ApiError extends Error {
  readonly code: string;
  readonly status: number;
  readonly details: FieldError[];

  constructor(code: string, message: string, status: number, details: unknown = []) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.status = status;
    this.details = Array.isArray(details) ? (details as FieldError[]) : [];
  }
}

type QueryValue = string | number | boolean | null | undefined | (string | number)[];

export interface RequestOptions {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  body?: unknown;
  form?: FormData;
  query?: Record<string, QueryValue>;
  /** Default 25s; use a longer value for Firecrawl / outreach bulk jobs. */
  timeoutMs?: number;
}

let sessionExpiredHandler: (() => void) | null = null;
let refreshing: Promise<boolean> | null = null;

/** Called once when the session can't be refreshed (the app sends the user to /login). */
export function onSessionExpired(handler: (() => void) | null): void {
  sessionExpiredHandler = handler;
}

export function readCookie(name: string): string {
  const prefix = `${name}=`;
  for (const part of document.cookie.split(";")) {
    const trimmed = part.trim();
    if (trimmed.startsWith(prefix)) return decodeURIComponent(trimmed.slice(prefix.length));
  }
  return "";
}

export function buildUrl(path: string, query?: Record<string, QueryValue>): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query ?? {})) {
    if (value === undefined || value === null || value === "") continue;
    if (Array.isArray(value)) value.forEach((v) => params.append(key, String(v)));
    else params.append(key, String(value));
  }
  const qs = params.toString();
  return `${API_BASE}${path}${qs ? `?${qs}` : ""}`;
}

async function send(path: string, options: RequestOptions): Promise<Response> {
  const method = options.method ?? "GET";
  const headers: Record<string, string> = { Accept: "application/json" };
  let body: BodyInit | undefined;
  if (options.form) {
    body = options.form;                                   // the browser sets the multipart boundary
  } else if (options.body !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(options.body);
  }
  if (!SAFE_METHODS.has(method)) headers[CSRF_HEADER] = readCookie(CSRF_COOKIE);
  const timeoutMs = options.timeoutMs ?? 25_000;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(buildUrl(path, options.query), {
      method, headers, body, credentials: "same-origin", signal: controller.signal,
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new ApiError(
        "TIMEOUT",
        "The server took too long to respond. Make sure the API is running (see docs/DEVELOPMENT.md).",
        0,
      );
    }
    throw error;
  } finally {
    clearTimeout(timer);
  }
}

async function parse<T>(response: Response): Promise<T> {
  let payload: { success?: boolean; data?: T; error?: { code: string; message: string; details?: unknown } };
  try {
    payload = await response.json();
  } catch {
    const offline = response.status >= 500 || response.status === 0 || response.status === 502;
    throw new ApiError(
      offline ? "SERVER_UNAVAILABLE" : "BAD_RESPONSE",
      offline && isDesktop
        ? DESKTOP_API_HINT
        : offline
          ? "The server isn't responding. Please try again in a moment."
          : "The server returned an unexpected response. Please try again.",
      response.status,
    );
  }
  if (payload.success) return payload.data as T;
  const error = payload.error ?? { code: "UNKNOWN", message: "Something went wrong." };
  throw new ApiError(error.code, error.message, response.status, error.details);
}

export function refreshSession(): Promise<boolean> {
  refreshing ??= send("/auth/refresh", { method: "POST" })
    .then((r) => r.ok)
    .catch(() => false)
    .finally(() => {
      refreshing = null;
    });
  return refreshing;
}

async function requestResponse(path: string, options: RequestOptions = {}): Promise<Response> {
  let response: Response;
  try {
    response = await send(path, options);
  } catch {
    const message = isDesktop
      ? DESKTOP_API_HINT
      : import.meta.env.DEV
        ? "Can't reach ApplyXAI. In two terminals run .\\scripts\\dev_api.ps1 and .\\scripts\\dev_frontend.ps1 " +
            "(or .\\scripts\\dev_stack.ps1), then open http://127.0.0.1:5173 — not the built dist/ folder."
        : "Can't reach ApplyXAI. Check your connection.";
    throw new ApiError("NETWORK_ERROR", message, 0);
  }
  if (response.status === 401 && !NO_REFRESH.some((p) => path.startsWith(p))) {
    if (await refreshSession()) {
      response = await send(path, options);
    }
    if (response.status === 401) {
      let expire = true;
      try {
        const payload = (await response.clone().json()) as {
          error?: { code?: string };
        };
        const code = payload.error?.code;
        if (code && !SESSION_EXPIRED_CODES.has(code)) expire = false;
      } catch {
        /* keep expire=true for opaque 401 */
      }
      if (expire) sessionExpiredHandler?.();
    }
  }
  return response;
}

export async function requestFull<T>(path: string, options: RequestOptions = {}): Promise<{ status: number; data: T }> {
  const response = await requestResponse(path, options);
  const data = await parse<T>(response);
  return { status: response.status, data };
}

export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const response = await requestResponse(path, options);
  return parse<T>(response);
}

/** Field-level messages from a VALIDATION_ERROR, keyed by field name (last path segment). */
export function fieldErrors(error: unknown): Record<string, string> {
  if (!(error instanceof ApiError)) return {};
  const out: Record<string, string> = {};
  for (const d of error.details) {
    const key = d.field.split(".").pop() ?? d.field;
    out[key] ??= d.message;
  }
  return out;
}

export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error && error.message.trim()) {
    const ipc = error.message.match(/Error invoking remote method '[^']+': (?:Error: )?(.+)$/s);
    return (ipc?.[1] || error.message).trim();
  }
  return "Something went wrong. Please try again.";
}
