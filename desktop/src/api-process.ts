import { spawn, type ChildProcess } from "child_process";
import { app } from "electron";
import fs from "fs";
import path from "path";
import { apiBackendOrigin } from "./config";

let apiProc: ChildProcess | null = null;
let weStartedApi = false;

function apiPort(): string {
  try {
    return new URL(apiBackendOrigin()).port || "8010";
  } catch {
    return "8010";
  }
}

export function isLocalApiBackend(): boolean {
  try {
    const host = new URL(apiBackendOrigin()).hostname.toLowerCase();
    return host === "127.0.0.1" || host === "localhost";
  } catch {
    return false;
  }
}

export async function checkApiHealth(): Promise<boolean> {
  try {
    const resp = await fetch(`${apiBackendOrigin()}/api/health`, {
      signal: AbortSignal.timeout(4000),
    });
    if (!resp.ok) return false;
    const body = (await resp.json()) as { success?: boolean };
    return body.success === true;
  } catch {
    return false;
  }
}

function projectRootFile(): string {
  return path.join(app.getPath("userData"), "project-root.txt");
}

function readPersistedProjectRoot(): string | null {
  try {
    const fromFile = fs.readFileSync(projectRootFile(), "utf8").trim();
    if (fromFile && fs.existsSync(path.join(fromFile, "backend", "app", "main.py"))) {
      return path.resolve(fromFile);
    }
  } catch {
    /* no saved root yet */
  }
  return null;
}

function persistProjectRoot(root: string): void {
  try {
    fs.mkdirSync(app.getPath("userData"), { recursive: true });
    fs.writeFileSync(projectRootFile(), path.resolve(root), "utf8");
  } catch {
    /* best-effort */
  }
}

/** Locate repo root (backend/app/main.py) for auto-starting uvicorn. */
export function resolveProjectRoot(): string | null {
  const fromEnv = process.env.APPLYXAI_PROJECT_ROOT?.trim();
  if (fromEnv && fs.existsSync(path.join(fromEnv, "backend", "app", "main.py"))) {
    return path.resolve(fromEnv);
  }

  const persisted = readPersistedProjectRoot();
  if (persisted) return persisted;

  const candidates = [
    path.join(__dirname, "..", ".."),
    path.join(__dirname, "..", "..", ".."),
    path.join(process.cwd()),
    "c:\\xampp\\htdocs\\applyxainew",
  ];
  for (const dir of candidates) {
    const root = path.resolve(dir);
    if (fs.existsSync(path.join(root, "backend", "app", "main.py"))) {
      return root;
    }
  }
  return null;
}

export async function ensureLocalApiRunning(): Promise<{ ok: boolean; detail?: string }> {
  if (!isLocalApiBackend()) {
    return { ok: true };
  }
  if (await checkApiHealth()) {
    return { ok: true };
  }

  const root = resolveProjectRoot();
  if (!root) {
    return {
      ok: false,
      detail:
        "From the project folder run: venv\\Scripts\\python -m uvicorn backend.app.main:app --reload --port 8010\n" +
        "Or set APPLYXAI_PROJECT_ROOT to your applyxainew folder, or use dist\\ApplyXAI-Launch.bat.",
    };
  }

  const python = path.join(root, "venv", "Scripts", "python.exe");
  if (!fs.existsSync(python)) {
    return {
      ok: false,
      detail: `Python venv not found at ${python}. Create venv and pip install -r requirements.txt.`,
    };
  }

  const port = apiPort();
  console.log("Starting ApplyXAI API from %s on port %s...", root, port);
  apiProc = spawn(
    python,
    ["-m", "uvicorn", "backend.app.main:app", "--host", "127.0.0.1", "--port", port],
    {
      cwd: root,
      windowsHide: true,
      stdio: ["ignore", "pipe", "pipe"],
      env: { ...process.env },
    },
  );
  weStartedApi = true;
  apiProc.stdout?.on("data", (chunk) => process.stdout.write(`[applyxai-api] ${chunk}`));
  apiProc.stderr?.on("data", (chunk) => process.stderr.write(`[applyxai-api] ${chunk}`));
  apiProc.on("exit", (code) => {
    console.log("ApplyXAI API exited (%s)", code);
    if (apiProc) apiProc = null;
    weStartedApi = false;
  });

  for (let attempt = 0; attempt < 60; attempt++) {
    await new Promise((r) => setTimeout(r, 1000));
    if (await checkApiHealth()) {
      console.log("ApplyXAI API is ready at %s", apiBackendOrigin());
      persistProjectRoot(root);
      return { ok: true };
    }
  }

  return {
    ok: false,
    detail: `API did not respond on ${apiBackendOrigin()} within 60s. Check port ${port} and run .\\scripts\\dev_api.ps1 manually.`,
  };
}

export function stopLocalApiIfStarted(): void {
  if (!weStartedApi || !apiProc) return;
  apiProc.kill();
  apiProc = null;
  weStartedApi = false;
}
