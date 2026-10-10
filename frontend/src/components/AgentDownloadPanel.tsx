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
  const href = automation.desktopAgentDownloadUrl();
  const useApi = href.includes("/automation/desktop-agent/download");

  if (useApi && info.isLoading) return <Spinner label="Checking agent download\u2026" />;

  if (useApi && info.isSuccess && info.data && !info.data.available) {
    return (
      <p className="text-sm text-slate-600">
        The desktop agent download is not on this server yet. Please contact support.
      </p>
    );
  }

  const filename = info.data?.filename ?? "ApplyXAI-Agent.exe";
  const size = info.data?.size_bytes ? formatBytes(info.data.size_bytes) : null;

  return (
    <div className={className}>
      <a
        href={href}
        download={useApi ? undefined : filename}
        className={buttonClass("primary", "sm")}
      >
        <Download className="h-4 w-4" aria-hidden />
        Download {filename.replace(".exe", "")}
        {size ? ` (${size})` : ""}
      </a>
      <p className="mt-2 text-xs text-slate-500">
        Windows 10 or later. Run the app, then use Connect — Live to link this account.
      </p>
    </div>
  );
}
