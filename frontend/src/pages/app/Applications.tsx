import { keepPreviousData, useQuery } from "@tanstack/react-query";
import {
  AlertCircle,
  Briefcase,
  Building2,
  CheckCircle2,
  Download,
  ExternalLink,
  Eye,
  Filter,
  ListChecks,
  Paperclip,
  Percent,
  Search,
  Sparkles,
  XCircle,
} from "lucide-react";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { DailyChart } from "../../components/BarChart";
import { ChipSelect, Select, TextInput } from "../../components/form";
import { Pagination } from "../../components/Pagination";
import { Modal } from "../../components/Modal";
import {
  Alert,
  Badge,
  Button,
  ButtonLink,
  buttonClass,
  Card,
  cx,
  EmptyState,
  PageHeader,
  Spinner,
  StatCard,
} from "../../components/ui";
import { ApplicationDetailModal, resumeKindLabel } from "../../features/ApplicationDetailModal";
import { formatDate, isUnlimitedUsageCap, safeExternalUrl, STATUS_LABELS, STATUS_TONES } from "../../lib/format";
import { useDebounced } from "../../lib/useDebounced";
import { errorMessage } from "../../services/api";
import { applications, dashboard, resumes as resumesApi, type ApplicationFilters } from "../../services/endpoints";
import { APPLICATION_STATUSES, type Application, type ApplicationStatus } from "../../types";

const PAGE_SIZE = 20;

const SORTS = [
  { value: "-created_at", label: "Newest first" },
  { value: "created_at", label: "Oldest first" },
  { value: "-applied_at", label: "Recently applied" },
  { value: "company", label: "Company A–Z" },
  { value: "title", label: "Title A–Z" },
];

const QUICK_STATUSES: ApplicationStatus[] = ["applied", "failed", "skipped", "external"];

function companyInitial(name: string): string {
  const t = name.trim();
  return t ? t[0]!.toUpperCase() : "?";
}

export function ApplicationsPage() {
  const [q, setQ] = useState("");
  const [status, setStatus] = useState<ApplicationStatus[]>([]);
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [sort, setSort] = useState("-created_at");
  const [page, setPage] = useState(1);
  const [openId, setOpenId] = useState<string | null>(null);
  const [resumeFor, setResumeFor] = useState<Application | null>(null);
  const [filtersOpen, setFiltersOpen] = useState(false);
  const search = useDebounced(q.trim());

  const filters: ApplicationFilters = {
    q: search || undefined,
    status,
    applied_from: from || undefined,
    applied_to: to || undefined,
    sort,
    page,
    page_size: PAGE_SIZE,
  };

  const statsQuery = useQuery({
    queryKey: ["dashboard"],
    queryFn: dashboard.stats,
    staleTime: 60_000,
  });

  const listQuery = useQuery({
    queryKey: ["applications", "list", filters],
    queryFn: () => applications.list(filters),
    placeholderData: keepPreviousData,
  });

  const resetPage = <T,>(setter: (v: T) => void) => (v: T) => {
    setter(v);
    setPage(1);
  };
  const labels = Object.fromEntries(APPLICATION_STATUSES.map((s) => [STATUS_LABELS[s], s])) as Record<string, ApplicationStatus>;

  const stats = statsQuery.data;
  const { data, isLoading, isFetching, error } = listQuery;

  const activeFilterCount = useMemo(
    () => (search ? 1 : 0) + status.length + (from ? 1 : 0) + (to ? 1 : 0),
    [search, status, from, to],
  );

  const toggleQuickStatus = (s: ApplicationStatus) => {
    setStatus((prev) => (prev.includes(s) ? prev.filter((x) => x !== s) : [...prev, s]));
    setPage(1);
  };

  const clearFilters = () => {
    setQ("");
    setStatus([]);
    setFrom("");
    setTo("");
    setPage(1);
  };

  return (
    <>
      <PageHeader
        title="Applications"
        description="Track every job your automation touched — applied, skipped, and failed."
        actions={
          <>
            <ButtonLink to="/app/automation" variant="secondary" className="w-full sm:w-auto">
              Automation
            </ButtonLink>
            <a href={applications.exportUrl(filters)} className={buttonClass("secondary")} download>
              <Download className="h-4 w-4" aria-hidden /> Export CSV
            </a>
          </>
        }
      />

      {statsQuery.isLoading ? (
        <div className="mb-6"><Spinner label="Loading dashboard…" /></div>
      ) : stats ? (
        <>
          <ApplicationsHero stats={stats} filteredTotal={data?.total} loadingList={listQuery.isLoading} />
          <div className="mb-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <StatCard
              icon={<CheckCircle2 className="h-4 w-4" aria-hidden />}
              label="Total applied"
              value={stats.total_applied.toLocaleString()}
              sub={`${stats.applied_today} today`}
            />
            <StatCard
              icon={<Briefcase className="h-4 w-4" aria-hidden />}
              label="This month"
              value={stats.usage.applications.used.toLocaleString()}
              sub={
                isUnlimitedUsageCap(stats.usage.applications.limit, "applications")
                  ? `${stats.usage.plan_name} · Unlimited`
                  : `${stats.usage.applications.remaining} left on ${stats.usage.plan_name}`
              }
            />
            <StatCard
              icon={<Percent className="h-4 w-4" aria-hidden />}
              label="Success rate"
              value={stats.success_rate === null ? "—" : `${Math.round(stats.success_rate * 100)}%`}
              sub="Applied ÷ (applied + failed)"
            />
            <StatCard
              icon={<XCircle className="h-4 w-4" aria-hidden />}
              label="Needs attention"
              value={(stats.applications_by_status.failed + stats.applications_by_status.skipped).toLocaleString()}
              sub={`${stats.applications_by_status.failed} failed · ${stats.applications_by_status.skipped} skipped`}
            />
          </div>

          <div className="mb-6 grid gap-6 lg:grid-cols-3">
            <Card title="Last 30 days" className="lg:col-span-2">
              <DailyChart data={stats.daily} />
              <p className="mt-3 text-xs text-slate-500">
                <span className="inline-block h-2 w-2 rounded-sm bg-brand-600 align-middle" aria-hidden /> Applied{" "}
                <span className="ml-3 inline-block h-2 w-2 rounded-sm bg-red-300 align-middle" aria-hidden /> Failed
              </p>
            </Card>
            <div className="space-y-6">
              <section className="rounded-xl bg-white p-4 shadow-sm ring-1 ring-slate-200/80 sm:p-5">
                <h2 className="text-sm font-semibold text-slate-900">By status</h2>
                <p className="mt-0.5 text-xs text-slate-500">Tap to filter the list below.</p>
                <ul className="mt-4 space-y-2">
                  {QUICK_STATUSES.map((s) => {
                    const count = stats.applications_by_status[s] ?? 0;
                    const active = status.includes(s);
                    return (
                      <li key={s}>
                        <button
                          type="button"
                          onClick={() => toggleQuickStatus(s)}
                          className={cx(
                            "flex w-full items-center justify-between gap-2 rounded-lg px-3 py-2 text-left text-sm transition-colors",
                            active ? "bg-brand-50 ring-1 ring-brand-600/30" : "hover:bg-slate-50",
                          )}
                        >
                          <span className="flex items-center gap-2">
                            <Badge tone={STATUS_TONES[s]}>{STATUS_LABELS[s]}</Badge>
                          </span>
                          <span className="font-semibold tabular-nums text-slate-900">{count}</span>
                        </button>
                      </li>
                    );
                  })}
                </ul>
                {status.length > 0 && (
                  <button type="button" onClick={() => { setStatus([]); setPage(1); }} className="mt-3 text-xs font-medium text-brand-600 hover:underline">
                    Clear status filters
                  </button>
                )}
              </section>
              {stats.top_companies.length > 0 && (
                <Card title="Top companies">
                  <ul className="space-y-2 text-sm">
                    {stats.top_companies.map((c) => (
                      <li key={c.company} className="flex items-center justify-between gap-2">
                        <span className="flex min-w-0 items-center gap-2 text-slate-700">
                          <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-slate-100 text-xs font-semibold text-slate-600">
                            {companyInitial(c.company)}
                          </span>
                          <span className="truncate">{c.company}</span>
                        </span>
                        <span className="shrink-0 font-medium tabular-nums">{c.applied}</span>
                      </li>
                    ))}
                  </ul>
                </Card>
              )}
            </div>
          </div>
        </>
      ) : statsQuery.error ? (
        <div className="mb-6"><Alert kind="error">{errorMessage(statsQuery.error)}</Alert></div>
      ) : null}

      <section className="rounded-xl bg-white shadow-sm ring-1 ring-slate-200/80">
        <header className="flex flex-col gap-3 border-b border-slate-100 px-4 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-5">
          <div>
            <h2 className="text-base font-semibold text-slate-900">All applications</h2>
            <p className="mt-0.5 text-sm text-slate-500">
              {data && !isLoading ? (
                <>
                  Showing {data.items.length} of {data.total.toLocaleString()}
                  {activeFilterCount > 0 && " · filters active"}
                </>
              ) : (
                "Search and filter your history"
              )}
            </p>
          </div>
          <Button variant="secondary" size="sm" onClick={() => setFiltersOpen((v) => !v)} className="shrink-0">
            <Filter className="h-4 w-4" aria-hidden />
            {filtersOpen ? "Hide filters" : "Filters"}
            {activeFilterCount > 0 && (
              <span className="ml-1 rounded-full bg-brand-100 px-1.5 py-0.5 text-xs font-semibold text-brand-700">{activeFilterCount}</span>
            )}
          </Button>
        </header>

        {filtersOpen && (
          <div className="border-b border-slate-100 bg-slate-50/80 px-4 py-4 sm:px-5">
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <div className="relative sm:col-span-2">
                <TextInput label="Search" value={q} onChange={resetPage(setQ)} placeholder="Title, company, or location" maxLength={200} className="pl-9" />
                <Search className="pointer-events-none absolute bottom-2.5 left-3 h-4 w-4 text-slate-400" aria-hidden />
              </div>
              <TextInput label="Applied from" type="date" value={from} onChange={resetPage(setFrom)} max={to || undefined} />
              <TextInput label="Applied to" type="date" value={to} onChange={resetPage(setTo)} min={from || undefined} />
            </div>
            <div className="mt-4 flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
              <ChipSelect
                label="Status"
                options={APPLICATION_STATUSES.map((s) => STATUS_LABELS[s])}
                value={status.map((s) => STATUS_LABELS[s])}
                onChange={(v) => {
                  setStatus(v.map((l) => labels[l]));
                  setPage(1);
                }}
              />
              <div className="flex w-full flex-col gap-2 sm:flex-row sm:items-end lg:w-auto">
                <div className="w-full lg:w-56">
                  <Select label="Sort" value={sort} onChange={resetPage(setSort)} options={SORTS} />
                </div>
                {activeFilterCount > 0 && (
                  <Button variant="ghost" size="sm" onClick={clearFilters} className="shrink-0">
                    Clear all
                  </Button>
                )}
              </div>
            </div>
          </div>
        )}

        <div className="px-4 py-4 sm:px-5">
          {isLoading ? (
            <Spinner label="Loading applications…" />
          ) : error || !data ? (
            <Alert kind="error">{errorMessage(error)}</Alert>
          ) : data.total === 0 ? (
            <EmptyState icon={<ListChecks className="h-10 w-10" />} title="No applications found">
              {search || status.length || from || to ? "Try clearing some filters." : "Run automation to start applying to jobs."}
            </EmptyState>
          ) : (
            <>
              <ul className={cx("divide-y divide-slate-100", isFetching && "opacity-70 transition-opacity")}>
                {data.items.map((a) => (
                  <ApplicationRow key={a.id} app={a} onOpen={() => setOpenId(a.id)} onResume={() => setResumeFor(a)} />
                ))}
              </ul>
              <Pagination page={data.page} pageSize={data.page_size} total={data.total} onPage={setPage} />
            </>
          )}
        </div>
      </section>

      <ApplicationDetailModal id={openId} onClose={() => setOpenId(null)} />
      <Modal
        open={!!resumeFor}
        onClose={() => setResumeFor(null)}
        title="Resume"
        footer={<Button variant="secondary" onClick={() => setResumeFor(null)}>Close</Button>}
      >
        {resumeFor?.resume ? (
          <div className="space-y-3">
            <div>
              <p className="font-medium text-slate-900">{resumeFor.resume.name}</p>
              <p className="mt-1 text-sm text-slate-600">{resumeKindLabel(resumeFor.resume)}</p>
              <p className="mt-1 text-xs text-slate-500">{resumeFor.resume.filename}</p>
              {(resumeFor.resume.job_title || resumeFor.resume.company) && (
                <p className="mt-1 text-sm text-slate-600">
                  Prepared for {[resumeFor.resume.job_title, resumeFor.resume.company].filter(Boolean).join(" at ")}
                </p>
              )}
            </div>
            <a
              href={resumesApi.downloadUrl(resumeFor.resume.id)}
              className="inline-flex items-center gap-1 font-medium text-brand-600 hover:underline"
            >
              <Download className="h-4 w-4" aria-hidden /> Download resume
            </a>
            {(resumeFor.generated_resumes?.length ?? 0) > 1 && (
              <ul className="divide-y divide-slate-100 rounded-lg ring-1 ring-slate-200">
                {resumeFor.generated_resumes!.filter((item) => item.id !== resumeFor.resume!.id).map((item) => (
                  <li key={item.id} className="flex items-center justify-between gap-3 px-3 py-2">
                    <span className="min-w-0 truncate text-sm text-slate-700">{item.name}</span>
                    <a href={resumesApi.downloadUrl(item.id)} className="shrink-0 text-sm font-medium text-brand-600 hover:underline">
                      Download
                    </a>
                  </li>
                ))}
              </ul>
            )}
          </div>
        ) : (
          <p>No resume was attached to this application.</p>
        )}
      </Modal>
    </>
  );
}

function ApplicationsHero({
  stats,
  filteredTotal,
  loadingList,
}: {
  stats: NonNullable<Awaited<ReturnType<typeof dashboard.stats>>>;
  filteredTotal: number | undefined;
  loadingList: boolean;
}) {
  const run = stats.automation.active ?? stats.automation.last;
  let headline = "Your application pipeline";
  let detail = `${stats.total_applied.toLocaleString()} successful applications on record.`;

  if (stats.automation.active) {
    headline = "Automation is running";
    detail = stats.automation.active.current_job || "New results will show up here as jobs are processed.";
  } else if (stats.applications_by_status.failed > 0 && stats.applied_today === 0) {
    headline = "Review failed applications";
    detail = `${stats.applications_by_status.failed} failed — filter by Failed to see what blocked submission.`;
  } else if (stats.applied_today > 0) {
    headline = `${stats.applied_today} applied today`;
    detail = "Nice momentum — open any row for job details and the resume used.";
  }

  if (!loadingList && filteredTotal !== undefined && filteredTotal !== stats.total_applied) {
    detail = `${filteredTotal.toLocaleString()} match your current filters.`;
  }

  return (
    <section className="mb-6 rounded-xl bg-gradient-to-br from-brand-900 via-brand-800 to-slate-900 p-4 text-white shadow-sm ring-1 ring-brand-700/40 sm:p-5">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex min-w-0 items-start gap-3">
          <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-white/10">
            <Sparkles className="h-5 w-5 text-brand-200" aria-hidden />
          </span>
          <div className="min-w-0">
            <p className="text-lg font-semibold tracking-tight">{headline}</p>
            <p className="mt-1 text-sm text-brand-100/90">{detail}</p>
            {run && (
              <p className="mt-2 text-xs text-brand-200/80">
                Last run: {run.successful_count} applied · {run.failed_count} failed · {run.skipped_count} skipped
              </p>
            )}
          </div>
        </div>
        {stats.usage.limit_reached && (
          <div className="flex items-start gap-2 rounded-lg bg-amber-500/20 px-3 py-2 text-sm text-amber-50 ring-1 ring-amber-400/30">
            <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" aria-hidden />
            <span>
              Monthly application limit reached.{" "}
              <Link to="/app/billing" className="font-medium underline">Upgrade</Link>
            </span>
          </div>
        )}
      </div>
    </section>
  );
}

function ApplicationRow({
  app,
  onOpen,
  onResume,
}: {
  app: Application;
  onOpen: () => void;
  onResume: () => void;
}) {
  const jobUrl = safeExternalUrl(app.job.job_url);
  const meta = [app.job.location, app.job.work_setting, app.job.employment_type].filter(Boolean).join(" · ");

  return (
    <li className="group py-4 first:pt-0 last:pb-0">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex min-w-0 flex-1 gap-3">
          <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-slate-100 text-sm font-bold text-slate-600 ring-1 ring-slate-200/80">
            {companyInitial(app.job.company || app.job.title)}
          </span>
          <div className="min-w-0 flex-1">
            <button type="button" onClick={onOpen} className="w-full text-left">
              <span className="line-clamp-2 font-medium text-slate-900 group-hover:text-brand-700">{app.job.title}</span>
              <span className="mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-sm text-slate-500">
                {app.job.company && (
                  <span className="inline-flex items-center gap-1">
                    <Building2 className="h-3.5 w-3.5 shrink-0 opacity-60" aria-hidden />
                    {app.job.company}
                  </span>
                )}
                {meta && <span className="text-slate-400">· {meta}</span>}
              </span>
            </button>
            {app.failure_reason && app.status === "failed" && (
              <p className="mt-1 line-clamp-2 text-xs text-red-700">{app.failure_reason}</p>
            )}
            {app.resume?.generated_by === "ai" && app.resume.match_score != null && (
              <p className="mt-1 text-xs text-slate-500">
                AI resume · {app.resume.match_score}% match
                {app.resume.fit_score != null && ` · ${app.resume.fit_score}% fit`}
              </p>
            )}
          </div>
        </div>
        <div className="flex shrink-0 flex-wrap items-center gap-2 sm:gap-3 lg:justify-end">
          <Badge tone={STATUS_TONES[app.status]}>{STATUS_LABELS[app.status]}</Badge>
          <span className="inline-flex items-center gap-1 whitespace-nowrap text-sm text-slate-500">
            {formatDate(app.applied_at)}
            {app.resume && (
              <button
                type="button"
                title={app.resume.name}
                aria-label={`Open resume ${app.resume.name}`}
                className="rounded-md p-1 text-brand-600 hover:bg-brand-50"
                onClick={onResume}
              >
                <Paperclip className="h-4 w-4" aria-hidden />
              </button>
            )}
          </span>
          {jobUrl && (
            <a
              href={jobUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="rounded-lg p-2 text-slate-400 hover:bg-slate-100 hover:text-slate-700"
              aria-label={`Open job posting for ${app.job.title}`}
            >
              <ExternalLink className="h-4 w-4" aria-hidden />
            </a>
          )}
          <Button size="sm" variant="secondary" onClick={onOpen}>
            <Eye className="h-4 w-4" aria-hidden /> View
          </Button>
        </div>
      </div>
    </li>
  );
}
