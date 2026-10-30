import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useToast } from "../components/Toast";
import { Alert, Button, Card, Spinner } from "../components/ui";
import { errorMessage } from "../services/api";
import { AUTOMATION_LIVE_POLL_MS, useAutomationOverview } from "../hooks/useAutomationOverview";
import { automation, profileLinkedIn } from "../services/endpoints";
import type { Profile } from "../types";

const MANUAL_CHECKLIST = [
  "Grow your network with relevant connections",
  "Request skill endorsements from colleagues",
  "Complete identity or workplace verification if LinkedIn prompts you",
];

export function LinkedInProfileSyncPanel({ profile }: { profile: Profile }) {
  const toast = useToast();
  const qc = useQueryClient();
  const readiness = useQuery({ queryKey: ["profile-sync-readiness"], queryFn: automation.profileSyncReadiness });
  const plan = useQuery({ queryKey: ["profile-sync-plan"], queryFn: () => profileLinkedIn.syncPlan() });
  const overview = useAutomationOverview();
  const [runId, setRunId] = useState<string | null>(null);
  const [logAfter, setLogAfter] = useState(0);
  const [pendingDraft, setPendingDraft] = useState<Record<string, unknown> | null>(null);

  const aiDraft = useMutation({
    mutationFn: () => profileLinkedIn.aiComplete(),
    onSuccess: (draft) => {
      if (draft.unchanged) {
        toast.success("AI had nothing new to suggest.");
        return;
      }
      setPendingDraft(draft as Record<string, unknown>);
      toast.success("Review the draft, then click Apply AI draft.");
    },
    onError: (e) => toast.error(errorMessage(e)),
  });

  const applyDraft = useMutation({
    mutationFn: (body: { draft: Record<string, unknown> }) => profileLinkedIn.applyAiDraft(body.draft),
    onSuccess: () => {
      toast.success("AI draft saved to your Master Profile.");
      setPendingDraft(null);
      qc.invalidateQueries({ queryKey: ["profile"] });
      plan.refetch();
      readiness.refetch();
    },
    onError: (e) => toast.error(errorMessage(e)),
  });

  const startSync = useMutation({
    mutationFn: (dryRun: boolean) =>
      automation.profileSyncStart({ dry_run: dryRun, include_photo: true }),
    onSuccess: (run) => {
      setRunId(run.id);
      setLogAfter(0);
      toast.success(run.dry_run ? "Preview run queued." : "LinkedIn sync queued.");
      overview.refetch();
    },
    onError: (e) => toast.error(errorMessage(e)),
  });

  const logs = useQuery({
    queryKey: ["profile-sync-logs", runId, logAfter],
    queryFn: () => automation.logs(runId!, logAfter),
    enabled: !!runId,
    refetchInterval: runId ? AUTOMATION_LIVE_POLL_MS : false,
  });

  useEffect(() => {
    if (!logs.data?.items.length) return;
    setLogAfter(logs.data.next_after);
    const finished = logs.data.items.some((l) => l.event === "profile_sync_finished" || l.event === "run_finished");
    if (finished) overview.refetch();
  }, [logs.data, overview]);

  const agentOnline = overview.data?.agent_online;
  const active = overview.data?.active;
  const completion = profile.completion?.percent ?? 0;

  return (
    <Card className="space-y-4 border-indigo-100 bg-indigo-50/40">
      <div>
        <h2 className="text-lg font-semibold text-slate-900">LinkedIn profile sync</h2>
        <p className="mt-1 text-sm text-slate-600">
          Fill empty sections on your LinkedIn profile from this Master Profile using ApplyXAI Desktop (local Chrome,
          same sign-in as Easy Apply). LinkedIn may still ask you to complete social steps manually.
        </p>
      </div>
      {readiness.isLoading ? (
        <Spinner />
      ) : readiness.data && !readiness.data.ready ? (
        <Alert kind="info">{readiness.data.problems.join(" ")}</Alert>
      ) : (
        <Alert kind="info">Master Profile completion: {completion}%. Sync uses fill-empty-only by default.</Alert>
      )}
      {plan.data && (
        <ul className="max-h-40 overflow-y-auto rounded border border-slate-200 bg-white text-sm">
          {plan.data.plan
            .filter((row) => row.action !== "manual")
            .map((row) => (
              <li key={row.section} className="flex justify-between gap-2 border-b border-slate-100 px-3 py-2 last:border-0">
                <span className="font-medium capitalize">{row.section.replace(/_/g, " ")}</span>
                <span className="truncate text-slate-500">{row.preview || row.action}</span>
              </li>
            ))}
        </ul>
      )}
      <div className="flex flex-wrap gap-2">
        <Button type="button" variant="secondary" loading={aiDraft.isPending} onClick={() => aiDraft.mutate()}>
          Improve with AI
        </Button>
        {pendingDraft && (
          <Button type="button" loading={applyDraft.isPending} onClick={() => applyDraft.mutate({ draft: pendingDraft })}>
            Apply AI draft
          </Button>
        )}
        <Button
          type="button"
          variant="secondary"
          disabled={!agentOnline || !!active}
          loading={startSync.isPending}
          onClick={() => startSync.mutate(true)}
        >
          Preview on LinkedIn (dry run)
        </Button>
        <Button
          type="button"
          disabled={!agentOnline || !!active || !(readiness.data?.ready ?? false)}
          loading={startSync.isPending}
          onClick={() => startSync.mutate(false)}
        >
          Sync to LinkedIn
        </Button>
      </div>
      {!agentOnline && <p className="text-sm text-amber-800">Open ApplyXAI Desktop and connect this computer to sync.</p>}
      {active && <p className="text-sm text-slate-600">Run in progress: {active.run_kind === "linkedin_profile_sync" ? "profile sync" : "job apply"}.</p>}
      <div>
        <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Manual steps on LinkedIn</p>
        <ul className="mt-1 list-inside list-disc text-sm text-slate-600">
          {MANUAL_CHECKLIST.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      </div>
      {logs.data && logs.data.items.length > 0 && (
        <div className="rounded border border-slate-200 bg-white p-2 text-xs text-slate-700">
          {logs.data.items.slice(-6).map((line) => (
            <div key={line.seq}>{line.message}</div>
          ))}
        </div>
      )}
    </Card>
  );
}
