import { useQuery } from "@tanstack/react-query";
import { Bot, Briefcase, CheckCircle2, ListChecks, Percent } from "lucide-react";
import { useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { DailyChart } from "../../components/BarChart";
import { Alert, Badge, ButtonLink, Card, EmptyState, PageHeader, ProgressBar, Spinner } from "../../components/ui";
import { ApplicationDetailModal } from "../../features/ApplicationDetailModal";
import { formatDate, formatRelative, STATUS_LABELS, STATUS_TONES } from "../../lib/format";
import { errorMessage } from "../../services/api";
import { dashboard } from "../../services/endpoints";
import type { AutomationRun } from "../../types";

function Stat({ icon, label, value, sub }: { icon: ReactNode; label: string; value: ReactNode; sub?: ReactNode }) {
  return (
    <div className="rounded-xl bg-white p-5 shadow-sm ring-1 ring-slate-200">
      <div className="flex items-center gap-2 text-sm text-slate-500">{icon}{label}</div>
      <p className="mt-2 text-3xl font-semibold tracking-tight text-slate-900">{value}</p>
      {sub && <p className="mt-1 text-xs text-slate-500">{sub}</p>}
    </div>
  );
}

const RUN_TONE = { queued: "blue", running: "blue", paused: "amber", completed: "green", failed: "red", cancelled: "slate" } as const;

function RunSummary({ run, label }: { run: AutomationRun; label: string }) {
  return (
    <div className="space-y-2 text-sm">
      <div className="flex items-center gap-2">
        <span className="text-slate-500">{label}</span>
        <Badge tone={RUN_TONE[run.status]}>{run.status}</Badge>
      </div>
      {run.current_job && run.status === "running" && <p className="text-slate-600">Working on: {run.current_job}</p>}
      <p className="text-slate-600">
        {run.successful_count} applied · {run.failed_count} failed · {run.skipped_count} skipped
      </p>
      {run.started_at && <p className="text-xs text-slate-400">Started {formatRelative(run.started_at)}</p>}
    </div>
  );
}

export function DashboardPage() {
  const [openId, setOpenId] = useState<string | null>(null);
  const { data, isLoading, error } = useQuery({ queryKey: ["dashboard"], queryFn: dashboard.stats, refetchInterval: 30_000 });
  if (isLoading) return <Spinner />;
  if (error || !data) return <Alert kind="error">{errorMessage(error)}</Alert>;
  const { usage } = data;

  return (
    <>
      <PageHeader title="Dashboard" description={`Your activity this month (${usage.period}).`}
                  actions={<ButtonLink to="/app/automation"><Bot className="h-4 w-4" aria-hidden /> Automation</ButtonLink>} />
      {usage.limit_reached && (
        <div className="mb-6">
          <Alert kind="info">
            You've used all {usage.applications.limit} applications in your plan this month. It resets on {formatDate(usage.resets_at)}.{" "}
            <Link to="/app/billing" className="font-medium underline">Upgrade for more</Link>.
          </Alert>
        </div>
      )}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Stat icon={<CheckCircle2 className="h-4 w-4" aria-hidden />} label="Applied this month"
              value={usage.applications.used} sub={`${usage.applications.remaining} left on ${usage.plan_name}`} />
        <Stat icon={<ListChecks className="h-4 w-4" aria-hidden />} label="Applied today" value={data.applied_today} />
        <Stat icon={<Percent className="h-4 w-4" aria-hidden />} label="Success rate"
              value={data.success_rate === null ? "—" : `${Math.round(data.success_rate * 100)}%`} sub="Applied ÷ attempted" />
        <Stat icon={<Briefcase className="h-4 w-4" aria-hidden />} label="Jobs found this month" value={usage.jobs_discovered} />
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-3">
        <Card title="Last 30 days" className="lg:col-span-2"><DailyChart data={data.daily} /></Card>
        <Card title="Plan usage">
          <div className="space-y-4">
            <ProgressBar label="Applications" value={usage.applications.used} max={usage.applications.limit} />
            <ProgressBar label="Resumes" value={usage.resumes.used} max={usage.resumes.limit} />
            <p className="text-xs text-slate-500">{usage.plan_name} plan · resets {formatDate(usage.resets_at)}</p>
            <ButtonLink to="/app/billing" variant="secondary" size="sm" className="w-full">Manage plan</ButtonLink>
          </div>
        </Card>
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-3">
        <Card title="Recent applications" className="lg:col-span-2"
              actions={<Link to="/app/applications" className="text-sm font-medium text-brand-600 hover:underline">View all</Link>}>
          {data.recent_applications.length === 0 ? (
            <EmptyState title="No applications yet">Once the automation runs, your applications appear here.</EmptyState>
          ) : (
            <ul className="divide-y divide-slate-100">
              {data.recent_applications.map((a) => (
                <li key={a.id}>
                  <button type="button" onClick={() => setOpenId(a.id)} className="flex w-full items-center gap-3 py-3 text-left hover:bg-slate-50">
                    <div className="min-w-0 flex-1">
                      <p className="truncate font-medium text-slate-900">{a.job.title}</p>
                      <p className="truncate text-sm text-slate-500">{a.job.company}{a.job.location && ` · ${a.job.location}`}</p>
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
            {data.automation.active ? <RunSummary run={data.automation.active} label="Current run" />
              : data.automation.last ? <RunSummary run={data.automation.last} label="Last run" />
              : <p className="text-sm text-slate-500">No runs yet.</p>}
          </Card>
          {data.top_companies.length > 0 && (
            <Card title="Top companies">
              <ul className="space-y-2 text-sm">
                {data.top_companies.map((c) => (
                  <li key={c.company} className="flex justify-between"><span className="truncate text-slate-700">{c.company}</span><span className="font-medium">{c.applied}</span></li>
                ))}
              </ul>
            </Card>
          )}
        </div>
      </div>
      <ApplicationDetailModal id={openId} onClose={() => setOpenId(null)} />
    </>
  );
}
