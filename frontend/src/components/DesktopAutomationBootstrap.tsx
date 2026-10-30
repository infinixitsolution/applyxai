import { useQuery } from "@tanstack/react-query";
import { useSession } from "../auth/session";
import { useDesktopAutoLink } from "../hooks/useDesktopAutoLink";
import { hasDesktopAgent, isDesktopHost } from "../lib/desktop";
import { automation } from "../services/endpoints";

/** After sign-in, link this PC to the account (no Connect button or installer steps). */
export function DesktopAutomationBootstrap() {
  const { data: user } = useSession();
  const { data: overview } = useQuery({
    queryKey: ["automation"],
    queryFn: automation.overview,
    enabled: Boolean(user && isDesktopHost && hasDesktopAgent()),
    staleTime: 15_000,
  });

  useDesktopAutoLink({
    serverHasDevice: (overview?.devices.length ?? 0) > 0,
    enabled: Boolean(user && isDesktopHost && hasDesktopAgent()),
  });

  return null;
}
