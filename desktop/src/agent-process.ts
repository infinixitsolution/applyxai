import { spawn, type ChildProcess } from "child_process";
import fs from "fs";
import path from "path";
import { AGENT_WAKE_PORT } from "./config";

let worker: ChildProcess | null = null;
let shuttingDown = false;

export function workerExecutablePath(): string {
  const packaged = path.join(process.resourcesPath, "agent-worker.exe");
  if (fs.existsSync(packaged)) return packaged;
  const dev = path.join(__dirname, "..", "..", "dist", "agent-worker.exe");
  if (fs.existsSync(dev)) return dev;
  return packaged;
}

export async function wakeAgentWorker(): Promise<boolean> {
  try {
    const resp = await fetch(`http://127.0.0.1:${AGENT_WAKE_PORT}/wake`, {
      signal: AbortSignal.timeout(3000),
    });
    return resp.status === 204;
  } catch {
    return false;
  }
}

function spawnAgentWorker(): boolean {
  const exe = workerExecutablePath();
  if (!fs.existsSync(exe)) {
    console.warn(`Agent worker not found at ${exe}`);
    return false;
  }
  const proc = spawn(exe, [], {
    stdio: ["ignore", "pipe", "pipe"],
    windowsHide: true,
    env: { ...process.env },
  });
  worker = proc;
  proc.stdout?.on("data", (chunk) => process.stdout.write(`[agent-worker] ${chunk}`));
  proc.stderr?.on("data", (chunk) => process.stderr.write(`[agent-worker] ${chunk}`));
  proc.on("exit", (code) => {
    console.log(`Agent worker exited (${code})`);
    worker = null;
    if (!shuttingDown) {
      setTimeout(() => {
        void ensureAgentWorker();
      }, 3000);
    }
  });
  return true;
}

/** One worker process on this PC — wake an existing listener or spawn a new one. */
export async function ensureAgentWorker(): Promise<boolean> {
  if (worker && !worker.killed) return true;
  if (await wakeAgentWorker()) {
    console.log("ApplyXAI worker already listening on port %s.", AGENT_WAKE_PORT);
    return true;
  }
  return spawnAgentWorker();
}

/** @deprecated Use ensureAgentWorker() */
export function startAgentWorker(): boolean {
  void ensureAgentWorker();
  return true;
}

export async function stopAgentWorkerAsync(): Promise<void> {
  if (!worker) return;
  const proc = worker;
  worker = null;
  await new Promise<void>((resolve) => {
    let settled = false;
    const finish = () => {
      if (settled) return;
      settled = true;
      resolve();
    };
    proc.once("exit", finish);
    proc.kill();
    setTimeout(finish, 8000);
  });
}

export function stopAgentWorker(): void {
  void stopAgentWorkerAsync();
}

export function markAgentWorkerShuttingDown(): void {
  shuttingDown = true;
}

/** Reload pairing without spawning a second worker when one is already listening. */
export async function refreshAgentWorkerAfterConnect(): Promise<void> {
  await wakeAgentWorker();
  if (worker && !worker.killed) return;
  if (await wakeAgentWorker()) return;
  await stopAgentWorkerAsync();
  spawnAgentWorker();
}

export function restartAgentWorker(): void {
  void (async () => {
    await stopAgentWorkerAsync();
    await ensureAgentWorker();
  })();
}

export async function isAgentWorkerRunning(): Promise<boolean> {
  if (worker && !worker.killed) return true;
  return wakeAgentWorker();
}

export function agentConfigPath(): string {
  const local = process.env.LOCALAPPDATA;
  if (local) return path.join(local, "ApplyXAI", "agent", "agent.json");
  return path.join(process.env.USERPROFILE || "", "AppData", "Local", "ApplyXAI", "agent", "agent.json");
}

export function readAgentConnected(): boolean {
  try {
    const raw = fs.readFileSync(agentConfigPath(), "utf8");
    const data = JSON.parse(raw) as { server?: string; device_id?: string; token?: string };
    return Boolean(data.server && data.device_id);
  } catch {
    return false;
  }
}
