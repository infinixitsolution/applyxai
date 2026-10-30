import os from "os";
import { apiOriginForDesktop, desktopUiOrigin } from "./config";
import { PRODUCT_VERSION } from "./productVersion";
import { refreshAgentWorkerAfterConnect } from "./agent-process";
import {
  forgetLocalAgentConfig,
  persistAgentConfig,
  readAgentJson,
  resolveAgentCredentials,
  resolveAgentToken,
} from "./agentToken";

const POLL_MS = 2000;
const MAX_WAIT_MS = 15 * 60 * 1000;

type Envelope<T> = { success: boolean; data?: T; error?: { code: string; message: string } };

async function apiPost<T>(apiPath: string, body: unknown): Promise<T> {
  const apiOrigin = apiOriginForDesktop();
  const resp = await fetch(`${apiOrigin}/api${apiPath}`, {
    method: "POST",
    headers: { Accept: "application/json", "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const json = (await resp.json()) as Envelope<T>;
  if (!resp.ok || !json.success) {
    const msg = json.error?.message || `HTTP ${resp.status}`;
    throw new Error(msg);
  }
  return json.data as T;
}

function defaultDeviceName(): string {
  return (os.hostname() || "My computer").slice(0, 100);
}

function platformName(): string {
  return `${os.type()} ${os.release()}`.trim().slice(0, 50);
}

export async function beginConnectSession(): Promise<{ session_id: string; secret: string }> {
  return apiPost<{ session_id: string; secret: string }>("/agent/connect/start", {
    name: defaultDeviceName(),
    platform: platformName(),
    agent_version: PRODUCT_VERSION,
  });
}

export async function completeConnectSession(sessionId: string, secret: string): Promise<{ name: string }> {
  const deadline = Date.now() + MAX_WAIT_MS;
  while (Date.now() < deadline) {
    await new Promise((r) => setTimeout(r, POLL_MS));
    const poll = await apiPost<{
      status: string;
      token?: string;
      device_id?: string;
      user_id?: string;
      name?: string;
    }>("/agent/connect/poll", { session_id: sessionId, secret });
    if (poll.status === "ready" && poll.token && poll.device_id && poll.user_id) {
      await persistAgentConfig({
        server: apiOriginForDesktop(),
        token: poll.token,
        device_id: poll.device_id,
        user_id: poll.user_id,
        name: poll.name || defaultDeviceName(),
      });
      await refreshAgentWorkerAfterConnect();
      return { name: poll.name || defaultDeviceName() };
    }
  }
  throw new Error("Timed out waiting for this computer to link to your account.");
}

/** Legacy flow: navigate away so the Connect page can approve in-browser. */
export async function runDesktopConnect(navigate: (url: string) => void): Promise<{ name: string }> {
  const started = await beginConnectSession();
  const connectUrl = `${desktopUiOrigin()}/app/automation/connect?session=${started.session_id}`;
  navigate(connectUrl);
  return completeConnectSession(started.session_id, started.secret);
}

export async function validateLocalAgentToken(): Promise<boolean> {
  let creds: { server: string; token: string };
  try {
    creds = await resolveAgentCredentials();
  } catch {
    return false;
  }
  try {
    const resp = await fetch(`${creds.server}/api/agent/me`, {
      headers: { Authorization: `Bearer ${creds.token}`, Accept: "application/json" },
    });
    if (resp.ok) return true;
    if (resp.status === 401 || resp.status === 403) {
      await forgetLocalAgentConfig();
    }
  } catch {
    /* network — keep local config */
  }
  return false;
}

export async function disconnectDesktopAgent(): Promise<void> {
  try {
    const data = readAgentJson();
    const token = data ? await resolveAgentToken().catch(() => data.token || "") : "";
    if (token && data?.server) {
      await fetch(`${data.server}/api/agent/unpair`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}`, Accept: "application/json" },
      }).catch(() => undefined);
    }
  } catch {
    /* not connected */
  }
  await forgetLocalAgentConfig();
}
