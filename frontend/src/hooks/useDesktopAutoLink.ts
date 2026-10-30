import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { errorMessage } from "../services/api";
import { reconcileDesktopLink } from "../lib/desktopConnect";
import { hasDesktopAgent, isDesktopHost } from "../lib/desktop";
import { automation } from "../services/endpoints";

const RETRY_MS = 8000;
const MAX_ATTEMPTS = 12;

type Options = {
  serverHasDevice: boolean;
  enabled: boolean;
};

/** Keeps Desktop linked to the signed-in account; no manual Connect step. */
export function useDesktopAutoLink({ serverHasDevice, enabled }: Options): { linking: boolean; linkError: string | null } {
  const client = useQueryClient();
  const attempts = useRef(0);
  const running = useRef(false);
  const [linking, setLinking] = useState(false);
  const [linkError, setLinkError] = useState<string | null>(null);

  useEffect(() => {
    if (!isDesktopHost || !hasDesktopAgent() || !enabled) return;

    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;

    const tick = async () => {
      if (cancelled || running.current) return;
      if (serverHasDevice) {
        setLinking(false);
        setLinkError(null);
        return;
      }
      if (attempts.current >= MAX_ATTEMPTS) {
        setLinking(false);
        setLinkError("Could not link this computer automatically. Sign out and sign in again, or restart ApplyXAI Desktop.");
        return;
      }

      running.current = true;
      setLinking(true);
      setLinkError(null);
      attempts.current += 1;

      try {
        const result = await reconcileDesktopLink(false);
        if (result) {
          await client.invalidateQueries({ queryKey: ["automation"] });
          await client.invalidateQueries({ queryKey: ["desktop-agent-local"] });
        }
        const overview = await client.fetchQuery({ queryKey: ["automation"], queryFn: automation.overview });
        if (overview.devices.length > 0) {
          setLinking(false);
          setLinkError(null);
          return;
        }
      } catch (error) {
        setLinkError(errorMessage(error));
      } finally {
        running.current = false;
      }

      if (!cancelled) {
        timer = setTimeout(() => void tick(), RETRY_MS);
      }
    };

    void tick();

    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [serverHasDevice, enabled, client]);

  return { linking, linkError };
}
