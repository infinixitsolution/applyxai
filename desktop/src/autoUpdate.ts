import { spawn } from "child_process";
import { app, dialog } from "electron";
import fs from "fs";
import https from "https";
import http from "http";
import path from "path";
import { getApiBackendOrigin } from "./apiBackendStore";

function parseVersion(raw: string): number[] {
  return raw.replace(/^v/i, "").split(/[.+-]/).map((p) => parseInt(p, 10) || 0);
}

function isNewer(remote: string, local: string): boolean {
  const a = parseVersion(remote);
  const b = parseVersion(local);
  const n = Math.max(a.length, b.length);
  for (let i = 0; i < n; i += 1) {
    const av = a[i] ?? 0;
    const bv = b[i] ?? 0;
    if (av > bv) return true;
    if (av < bv) return false;
  }
  return false;
}

function fetchJson(url: string): Promise<Record<string, unknown>> {
  return new Promise((resolve, reject) => {
    const lib = url.startsWith("https:") ? https : http;
    lib
      .get(url, (res) => {
        const chunks: Buffer[] = [];
        res.on("data", (c) => chunks.push(c as Buffer));
        res.on("end", () => {
          try {
            resolve(JSON.parse(Buffer.concat(chunks).toString("utf8")) as Record<string, unknown>);
          } catch (err) {
            reject(err);
          }
        });
      })
      .on("error", reject);
  });
}

function downloadFile(url: string, dest: string): Promise<void> {
  return new Promise((resolve, reject) => {
    const lib = url.startsWith("https:") ? https : http;
    const request = lib.get(url, (res) => {
      const status = res.statusCode || 0;
      const location = res.headers.location;
      if (status >= 300 && status < 400 && location) {
        res.resume();
        downloadFile(new URL(location, url).toString(), dest).then(resolve).catch(reject);
        return;
      }
      if (status !== 200) {
        res.resume();
        reject(new Error(`HTTP ${status}`));
        return;
      }
      const file = fs.createWriteStream(dest);
      res.pipe(file);
      file.on("finish", () => file.close(() => resolve()));
      file.on("error", (err) => {
        try {
          fs.unlinkSync(dest);
        } catch {
          /* ignore */
        }
        reject(err);
      });
    });
    request.on("error", reject);
  });
}

function launchInstaller(installerPath: string): void {
  spawn(installerPath, [], { detached: true, stdio: "ignore" }).unref();
}

export async function checkDesktopUpdate(): Promise<void> {
  if (!app.isPackaged) return;
  const origin = getApiBackendOrigin().replace(/\/$/, "");
  let body: Record<string, unknown>;
  try {
    body = await fetchJson(`${origin}/api/site/agent-release`);
  } catch {
    return;
  }
  const data = (body.data as Record<string, unknown> | undefined) ?? body;
  const version = String(data.version || "");
  const downloadUrl = String(data.download_url || "");
  if (!version || !isNewer(version, app.getVersion())) return;
  const choice = await dialog.showMessageBox({
    type: "info",
    title: "ApplyXAI update",
    message: `Version ${version} is available (you have ${app.getVersion()}).`,
    detail: "Download and install now? The app will quit so the installer can replace it. Unsigned builds may be blocked by SmartScreen.",
    buttons: ["Download and install", "Later"],
    defaultId: 0,
    cancelId: 1,
  });
  if (choice.response !== 0) return;
  const url = downloadUrl.startsWith("http") ? downloadUrl : `${origin}${downloadUrl.startsWith("/") ? "" : "/"}${downloadUrl}`;
  const dest = path.join(app.getPath("temp"), `ApplyXAI-Desktop-Setup-v${version}.exe`);
  try {
    await downloadFile(url, dest);
  } catch (err) {
    await dialog.showMessageBox({
      type: "error",
      title: "ApplyXAI update",
      message: "Could not download the installer.",
      detail: err instanceof Error ? err.message : String(err),
    });
    return;
  }
  launchInstaller(dest);
  app.quit();
}
