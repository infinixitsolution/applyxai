/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_CONTACT_EMAIL?: string;
  readonly VITE_AGENT_SERVER_URL?: string;
  /** Optional direct URL for the desktop agent (CDN); otherwise uses /api/automation/desktop-agent/download */
  readonly VITE_AGENT_DOWNLOAD_URL?: string;
}
