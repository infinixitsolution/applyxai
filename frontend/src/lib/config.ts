export const APP_NAME = "ApplyXAI";
export const CONTACT_EMAIL: string = import.meta.env.VITE_CONTACT_EMAIL || "support@applyxai.com";
export const CHROME_EXTENSION_URL =
  "https://chromewebstore.google.com/detail/apply-x-ai/agnpjnbmfjghkndegbbocadckpjjgeea";

/** Public marketing site (desktop app links here instead of in-app landing). */
export function publicWebsiteUrl(): string {
  return import.meta.env.VITE_PUBLIC_WEBSITE_URL || "https://applyxai.com";
}

/** The address the desktop agent connects to; the site itself unless the API lives elsewhere. */
export function agentServerUrl(): string {
  return import.meta.env.VITE_AGENT_SERVER_URL || window.location.origin;
}
