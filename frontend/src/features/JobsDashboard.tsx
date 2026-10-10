import { keepPreviousData, useQuery } from "@tanstack/react-query";
import {
  Briefcase,
  Building2,
  ExternalLink,
  Filter,
  Mail,
  MapPin,
  Radar,
  Search,
  Sparkles,
  TrendingUp,
} from "lucide-react";
import { useMemo, useState } from "react";
import { Select, TextInput } from "../components/form";
import { Pagination } from "../components/Pagination";
import {
  Alert,
  Badge,
  Button,
  ButtonLink,
  Card,
  cx,
  EmptyState,
  PageHeader,
  Spinner,
  StatCard,
} from "../components/ui";
import { ApplicationDetailModal } from "./ApplicationDetailModal";
import { formatRelative, safeExternalUrl, STATUS_LABELS, STATUS_TONES } from "../lib/format";
import { useDebounced } from "../lib/useDebounced";
import { errorMessage } from "../services/api";
import { dashboard, jobs, preferences } from "../services/endpoints";
import type { ApplicationStatus, JobWithApplication } from "../types";

const PAGE_SIZE = 20;

const QUICK_STATUSES: ApplicationStatus[] = ["applied", "failed", "skipped", "discovered", "queued"];

function companyInitial(name: string): string {
  const t = name.trim();
  return t ? t[0]!.toUpperCase() : "?";
}

function aggregateJobs(items: JobWithApplication[]) {
  const byStatus: Partial<Record<ApplicationStatus, number>> = {};
  const byWork: Record<string, number> = {};
  const companies: Record<string, number> = {};
  const weekAgo = Date.now() - 7 * 86_400_000;
  let thisWeek = 0;

  for (const job of items) {
    const st = job.application.status;
    byStatus[st] = (byStatus[st] ?? 0) + 1;
    if (job.work_setting) byWork[job.work_setting] = (byWork[job.work_setting] ?? 0) + 1;
    if (job.company) companies[job.company] = (companies[job.company] ?? 0) + 1;
    if (new Date(job.discovered_at).getTime() >= weekAgo) thisWeek += 1;
  }

  const topCompanies = Object.entries(companies)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 5)
    .map(([company, count]) => ({ company, count }));

  return { byStatus, byWork, topCompanies, thisWeek };
}

function discoverySeries(items: JobWithApplication[], days = 30) {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const series: { date: string; count: number }[] = [];
  for (let i = days - 1; i >= 0; i--) {
    const d = new Date(today);
    d.setDate(d.getDate() - i);
    const key = d.toISOString().slice(0, 10);
    series.push({ date: key, count: 0 });
  }
  const index = new Map(series.map((p, i) => [p.date, i]));
  for (const job of items) {
    const key = job.discovered_at.slice(0, 10);
    const i = index.get(key);
    if (i != null) series[i]!.count += 1;
  }
  return series;
}

function DiscoveryChart({ data }: { data: { date: string; count: number }[] }) {
  const max = Math.max(1, ...data.map((d) => d.count));
  const width = 600;
  const height = 120;
  const gap = 3;
  const barW = (width - gap * (data.length - 1)) / data.length;
  const total = data.reduce((s, d) => s + d.count, 0);

  return (
    <figure>
      <svg viewBox={`0 0 ${width} ${height + 20}`} className="h-40 w-full" role="img" aria-label={`Jobs discovered in the last ${data.length} days: ${total} total`}>
        {data.map((d, i) => {
          const h = (d.count / max) * height;
          const x = i * (barW + gap);
          return (
            <g key={d.date}>
              <title>{`${d.date}: ${d.count} jobs`}</title>
              <rect x={x} y={height - h} width={barW} height={h} rx={2} className="fill-brand-600" />
            </g>
          );
        })}
        <line x1={0} x2={width} y1={height} y2={height} className="stroke-slate-200" />
        {data.length > 0 && (
          <>
            <text x={0} y={height + 15} className="fill-slate-400 text-[11px]">{data[0]!.date.slice(5)}</text>
            <text x={width} y={height + 15} textAnchor="end" className="fill-slate-400 text-[11px]">
              {data[data.length - 1]!.date.slice(5)}
            </text>
          </>
        )}
      </svg>
    </figure>
  );
}

export function JobsDashboard() {
  const [q, setQ] = useState("");
  const [workSetting, setWorkSetting] = useState("");
  const [statusFilter, setStatusFilter] = useState<ApplicationStatus | "">("");
  const [page, setPage] = useState(1);
  const [filtersOpen, setFiltersOpen] = useState(true);
  const [openId, setOpenId] = useState<string | null>(null);
  const search = useDebounced(q.trim());

  const options = useQuery({ queryKey: ["preferences", "options"], queryFn: preferences.options, staleTime: Infinity });

  const statsQuery = useQuery({
    queryKey: ["jobs", "stats-pool"],
    queryFn: () => jobs.list({ page: 1, page_size: 100 }),
    staleTime: 60_000,
  });

  const dashQuery = useQuery({
    queryKey: ["dashboard"],
    queryFn: dashboard.stats,
    staleTime: 60_000,
  });

  const serverQuery = useQuery({
    queryKey: ["jobs", "list", search, workSetting, page],
    queryFn: () =>
      jobs.list({
        q: search || undefined,
        work_setting: workSetting || undefined,
        page,
        page_size: PAGE_SIZE,
      }),
    placeholderData: keepPreviousData,
    enabled: !statusFilter,
  });

  const pool = statsQuery.data?.items ?? [];
  const agg = useMemo(() => aggregateJobs(pool), [pool]);
  const discovery = useMemo(() => discoverySeries(pool), [pool]);

  const clientPage = useMemo(() => {
    if (!statusFilter) return null;
    let items = [...pool];
    if (search) {
      const s = search.toLowerCase();
      items = items.filter(
        (j) =>
          j.title.toLowerCase().includes(s) ||
          j.company.toLowerCase().includes(s),
      );
    }
    if (workSetting) items = items.filter((j) => j.work_setting === workSetting);
    items = items.filter((j) => j.application.status === statusFilter);
    const total = items.length;
    const start = (page - 1) * PAGE_SIZE;
    return {
      items: items.slice(start, start + PAGE_SIZE),
      total,
      page,
      page_size: PAGE_SIZE,
    };
  }, [statusFilter, pool, search, workSetting, page]);

  const data = statusFilter ? clientPage : serverQuery.data;
  const isLoading = statusFilter ? statsQuery.isLoading : serverQuery.isLoading;
  const error = statusFilter ? statsQuery.error : serverQuery.error;
  const isFetching = !statusFilter && serverQuery.isFetching;

  const totalJobs = serverQuery.data?.total ?? statsQuery.data?.total ?? 0;
  const appliedCount = agg.byStatus.applied ?? dashQuery.data?.applications_by_status?.applied ?? 0;

  const activeFilterCount = (search ? 1 : 0) + (workSetting ? 1 : 0) + (statusFilter ? 1 : 0);

  const toggleStatus = (s: ApplicationStatus) => {
    setStatusFilter((prev) => (prev === s ? "" : s));
    setPage(1);
  };

  return (
    <>
      <PageHeader
        title="Jobs"
        description="Every role your automation discovered — track outcomes and open postings."
        actions={
          <>
            <ButtonLink to="/app/automation" variant="secondary" className="w-full sm:w-auto">
              Automation
            </ButtonLink>
            <ButtonLink to="/app/applications" variant="secondary" className="w-full sm:w-auto">
              Applications
            </ButtonLink>
          </>
        }
      />

      <JobsHero
        totalJobs={totalJobs}
        monthDiscovered={dashQuery.data?.usage.jobs_discovered}
        thisWeek={agg.thisWeek}
        automationActive={Boolean(dashQuery.data?.automation.active)}
      />

      <div className="mb-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard
          icon={<Briefcase className="h-4 w-4" aria-hidden />}
          label="Jobs in library"
          value={totalJobs.toLocaleString()}
          sub={`${agg.thisWeek} discovered this week`}
        />
        <StatCard
          icon={<Radar className="h-4 w-4" aria-hidden />}
          label="Found this month"
          value={(dashQuery.data?.usage.jobs_discovered ?? 0).toLocaleString()}
          sub={`${dashQuery.data?.usage.plan_name ?? "Plan"} usage counter`}
        />
        <StatCard
          icon={<TrendingUp className="h-4 w-4" aria-hidden />}
          label="Applied"
          value={appliedCount.toLocaleString()}
          sub={`${agg.byStatus.failed ?? 0} failed · ${agg.byStatus.skipped ?? 0} skipped`}
        />
        <StatCard
          icon={<MapPin className="h-4 w-4" aria-hidden />}
          label="Work settings"
          value={Object.keys(agg.byWork).length.toLocaleString()}
          sub={Object.entries(agg.byWork)
            .sort((a, b) => b[1] - a[1])
            .slice(0, 2)
            .map(([k, v]) => `${k} (${v})`)
            .join(" · ") || "Mix appears as automation runs"}
        />
      </div>

      <div className="mb-6 grid gap-6 lg:grid-cols-3">
        <Card title="Discovery (last 30 days)" className="lg:col-span-2">
          {statsQuery.isLoading ? <Spinner label="Loading chart…" /> : <DiscoveryChart data={discovery} />}
        </Card>
        <div className="space-y-6">
          <section className="rounded-xl bg-white p-4 shadow-sm ring-1 ring-slate-200/80 sm:p-5">
            <h2 className="text-sm font-semibold text-slate-900">By outcome</h2>
            <p className="mt-0.5 text-xs text-slate-500">Filter the job list (recent 100 roles).</p>
            <ul className="mt-4 space-y-2">
              {QUICK_STATUSES.map((s) => {
                const count = agg.byStatus[s] ?? 0;
                const active = statusFilter === s;
                return (
                  <li key={s}>
                    <button
                      type="button"
                      onClick={() => toggleStatus(s)}
                      className={cx(
                        "flex w-full items-center justify-between gap-2 rounded-lg px-3 py-2 text-left text-sm transition-colors",
                        active ? "bg-brand-50 ring-1 ring-brand-600/30" : "hover:bg-slate-50",
                      )}
                    >
                      <Badge tone={STATUS_TONES[s]}>{STATUS_LABELS[s]}</Badge>
                      <span className="font-semibold tabular-nums text-slate-900">{count}</span>
                    </button>
                  </li>
                );
              })}
            </ul>
            {statusFilter && (
              <button
                type="button"
                onClick={() => { setStatusFilter(""); setPage(1); }}
                className="mt-3 text-xs font-medium text-brand-600 hover:underline"
              >
                Clear outcome filter
              </button>
            )}
          </section>
          {agg.topCompanies.length > 0 && (
            <Card title="Top companies">
              <ul className="space-y-2 text-sm">
                {agg.topCompanies.map((c) => (
                  <li key={c.company} className="flex items-center justify-between gap-2">
                    <span className="flex min-w-0 items-center gap-2 text-slate-700">
                      <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-slate-100 text-xs font-semibold text-slate-600">
                        {companyInitial(c.company)}
                      </span>
                      <span className="truncate">{c.company}</span>
                    </span>
                    <span className="shrink-0 font-medium tabular-nums">{c.count}</span>
                  </li>
                ))}
              </ul>
            </Card>
          )}
        </div>
      </div>

      <section className="rounded-xl bg-white shadow-sm ring-1 ring-slate-200/80">
        <header className="flex flex-col gap-3 border-b border-slate-100 px-4 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-5">
          <div>
            <h2 className="text-base font-semibold text-slate-900">Job library</h2>
            <p className="mt-0.5 text-sm text-slate-500">
              {data && !isLoading
                ? `Showing ${data.items.length} of ${data.total.toLocaleString()}${statusFilter ? " (filtered)" : ""}`
                : "Newest discoveries first"}
            </p>
          </div>
          <Button variant="secondary" size="sm" onClick={() => setFiltersOpen((v) => !v)}>
            <Filter className="h-4 w-4" aria-hidden />
            {filtersOpen ? "Hide filters" : "Filters"}
            {activeFilterCount > 0 && (
              <span className="ml-1 rounded-full bg-brand-100 px-1.5 py-0.5 text-xs font-semibold text-brand-700">{activeFilterCount}</span>
            )}
          </Button>
        </header>

        {filtersOpen && (
          <div className="border-b border-slate-100 bg-slate-50/80 px-4 py-4 sm:px-5">
            <div className="grid gap-4 sm:grid-cols-3">
              <div className="relative sm:col-span-2">
                <TextInput
                  label="Search"
                  value={q}
                  onChange={(v) => { setQ(v); setPage(1); }}
                  placeholder="Title, company, or description"
                  maxLength={200}
                  className="pl-9"
                />
                <Search className="pointer-events-none absolute bottom-2.5 left-3 h-4 w-4 text-slate-400" aria-hidden />
              </div>
              <Select
                label="Work setting"
                value={workSetting}
                onChange={(v) => { setWorkSetting(v); setPage(1); }}
                options={[{ value: "", label: "Any" }, ...(options.data?.search.on_site ?? []).map((o) => ({ value: o, label: o }))]}
              />
            </div>
          </div>
        )}

        <div className="px-4 py-4 sm:px-5">
          {isLoading ? (
            <Spinner label="Loading jobs…" />
          ) : error || !data ? (
            <Alert kind="error">{errorMessage(error)}</Alert>
          ) : data.total === 0 ? (
            <EmptyState icon={<Briefcase className="h-10 w-10" />} title="No jobs found">
              {search || workSetting || statusFilter
                ? "Try clearing filters."
                : "Jobs appear here as the automation discovers them."}
            </EmptyState>
          ) : (
            <>
              <ul className={cx("grid gap-4 md:grid-cols-2", isFetching && "opacity-70 transition-opacity")}>
                {data.items.map((job) => (
                  <JobCard key={job.id} job={job} onOpen={() => setOpenId(job.application.id)} />
                ))}
              </ul>
              <Pagination page={data.page} pageSize={data.page_size} total={data.total} onPage={setPage} />
            </>
          )}
        </div>
      </section>

      <ApplicationDetailModal id={openId} onClose={() => setOpenId(null)} />
    </>
  );
}

function JobsHero({
  totalJobs,
  monthDiscovered,
  thisWeek,
  automationActive,
}: {
  totalJobs: number;
  monthDiscovered?: number;
  thisWeek: number;
  automationActive: boolean;
}) {
  let headline = "Your job discovery hub";
  let detail = "Roles appear here as automation scans LinkedIn against your preferences.";

  if (automationActive) {
    headline = "Automation is discovering jobs";
    detail = "New cards will show up below as matches are found and processed.";
  } else if (totalJobs === 0) {
    headline = "No jobs yet";
    detail = "Start a run from Automation to populate your library.";
  } else if (thisWeek > 0) {
    headline = `${thisWeek} new jobs this week`;
    detail = `${totalJobs.toLocaleString()} total in your library · ${monthDiscovered ?? 0} counted this month on your plan.`;
  } else if (totalJobs > 0) {
    headline = `${totalJobs.toLocaleString()} jobs tracked`;
    detail = "Filter by outcome or work setting, then open a card for application details.";
  }

  return (
    <section className="mb-6 rounded-xl bg-gradient-to-br from-slate-900 via-slate-800 to-brand-900 p-4 text-white shadow-sm ring-1 ring-slate-700/50 sm:p-5">
      <div className="flex min-w-0 items-start gap-3">
        <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-white/10">
          <Sparkles className="h-5 w-5 text-brand-200" aria-hidden />
        </span>
        <div className="min-w-0">
          <p className="text-lg font-semibold tracking-tight">{headline}</p>
          <p className="mt-1 text-sm text-slate-300">{detail}</p>
        </div>
      </div>
    </section>
  );
}

function hasPublishedContact(job: JobWithApplication): boolean {
  return (job.published_contacts ?? []).some((c) => c.email?.trim() || c.phone?.trim());
}

function JobCard({ job, onOpen }: { job: JobWithApplication; onOpen: () => void }) {
  const url = safeExternalUrl(job.job_url);
  const meta = [job.location, job.employment_type, job.experience_level].filter(Boolean).join(" · ");
  const showContact = hasPublishedContact(job);

  return (
    <li className="flex flex-col rounded-xl bg-slate-50/50 p-4 ring-1 ring-slate-200/80 transition-shadow hover:shadow-md sm:p-5">
      <div className="flex items-start gap-3">
        <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-white text-sm font-bold text-slate-600 ring-1 ring-slate-200/80">
          {companyInitial(job.company || job.title)}
        </span>
        <div className="min-w-0 flex-1">
          <button type="button" onClick={onOpen} className="w-full text-left">
            <p className="line-clamp-2 font-medium text-slate-900 hover:text-brand-700">{job.title}</p>
            <p className="mt-0.5 flex items-center gap-1 truncate text-sm text-slate-500">
              <Building2 className="h-3.5 w-3.5 shrink-0 opacity-60" aria-hidden />
              {job.company || "Company not listed"}
            </p>
          </button>
          {meta && <p className="mt-1 text-xs text-slate-500">{meta}</p>}
          <div className="mt-2 flex flex-wrap gap-1.5">
            {job.work_setting && <Badge tone="blue">{job.work_setting}</Badge>}
            <Badge tone={STATUS_TONES[job.application.status]}>{STATUS_LABELS[job.application.status]}</Badge>
            {showContact && (
              <Badge tone="slate">
                <Mail className="mr-0.5 inline h-3 w-3" aria-hidden />
                Contact on posting
              </Badge>
            )}
          </div>
        </div>
      </div>
      <div className="mt-4 flex items-center justify-between border-t border-slate-200/80 pt-3 text-xs text-slate-500">
        <span>Found {formatRelative(job.discovered_at)}</span>
        <div className="flex items-center gap-2">
          <button type="button" onClick={onOpen} className="font-medium text-brand-600 hover:underline">
            Details
          </button>
          {url && (
            <a
              href={url}
              target="_blank"
              rel="noopener noreferrer nofollow"
              className="inline-flex items-center gap-1 font-medium text-slate-600 hover:text-brand-600"
            >
              Posting <ExternalLink className="h-3.5 w-3.5" aria-hidden />
            </a>
          )}
        </div>
      </div>
    </li>
  );
}
