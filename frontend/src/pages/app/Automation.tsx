import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bot, CheckCircle2, Copy, Laptop, Monitor, Pause, Play, ShieldCheck, Square, Trash2, Wifi, WifiOff } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { AgentDownloadPanel } from "../../components/AgentDownloadPanel";
import { DesktopAgentPanel } from "../../components/DesktopAgentPanel";
import { PendingQuestionsModal } from "../../components/PendingQuestionsModal";
import { ConfirmDialog, Modal } from "../../components/Modal";
import { useToast } from "../../components/Toast";
import { RunStatusBadge } from "../../components/RunStatusBadge";
import { Alert, Badge, Button, ButtonLink, Card, cx, EmptyState, PageHeader, ProgressBar, Spinner } from "../../components/ui";
import { agentServerUrl } from "../../lib/config";
import { isDesktopAutomationHost, isDesktopHost } from "../../lib/desktop";
import { AUTOMATION_LIVE_POLL_MS, useActiveRunLive, useAutomationOverview } from "../../hooks/useAutomationOverview";
import { useDesktopAutoLink } from "../../hooks/useDesktopAutoLink";
import { wakeDesktopAgent } from "../../lib/wakeDesktopAgent";
import { formatDateTime, formatRelative } from "../../lib/format";
import { errorMessage } from "../../services/api";
import { automation, preferences } from "../../services/endpoints";
import type {
  AgentDevice,
  AutomationOverview,
  AutomationRun,
  PendingFormQuestion,
  ResumeRunMode,
  RunLogLine,
} from "../../types";

const LOG_POLL_MS = 2500;
const LOG_PAGE = 200;
const MAX_LOG_LINES = 1000;

export function AutomationPage() {
  const client = useQueryClient();
  const [params, setParams] = useSearchParams();
  const [connectOpen, setConnectOpen] = useState(false);
  const [pendingOpen, setPendingOpen] = useState(false);
  const [pendingItems, setPendingItems] = useState<PendingFormQuestion[]>([]);
  const { data, isLoading, error } = useAutomationOverview({
    liveBoost: connectOpen,
  });

  // When a run ends, the dashboard, applications, usage, and notifications have all changed.
  const activeId = data?.active?.id ?? null;
  const previousActive = useRef<string | null>(null);
  useEffect(() => {
    if (previousActive.current && previousActive.current !== activeId) {
      for (const key of ["dashboard", "usage", "applications", "jobs", "notifications"]) {
        void client.invalidateQueries({ queryKey: [key] });
      }
      void preferences.application().then((doc) => {
        const pending = (doc.pending_form_questions ?? []).filter((q) => q.needs_answer && !q.has_saved_rule);
        if (pending.length) {
          setPendingItems(pending);
          setPendingOpen(true);
        }
      });
    }
    previousActive.current = activeId;
  }, [activeId, client]);

  const serverLinked = (data?.devices.length ?? 0) > 0;
  const { linking: desktopLinking, linkError: desktopLinkError } = useDesktopAutoLink({
    serverHasDevice: serverLinked,
    enabled: Boolean(data),
  });

  useEffect(() => {
    if (params.get("pending") !== "1") return;
    void preferences.application().then((doc) => {
      const pending = (doc.pending_form_questions ?? []).filter((q) => q.needs_answer);
      if (pending.length) {
        setPendingItems(pending);
        setPendingOpen(true);
      }
      params.delete("pending");
      setParams(params, { replace: true });
    });
  }, [params, setParams]);

  if (isLoading) return <Spinner />;
  if (!data) return <Alert kind="error">{errorMessage(error)}</Alert>;
  const shownRun = data.active ?? data.recent[0] ?? null;

  return (
    <>
      <PageHeader title="Automation" description="Start, pause, and watch your job applications as they happen."
                  actions={
                    !isDesktopHost ? (
                      <Button variant="secondary" className="w-full sm:w-auto" onClick={() => setConnectOpen(true)}>
                        <Laptop className="h-4 w-4" aria-hidden />{" "}
                        {data.devices.length ? "Switch computer" : "Connect a computer"}
                      </Button>
                    ) : undefined
                  } />
      <AutomationStatusStrip
        overview={data}
        onConnect={() => setConnectOpen(true)}
        desktopLinking={desktopLinking}
        desktopLinkError={desktopLinkError}
      />
      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          {data.active
            ? <ActiveRunCard run={data.active} agentOnline={data.agent_online} />
            : (
              <StartCard
                overview={data}
                onConnect={() => setConnectOpen(true)}
                desktopLinking={desktopLinking}
                desktopLinkError={desktopLinkError}
              />
            )}
          {shownRun && <RunLog key={shownRun.id} run={shownRun} live={shownRun.id === data.active?.id} />}
        </div>
        <div className="space-y-6">
          <DevicesCard
            devices={data.devices}
            onConnect={() => setConnectOpen(true)}
            desktopLinking={desktopLinking}
            desktopLinkError={desktopLinkError}
          />
          <Card title="This month">
            <ProgressBar label="Applications" value={data.usage.applications.used} max={data.usage.applications.limit} />
            <p className="mt-3 text-xs text-slate-500">
              {data.usage.plan_name} plan. Runs stop by themselves when the monthly limit is reached.
            </p>
          </Card>
          <RecentRuns runs={data.recent.filter((r) => r.id !== data.active?.id)} />
        </div>
      </div>
      {!isDesktopHost && (
        <ConnectDialog open={connectOpen} onClose={() => setConnectOpen(false)} knownIds={data.devices.map((d) => d.id)} />
      )}
      <PendingQuestionsModal
        open={pendingOpen}
        onClose={() => setPendingOpen(false)}
        items={pendingItems}
      />
    </>
  );
}

// ------------------------------------------------------------------------------------------ start
function StartCard({
  overview,
  onConnect,
  desktopLinking,
  desktopLinkError,
}: {
  overview: AutomationOverview;
  onConnect: () => void;
  desktopLinking?: boolean;
  desktopLinkError?: string | null;
}) {
  const client = useQueryClient();
  const toast = useToast();
  const [dryRun, setDryRun] = useState(false);
  const enabledSources = overview.enabled_sources?.length
    ? overview.enabled_sources
    : (["linkedin", "naukri"] as Array<"linkedin" | "naukri">);
  const linkedinAvailable = enabledSources.includes("linkedin");
  const naukriAvailable = enabledSources.includes("naukri");
  const [useLinkedIn, setUseLinkedIn] = useState(linkedinAvailable);
  const [useNaukri, setUseNaukri] = useState(naukriAvailable && !linkedinAvailable);
  const [switchAfter, setSwitchAfter] = useState(10);
  const tailorSnap = overview.resume_tailor;
  const [resumeMode, setResumeMode] = useState<ResumeRunMode>(tailorSnap?.mode ?? "default");
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [modalChoice, setModalChoice] = useState<ResumeRunMode | null>(null);

  useEffect(() => {
    if (tailorSnap?.mode) setResumeMode(tailorSnap.mode);
  }, [tailorSnap?.mode]);
  useEffect(() => {
    if (!linkedinAvailable) setUseLinkedIn(false);
    if (!naukriAvailable) setUseNaukri(false);
    if (linkedinAvailable && !naukriAvailable) setUseLinkedIn(true);
    if (naukriAvailable && !linkedinAvailable) setUseNaukri(true);
  }, [linkedinAvailable, naukriAvailable]);

  const selectedSources = [
    ...(useLinkedIn ? ["linkedin" as const] : []),
    ...(useNaukri ? ["naukri" as const] : []),
  ];
  const bothSources = selectedSources.length > 1;
  const sourcesValid = selectedSources.length > 0 && (!bothSources || switchAfter >= 1);

  const start = useMutation({
    mutationFn: (mode: ResumeRunMode) => automation.start({
      dry_run: dryRun,
      resume_mode: mode,
      sources: selectedSources,
      ...(bothSources ? { switch_after: switchAfter } : {}),
    }),
    onSuccess: () => {
      toast.success(dryRun ? "Practice run queued." : "Run queued.");
      wakeDesktopAgent();
      setConfirmOpen(false);
      void client.invalidateQueries({ queryKey: ["automation"] });
      void client.invalidateQueries({ queryKey: ["preferences", "search"] });
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  const { readiness, devices, usage } = overview;
  const computerReady = devices.length > 0;
  const canStart = readiness.ready && computerReady && !usage.limit_reached && sourcesValid && !desktopLinking;
  const aiReady = tailorSnap?.resume_ai_available ?? false;
  const skillsReady = tailorSnap?.master_skills_ready ?? false;
  const canPickTailor = tailorSnap?.can_tailor ?? false;

  const openConfirm = () => {
    setModalChoice(null);
    setConfirmOpen(true);
  };

  return (
    <Card title="Start a run">
      <div className="space-y-4 text-sm text-slate-600">
        <div className="flex gap-3">
          <Laptop className="h-6 w-6 shrink-0 text-brand-600" aria-hidden />
          <p>
            The run happens in a browser on <strong>your own computer</strong>, using your saved preferences, answers,
            and default resume. You sign in to LinkedIn and Naukri there (or save logins on this PC in Desktop), so
            ApplyXAI never receives your passwords.
          </p>
        </div>
        <div className="flex gap-3">
          <ShieldCheck className="h-6 w-6 shrink-0 text-brand-600" aria-hidden />
          <p>You can watch every step, and pause or stop at any time. Results appear here as they happen.</p>
        </div>

        {!readiness.ready && (
          <Alert kind="error">
            <p className="font-medium">Finish setting up first:</p>
            <ul className="mt-1 list-disc pl-5">{readiness.problems.map((p) => <li key={p}>{p}</li>)}</ul>
            <p className="mt-2 flex flex-wrap gap-x-3">
              <Link className="font-medium underline" to="/app/profile">Master Profile</Link>
              <Link className="font-medium underline" to="/app/questions">Custom Questions</Link>
              <Link className="font-medium underline" to="/app/settings/automation">Automation Settings</Link>
              <Link className="font-medium underline" to="/app/automation/search">Job search</Link>
              <Link className="font-medium underline" to="/app/resumes">Resumes</Link>
            </p>
          </Alert>
        )}
        {isDesktopAutomationHost() && (
          <DesktopAgentPanel
            className="mt-2"
            serverLinked={computerReady}
            linking={desktopLinking}
            linkError={desktopLinkError}
          />
        )}
        {isDesktopAutomationHost() && (
          <p className="text-sm text-slate-600">
            LinkedIn / Naukri passwords: save them under{" "}
            <Link className="font-medium text-brand-600 underline" to="/app/job-logins">
              Job logins
            </Link>{" "}
            (stored only on this PC). Automation opens an isolated Chrome window — not your personal Chrome profiles.
          </p>
        )}
        {devices.length === 0 && (
          <Alert kind={desktopLinkError ? "error" : "info"}>
            {isDesktopHost ? (
              <p>
                {desktopLinkError
                  ? desktopLinkError
                  : desktopLinking
                    ? "Linking this computer to your account… Start run will unlock when linking finishes."
                    : "This computer links to your account automatically after sign-in."}
              </p>
            ) : (
              <>
                <p>
                  Install <strong>ApplyXAI Desktop</strong> on this computer (one installer), sign in, and connect it to this account.
                </p>
                <div className="mt-3">
                  <AgentDownloadPanel />
                </div>
                <p className="mt-3">
                  Already installed?{" "}
                  <button type="button" onClick={onConnect} className="font-medium underline">Connect a computer</button>
                </p>
              </>
            )}
          </Alert>
        )}
        {devices.length > 0 && !overview.agent_online && (
          <Alert kind="info">
            None of your computers is online. You can still queue a run — open <strong>ApplyXAI Desktop</strong> on this PC to pick it up.
          </Alert>
        )}
        {usage.limit_reached && (
          <Alert kind="error">
            You've used all {usage.applications.limit} applications for this month.{" "}
            <Link className="font-medium underline" to="/app/billing">See plans</Link>
          </Alert>
        )}

        <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
          <p className="text-sm font-medium text-slate-900">Resume for this run</p>
          <p className="mt-1 text-xs text-slate-600">
            Tailor builds a JD-matched resume per job (when match ≥60%) and attaches it during apply on LinkedIn or
            Naukri.
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            <button
              type="button"
              disabled={!canStart}
              onClick={() => setResumeMode("default")}
              className={cx(
                "rounded-lg px-4 py-2 text-sm font-medium ring-1 transition",
                resumeMode === "default"
                  ? "bg-white text-brand-700 ring-brand-600 shadow-sm"
                  : "bg-transparent text-slate-600 ring-slate-300 hover:bg-white",
              )}
            >
              Default resume only
            </button>
            <button
              type="button"
              disabled={!canStart || !canPickTailor}
              title={
                !aiReady
                  ? "Ask an admin to enable Platform AI and Resume AI"
                  : !skillsReady
                    ? "Analyze master skills on your default resume (Resumes page)"
                    : undefined
              }
              onClick={() => setResumeMode("tailor_if_gate")}
              className={cx(
                "rounded-lg px-4 py-2 text-sm font-medium ring-1 transition",
                resumeMode === "tailor_if_gate"
                  ? "bg-brand-600 text-white ring-brand-600 shadow-sm"
                  : "bg-transparent text-slate-600 ring-slate-300 hover:bg-white",
                !canPickTailor && "cursor-not-allowed opacity-50",
              )}
            >
              Tailor per job (JD)
            </button>
          </div>
          {!canPickTailor && (
            <p className="mt-2 text-xs text-amber-800">
              {!aiReady ? (
                <>Resume tailoring needs <strong>Platform AI</strong> with <strong>Resume AI</strong> turned on in admin Settings.</>
              ) : (
                <>
                  Platform AI is ready. On{" "}
                  <Link to="/app/resumes" className="font-medium underline">Resumes</Link>, open your{" "}
                  <strong>default</strong> resume and click <strong>Analyze skills</strong> (or re-run resume intake if your profile already lists skills).
                </>
              )}
            </p>
          )}
        </div>

        <fieldset className="space-y-3">
          <legend className="text-sm font-medium text-slate-900">Job sources</legend>
          <p className="text-sm text-slate-500">
            {linkedinAvailable && naukriAvailable
              ? "Choose LinkedIn, Naukri, or both. With both, the run switches site after the number of successful applications you set."
              : "Your administrator has activated this job source for runs."}
          </p>
          {linkedinAvailable && (
            <label className="flex items-center gap-2">
              <input type="checkbox" className="h-4 w-4 rounded border-slate-300" checked={useLinkedIn}
                     disabled={!naukriAvailable}
                     onChange={(e) => setUseLinkedIn(e.target.checked)} />
              <span className="font-medium text-slate-900">LinkedIn</span>
            </label>
          )}
          {naukriAvailable && (
            <label className="flex items-center gap-2">
              <input type="checkbox" className="h-4 w-4 rounded border-slate-300" checked={useNaukri}
                     disabled={!linkedinAvailable}
                     onChange={(e) => setUseNaukri(e.target.checked)} />
              <span className="font-medium text-slate-900">Naukri</span>
            </label>
          )}
          {bothSources && (
            <label className="block max-w-xs">
              <span className="text-sm font-medium text-slate-900">Jobs before switching</span>
              <input
                type="number"
                min={1}
                className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                value={switchAfter}
                onChange={(e) => setSwitchAfter(Number(e.target.value))}
              />
            </label>
          )}
        </fieldset>

        <label className="flex items-start gap-2">
          <input type="checkbox" className="mt-0.5 h-4 w-4 rounded border-slate-300" checked={dryRun}
                 onChange={(e) => setDryRun(e.target.checked)} />
          <span>
            <span className="font-medium text-slate-900">Practice run</span>
            <span className="block text-slate-500">Fill in applications but stop before submitting them.</span>
          </span>
        </label>
        <Button onClick={openConfirm} loading={start.isPending} disabled={!canStart}>
          <Play className="h-4 w-4" aria-hidden /> Start run
        </Button>
      </div>

      <Modal
        open={confirmOpen}
        onClose={() => setConfirmOpen(false)}
        title="Confirm before starting"
        wide
        footer={
          <>
            <Button variant="secondary" onClick={() => setConfirmOpen(false)}>Cancel</Button>
            <Button
              loading={start.isPending}
              disabled={modalChoice === null}
              onClick={() => modalChoice && start.mutate(modalChoice)}
            >
              Start run
            </Button>
          </>
        }
      >
        <p className="mb-4 text-slate-600">
          Choose how resumes are handled for <strong>this run</strong>. You must pick one option below.
        </p>
        <div className="space-y-3">
          <label
            className={cx(
              "flex cursor-pointer gap-3 rounded-lg border p-4",
              modalChoice === "default" ? "border-brand-600 bg-brand-50/50 ring-1 ring-brand-600" : "border-slate-200",
            )}
          >
            <input
              type="radio"
              name="resume_mode_confirm"
              className="mt-1"
              checked={modalChoice === "default"}
              onChange={() => setModalChoice("default")}
            />
            <span>
              <span className="font-medium text-slate-900">Off — default resume only</span>
              <span className="mt-1 block text-sm text-slate-600">
                Upload your default resume for every Easy Apply job.
              </span>
            </span>
          </label>
          <label
            className={cx(
              "flex gap-3 rounded-lg border p-4",
              !canPickTailor ? "cursor-not-allowed opacity-60" : "cursor-pointer",
              modalChoice === "tailor_if_gate" ? "border-brand-600 bg-brand-50/50 ring-1 ring-brand-600" : "border-slate-200",
            )}
          >
            <input
              type="radio"
              name="resume_mode_confirm"
              className="mt-1"
              disabled={!canPickTailor}
              checked={modalChoice === "tailor_if_gate"}
              onChange={() => setModalChoice("tailor_if_gate")}
            />
            <span>
              <span className="font-medium text-slate-900">On — tailor per job (tailor_if_gate)</span>
              <span className="mt-1 block text-sm text-slate-600">
                After reading each job description, AI tailors your resume when it matches well enough, saves a version,
                and uploads it to LinkedIn.
              </span>
            </span>
          </label>
        </div>
      </Modal>
    </Card>
  );
}

// ------------------------------------------------------------------------------------------ active run
function sourceProgress(run: AutomationRun): string | null {
  const label = run.active_source === "naukri" ? "Naukri" : "LinkedIn";
  if (run.switch_after && run.switch_after > 0) {
    return `${label} · ${run.source_submitted ?? 0} of ${run.switch_after}`;
  }
  if ((run.sources ?? []).length > 1) return label;
  return (run.sources ?? []).length ? label : null;
}

function statusLine(run: AutomationRun, agentOnline: boolean): string {
  if (run.control === "stop") {
    return run.stop_reason === "plan_limit"
      ? "This month's application limit is reached. Stopping after the current job\u2026"
      : "Stopping after the current job\u2026";
  }
  if (run.status === "queued") {
    if (run.claimed) return "Your computer is opening the browser\u2026";
    return agentOnline
      ? "Waiting for your computer to pick this up\u2026"
      : "Waiting for a computer. Open ApplyXAI Desktop on a linked PC to begin.";
  }
  if (run.status === "paused") return "Paused. Resume when you're ready.";
  if (run.control === "pause") return "Pausing after the current job\u2026";
  return run.current_job ? run.current_job : "Running\u2026";
}

function ActiveRunCard({ run: overviewRun, agentOnline }: { run: AutomationRun; agentOnline: boolean }) {
  const run = useActiveRunLive(overviewRun) ?? overviewRun;
  const client = useQueryClient();
  const toast = useToast();
  const [confirmStop, setConfirmStop] = useState(false);
  const act = useMutation({
    mutationFn: (action: "pause" | "resume" | "stop") => automation[action](run.id),
    onSuccess: (updated) => {
      client.setQueryData<AutomationOverview>(["automation"], (old) =>
        old && { ...old, active: updated.status === "queued" || updated.status === "running" || updated.status === "paused" ? updated : null });
      void client.invalidateQueries({ queryKey: ["automation"] });
      setConfirmStop(false);
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  const stopping = run.control === "stop";
  const counters = [
    { label: "Applied", value: run.successful_count },
    { label: "Failed", value: run.failed_count },
    { label: "Skipped", value: run.skipped_count },
    { label: "Jobs looked at", value: run.total_jobs },
  ];

  return (
    <Card title={<span className="flex items-center gap-2">Current run <RunStatusBadge status={run.status} />
      {run.dry_run && <Badge tone="amber">Practice</Badge>}</span>}>
      <p className="text-sm text-slate-700" aria-live="polite">{statusLine(run, agentOnline)}</p>
      {sourceProgress(run) && <p className="mt-1 text-sm font-medium text-slate-900">{sourceProgress(run)}</p>}
      <dl className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
        {counters.map((c) => (
          <div key={c.label} className="rounded-lg bg-slate-50 p-3">
            <dt className="text-xs text-slate-500">{c.label}</dt>
            <dd className="text-xl font-semibold text-slate-900">{c.value}</dd>
          </div>
        ))}
      </dl>
      <div className="mt-4 flex flex-wrap gap-2">
        {run.status !== "queued" && (run.control === "pause"
          ? <Button variant="secondary" onClick={() => act.mutate("resume")} loading={act.isPending && act.variables === "resume"}
                    disabled={stopping}><Play className="h-4 w-4" aria-hidden /> Resume</Button>
          : <Button variant="secondary" onClick={() => act.mutate("pause")} loading={act.isPending && act.variables === "pause"}
                    disabled={stopping}><Pause className="h-4 w-4" aria-hidden /> Pause</Button>)}
        <Button variant="danger" onClick={() => setConfirmStop(true)} disabled={stopping}>
          <Square className="h-4 w-4" aria-hidden /> {stopping ? "Stopping\u2026" : "Stop"}
        </Button>
      </div>
      <p className="mt-3 text-xs text-slate-500">Started {formatDateTime(run.started_at ?? run.created_at)}</p>
      <ConfirmDialog open={confirmStop} onClose={() => setConfirmStop(false)} title="Stop this run?" danger
                     confirmLabel="Stop run" loading={act.isPending && act.variables === "stop"}
                     onConfirm={() => act.mutate("stop")}
                     message="The job in progress is finished first, so nothing is left half-submitted. Results so far are kept." />
    </Card>
  );
}

// ------------------------------------------------------------------------------------------ log
const timeFmt = new Intl.DateTimeFormat(undefined, { hour: "2-digit", minute: "2-digit", second: "2-digit" });
const LEVEL_DOT = { info: "bg-slate-300", warning: "bg-amber-500", error: "bg-red-500" };

/** Lines of a run's log, polled with the ?after= cursor while the run is live. */
function useRunLogs(runId: string, live: boolean): RunLogLine[] {
  const [lines, setLines] = useState<RunLogLine[]>([]);
  const after = useRef(0);
  useEffect(() => {
    let cancelled = false;
    let timer: number | undefined;
    const tick = async () => {
      try {
        for (;;) {
          const page = await automation.logs(runId, after.current);
          if (cancelled) return;
          if (page.items.length) {
            after.current = page.next_after;
            setLines((prev) => [...prev, ...page.items].slice(-MAX_LOG_LINES));
          }
          if (page.items.length < LOG_PAGE) break;
        }
      } catch {
        // try again on the next tick
      }
      if (!cancelled && live) timer = window.setTimeout(tick, LOG_POLL_MS);
    };
    void tick();
    return () => { cancelled = true; window.clearTimeout(timer); };
  }, [runId, live]);
  return lines;
}

function RunLog({ run, live }: { run: AutomationRun; live: boolean }) {
  const lines = useRunLogs(run.id, live);
  const box = useRef<HTMLOListElement>(null);
  const followTail = useRef(true);
  useEffect(() => {
    const el = box.current;
    if (el && followTail.current) el.scrollTop = el.scrollHeight;
  }, [lines]);
  const onScroll = () => {
    const el = box.current;
    if (el) followTail.current = el.scrollHeight - el.scrollTop - el.clientHeight < 40;
  };

  return (
    <Card title={live ? "Activity" : "Last run's activity"}>
      {lines.length === 0 ? (
        <p className="text-sm text-slate-500">{live ? "Waiting for the first update\u2026" : "Nothing was recorded for this run."}</p>
      ) : (
        <ol ref={box} onScroll={onScroll} className="max-h-96 space-y-1.5 overflow-y-auto pr-1 text-sm"
            aria-label="Run activity" aria-live="polite">
          {lines.map((l) => (
            <li key={l.seq} className="flex gap-3">
              <time dateTime={l.ts} className="shrink-0 tabular-nums text-xs leading-5 text-slate-400">
                {timeFmt.format(new Date(l.ts))}
              </time>
              <span className={cx("mt-2 h-1.5 w-1.5 shrink-0 rounded-full", LEVEL_DOT[l.level] ?? LEVEL_DOT.info)} aria-hidden />
              <span className={cx(l.level === "error" ? "text-red-700" : l.level === "warning" ? "text-amber-800" : "text-slate-700")}>
                {l.message}
              </span>
            </li>
          ))}
        </ol>
      )}
    </Card>
  );
}

// ------------------------------------------------------------------------------------------ devices
function AutomationStatusStrip({
  overview,
  onConnect,
  desktopLinking,
  desktopLinkError,
}: {
  overview: AutomationOverview;
  onConnect: () => void;
  desktopLinking?: boolean;
  desktopLinkError?: string | null;
}) {
  const { devices, agent_online, active, readiness } = overview;
  const computer = devices[0] ?? null;
  let headline = "Connect your computer to run applications";
  let detail = "Install ApplyXAI Desktop, connect this computer, then start a run.";
  if (!computer && isDesktopHost) {
    headline = desktopLinkError ? "Could not link this computer" : "Setting up this computer";
    detail = desktopLinkError
      ? desktopLinkError
      : desktopLinking
        ? "Linking to your account… This usually takes a few seconds after sign-in."
        : "Stay signed in — ApplyXAI Desktop links this PC automatically.";
  }
  if (computer) {
    headline = computer.online ? `${computer.name} is online` : `${computer.name} is offline`;
    detail = computer.online
      ? "Ready to run. Start or resume from the panel on the left."
      : "Open ApplyXAI Desktop on this computer, or connect a different one.";
  } else if (!readiness.ready) {
    detail = "Finish profile, preferences, and resume setup, then connect one computer.";
  }
  if (active) {
    headline = active.control === "pause" ? "Run paused" : "Run in progress";
    detail = active.current_job || "Automation is running on your computer using saved job preferences.";
  }

  return (
    <section className="mb-6 rounded-xl bg-gradient-to-br from-slate-900 to-slate-800 p-4 text-white shadow-sm ring-1 ring-slate-700/50 sm:p-5">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex min-w-0 items-start gap-3">
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-white/10">
            {active ? <Bot className="h-5 w-5" aria-hidden /> : agent_online ? <Wifi className="h-5 w-5 text-emerald-300" aria-hidden /> : <WifiOff className="h-5 w-5 text-slate-400" aria-hidden />}
          </span>
          <div className="min-w-0">
            <p className="font-semibold tracking-tight">{headline}</p>
            <p className="mt-0.5 text-sm text-slate-300">{detail}</p>
          </div>
        </div>
        {!computer && !isDesktopHost && (
          <Button variant="secondary" size="sm" className="shrink-0 border-white/20 bg-white/10 text-white hover:bg-white/20" onClick={onConnect}>
            Connect computer
          </Button>
        )}
      </div>
    </section>
  );
}

function DevicesCard({
  devices,
  onConnect,
  desktopLinking,
  desktopLinkError,
}: {
  devices: AgentDevice[];
  onConnect: () => void;
  desktopLinking?: boolean;
  desktopLinkError?: string | null;
}) {
  const client = useQueryClient();
  const toast = useToast();
  const [removing, setRemoving] = useState<AgentDevice | null>(null);
  const active = devices[0] ?? null;
  const remove = useMutation({
    mutationFn: (id: string) => automation.removeDevice(id),
    onSuccess: () => {
      toast.success("Computer disconnected.");
      setRemoving(null);
      void client.invalidateQueries({ queryKey: ["automation"] });
    },
    onError: (e) => toast.error(errorMessage(e)),
  });

  return (
    <section className="rounded-xl bg-white p-4 shadow-sm ring-1 ring-slate-200/80 sm:p-5">
      <div className="flex items-start justify-between gap-2">
        <div>
          <h2 className="text-sm font-semibold text-slate-900">Active computer</h2>
          <p className="mt-0.5 text-xs text-slate-500">One computer per account. Connecting a new one replaces the previous.</p>
        </div>
        {active && !isDesktopHost && (
          <button type="button" onClick={onConnect} className="shrink-0 text-xs font-medium text-brand-600 hover:underline">
            Replace
          </button>
        )}
      </div>
      {active ? (
        <div className="mt-4 flex items-center gap-3 rounded-lg border border-slate-100 bg-slate-50/80 p-3">
          <span className={cx("flex h-11 w-11 shrink-0 items-center justify-center rounded-lg",
            active.online ? "bg-emerald-100 text-emerald-700" : "bg-slate-200 text-slate-600")}>
            <Monitor className="h-5 w-5" aria-hidden />
          </span>
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <p className="truncate text-sm font-medium text-slate-900">{active.name}</p>
              <Badge tone={active.online ? "green" : "slate"}>{active.online ? "Online" : "Offline"}</Badge>
            </div>
            <p className="text-xs text-slate-500">
              {active.online ? "Online" : active.last_seen_at ? `Last seen ${formatRelative(active.last_seen_at)}` : "Not seen yet"}
              {active.platform && ` · ${active.platform}`}
            </p>
          </div>
          <button type="button" aria-label={`Disconnect ${active.name}`} onClick={() => setRemoving(active)}
                  className="rounded p-1.5 text-slate-400 hover:bg-white hover:text-red-600">
            <Trash2 className="h-4 w-4" />
          </button>
        </div>
      ) : (
        <div className="mt-4 text-sm text-slate-600">
          {isDesktopHost ? (
            <>
              <p>{desktopLinkError ? desktopLinkError : desktopLinking ? "Linking this computer…" : "Pairing this PC after sign-in…"}</p>
              {isDesktopAutomationHost() && (
                <div className="mt-3">
                  <DesktopAgentPanel serverLinked={false} linking={desktopLinking} linkError={desktopLinkError} />
                </div>
              )}
            </>
          ) : (
            <>
              <p>No computer linked yet.</p>
              <div className="mt-3">
                <AgentDownloadPanel />
              </div>
              <Button className="mt-3 w-full" size="sm" variant="secondary" onClick={onConnect}>Connect a computer</Button>
            </>
          )}
        </div>
      )}
      <ConfirmDialog open={removing !== null} onClose={() => setRemoving(null)} title="Disconnect this computer?" danger
                     confirmLabel="Disconnect" loading={remove.isPending} onConfirm={() => removing && remove.mutate(removing.id)}
                     message={`${removing?.name ?? "This computer"} won't be able to run automations until you connect it again.`} />
    </section>
  );
}

const IS_WINDOWS = typeof navigator !== "undefined" && /Windows/i.test(navigator.userAgent);
/** The agent needs the project's virtual environment, run from the project folder. */
const AGENT = IS_WINDOWS ? "venv\\Scripts\\python -m agent" : "venv/bin/python -m agent";

function CopyLine({ text }: { text: string }) {
  const toast = useToast();
  const copy = () => navigator.clipboard?.writeText(text).then(() => toast.success("Copied."), () => toast.error("Couldn't copy."));
  return (
    <div className="mt-1 flex items-center gap-2 rounded-lg bg-slate-900 px-3 py-2 font-mono text-xs text-slate-100">
      <code className="flex-1 overflow-x-auto whitespace-nowrap">{text}</code>
      <button type="button" onClick={copy} aria-label={`Copy: ${text}`} className="text-slate-400 hover:text-white">
        <Copy className="h-4 w-4" />
      </button>
    </div>
  );
}

function ConnectDialog({ open, onClose, knownIds }: { open: boolean; onClose: () => void; knownIds: string[] }) {
  const known = useRef<string[]>(knownIds);
  const [devOpen, setDevOpen] = useState(false);
  const code = useMutation({ mutationFn: automation.pairingCode });
  const devices = useQuery({ queryKey: ["automation", "devices"], queryFn: automation.devices, enabled: open,
                             refetchInterval: open ? AUTOMATION_LIVE_POLL_MS : false });
  const { mutate, reset } = code;
  useEffect(() => {
    if (open) {
      known.current = knownIds;
    } else {
      reset();
      setDevOpen(false);
    }
  }, [open, reset]);
  useEffect(() => {
    if (open && devOpen && !code.data && !code.isPending) {
      mutate();
    }
  }, [open, devOpen, code.data, code.isPending, mutate]);
  const connected = devices.data?.find((d) => !known.current.includes(d.id));
  const server = agentServerUrl();

  return (
    <Modal open={open} onClose={onClose} title={knownIds.length ? "Switch active computer" : "Connect a computer"} wide
           footer={<Button variant={connected ? "primary" : "secondary"} onClick={onClose}>{connected ? "Done" : "Close"}</Button>}>
      {connected ? (
        <div className="flex flex-col items-center gap-2 py-6 text-center">
          <CheckCircle2 className="h-10 w-10 text-emerald-500" aria-hidden />
          <p className="font-medium text-slate-900">{connected.name} is now your active computer</p>
          <p>Any previous computer was disconnected. Keep ApplyXAI Desktop open, then start a run from this page.</p>
        </div>
      ) : (
        <ol className="space-y-5">
          {knownIds.length > 0 && (
            <Alert kind="info">
              Approving a new connection replaces your current computer. Only one machine can run automation at a time.
            </Alert>
          )}
          <li>
            <p className="font-medium text-slate-900">1. Install and open ApplyXAI Desktop on this computer.</p>
            <div className="mt-2">
              <AgentDownloadPanel />
            </div>
          </li>
          <li>
            <p className="font-medium text-slate-900">2. Sign in on Desktop — this computer links automatically.</p>
            <p className="mt-1 text-sm text-slate-600">
              No separate connect step. Keep ApplyXAI Desktop open while runs are queued.
            </p>
          </li>
          <li>
            <p className="font-medium text-slate-900">3. Start a run from Automation and watch progress here.</p>
          </li>
          <li className="text-xs text-slate-500">
            LinkedIn sign-in happens in Chrome on this computer. Your LinkedIn password never goes to ApplyXAI.
            This dialog updates when the computer appears in your device list.
          </li>
          <li>
            <button
              type="button"
              className="text-sm font-medium text-brand-600 hover:underline"
              onClick={() => setDevOpen((v) => !v)}
            >
              {devOpen ? "Hide" : "Show"} developer pairing (terminal + one-time code)
            </button>
            {devOpen && (
              <div className="mt-3 space-y-3 rounded-lg border border-slate-200 bg-slate-50 p-4 text-sm">
                {code.isPending ? <Spinner label="Getting a code\u2026" /> : code.isError ? (
                  <Alert kind="error">{errorMessage(code.error)}</Alert>
                ) : code.data ? (
                  <>
                    <p className="font-medium text-slate-900">One-time code</p>
                    <span className="inline-block rounded-lg bg-brand-50 px-4 py-2 font-mono text-xl font-semibold tracking-widest text-brand-700"
                          data-testid="pairing-code">{code.data.code}</span>
                    <CopyLine text={`${AGENT} pair --server ${server} --code ${code.data.code}`} />
                  </>
                ) : null}
                <CopyLine text={`${AGENT} run`} />
              </div>
            )}
          </li>
        </ol>
      )}
    </Modal>
  );
}

// ------------------------------------------------------------------------------------------ history
function RecentRuns({ runs }: { runs: AutomationRun[] }) {
  return (
    <Card title="Recent runs">
      {runs.length === 0 ? <EmptyState icon={<Bot className="h-8 w-8" />} title="No runs yet" /> : (
        <ul className="-my-2 divide-y divide-slate-100">
          {runs.map((r) => (
            <li key={r.id} className="space-y-1 py-2 text-sm">
              <div className="flex items-center justify-between gap-2">
                <span className="text-slate-600">{formatDateTime(r.started_at ?? r.created_at)}</span>
                <span className="flex gap-1">{r.dry_run && <Badge tone="amber">Practice</Badge>}<RunStatusBadge status={r.status} /></span>
              </div>
              <p className="text-slate-700">{r.successful_count} applied &middot; {r.failed_count} failed &middot; {r.skipped_count} skipped</p>
              {r.stop_reason === "plan_limit" && <p className="text-xs text-amber-700">Stopped at the monthly limit.</p>}
              {r.stop_reason === "admin" && <p className="text-xs text-amber-700">Stopped by ApplyXAI support.</p>}
              {r.error_message && <p className="line-clamp-2 text-xs text-red-700">{r.error_message}</p>}
            </li>
          ))}
        </ul>
      )}
      <ButtonLink to="/app/applications" variant="ghost" size="sm" className="mt-3 w-full">See all applications</ButtonLink>
    </Card>
  );
}
