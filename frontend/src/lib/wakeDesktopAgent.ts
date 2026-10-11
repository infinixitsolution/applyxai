/** Nudge the local ApplyXAI Agent GUI to start (Windows desktop app listens on 127.0.0.1:39217). */
const WAKE_URL = "http://127.0.0.1:39217/wake";

export function wakeDesktopAgent(): void {
  if (typeof window === "undefined") return;
  try {
    void fetch(WAKE_URL, { mode: "no-cors", keepalive: true });
  } catch {
    // Agent not installed or GUI closed — run still queues on the server.
  }
}
