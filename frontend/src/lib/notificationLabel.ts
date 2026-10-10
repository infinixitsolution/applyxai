/** Fallback when platform preference labels are not loaded. */
export function formatNotificationType(type: string): string {
  return type.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}
