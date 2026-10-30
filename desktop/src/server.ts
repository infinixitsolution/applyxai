import express, { type Request, type Response } from "express";
import fs from "fs";
import type { Server } from "http";
import { createProxyMiddleware } from "http-proxy-middleware";
import path from "path";
import { DESKTOP_UI_PORT } from "./config";

function rewriteSetCookieHeader(value: string | string[] | undefined): string[] | undefined {
  if (!value) return undefined;
  const stripDomain = (line: string) =>
    line
      .split(";")
      .map((part) => part.trim())
      .filter((part) => part && !/^domain=/i.test(part))
      .join("; ");
  if (Array.isArray(value)) return value.map(stripDomain);
  return [stripDomain(value)];
}

function apiUnavailable(res: Response): void {
  res.status(502).json({
    success: false,
    error: {
      code: "SERVER_UNAVAILABLE",
      message:
        "Can't reach the ApplyXAI API on port 8010. Close and reopen the app to auto-start it, " +
        "or run .\\scripts\\dev_api.ps1 from the applyxainew project folder.",
    },
  });
}

export function resolveStaticRoot(): string {
  if (process.env.APPLYXAI_DESKTOP_DIST) {
    return process.env.APPLYXAI_DESKTOP_DIST;
  }
  const packaged = path.join(process.resourcesPath, "app", "dist");
  if (fs.existsSync(path.join(packaged, "index.html"))) {
    return packaged;
  }
  return path.join(__dirname, "..", "..", "frontend", "dist");
}

export function startLocalServer(apiBackendOrigin: string): Promise<Server> {
  const staticRoot = resolveStaticRoot();
  if (!fs.existsSync(path.join(staticRoot, "index.html"))) {
    throw new Error(`Desktop UI build not found at ${staticRoot}. Run frontend build first.`);
  }

  const target = apiBackendOrigin.replace(/\/$/, "");
  const secure = target.startsWith("https://");
  console.log("Desktop API proxy: /api -> %s", target);

  const app = express();
  const onProxyError = (_err: unknown, _req: unknown, res: unknown) => {
    if (res && typeof res === "object" && "writeHead" in res && typeof (res as Response).json === "function") {
      apiUnavailable(res as Response);
    }
  };
  for (const publicPath of ["/robots.txt", "/sitemap.xml"]) {
    app.use(
      publicPath,
      createProxyMiddleware({
        target,
        changeOrigin: true,
        secure,
        on: { error: onProxyError },
      }),
    );
  }
  // Mounted at /api — Express passes paths without the mount prefix (e.g. /auth/login).
  // FastAPI routes live under /api/*, so prepend /api on the upstream URL.
  app.use(
    "/api",
    createProxyMiddleware({
      target,
      changeOrigin: true,
      secure,
      cookieDomainRewrite: "",
      pathRewrite: (path) => `/api${path.startsWith("/") ? path : `/${path}`}`,
      on: {
        proxyRes(proxyRes: { headers: { [key: string]: string | string[] | undefined } }) {
          const cookies = proxyRes.headers["set-cookie"];
          proxyRes.headers["set-cookie"] = rewriteSetCookieHeader(cookies);
        },
        error: onProxyError,
      },
    }),
  );

  app.use(express.static(staticRoot, { index: false }));
  app.get("*", (_req: Request, res: Response) => {
    res.sendFile(path.join(staticRoot, "index.html"));
  });

  return new Promise((resolve, reject) => {
    const server = app.listen(DESKTOP_UI_PORT, "127.0.0.1", () => resolve(server));
    server.on("error", reject);
  });
}
