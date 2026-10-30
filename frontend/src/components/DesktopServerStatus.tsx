import { useEffect, useState } from "react";
import { desktopApiBackendLabel, isDesktop } from "../lib/desktop";

type HealthPayload = {
  status?: string;
  version?: string;
  env?: string;
};

/** Shows which ApplyXAI API the desktop login shell is using (packaged app vs local dev). */
export function DesktopServerStatus({ className = "" }: { className?: string }) {
  const configured = desktopApiBackendLabel();
  const [live, setLive] = useState<HealthPayload | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    if (!isDesktop) return;
    let cancelled = false;
    (async () => {
      try {
        const resp = await fetch("/api/health", { credentials: "same-origin" });
        const body = (await resp.json()) as { success?: boolean; data?: HealthPayload };
        if (cancelled) return;
        if (resp.ok && body.success && body.data) {
          setLive(body.data);
          setError(false);
        } else {
          setLive(null);
          setError(true);
        }
      } catch {
        if (!cancelled) {
          setLive(null);
          setError(true);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [configured]);

  if (!isDesktop || !configured) return null;

  const isLocal = /^(https?:\/\/)?(127\.0\.0\.1|localhost)(:\d+)?$/i.test(configured);
  const tone = error ? "text-amber-800 bg-amber-50 ring-amber-200/80" : isLocal ? "text-emerald-900 bg-emerald-50 ring-emerald-200/80" : "text-slate-700 bg-slate-100 ring-slate-200/80";

  return (
    <div
      className={`rounded-lg px-3 py-2 text-xs ring-1 ${tone} ${className}`.trim()}
      role="status"
      aria-live="polite"
    >
      <div className="font-medium text-slate-900">API server</div>
      <div className="mt-0.5 break-all font-mono text-[11px]">{configured}</div>
      {error ? (
        <div className="mt-1 text-amber-900">Not reachable — start the API or check APPLYXAI_API_URL.</div>
      ) : live ? (
        <div className="mt-1 text-slate-600">
          Connected · {live.env ?? "unknown"} · v{live.version ?? "?"}
        </div>
      ) : (
        <div className="mt-1 text-slate-500">Checking connection…</div>
      )}
      {!isLocal && (
        <div className="mt-1 text-slate-600">
          Production API — local-only admin settings (mock unlimited allowlist) apply on that server, not your PC.
        </div>
      )}
    </div>
  );
}
