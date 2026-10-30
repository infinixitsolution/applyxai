import { useQuery } from "@tanstack/react-query";
import { Laptop, Loader2, Wifi, WifiOff } from "lucide-react";
import { Spinner } from "./ui";
import { desktopAgent, hasDesktopAgent } from "../lib/desktop";

type Props = {
  className?: string;
  serverLinked: boolean;
  linking?: boolean;
  linkError?: string | null;
};

/** Status for ApplyXAI Desktop — linking is automatic; no Connect button. */
export function DesktopAgentPanel({ className, serverLinked, linking, linkError }: Props) {
  const agent = desktopAgent();
  const status = useQuery({
    queryKey: ["desktop-agent-local"],
    queryFn: () => agent!.status(),
    enabled: hasDesktopAgent() && Boolean(agent),
    refetchInterval: 10_000,
  });

  if (!hasDesktopAgent() || !agent) return null;

  const workerRunning = status.data?.workerRunning ?? false;

  let message = "Starting ApplyXAI Desktop…";
  if (linking) {
    message = "Linking this computer to your account…";
  } else if (linkError) {
    message = linkError;
  } else if (serverLinked) {
    message = workerRunning
      ? "This computer is ready — you can start a run."
      : "Linked — starting the automation worker…";
  } else if (workerRunning) {
    message = "Linking this computer to your account…";
  } else {
    message = "Starting automation on this computer…";
  }

  return (
    <div className={className}>
      <div className="flex flex-wrap items-center gap-2 rounded-lg border border-brand-200 bg-brand-50/80 px-3 py-2 text-sm text-slate-700">
        {linking ? (
          <Loader2 className="h-4 w-4 shrink-0 animate-spin text-brand-600" aria-hidden />
        ) : workerRunning ? (
          <Wifi className="h-4 w-4 shrink-0 text-emerald-600" aria-hidden />
        ) : (
          <WifiOff className="h-4 w-4 shrink-0 text-slate-400" aria-hidden />
        )}
        <Laptop className="h-4 w-4 shrink-0 text-brand-600" aria-hidden />
        <span>{message}</span>
      </div>
      {status.isLoading && <Spinner label="Checking this computer\u2026" />}
    </div>
  );
}
