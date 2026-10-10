import { useQuery } from "@tanstack/react-query";
import {
  ArrowRight,
  Bot,
  Briefcase,
  CheckCircle2,
  Laptop,
  ListChecks,
  Mic,
  Percent,
  Sparkles,
  Target,
  XCircle,
} from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { useSession } from "../auth/session";
import { DailyChart } from "../components/BarChart";
import { RunStatusBadge } from "../components/RunStatusBadge";
import {
  Alert,
  Badge,
  ButtonLink,
  Card,
  EmptyState,
  PageHeader,
  ProgressBar,
  Spinner,
  StatCard,
  cx,
} from "../components/ui";
import { ApplicationDetailModal } from "./ApplicationDetailModal";
import { formatDate, formatRelative, isUnlimitedUsageCap, STATUS_LABELS, STATUS_TONES } from "../lib/format";
import { errorMessage } from "../services/api";
import { automation, dashboard } from "../services/endpoints";
import type { ApplicationStatus, AutomationRun, DashboardStats, MockInterviewSessionStatus } from "../types";

const MI_STATUS_LABEL: Record<MockInterviewSessionStatus, string> = {
  active: "In progress",
  completed: "Completed",
  abandoned: "Abandoned",
};

const PIPELINE_STATUSES: ApplicationStatus[] = ["applied", "failed", "skipped", "queued", "running"];

const QUICK_LINKS = [
  {
    to: "/app/automation",
    icon: Bot,
    title: "Automation",
    description: "Connect your computer, start runs, and watch live progress.",
    accent: "from-brand-600 to-brand-800",
  },
  {
    to: "/app/applications",
    icon: ListChecks,
    title: "Applications",
    description: "Full history, filters, exports, and resume attachments.",
    accent: "from-emerald-600 to-teal-800",
  },
  {
    to: "/app/jobs",
    icon: Briefcase,
    title: "Jobs",
    description: "Every role discovered, with outcomes and posting links.",
    accent: "from-slate-700 to-slate-900",
  },
  {
    to: "/app/mock-interview",
    icon: Mic,
    title: "Mock interview",
    description: "AI video-style practice tied to your applications.",
    accent: "from-violet-600 to-purple-900",
  },
] as const;

function RunSummary({ run, label }: { run: AutomationRun; label: string }) {
  return (
    <div className="space-y-2 text-sm">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-slate-500">{label}</span>
        <RunStatusBadge status={run.status} />
        {run.dry_run && <Badge tone="amber">Practice</Badge>}
      </div>
      {run.current_job && run.status === "running" && (
        <p className="text-slate-600 line-clamp-2">Working on: {run.current_job}</p>
      )}
      <p className="text-slate-600">
        {run.successful_count} applied · {run.failed_count} failed · {run.skipped_count} skipped
      </p>
      {run.started_at && <p className="text-xs text-slate-400">Started {formatRelative(run.started_at)}</p>}
    </div>
  );
}

export function HomeDashboard() {
  const [openId, setOpenId] = useState<string | null>(null);
  const { data: user } = useSession();

  const { data, isLoading, error } = useQuery({
    queryKey: ["dashboard"],
    queryFn: dashboard.stats,
    refetchInterval: 30_000,
  });

  const automationQuery = useQuery({
    queryKey: ["automation"],
    queryFn: automation.overview,
    staleTime: 20_000,
  });

  if (isLoading) return <Spinner />;
  if (error || !data) return <Alert kind="error">{errorMessage(error)}</Alert>;

  const { usage } = data;
  const mi = data.mock_interviews;
  const mockUsage = usage.mock_interviews;
  const auto = automationQuery.data;
  const firstName = user?.first_name?.trim() || "there";

  return (
    <>
      <PageHeader
        title="Dashboard"
        description={`Overview for ${usage.period} · ${usage.plan_name} plan`}
        actions={
          <ButtonLink to="/app/automation">
            <Bot className="h-4 w-4" aria-hidden /> Automation
          </ButtonLink>
        }
      />

      {usage.limit_reached && (
        <div className="mb-6">
          <Alert kind="info">
            You&apos;ve used all {usage.applications.limit} applications this month. Resets {formatDate(usage.resets_at)}.{" "}
            <Link to="/app/billing" className="font-medium underline">Upgrade for more</Link>.
          </Alert>
        </div>
      )}

      <DashboardHero
        firstName={firstName}
        stats={data}
        agentOnline={auto?.agent_online}
        readinessReady={auto?.readiness.ready}
        activeRun={data.automation.active}
      />

      <div className="mb-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard
          icon={<CheckCircle2 className="h-4 w-4" aria-hidden />}
          label="Applied this month"
          value={usage.applications.used.toLocaleString()}
          sub={
            isUnlimitedUsageCap(usage.applications.limit, "applications")
              ? "Unlimited on your plan"
              : `${usage.applications.remaining} remaining`
          }
        />
        <StatCard icon={<Target className="h-4 w-4" aria-hidden />} label="Applied today" value={data.applied_today} />
        <StatCard
          icon={<Percent className="h-4 w-4" aria-hidden />}
          label="Success rate"
          value={data.success_rate === null ? "—" : `${Math.round(data.success_rate * 100)}%`}
          sub="Applied ÷ (applied + failed)"
        />
        <StatCard
          icon={<Briefcase className="h-4 w-4" aria-hidden />}
          label="Jobs found"
          value={usage.jobs_discovered.toLocaleString()}
          sub="This month on your plan"
        />
      </div>

      <section className="mb-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {QUICK_LINKS.map((item) => (
          <Link
            key={item.to}
            to={item.to}
            className="group flex flex-col rounded-xl bg-white p-4 shadow-sm ring-1 ring-slate-200/80 transition hover:shadow-md sm:p-5"
          >
            <span className={cx("mb-3 inline-flex h-10 w-10 items-center justify-center rounded-lg bg-gradient-to-br text-white", item.accent)}>
              <item.icon className="h-5 w-5" aria-hidden />
            </span>
            <span className="font-semibold text-slate-900 group-hover:text-brand-700">{item.title}</span>
            <span className="mt-1 flex-1 text-sm text-slate-500">{item.description}</span>
            <span className="mt-3 inline-flex items-center gap-1 text-sm font-medium text-brand-600">
              Open <ArrowRight className="h-4 w-4 transition group-hover:translate-x-0.5" aria-hidden />
            </span>
          </Link>
        ))}
      </section>

      <Card
        className="mb-6"
        title="Mock interview practice"
        actions={
          <Link to="/app/mock-interview" className="text-sm font-medium text-brand-600 hover:underline">
            Open mock interviews
          </Link>
        }
      >
        {mi && mi.total > 0 ? (
          <>
            <div className="mb-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <StatCard
                icon={<Mic className="h-4 w-4" aria-hidden />}
                label="Total sessions"
                value={mi.total.toLocaleString()}
                sub={`${mi.by_status.completed ?? 0} completed`}
              />
              <StatCard
                icon={<ListChecks className="h-4 w-4" aria-hidden />}
                label="In progress"
                value={(mi.by_status.active ?? 0).toLocaleString()}
                sub={`${mi.by_status.abandoned ?? 0} abandoned`}
              />
              <StatCard
                icon={<Target className="h-4 w-4" aria-hidden />}
                label="Average score"
                value={mi.average_score == null ? "—" : `${mi.average_score}`}
                sub={mi.completed_with_score ? `From ${mi.completed_with_score} report${mi.completed_with_score === 1 ? "" : "s"}` : "Complete a session for scores"}
              />
              <StatCard
                icon={<Sparkles className="h-4 w-4" aria-hidden />}
                label="Best score"
                value={mi.best_score == null ? "—" : `${mi.best_score}`}
                sub={
                  mockUsage
                    ? isUnlimitedUsageCap(mockUsage.limit, "mock_interviews")
                      ? `${mockUsage.used} this month · unlimited plan`
                      : `${mockUsage.used} / ${mockUsage.limit} this month`
                    : undefined
                }
              />
            </div>
            {mi.recent.length > 0 && (
              <ul className="divide-y divide-slate-100 border-t border-slate-100 pt-2">
                {mi.recent.map((s) => (
                  <li key={s.id}>
                    <Link
                      to={s.status === "completed" ? `/app/mock-interview/${s.id}/report` : `/app/mock-interview/${s.id}`}
                      className="flex items-center gap-3 py-3 hover:bg-slate-50"
                    >
                      <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-violet-100 text-sm font-bold text-violet-800">
                        {s.overall_score != null ? s.overall_score : <Mic className="h-4 w-4" aria-hidden />}
                      </span>
                      <div className="min-w-0 flex-1">
                        <p className="truncate font-medium text-slate-900">
                          {s.job_title || "Mock interview"}
                          {s.company ? ` · ${s.company}` : ""}
                        </p>
                        <p className="text-sm text-slate-500">
                          {formatRelative(s.created_at)} · {s.turn_count} answer{s.turn_count === 1 ? "" : "s"}
                        </p>
                      </div>
                      <Badge tone={s.status === "completed" ? "green" : s.status === "active" ? "blue" : "amber"}>
                        {MI_STATUS_LABEL[s.status]}
                      </Badge>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </>
        ) : (
          <EmptyState title="No mock interviews yet">
            Practice with AI tied to your applications — JD and resume drive the questions.{" "}
            <Link to="/app/mock-interview" className="font-medium text-brand-600 underline">
              Start a session
            </Link>
          </EmptyState>
        )}
      </Card>

      <div className="mb-6 grid gap-6 lg:grid-cols-3">
        <Card title="Applications (last 30 days)" className="lg:col-span-2">
          <DailyChart data={data.daily} />
          <p className="mt-3 text-xs text-slate-500">
            <span className="inline-block h-2 w-2 rounded-sm bg-brand-600 align-middle" aria-hidden /> Applied{" "}
            <span className="ml-3 inline-block h-2 w-2 rounded-sm bg-red-300 align-middle" aria-hidden /> Failed
          </p>
        </Card>
        <Card title="Plan usage">
          <div className="space-y-4">
            <ProgressBar label="Applications" usageKind="applications" value={usage.applications.used} max={usage.applications.limit} />
            <ProgressBar label="Resumes" usageKind="resumes" value={usage.resumes.used} max={usage.resumes.limit} />
            {mockUsage && mockUsage.limit > 0 && (
              <ProgressBar
                label="Mock interviews"
                usageKind="mock_interviews"
                value={mockUsage.used}
                max={mockUsage.limit}
              />
            )}
            <p className="text-xs text-slate-500">
              {usage.plan_name} · resets {formatDate(usage.resets_at)}
            </p>
            <ButtonLink to="/app/billing" variant="secondary" size="sm" className="w-full">
              Manage plan
            </ButtonLink>
          </div>
        </Card>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <Card
          title="Recent applications"
          className="lg:col-span-2"
          actions={
            <Link to="/app/applications" className="text-sm font-medium text-brand-600 hover:underline">
              View all
            </Link>
          }
        >
          {data.recent_applications.length === 0 ? (
            <EmptyState title="No applications yet">
              Connect automation and start a run to see results here.
            </EmptyState>
          ) : (
            <ul className="divide-y divide-slate-100">
              {data.recent_applications.map((a) => (
                <li key={a.id}>
                  <button
                    type="button"
                    onClick={() => setOpenId(a.id)}
                    className="flex w-full items-center gap-3 py-3 text-left hover:bg-slate-50"
                  >
                    <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-slate-100 text-sm font-bold text-slate-600">
                      {(a.job.company || a.job.title)[0]?.toUpperCase() ?? "?"}
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="truncate font-medium text-slate-900">{a.job.title}</p>
                      <p className="truncate text-sm text-slate-500">
                        {a.job.company}
                        {a.job.location && ` · ${a.job.location}`}
                      </p>
                    </div>
                    <Badge tone={STATUS_TONES[a.status]}>{STATUS_LABELS[a.status]}</Badge>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <div className="space-y-6">
          <Card title="Automation">
            {auto && !auto.readiness.ready && (
              <div className="mb-4">
                <Alert kind="info">
                  <p className="font-medium">Finish setup:</p>
                  <ul className="mt-1 list-disc pl-5 text-sm">
                    {auto.readiness.problems.slice(0, 3).map((p) => (
                      <li key={p}>{p}</li>
                    ))}
                  </ul>
                  <Link to="/app/profile" className="mt-2 inline-block text-sm font-medium underline">
                    Go to setup
                  </Link>
                </Alert>
              </div>
            )}
            {auto && auto.devices.length === 0 && (
              <p className="mb-3 flex items-center gap-2 text-sm text-slate-600">
                <Laptop className="h-4 w-4 shrink-0 text-slate-400" aria-hidden />
                No computer connected —{" "}
                <Link to="/app/automation" className="font-medium text-brand-600 underline">
                  connect agent
                </Link>
              </p>
            )}
            {auto?.agent_online && (
              <p className="mb-3 text-sm text-emerald-700">Desktop agent is online and ready.</p>
            )}
            {data.automation.active ? (
              <RunSummary run={data.automation.active} label="Current run" />
            ) : data.automation.last ? (
              <RunSummary run={data.automation.last} label="Last run" />
            ) : (
              <p className="text-sm text-slate-500">No runs yet.</p>
            )}
            <ButtonLink to="/app/automation" variant="secondary" size="sm" className="mt-4 w-full">
              Open automation
            </ButtonLink>
          </Card>

          <section className="rounded-xl bg-white p-4 shadow-sm ring-1 ring-slate-200/80 sm:p-5">
            <h2 className="text-sm font-semibold text-slate-900">Pipeline snapshot</h2>
            <ul className="mt-3 space-y-2">
              {PIPELINE_STATUSES.map((s) => {
                const count = data.applications_by_status[s] ?? 0;
                return (
                  <li key={s} className="flex items-center justify-between gap-2 text-sm">
                    <Badge tone={STATUS_TONES[s]}>{STATUS_LABELS[s]}</Badge>
                    <span className="font-semibold tabular-nums text-slate-900">{count}</span>
                  </li>
                );
              })}
            </ul>
            <Link to="/app/applications" className="mt-3 inline-block text-xs font-medium text-brand-600 hover:underline">
              Full applications dashboard
            </Link>
          </section>

          {(data.top_companies.length > 0 || (data.applications_by_status.failed ?? 0) > 0) && (
            <Card title="Highlights">
              {data.top_companies.length > 0 && (
                <div className="mb-4">
                  <p className="text-xs font-medium uppercase tracking-wide text-slate-500">Top companies (applied)</p>
                  <ul className="mt-2 space-y-2 text-sm">
                    {data.top_companies.map((c) => (
                      <li key={c.company} className="flex justify-between gap-2">
                        <span className="truncate text-slate-700">{c.company}</span>
                        <span className="font-medium tabular-nums">{c.applied}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              {(data.applications_by_status.failed ?? 0) > 0 && (
                <p className="mt-3 flex items-start gap-2 text-sm text-slate-600">
                  <XCircle className="h-4 w-4 shrink-0 text-red-500 mt-0.5" aria-hidden />
                  {data.applications_by_status.failed} failed — check Applications for details.
                </p>
              )}
            </Card>
          )}
        </div>
      </div>

      <ApplicationDetailModal id={openId} onClose={() => setOpenId(null)} />
    </>
  );
}

function DashboardHero({
  firstName,
  stats,
  agentOnline,
  readinessReady,
  activeRun,
}: {
  firstName: string;
  stats: DashboardStats;
  agentOnline?: boolean;
  readinessReady?: boolean;
  activeRun: AutomationRun | null;
}) {
  let headline = `Welcome back, ${firstName}`;
  let detail = "Your command center for applications, jobs, automation, and interview practice.";

  if (activeRun) {
    headline = "Automation is running";
    detail = activeRun.current_job || "Track progress in Automation or watch applications update live.";
  } else if (stats.applied_today > 0) {
    headline = `${stats.applied_today} application${stats.applied_today === 1 ? "" : "s"} today`;
    detail = `Success rate ${stats.success_rate == null ? "—" : `${Math.round(stats.success_rate * 100)}%`} · ${stats.total_applied} total applied.`;
  } else if (readinessReady === false) {
    headline = "Complete your setup";
    detail = "Profile, preferences, and resume must be ready before your first run.";
  } else if (agentOnline) {
    headline = "Agent online — ready when you are";
    detail = "Start a run from Automation or explore jobs and mock interviews.";
  } else if (stats.total_applied === 0) {
    headline = `Hi ${firstName}, let's get started`;
    detail = "Connect the desktop agent and run automation to fill your dashboard.";
  }

  return (
    <section className="mb-6 rounded-xl bg-gradient-to-br from-brand-950 via-brand-900 to-slate-900 p-4 text-white shadow-sm ring-1 ring-brand-800/40 sm:p-5">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex min-w-0 items-start gap-3">
          <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-white/10">
            <Sparkles className="h-5 w-5 text-brand-200" aria-hidden />
          </span>
          <div className="min-w-0">
            <p className="text-lg font-semibold tracking-tight">{headline}</p>
            <p className="mt-1 text-sm text-brand-100/90">{detail}</p>
          </div>
        </div>
        <div className="flex shrink-0 flex-wrap gap-2">
          {!activeRun && (
            <ButtonLink
              to="/app/automation"
              variant="secondary"
              size="sm"
              className="border-white/20 bg-white/10 text-white hover:bg-white/20"
            >
              Start automation
            </ButtonLink>
          )}
          {activeRun && (
            <ButtonLink
              to="/app/automation"
              variant="secondary"
              size="sm"
              className="border-white/20 bg-white/10 text-white hover:bg-white/20"
            >
              View live run
            </ButtonLink>
          )}
        </div>
      </div>
    </section>
  );
}
