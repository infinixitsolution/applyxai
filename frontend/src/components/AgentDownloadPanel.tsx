import { useQuery } from "@tanstack/react-query";
import { Download } from "lucide-react";
import { automation } from "../services/endpoints";
import { buttonClass, Spinner } from "./ui";

function formatBytes(n: number): string {
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(0)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}

/** Logged-in download for the Windows desktop agent (uses session cookies; no forced filename). */
export function AgentDownloadPanel({ className }: { className?: string }) {
  const info = useQuery({
    queryKey: ["desktop-agent-info"],
    queryFn: automation.desktopAgentInfo,
    staleTime: 60_000,
  });
  const useApi = !import.meta.env.VITE_AGENT_DOWNLOAD_URL;

  if (useApi && info.isLoading) return <Spinner label="Checking agent download\u2026" />;

  if (useApi && info.isSuccess && info.data && !info.data.available) {
    return (
      <p className="text-sm text-slate-600">
        The desktop agent download is not on this server yet. Please contact support.
      </p>
    );
  }

  const exeName = info.data?.filename ?? "ApplyXAI-Agent.exe";
  const exeSize = info.data?.size_bytes ? formatBytes(info.data.size_bytes) : null;
  const zip = info.data?.zip;
  const zipHref = automation.desktopAgentDownloadUrl("zip");
  const exeHref = automation.desktopAgentDownloadUrl("exe");

  return (
    <div className={className}>
      <div className="flex flex-wrap items-center gap-2">
        {zip ? (
          <a href={zipHref} className={buttonClass("primary", "sm")}>
            <Download className="h-4 w-4" aria-hidden />
            Download ZIP ({formatBytes(zip.size_bytes)})
          </a>
        ) : null}
        <a
          href={exeHref}
          className={buttonClass(zip ? "secondary" : "primary", "sm")}
        >
          <Download className="h-4 w-4" aria-hidden />
          {zip ? "Direct .exe" : `Download ${exeName.replace(".exe", "")}`}
          {!zip && exeSize ? ` (${exeSize})` : ""}
        </a>
      </div>
      <p className="mt-2 text-xs text-slate-500">
        Windows 10 or later. Extract the ZIP if needed, run the installer, then use Connect — Live in the app.
      </p>
      <details className="mt-2 text-xs text-slate-600">
        <summary className="cursor-pointer font-medium text-slate-700">Chrome blocked the download?</summary>
        <ul className="mt-2 list-disc space-y-1 pl-4">
          <li>
            Prefer the <strong>ZIP</strong> link — Chrome usually allows it; extract, then run{" "}
            <code className="rounded bg-slate-100 px-1">ApplyXAI-Agent-Setup.exe</code>.
          </li>
          <li>
            For a blocked .exe: open Chrome&apos;s download bar → ⋮ on the file → <strong>Keep</strong> or{" "}
            <strong>Download unverified file</strong>.
          </li>
          <li>
            Windows SmartScreen may ask for confirmation — normal for a new, unsigned installer until we ship code
            signing.
          </li>
        </ul>
      </details>
    </div>
  );
}
