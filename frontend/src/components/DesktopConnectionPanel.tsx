import { useEffect, useState } from "react";
import { Button } from "./ui";
import { desktopApiBackendLabel, isDesktop } from "../lib/desktop";

type HealthPayload = {
  status?: string;
  version?: string;
  env?: string;
};

/** API server picker + health for ApplyXAI Desktop (login shell). */
export function DesktopConnectionPanel({ className = "" }: { className?: string }) {
  const configured = desktopApiBackendLabel();
  const presets = window.applyxaiDesktop?.apiPresets;
  const connection = window.applyxaiDesktop?.connection;

  const [draft, setDraft] = useState(configured ?? "");
  const [live, setLive] = useState<HealthPayload | null>(null);
  const [error, setError] = useState(false);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    setDraft(configured ?? "");
  }, [configured]);

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

  if (!isDesktop || !configured || !connection) return null;

  const applyPreset = (url: string) => {
    setDraft(url);
    setMessage(null);
  };

  const save = async () => {
    setSaving(true);
    setMessage(null);
    try {
      const result = await connection.setApiBackend(draft.trim());
      if (!result.ok) {
        setMessage(result.message);
        return;
      }
      setMessage("Saved. Restarting ApplyXAI to connect to the new server…");
      await connection.restart();
    } finally {
      setSaving(false);
    }
  };

  const isLocal = /^(https?:\/\/)?(127\.0\.0\.1|localhost)(:\d+)?$/i.test(draft);
  const tone = error
    ? "text-amber-900 bg-amber-50 ring-amber-200/80"
    : isLocal
      ? "text-emerald-900 bg-emerald-50 ring-emerald-200/80"
      : "text-slate-800 bg-slate-100 ring-slate-200/80";

  return (
    <div className={`rounded-lg px-3 py-3 text-xs ring-1 ${tone} ${className}`.trim()} role="region" aria-label="API server">
      <div className="font-semibold text-slate-900">ApplyXAI server</div>
      <p className="mt-1 text-slate-600">Choose which backend this app talks to. Restart applies the change.</p>

      <div className="mt-2 flex flex-wrap gap-2">
        <button
          type="button"
          className={`rounded-md px-2 py-1 font-medium ring-1 ${
            draft === presets?.local ? "bg-white ring-brand-400 text-brand-800" : "bg-white/60 ring-slate-300"
          }`}
          onClick={() => applyPreset(presets?.local ?? "http://127.0.0.1:8010")}
        >
          Local dev
        </button>
        <button
          type="button"
          className={`rounded-md px-2 py-1 font-medium ring-1 ${
            draft === presets?.production ? "bg-white ring-brand-400 text-brand-800" : "bg-white/60 ring-slate-300"
          }`}
          onClick={() => applyPreset(presets?.production ?? "https://applyxai.com")}
        >
          Production
        </button>
      </div>

      <label className="mt-2 block">
        <span className="sr-only">API base URL</span>
        <input
          type="url"
          className="mt-1 w-full rounded-md border border-slate-300 bg-white px-2 py-1.5 font-mono text-[11px] text-slate-900"
          value={draft}
          onChange={(e) => {
            setDraft(e.target.value);
            setMessage(null);
          }}
          placeholder="http://127.0.0.1:8010"
        />
      </label>

      {error ? (
        <p className="mt-2 text-amber-900">Not connected — start the API or pick another URL, then Save &amp; restart.</p>
      ) : live ? (
        <p className="mt-2 text-slate-600">
          Connected · {live.env ?? "unknown"} · v{live.version ?? "?"}
        </p>
      ) : (
        <p className="mt-2 text-slate-500">Checking connection…</p>
      )}

      {message && <p className="mt-2 text-slate-800">{message}</p>}

      <Button type="button" variant="secondary" className="mt-3 w-full text-xs" loading={saving} onClick={() => void save()}>
        Save server &amp; restart
      </Button>
    </div>
  );
}
