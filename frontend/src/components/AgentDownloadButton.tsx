import { useQuery } from "@tanstack/react-query";
import { Download } from "lucide-react";
import { isDesktopHost } from "../lib/desktop";
import { automation } from "../services/endpoints";
import { cx } from "./ui";

/** Header control: download ApplyXAI Desktop for Windows. */
export function AgentDownloadButton() {
  if (isDesktopHost) return null;
  const href = automation.desktopAgentDownloadUrl();
  const useApi = href.includes("/automation/desktop-agent/download");
  const info = useQuery({
    queryKey: ["desktop-agent-info"],
    queryFn: automation.desktopAgentInfo,
    enabled: useApi,
    staleTime: 60_000,
  });
  const disabled = useApi && info.isSuccess && info.data && !info.data.available;

  if (disabled) return null;

  return (
    <a
      href={href}
      title="Download ApplyXAI Desktop for Windows"
      className={cx(
        "inline-flex items-center gap-1.5 rounded-lg px-2.5 py-2 text-sm font-medium text-slate-600",
        "hover:bg-slate-100 hover:text-slate-900",
      )}
    >
      <img src="/mascot.png" alt="" className="h-6 w-6 shrink-0 rounded-md object-cover ring-1 ring-slate-200/80" width={24} height={24} />
      <Download className="h-4 w-4 shrink-0 opacity-70" aria-hidden />
      <span className="hidden sm:inline">Desktop app</span>
    </a>
  );
}
