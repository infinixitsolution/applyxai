export const APP_NAME = "ApplyXAI";
export const CONTACT_EMAIL: string = import.meta.env.VITE_CONTACT_EMAIL || "support@applyxai.example";
/** The address the desktop agent connects to; the site itself unless the API lives elsewhere. */
export function agentServerUrl(): string {
  return import.meta.env.VITE_AGENT_SERVER_URL || window.location.origin;
}
