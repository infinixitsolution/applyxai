/** Backend links are in-app paths; candidate UI lives under /app. */
const LEGACY_APP_PATHS = [
  "/automation",
  "/billing",
  "/applications",
  "/jobs",
  "/preferences",
  "/settings",
  "/resumes",
  "/profile",
  "/dashboard",
] as const;

function isLegacyAppPath(link: string): boolean {
  const path = link.split("?")[0];
  return LEGACY_APP_PATHS.some((p) => path === p || path.startsWith(`${p}/`));
}

/**
 * Resolve a notification `link` from the API to a client route.
 */
export function notificationLink(link: string): string {
  if (!link || !link.startsWith("/") || link.startsWith("//")) {
    return "/app/notifications";
  }
  if (link.startsWith("/app")) {
    return link;
  }
  if (link.startsWith("/invite/") || link === "/onboarding") {
    return link;
  }
  if (isLegacyAppPath(link)) {
    return `/app${link}`;
  }
  return `/app${link}`;
}
