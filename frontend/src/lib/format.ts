import type { ApplicationStatus } from "../types";

const dateFmt = new Intl.DateTimeFormat(undefined, { day: "numeric", month: "short", year: "numeric" });
const dateTimeFmt = new Intl.DateTimeFormat(undefined, {
  day: "numeric", month: "short", year: "numeric", hour: "numeric", minute: "2-digit",
});
const relFmt = new Intl.RelativeTimeFormat(undefined, { numeric: "auto" });

export function formatDate(iso: string | null | undefined): string {
  return iso ? dateFmt.format(new Date(iso)) : "—";
}

export function formatDateTime(iso: string | null | undefined): string {
  return iso ? dateTimeFmt.format(new Date(iso)) : "—";
}

export function formatRelative(iso: string, now: Date = new Date()): string {
  const seconds = Math.round((new Date(iso).getTime() - now.getTime()) / 1000);
  const units: [Intl.RelativeTimeFormatUnit, number][] = [
    ["year", 31_536_000], ["month", 2_592_000], ["day", 86_400], ["hour", 3_600], ["minute", 60],
  ];
  for (const [unit, size] of units) {
    if (Math.abs(seconds) >= size) return relFmt.format(Math.round(seconds / size), unit);
  }
  return "just now";
}

export function formatMoney(cents: number, currency: string): string {
  return new Intl.NumberFormat(currency === "INR" ? "en-IN" : undefined, {
    style: "currency", currency, maximumFractionDigits: cents % 100 === 0 ? 0 : 2,
  }).format(cents / 100);
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/** Backend “unlimited” personal plan caps (see `backend/app/core/plans.py`). */
export const UNLIMITED_APPLICATIONS_CAP = 999_999;
export const UNLIMITED_RESUMES_CAP = 999_999;
export const UNLIMITED_MOCK_INTERVIEWS_CAP = 999_999;

export type UsageMeterKind = "applications" | "resumes" | "mock_interviews";

export function isUnlimitedUsageCap(limit: number, kind: UsageMeterKind): boolean {
  if (kind === "applications") return limit >= UNLIMITED_APPLICATIONS_CAP;
  if (kind === "resumes") return limit >= UNLIMITED_RESUMES_CAP;
  return limit >= UNLIMITED_MOCK_INTERVIEWS_CAP;
}

export function formatUsageCap(limit: number, kind: UsageMeterKind): string {
  return isUnlimitedUsageCap(limit, kind) ? "Unlimited" : limit.toLocaleString();
}

/** Progress fill %; unlimited plans use a visual scale so non-zero usage still shows a bar. */
export function usageMeterPercent(value: number, limit: number, kind: UsageMeterKind): number {
  if (isUnlimitedUsageCap(limit, kind)) {
    const visualMax = kind === "applications" ? 500 : kind === "mock_interviews" ? 30 : 20;
    if (value <= 0) return 0;
    return Math.max(6, Math.min(100, Math.round((value / visualMax) * 100)));
  }
  if (limit <= 0) return 0;
  const pct = Math.round((value / limit) * 100);
  if (value > 0 && pct === 0) return 6;
  return Math.min(100, pct);
}

/** Job URLs come from third-party pages: only ever render http(s) links. */
export function safeExternalUrl(url: string | null | undefined): string | null {
  if (!url) return null;
  try {
    const parsed = new URL(url);
    return parsed.protocol === "https:" || parsed.protocol === "http:" ? parsed.href : null;
  } catch {
    return null;
  }
}

export const STATUS_LABELS: Record<ApplicationStatus, string> = {
  discovered: "Discovered",
  queued: "Queued",
  running: "In progress",
  applied: "Applied",
  failed: "Failed",
  skipped: "Skipped",
  external: "External",
  cancelled: "Cancelled",
};

export const STATUS_TONES: Record<ApplicationStatus, "green" | "red" | "slate" | "amber" | "blue"> = {
  discovered: "slate",
  queued: "blue",
  running: "blue",
  applied: "green",
  failed: "red",
  skipped: "slate",
  external: "amber",
  cancelled: "slate",
};
