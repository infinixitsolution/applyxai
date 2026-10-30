import { useQuery, useQueryClient, type UseQueryResult } from "@tanstack/react-query";
import { useEffect } from "react";
import { isDesktop } from "../lib/desktop";
import { automation } from "../services/endpoints";
import type { AutomationOverview, AutomationRun, DashboardStats } from "../types";

export const AUTOMATION_QUERY_KEY = ["automation"] as const;

/** Poll faster while a run is live so Desktop and browser stay in sync. */
export const AUTOMATION_LIVE_POLL_MS = 2000;
export const AUTOMATION_IDLE_POLL_MS = 15000;

function patchDashboardActiveRun(client: ReturnType<typeof useQueryClient>, active: AutomationRun | null) {
  client.setQueryData<DashboardStats>(["dashboard"], (old) => {
    if (!old) return old;
    return { ...old, automation: { ...old.automation, active } };
  });
}

export function useAutomationOverview(options?: {
  /** Extra reason to poll quickly (connect dialog open, desktop linking, etc.). */
  liveBoost?: boolean;
}): UseQueryResult<AutomationOverview> {
  const client = useQueryClient();
  const query = useQuery({
    queryKey: [...AUTOMATION_QUERY_KEY],
    queryFn: automation.overview,
    refetchInterval: (q) => {
      const data = q.state.data;
      const linked = (data?.devices.length ?? 0) > 0;
      const live = Boolean(data?.active) || options?.liveBoost || (isDesktop && !linked);
      return live ? AUTOMATION_LIVE_POLL_MS : AUTOMATION_IDLE_POLL_MS;
    },
    refetchOnWindowFocus: (q) => Boolean(q.state.data?.active),
  });

  const active = query.data?.active;
  useEffect(() => {
    if (!query.data) return;
    patchDashboardActiveRun(client, query.data.active);
  }, [client, query.data]);

  useEffect(() => {
    if (!active) return;
    void client.invalidateQueries({ queryKey: ["notifications"] });
  }, [
    active,
    active?.id,
    active?.status,
    active?.successful_count,
    active?.failed_count,
    active?.skipped_count,
    active?.current_job,
    active?.active_source,
    client,
  ]);

  return query;
}

/** 2s while a Desktop run is live; otherwise do not poll this query. */
export function useLiveRunPoll(): number | false {
  const { data } = useAutomationOverview();
  return data?.active ? AUTOMATION_LIVE_POLL_MS : false;
}

/** Live counters for the active run card (GET /automation/{id} while the run is open). */
export function useActiveRunLive(run: AutomationRun | null | undefined) {
  const client = useQueryClient();
  const live =
    run && (run.status === "running" || run.status === "queued" || run.status === "paused");
  const detail = useQuery({
    queryKey: [...AUTOMATION_QUERY_KEY, "run", run?.id ?? ""],
    queryFn: () => automation.getRun(run!.id),
    enabled: Boolean(live && run?.id),
    refetchInterval: AUTOMATION_LIVE_POLL_MS,
    refetchOnWindowFocus: true,
  });

  useEffect(() => {
    const fresh = detail.data;
    if (!fresh) return;
    client.setQueryData<AutomationOverview>([...AUTOMATION_QUERY_KEY], (old) => {
      if (!old?.active || old.active.id !== fresh.id) return old;
      return { ...old, active: fresh };
    });
    patchDashboardActiveRun(client, fresh);
  }, [client, detail.data]);

  return detail.data ?? run ?? null;
}
