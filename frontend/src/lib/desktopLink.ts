import type { User } from "../types";
import { homeFor, safeNext } from "../auth/session";

function isDesktopRuntime(): boolean {
  return typeof window !== "undefined" && window.applyxaiDesktop?.isDesktop === true;
}

/** Default landing path after sign-in in ApplyXAI Desktop (candidate workspace). */
export function postLoginPath(user: User, next: string | null): string {
  const fallback = homeFor(user);
  if (!isDesktopRuntime()) return safeNext(next, fallback);
  if (user.is_admin || user.workspace === "institute" || user.workspace === "partner") {
    return safeNext(next, fallback);
  }
  const resolved = safeNext(next, fallback);
  if (resolved !== "/app" && resolved !== "/app/") return resolved;
  return "/app/automation";
}
