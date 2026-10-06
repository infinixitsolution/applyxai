/**
 * The only place the app talks to the backend.
 *
 * - Cookies carry the session (HttpOnly; JavaScript never sees the tokens).
 * - Every mutating request sends X-CSRF-Token, copied from the readable applyxai_csrf cookie.
 * - Responses use the {success, data | error} envelope; errors become ApiError.
 * - A 401 triggers one shared POST /auth/refresh, then the request is retried once.
 */

export const API_BASE = "/api";
const CSRF_COOKIE = "applyxai_csrf";
const CSRF_HEADER = "X-CSRF-Token";
const SAFE_METHODS = new Set(["GET", "HEAD", "OPTIONS"]);
// Endpoints where a 401 means "wrong credentials / no session", not "access token expired".
const NO_REFRESH = ["/auth/login", "/auth/refresh", "/auth/register", "/auth/logout"];

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
  return fetch(buildUrl(path, options.query), { method, headers, body, credentials: "same-origin" });
}

async function parse<T>(response: Response): Promise<T> {
  let payload: { success?: boolean; data?: T; error?: { code: string; message: string; details?: unknown } };
  try {
    payload = await response.json();
  } catch {
    throw new ApiError(
      response.status >= 500 || response.status === 0 ? "SERVER_UNAVAILABLE" : "BAD_RESPONSE",
      "The server isn't responding. Please try again in a moment.",
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

export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  let response: Response;
  try {
    response = await send(path, options);
  } catch {
    throw new ApiError("NETWORK_ERROR", "Can't reach ApplyXAI. Check your connection.", 0);
  }
  if (response.status === 401 && !NO_REFRESH.some((p) => path.startsWith(p))) {
    if (await refreshSession()) {
      response = await send(path, options);
    }
    if (response.status === 401) {
      sessionExpiredHandler?.();
    }
  }
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
  return "Something went wrong. Please try again.";
}
