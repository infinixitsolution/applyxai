/**
 * Device token resolution — matches agent/config.py + agent/credentials.py (keyring).
 */
import fs from "fs";
import path from "path";
import keytar from "keytar";
import { agentConfigPath } from "./agent-process";

const KEYRING_SERVICE = "ApplyXAI";
const KEYRING_ACCOUNT = "agent_device_token";

export type ResolvedAgentConfig = { server: string; token: string };

export type AgentJson = {
  server?: string;
  token?: string;
  device_id?: string;
  user_id?: string;
  name?: string;
};

export function readAgentJson(): AgentJson | null {
  try {
    return JSON.parse(fs.readFileSync(agentConfigPath(), "utf8")) as AgentJson;
  } catch {
    return null;
  }
}

function writeAgentJson(data: AgentJson): void {
  const file = agentConfigPath();
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, JSON.stringify(data, null, 2), "utf8");
}

async function keyringGet(): Promise<string> {
  try {
    return ((await keytar.getPassword(KEYRING_SERVICE, KEYRING_ACCOUNT)) || "").trim();
  } catch {
    return "";
  }
}

async function keyringSet(token: string): Promise<boolean> {
  if (!token) return false;
  try {
    await keytar.setPassword(KEYRING_SERVICE, KEYRING_ACCOUNT, token);
    return true;
  } catch {
    return false;
  }
}

export async function clearStoredAgentToken(): Promise<void> {
  try {
    await keytar.deletePassword(KEYRING_SERVICE, KEYRING_ACCOUNT);
  } catch {
    /* missing keyring or empty slot */
  }
}

export async function persistAgentConfig(payload: {
  server: string;
  token: string;
  device_id: string;
  user_id: string;
  name: string;
}): Promise<void> {
  const stored = await keyringSet(payload.token);
  writeAgentJson({
    server: payload.server,
    token: stored ? "" : payload.token,
    device_id: payload.device_id,
    user_id: payload.user_id,
    name: payload.name,
  });
}

export async function forgetLocalAgentConfig(): Promise<void> {
  await clearStoredAgentToken();
  try {
    fs.unlinkSync(agentConfigPath());
  } catch {
    /* missing */
  }
}

export async function resolveAgentCredentials(): Promise<ResolvedAgentConfig> {
  const data = readAgentJson();
  if (!data?.server) {
    throw new Error("This computer is not linked. Open Automation and connect this PC.");
  }
  const fromFile = (data.token || "").trim();
  const fromKeyring = await keyringGet();
  const token = fromKeyring || fromFile;
  if (!token) {
    throw new Error("This computer is not linked. Open Automation and connect this PC.");
  }
  if (fromFile && (fromKeyring || (await keyringSet(fromFile)))) {
    writeAgentJson({ ...data, token: "" });
  }
  return { server: data.server.replace(/\/$/, ""), token };
}

export async function resolveAgentToken(): Promise<string> {
  return (await resolveAgentCredentials()).token;
}
