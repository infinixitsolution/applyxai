import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft,
  Briefcase,
  Building2,
  CheckCircle2,
  ExternalLink,
  FileText,
  Globe,
  Loader2,
  Mail,
  MapPin,
  Phone,
  RefreshCw,
  Search,
  SkipForward,
  Users,
  XCircle,
} from "lucide-react";
import { useMemo, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { useToast } from "../../components/Toast";
import { AdminTabNav, Alert, Badge, Button, Card, EmptyState, Spinner, cx } from "../../components/ui";
import { formatDateTime, safeExternalUrl, STATUS_LABELS, STATUS_TONES } from "../../lib/format";
import { errorMessage } from "../../services/api";
import { admin } from "../../services/endpoints";
import { APPLICATION_STATUSES, type ApplicationStatus } from "../../types";
import { Stat, Table, Td, UserLink } from "./shared";

const ORIGIN_LABEL = { posting: "Posting", web: "Web", both: "Posting + web" } as const;

const PLATFORM_LABEL: Record<string, string> = {
  linkedin: "LinkedIn",
  naukri: "Naukri",
};

const COMPANY_TABS = ["overview", "jobs", "applications", "contacts", "candidates", "sources"] as const;
type CompanyTab = (typeof COMPANY_TABS)[number];

const OUTCOME_META: { key: ApplicationStatus; label: string; tone: "emerald" | "sky" | "amber" | "rose" | "slate"; icon: typeof CheckCircle2 }[] = [
  { key: "applied", label: "Applied", tone: "emerald", icon: CheckCircle2 },
  { key: "discovered", label: "Discovered", tone: "sky", icon: Search },
  { key: "skipped", label: "Skipped", tone: "amber", icon: SkipForward },
  { key: "failed", label: "Failed", tone: "rose", icon: XCircle },
];

const PROFILING_BADGE: Record<string, { label: string; tone: "slate" | "blue" | "green" | "red" }> = {
  idle: { label: "Not profiled", tone: "slate" },
  running: { label: "Profiling…", tone: "blue" },
  ready: { label: "Web profile ready", tone: "green" },
  failed: { label: "Profiling failed", tone: "red" },
};

function platformLabel(platform?: string) {
  if (!platform) return "LinkedIn";
  return PLATFORM_LABEL[platform.toLowerCase()] ?? platform;
}

function FunnelBar({ breakdown }: { breakdown: Record<string, number> }) {
  const total = OUTCOME_META.reduce((n, row) => n + (breakdown[row.key] ?? 0), 0);
  if (total <= 0) {
    return <p className="text-sm text-slate-500">No automation outcomes yet for this company.</p>;
  }
  return (
    <div className="space-y-3">
      <div className="flex h-3 overflow-hidden rounded-full bg-slate-100">
        {OUTCOME_META.map((row) => {
          const count = breakdown[row.key] ?? 0;
          if (count <= 0) return null;
          const pct = (count / total) * 100;
          const color =
            row.tone === "emerald"
              ? "bg-emerald-500"
              : row.tone === "sky"
                ? "bg-sky-500"
                : row.tone === "amber"
                  ? "bg-amber-400"
                  : row.tone === "rose"
                    ? "bg-rose-500"
                    : "bg-slate-400";
          return (
            <div
              key={row.key}
              className={cx(color, "min-w-[2px] transition-all")}
              style={{ width: `${pct}%` }}
              title={`${row.label}: ${count}`}
            />
          );
        })}
      </div>
      <ul className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
        {OUTCOME_META.map((row) => {
          const count = breakdown[row.key] ?? 0;
          const Icon = row.icon;
          return (
            <li key={row.key} className="flex items-center gap-2 rounded-lg border border-slate-100 px-3 py-2 text-sm">
              <Icon className="h-4 w-4 shrink-0 text-slate-400" aria-hidden />
              <span className="text-slate-600">{row.label}</span>
              <span className="ml-auto font-semibold tabular-nums text-slate-900">{count}</span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

export function AdminCompanyPage() {
  const { company: encoded = "" } = useParams();
  const name = decodeURIComponent(encoded);
  const [searchParams, setSearchParams] = useSearchParams();
  const requested = searchParams.get("tab") as CompanyTab | null;
  const tab: CompanyTab = requested && COMPANY_TABS.includes(requested) ? requested : "overview";
  const setTab = (next: CompanyTab) => setSearchParams(next === "overview" ? {} : { tab: next }, { replace: true });

  const client = useQueryClient();
  const toast = useToast();
  const [contactQuery, setContactQuery] = useState("");
  const [appStatus, setAppStatus] = useState<ApplicationStatus | "">("");

  const { data, isLoading, error, isFetching, refetch } = useQuery({
    queryKey: ["admin", "company", name],
    queryFn: () => admin.company(name),
    enabled: Boolean(name),
    refetchInterval: (q) => (q.state.data?.profiling?.status === "running" ? 4000 : false),
  });

  const enrich = useMutation({
    mutationFn: () => admin.enrichCompany(name),
    onSuccess: (updated) => {
      client.setQueryData(["admin", "company", name], updated);
      toast.success("HR profiling started — results appear in a minute.");
    },
    onError: (e) => toast.error(errorMessage(e)),
  });

  const profiling = data?.profiling;
  const profilingRunning = profiling?.status === "running" || enrich.isPending;
  const profilingBadge = PROFILING_BADGE[profiling?.status ?? "idle"] ?? PROFILING_BADGE.idle;

  const filteredContacts = useMemo(() => {
    const list = data?.contacts ?? [];
    const q = contactQuery.trim().toLowerCase();
    if (!q) return list;
    return list.filter(
      (c) =>
        c.name.toLowerCase().includes(q) ||
        c.email.toLowerCase().includes(q) ||
        c.phone.includes(q) ||
        (c.role ?? "").toLowerCase().includes(q),
    );
  }, [data?.contacts, contactQuery]);

  const filteredApplications = useMemo(() => {
    const list = data?.applications ?? [];
    if (!appStatus) return list;
    return list.filter((a) => a.status === appStatus);
  }, [data?.applications, appStatus]);

  const breakdown = data?.status_breakdown ?? {};
  const outcomeTotal = OUTCOME_META.reduce((n, row) => n + (breakdown[row.key] ?? 0), 0);
  const appsTotal = data?.applications_total ?? data?.applications?.length ?? 0;
  const contactsTotal = data?.contact_stats?.total ?? data?.contacts.length ?? 0;
  const candidatesTotal = data?.candidates?.length ?? data?.users ?? 0;
  const sourcesTotal = (data?.source_pages?.length ?? 0) + (data?.external_job_links?.length ?? 0);

  const tabs = useMemo(
    () =>
      data
        ? [
            { id: "overview" as const, label: "Overview" },
            { id: "jobs" as const, label: `Jobs (${data.jobs})` },
            { id: "applications" as const, label: `Applications (${appsTotal})` },
            { id: "contacts" as const, label: `Contacts (${contactsTotal})` },
            { id: "candidates" as const, label: `Candidates (${candidatesTotal})` },
            { id: "sources" as const, label: `Sources (${sourcesTotal})` },
          ]
        : [],
    [data, appsTotal, contactsTotal, candidatesTotal, sourcesTotal],
  );

  return (
    <>
      <Link
        to="/admin/companies"
        className="mb-4 inline-flex items-center gap-1.5 text-sm font-medium text-slate-600 hover:text-slate-900"
      >
        <ArrowLeft className="h-4 w-4" aria-hidden /> All companies
      </Link>
      {isLoading ? (
        <Spinner />
      ) : error || !data ? (
        <Alert kind="error">{errorMessage(error)}</Alert>
      ) : (
        <>
          <div
            className={cx(
              "mb-6 overflow-hidden rounded-2xl border border-slate-200/80 bg-gradient-to-br from-slate-50 via-white to-brand-50/40 p-6 shadow-sm sm:p-8",
              isFetching && "opacity-90 transition-opacity",
            )}
          >
            <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
              <div className="flex gap-4">
                <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-xl bg-white shadow-sm ring-1 ring-slate-200/80">
                  <Building2 className="h-7 w-7 text-brand-600" aria-hidden />
                </div>
                <div>
                  <div className="flex flex-wrap items-center gap-2">
                    <h1 className="text-2xl font-bold tracking-tight text-slate-900 sm:text-3xl">{data.company}</h1>
                    <Badge tone={profilingBadge.tone}>{profilingBadge.label}</Badge>
                  </div>
                  <p className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-slate-600">
                    {data.locations.length > 0 && (
                      <span className="inline-flex items-center gap-1">
                        <MapPin className="h-3.5 w-3.5 text-slate-400" aria-hidden />
                        {data.locations.join(" · ")}
                      </span>
                    )}
                    {data.last_seen && <span>Last activity {formatDateTime(data.last_seen)}</span>}
                  </p>
                </div>
              </div>
              <div className="flex flex-wrap gap-2 lg:justify-end">
                <Button variant="secondary" onClick={() => void refetch()} disabled={isFetching}>
                  <RefreshCw className={cx("h-4 w-4", isFetching && "animate-spin")} aria-hidden /> Refresh
                </Button>
                <Button variant="secondary" onClick={() => enrich.mutate()} disabled={profilingRunning} loading={profilingRunning}>
                  {profilingRunning ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> Profiling…
                    </>
                  ) : (
                    <>
                      <Globe className="h-4 w-4" aria-hidden /> Run HR profiling
                    </>
                  )}
                </Button>
              </div>
            </div>
          </div>

          {profiling?.status === "failed" && profiling.error && (
            <div className="mb-4">
              <Alert kind="error">{profiling.error}</Alert>
            </div>
          )}

          <AdminTabNav tabs={tabs} value={tab} onChange={setTab} ariaLabel="Company dashboard sections" />

          <div role="tabpanel" className="min-h-[20rem]">
            {tab === "overview" && (
              <div className="space-y-6">
                <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                  <Stat icon={<Briefcase className="h-4 w-4" />} label="Unique jobs" value={data.jobs} sub={`${outcomeTotal} total outcomes`} />
                  <Stat
                    icon={<CheckCircle2 className="h-4 w-4" />}
                    label="Applications submitted"
                    value={data.applied}
                    sub={`${breakdown.skipped ?? 0} skipped · ${breakdown.failed ?? 0} failed`}
                  />
                  <Stat
                    icon={<Users className="h-4 w-4" />}
                    label="Candidates"
                    value={candidatesTotal}
                    sub={`${data.search_filters} search filter${data.search_filters === 1 ? "" : "s"}`}
                  />
                  <Stat
                    icon={<Mail className="h-4 w-4" />}
                    label="HR contacts"
                    value={contactsTotal}
                    sub={`${data.external_job_links?.length ?? 0} web job links · ${profiling?.sources_scraped ?? 0} pages scanned`}
                  />
                </div>
                <Card title="Automation funnel">
                  <FunnelBar breakdown={breakdown} />
                </Card>
                <Card title="At a glance">
                  <dl className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 text-sm">
                    <div>
                      <dt className="text-slate-500">Web profiling</dt>
                      <dd className="mt-1 font-medium text-slate-900">
                        {profiling?.last_enriched_at ? formatDateTime(profiling.last_enriched_at) : "Not run yet"}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-slate-500">Posting contacts</dt>
                      <dd className="mt-1 font-medium text-slate-900">{data.contact_stats?.from_postings ?? 0}</dd>
                    </div>
                    <div>
                      <dt className="text-slate-500">Web contacts</dt>
                      <dd className="mt-1 font-medium text-slate-900">{data.contact_stats?.from_web ?? 0}</dd>
                    </div>
                  </dl>
                </Card>
              </div>
            )}

            {tab === "jobs" && (
              <Card title="Jobs from automation">
                {data.job_list.length === 0 ? (
                  <EmptyState icon={<Briefcase className="h-10 w-10" />} title="No jobs yet">
                    Runs have not opened a posting at this company yet, or titles use a different spelling.
                  </EmptyState>
                ) : (
                  <Table head={["Job", "Source", "Location", "Applied", "Other", "Users", "First seen", "Last seen"]}>
                    {data.job_list.map((job) => {
                      const url = safeExternalUrl(job.job_url);
                      return (
                        <tr key={job.id} className="hover:bg-slate-50/80">
                          <Td className="max-w-xs font-medium text-slate-900">
                            {url ? (
                              <a
                                href={url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="inline-flex items-start gap-1 hover:text-brand-700"
                              >
                                <span>{job.title}</span>
                                <ExternalLink className="mt-0.5 h-3.5 w-3.5 shrink-0 text-slate-400" aria-hidden />
                              </a>
                            ) : (
                              job.title
                            )}
                          </Td>
                          <Td>
                            <Badge tone="slate">{platformLabel(job.platform)}</Badge>
                          </Td>
                          <Td className="max-w-[10rem] text-slate-600">{job.location || "—"}</Td>
                          <Td className="font-medium text-emerald-700">{job.applied}</Td>
                          <Td className="text-slate-600">{job.other}</Td>
                          <Td>{job.users}</Td>
                          <Td className="whitespace-nowrap text-slate-600">{job.discovered_at ? formatDateTime(job.discovered_at) : "—"}</Td>
                          <Td className="whitespace-nowrap text-slate-600">{job.last_seen ? formatDateTime(job.last_seen) : "—"}</Td>
                        </tr>
                      );
                    })}
                  </Table>
                )}
              </Card>
            )}

            {tab === "applications" && (
              <Card title="Applications">
                <div className="mb-4 flex flex-wrap items-center gap-2">
                  <button
                    type="button"
                    onClick={() => setAppStatus("")}
                    className={cx(
                      "rounded-full px-3 py-1 text-xs font-medium ring-1 ring-inset transition-colors",
                      appStatus === "" ? "bg-slate-900 text-white ring-slate-900" : "bg-white text-slate-600 ring-slate-200 hover:bg-slate-50",
                    )}
                  >
                    All ({appsTotal})
                  </button>
                  {APPLICATION_STATUSES.filter((s) => (breakdown[s] ?? 0) > 0).map((s) => (
                    <button
                      key={s}
                      type="button"
                      onClick={() => setAppStatus(s)}
                      className={cx(
                        "rounded-full px-3 py-1 text-xs font-medium ring-1 ring-inset transition-colors",
                        appStatus === s ? "bg-brand-600 text-white ring-brand-600" : "bg-white text-slate-600 ring-slate-200 hover:bg-slate-50",
                      )}
                    >
                      {STATUS_LABELS[s]} ({breakdown[s]})
                    </button>
                  ))}
                </div>
                {(data.applications?.length ?? 0) === 0 ? (
                  <EmptyState icon={<FileText className="h-10 w-10" />} title="No applications yet">
                    Automation has not recorded any outcomes for this company.
                  </EmptyState>
                ) : filteredApplications.length === 0 ? (
                  <EmptyState icon={<FileText className="h-10 w-10" />} title="No matches">
                    No applications with this status.
                  </EmptyState>
                ) : (
                  <>
                    {appsTotal > (data.applications?.length ?? 0) && (
                      <p className="mb-3 text-xs text-slate-500">
                        Showing latest {data.applications!.length} of {appsTotal} applications.
                      </p>
                    )}
                    <Table head={["Job", "Candidate", "Status", "Updated", "Notes"]}>
                      {filteredApplications.map((a) => {
                        const url = safeExternalUrl(a.job.job_url);
                        return (
                          <tr key={a.id} className="hover:bg-slate-50/80">
                            <Td className="max-w-xs">
                              <p className="font-medium text-slate-900">{a.job.title}</p>
                              <p className="mt-0.5 text-xs text-slate-500">
                                {platformLabel(a.job.platform)}
                                {a.job.location ? ` · ${a.job.location}` : ""}
                              </p>
                              {url && (
                                <a href={url} target="_blank" rel="noopener noreferrer" className="mt-1 inline-flex items-center gap-1 text-xs text-brand-700 hover:underline">
                                  View posting <ExternalLink className="h-3 w-3" aria-hidden />
                                </a>
                              )}
                            </Td>
                            <Td>
                              <UserLink id={a.user_id} email={a.user_email} />
                            </Td>
                            <Td>
                              <Badge tone={STATUS_TONES[a.status]}>{STATUS_LABELS[a.status]}</Badge>
                            </Td>
                            <Td className="whitespace-nowrap text-slate-600">{a.updated_at ? formatDateTime(a.updated_at) : "—"}</Td>
                            <Td className="max-w-xs text-xs text-slate-600">
                              {a.status === "applied" && a.applied_at && (
                                <span className="block text-emerald-700">Applied {formatDateTime(a.applied_at)}</span>
                              )}
                              {a.failure_reason || "—"}
                            </Td>
                          </tr>
                        );
                      })}
                    </Table>
                  </>
                )}
              </Card>
            )}

            {tab === "contacts" && (
              <Card title="Contact directory">
                <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                  <p className="text-sm text-slate-500">
                    HR emails and phones from postings and web search. Applicant accounts are never listed.
                    {(data.contact_stats?.from_postings ?? 0) > 0 && (
                      <span className="mt-1 block text-xs text-slate-400">
                        {data.contact_stats!.from_postings} from postings · {data.contact_stats!.from_web} from web
                      </span>
                    )}
                  </p>
                  {data.contacts.length > 4 && (
                    <label className="relative block w-full sm:max-w-xs">
                      <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" aria-hidden />
                      <input
                        type="search"
                        placeholder="Filter contacts…"
                        value={contactQuery}
                        onChange={(e) => setContactQuery(e.target.value)}
                        className="w-full rounded-lg border border-slate-200 py-2 pl-9 pr-3 text-sm focus:border-brand-400 focus:outline-none focus:ring-2 focus:ring-brand-100"
                      />
                    </label>
                  )}
                </div>
                {filteredContacts.length === 0 ? (
                  <EmptyState icon={<Phone className="h-10 w-10" />} title={data.contacts.length ? "No matches" : "No contacts yet"}>
                    {data.contacts.length
                      ? "Try a different search term."
                      : "Run HR profiling or run automation so postings can surface contacts."}
                  </EmptyState>
                ) : (
                  <Table head={["Name", "Email", "Phone", "Source", "Found on"]}>
                    {filteredContacts.map((c, index) => {
                      const profile = safeExternalUrl(c.link);
                      const origin = c.origin ? ORIGIN_LABEL[c.origin] ?? c.origin : "—";
                      return (
                        <tr key={`${c.email}-${c.phone}-${c.name}-${index}`} className="hover:bg-slate-50/80">
                          <Td>
                            {profile ? (
                              <a href={profile} target="_blank" rel="noopener noreferrer" className="font-medium text-slate-900 hover:text-brand-700">
                                {c.name || "Hiring contact"}
                              </a>
                            ) : (
                              <span className="font-medium text-slate-900">{c.name || "—"}</span>
                            )}
                            {c.role && <p className="mt-1 text-xs text-slate-500">{c.role}</p>}
                          </Td>
                          <Td className="max-w-[14rem] truncate">
                            {c.email ? (
                              <a className="text-brand-700 hover:underline" href={`mailto:${c.email}`}>
                                {c.email}
                              </a>
                            ) : (
                              <span className="text-slate-400">—</span>
                            )}
                          </Td>
                          <Td className="whitespace-nowrap">
                            {c.phone ? (
                              <a className="inline-flex items-center gap-1 text-slate-900 hover:text-brand-700" href={`tel:${c.phone.replace(/\s/g, "")}`}>
                                <Phone className="h-3.5 w-3.5 text-slate-400" aria-hidden />
                                {c.phone}
                              </a>
                            ) : (
                              <span className="text-slate-400">—</span>
                            )}
                          </Td>
                          <Td>
                            <Badge tone={c.origin === "web" ? "blue" : c.origin === "both" ? "green" : "slate"}>{origin}</Badge>
                          </Td>
                          <Td className="max-w-[12rem] text-slate-600">
                            {c.jobs.map((job) => job.title).join(", ")}
                            {(c.sources?.length ?? 0) > 0 && (
                              <ul className="mt-1 list-none space-y-0.5 text-xs">
                                {c.sources!.slice(0, 2).map((s) => {
                                  const src = safeExternalUrl(s.url);
                                  return (
                                    <li key={s.url}>
                                      {src ? (
                                        <a href={src} target="_blank" rel="noopener noreferrer" className="block max-w-[14rem] truncate text-brand-600 hover:underline">
                                          {s.title || "Web page"}
                                        </a>
                                      ) : (
                                        s.title
                                      )}
                                    </li>
                                  );
                                })}
                              </ul>
                            )}
                            {!c.jobs.length && !(c.sources?.length) && "—"}
                          </Td>
                        </tr>
                      );
                    })}
                  </Table>
                )}
              </Card>
            )}

            {tab === "candidates" && (
              <Card title="Candidates">
                <p className="mb-4 text-sm text-slate-500">
                  Users who ran automation on this company or listed it in search preferences.
                </p>
                {(data.candidates?.length ?? 0) === 0 ? (
                  <EmptyState icon={<Users className="h-10 w-10" />} title="No candidates yet">
                    Nobody has targeted or applied to this company in the app.
                  </EmptyState>
                ) : (
                  <Table head={["Candidate", "Applications", "Submitted", "Search filter", "Last activity"]}>
                    {data.candidates!.map((c) => (
                      <tr key={c.user_id} className="hover:bg-slate-50/80">
                        <Td>
                          <UserLink id={c.user_id} email={c.user_email} />
                        </Td>
                        <Td className="font-medium tabular-nums text-slate-900">{c.applications}</Td>
                        <Td className="font-medium tabular-nums text-emerald-700">{c.applied}</Td>
                        <Td>{c.in_search_filter ? <Badge tone="brand">Yes</Badge> : <span className="text-slate-400">—</span>}</Td>
                        <Td className="whitespace-nowrap text-slate-600">{c.last_seen ? formatDateTime(c.last_seen) : "—"}</Td>
                      </tr>
                    ))}
                  </Table>
                )}
              </Card>
            )}

            {tab === "sources" && (
              <div className="space-y-6">
                <Card title="Web profiling">
                  <dl className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4 text-sm">
                    <div>
                      <dt className="text-slate-500">Status</dt>
                      <dd className="mt-1">
                        <Badge tone={profilingBadge.tone}>{profilingBadge.label}</Badge>
                      </dd>
                    </div>
                    <div>
                      <dt className="text-slate-500">Pages scanned</dt>
                      <dd className="mt-1 font-semibold text-slate-900">{profiling?.sources_scraped ?? 0}</dd>
                    </div>
                    <div>
                      <dt className="text-slate-500">Last run</dt>
                      <dd className="mt-1 font-medium text-slate-900">
                        {profiling?.last_enriched_at ? formatDateTime(profiling.last_enriched_at) : "—"}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-slate-500">Job links found</dt>
                      <dd className="mt-1 font-semibold text-slate-900">{data.external_job_links?.length ?? 0}</dd>
                    </div>
                  </dl>
                </Card>

                <Card title="Scraped pages">
                  {(data.source_pages?.length ?? 0) === 0 ? (
                    <EmptyState icon={<Globe className="h-10 w-10" />} title="No scraped pages">
                      Run HR profiling to crawl public career and contact pages (requires Firecrawl in Admin → Settings).
                    </EmptyState>
                  ) : (
                    <ul className="space-y-2 text-sm">
                      {data.source_pages!.map((page) => {
                        const url = safeExternalUrl(page.url);
                        return (
                          <li key={page.url} className="flex items-start gap-2 rounded-lg border border-slate-100 px-3 py-2.5">
                            <Globe className="mt-0.5 h-4 w-4 shrink-0 text-slate-400" aria-hidden />
                            {url ? (
                              <a href={url} target="_blank" rel="noopener noreferrer" className="font-medium text-brand-700 hover:underline break-all">
                                {page.title || page.url}
                              </a>
                            ) : (
                              <span>{page.title || page.url}</span>
                            )}
                          </li>
                        );
                      })}
                    </ul>
                  )}
                </Card>

                <Card title="Job links from web research">
                  <p className="mb-4 text-sm text-slate-500">
                    LinkedIn, Naukri, Greenhouse, Lever, and careers URLs found during profiling.
                  </p>
                  {(data.external_job_links?.length ?? 0) === 0 ? (
                    <EmptyState icon={<Briefcase className="h-10 w-10" />} title="No web job links">
                      Run HR profiling or wait for automatic profiling when automation discovers this company.
                    </EmptyState>
                  ) : (
                    <ul className="space-y-2 text-sm">
                      {data.external_job_links!.map((link) => {
                        const url = safeExternalUrl(link.url);
                        return (
                          <li key={link.url} className="flex flex-wrap items-center gap-2 rounded-lg border border-slate-100 px-3 py-2.5">
                            {url ? (
                              <a href={url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 font-medium text-brand-700 hover:underline break-all">
                                {link.title || link.url}
                                <ExternalLink className="h-3.5 w-3.5 shrink-0" aria-hidden />
                              </a>
                            ) : (
                              <span>{link.title || link.url}</span>
                            )}
                            {link.known_in_app && <Badge tone="green">Also in automation</Badge>}
                          </li>
                        );
                      })}
                    </ul>
                  )}
                </Card>
              </div>
            )}
          </div>
        </>
      )}
    </>
  );
}
