import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { Fragment, useEffect, useState } from "react";
import { TextArea, TextInput } from "../../../components/form";
import { Modal } from "../../../components/Modal";
import { Pagination } from "../../../components/Pagination";
import { useToast } from "../../../components/Toast";
import { Alert, Badge, Button, ButtonLink, Card, EmptyState, PageHeader, Spinner, cx } from "../../../components/ui";
import { formatDateTime, formatRelative } from "../../../lib/format";
import { errorMessage } from "../../../services/api";
import { admin } from "../../../services/endpoints";
import type { OutreachScrapeJob } from "../../../types";
import { OUTREACH_SOURCES, OutreachSetupAlert, useOutreachPlatform } from "./shared";

const JOBS_PAGE_SIZE = 10;

function listToLines(items: string[] | undefined): string {
  return (items ?? []).join("\n");
}

function linesToList(text: string): string[] {
  return text.split(/\n+/).map((s) => s.trim()).filter(Boolean);
}

const SOURCE_SHORT: Record<string, string> = {
  google: "Google",
  facebook: "Facebook",
  instagram: "Instagram",
  linkedin: "LinkedIn",
};

function jobStatusTone(status: string): "green" | "red" | "amber" | "slate" {
  const s = status.toLowerCase();
  if (s === "completed") return "green";
  if (s === "completed_with_errors") return "amber";
  if (s === "failed") return "red";
  if (s === "running" || s === "processing" || s === "pending" || s === "queued") return "amber";
  return "slate";
}

function jobStatusLabel(status: string): string {
  return status.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function jobIsActive(status: string): boolean {
  const s = status.toLowerCase();
  return s === "running" || s === "processing" || s === "pending" || s === "queued";
}

function sourceLabel(id: string): string {
  return SOURCE_SHORT[id] ?? id.replace(/_/g, " ");
}

function jobWhen(job: OutreachScrapeJob): string {
  const iso = job.finished_at || job.started_at || job.created_at;
  return iso ? formatRelative(iso) : "—";
}

function jobWhenTitle(job: OutreachScrapeJob): string | undefined {
  const iso = job.finished_at || job.started_at || job.created_at;
  return iso ? formatDateTime(iso) : undefined;
}

export function AdminOutreachScrapePage() {
  const toast = useToast();
  const qc = useQueryClient();
  const { platform, firecrawlOk, aiOutreachOk } = useOutreachPlatform();
  const [keywordLines, setKeywordLines] = useState("IT training institute");
  const [cityLines, setCityLines] = useState("Bangalore");
  const [query, setQuery] = useState("IT training institute");
  const [location, setLocation] = useState("Bangalore");
  const [sources, setSources] = useState<string[]>(["google"]);
  const [maxResults, setMaxResults] = useState(10);
  const [attest, setAttest] = useState(false);
  const [jobsPage, setJobsPage] = useState(1);
  const [detailId, setDetailId] = useState<string | null>(null);

  useEffect(() => {
    const c = platform.data?.outreach?.campaign;
    if (!c) return;
    const kw = listToLines(c.keywords);
    const cities = listToLines(c.cities);
    if (kw) setKeywordLines(kw);
    if (cities) setCityLines(cities);
    const kwFirst = linesToList(kw)[0];
    const cityFirst = linesToList(cities)[0];
    if (kwFirst) setQuery(kwFirst);
    if (cityFirst) setLocation(cityFirst);
    setSources(c.sources?.length ? c.sources : ["google"]);
    setMaxResults(c.max_results ?? 10);
    setAttest(c.public_listing_attestation ?? false);
  }, [platform.data?.outreach?.campaign]);

  const saveCampaign = useMutation({
    mutationFn: () =>
      admin.updateOutreach({
        campaign: {
          keywords: linesToList(keywordLines),
          cities: linesToList(cityLines),
          sources,
          max_results: maxResults,
          public_listing_attestation: attest,
          send_interval_min_sec: 60,
          send_interval_max_sec: 120,
        },
      }),
    onSuccess: () => {
      toast.success("Automation campaign saved");
      const kw = linesToList(keywordLines);
      const cities = linesToList(cityLines);
      if (kw[0]) setQuery(kw[0]);
      if (cities[0]) setLocation(cities[0]);
      void qc.invalidateQueries({ queryKey: ["admin", "settings"] });
    },
    onError: (err) => toast.error(errorMessage(err)),
  });

  const jobs = useQuery({
    queryKey: ["admin-outreach-jobs", jobsPage],
    queryFn: () => admin.outreachScrapeJobs({ page: jobsPage, page_size: JOBS_PAGE_SIZE }),
    refetchInterval: 5000,
    placeholderData: keepPreviousData,
  });

  const jobDetail = useQuery({
    queryKey: ["admin-outreach-job", detailId],
    queryFn: () => admin.outreachScrapeJob(detailId!),
    enabled: Boolean(detailId),
  });

  const startScrape = useMutation({
    mutationFn: () =>
      admin.outreachStartScrape({
        query,
        location,
        sources,
        max_results: maxResults,
        public_listing_attestation: attest,
      }),
    onSuccess: () => {
      toast.success("Scrape job started");
      void qc.invalidateQueries({ queryKey: ["admin-outreach-jobs"] });
      void qc.invalidateQueries({ queryKey: ["admin-outreach-leads"] });
    },
    onError: (err) => toast.error(errorMessage(err)),
  });

  const canStart =
    attest && sources.length > 0 && !startScrape.isPending && query.trim() && firecrawlOk && aiOutreachOk;
  const canSaveCampaign =
    attest &&
    linesToList(keywordLines).length > 0 &&
    linesToList(cityLines).length > 0 &&
    sources.length > 0 &&
    firecrawlOk &&
    aiOutreachOk;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Outreach scrape"
        description="Rotate keyword and city lists automatically; leads are completed, proposed, and sent on a schedule."
      />
      <OutreachSetupAlert />
      {platform.data?.outreach?.automation_enabled !== false ? (
        <Alert kind="info">
          Always-on automation runs when Celery worker and beat are running (
          <code className="text-xs">celery -A backend.app.worker worker --beat --pool=solo</code>
          ). Save the campaign below with compliance checked so rotation can start.
        </Alert>
      ) : null}
      <div className="flex flex-col gap-6">
        <Card className="w-full space-y-4 !p-4 sm:!p-5">
          <h2 className="text-base font-semibold text-slate-900">Automation campaign</h2>
          <p className="text-sm text-slate-600">
            One keyword and city pair runs per idle scrape slot. Leads are completed to 100%, then get proposals, then
            email and WhatsApp (1–2 minutes between sends).
          </p>
          <div className="grid gap-4 lg:grid-cols-2">
            <TextArea
              label="Keywords (one per line)"
              rows={4}
              value={keywordLines}
              onChange={setKeywordLines}
              placeholder={"IT training institute\ncoaching centre"}
            />
            <TextArea
              label="Cities (one per line)"
              rows={4}
              value={cityLines}
              onChange={setCityLines}
              placeholder={"Bangalore\nMumbai"}
            />
          </div>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-[1fr_7rem] lg:items-end">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-xs font-medium text-slate-500">Sources</span>
              {OUTREACH_SOURCES.map((s) => {
                const on = sources.includes(s.id);
                return (
                  <button
                    key={s.id}
                    type="button"
                    aria-pressed={on}
                    onClick={() =>
                      setSources((prev) => (on ? prev.filter((x) => x !== s.id) : [...prev, s.id]))
                    }
                    className={cx(
                      "rounded-full px-3 py-1 text-xs font-medium transition-colors",
                      on
                        ? "bg-brand-600 text-white shadow-sm"
                        : "bg-slate-100 text-slate-600 ring-1 ring-slate-200/80 hover:bg-slate-50",
                    )}
                  >
                    {SOURCE_SHORT[s.id] ?? s.label}
                  </button>
                );
              })}
            </div>
            <TextInput
              label="Max per job"
              type="number"
              min={1}
              max={50}
              value={String(maxResults)}
              onChange={(v) => setMaxResults(Number(v) || 10)}
            />
          </div>
          <div className="flex flex-col gap-3 border-t border-slate-100 pt-4 sm:flex-row sm:items-center sm:justify-between">
            <label className="flex cursor-pointer items-start gap-2 text-sm text-slate-600">
              <input
                type="checkbox"
                className="mt-0.5 h-4 w-4 rounded border-slate-300 text-brand-600 focus:ring-brand-600"
                checked={attest}
                onChange={(e) => setAttest(e.target.checked)}
              />
              <span>Public business listings only (required for automation and manual scrape)</span>
            </label>
            <Button
              size="sm"
              variant="secondary"
              onClick={() => saveCampaign.mutate()}
              disabled={!canSaveCampaign}
              loading={saveCampaign.isPending}
            >
              Save campaign
            </Button>
          </div>
        </Card>

        <Card className="w-full space-y-4 !p-4 sm:!p-5">
          <h2 className="text-base font-semibold text-slate-900">Run once (manual)</h2>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-[1fr_1fr_7rem] lg:items-end">
            <TextInput label="Keywords" value={query} onChange={setQuery} placeholder="e.g. IT training institute" />
            <TextInput label="City / region" value={location} onChange={setLocation} placeholder="Bangalore" />
            <TextInput
              label="Max"
              type="number"
              min={1}
              max={50}
              value={String(maxResults)}
              onChange={(v) => setMaxResults(Number(v) || 10)}
            />
          </div>

          <p className="text-xs text-slate-500">
            Discovery (search + page crawl), enrichment (AI on evidence), and contact verification are separate stages.
            Manual run uses the first saved keyword/city when you load or save the campaign. Directory listings on the
            same site stay separate leads; identical institutes merge only on strong identity signals.
          </p>
          <div className="flex justify-end border-t border-slate-100 pt-4">
            <Button size="sm" onClick={() => startScrape.mutate()} disabled={!canStart} loading={startScrape.isPending}>
              Start scrape
            </Button>
          </div>
        </Card>

        <Card className="w-full overflow-hidden !p-0">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 px-4 py-3 sm:px-5">
            <h2 className="text-base font-semibold text-slate-900">Recent jobs</h2>
            {jobs.data && jobs.data.total > 0 ? (
              <span className="text-xs text-slate-500">Auto-refreshes every 5s · {jobs.data.total} total</span>
            ) : null}
          </div>

          {jobs.isLoading && !jobs.data ? (
            <Spinner />
          ) : !jobs.data?.total ? (
            <div className="px-4 py-8 sm:px-5">
              <EmptyState title="No jobs yet">Start a scrape above to discover institutes.</EmptyState>
            </div>
          ) : (
            <>
              <div className="overflow-x-auto">
                <table className="w-full min-w-[640px] text-sm">
                  <thead className="bg-slate-50 text-left text-xs font-medium uppercase tracking-wide text-slate-500">
                    <tr>
                      <th className="px-4 py-2.5 sm:px-5">Search</th>
                      <th className="px-4 py-2.5 sm:px-5">Sources</th>
                      <th className="px-4 py-2.5 sm:px-5">Outcomes</th>
                      <th className="px-4 py-2.5 sm:px-5">Status</th>
                      <th className="px-4 py-2.5 sm:px-5">When</th>
                      <th className="px-4 py-2.5 sm:px-5 text-right"> </th>
                    </tr>
                  </thead>
                  <tbody>
                    {jobs.data.items.map((j) => (
                      <Fragment key={j.id}>
                        <tr className="border-t border-slate-100 hover:bg-slate-50/80">
                          <td className="px-4 py-3 sm:px-5">
                            <div className="font-medium text-slate-900">{j.query || "—"}</div>
                            {j.location ? (
                              <div className="mt-0.5 text-xs text-slate-500">{j.location}</div>
                            ) : null}
                          </td>
                          <td className="px-4 py-3 sm:px-5">
                            <div className="flex flex-wrap gap-1">
                              {(j.sources?.length ? j.sources : ["google"]).map((src) => (
                                <span
                                  key={src}
                                  className="rounded-md bg-slate-100 px-1.5 py-0.5 text-xs text-slate-600 ring-1 ring-slate-200/80"
                                >
                                  {sourceLabel(src)}
                                </span>
                              ))}
                            </div>
                          </td>
                          <td className="px-4 py-3 sm:px-5 text-slate-700">
                            <div className="whitespace-nowrap">
                              <span className="font-medium tabular-nums text-slate-900">{j.leads_found}</span>
                              <span className="text-slate-400"> new</span>
                              {(j.leads_updated ?? j.stats?.leads_updated) ? (
                                <>
                                  <span className="mx-1 text-slate-300">·</span>
                                  <span className="font-medium tabular-nums text-slate-900">
                                    {j.leads_updated ?? j.stats?.leads_updated}
                                  </span>
                                  <span className="text-slate-400"> updated</span>
                                </>
                              ) : null}
                              <span className="mx-1 text-slate-300">·</span>
                              <span className="font-medium tabular-nums text-slate-900">{j.leads_enriched}</span>
                              <span className="text-slate-400"> enriched</span>
                            </div>
                            {j.stats && (j.stats.pages_scraped || j.stats.search_results) ? (
                              <div className="mt-0.5 text-xs text-slate-500">
                                {j.stats.search_results ?? 0} search hits · {j.stats.pages_scraped ?? 0}/
                                {j.stats.pages_attempted ?? 0} pages · {j.stats.contacts_syntax_valid ?? 0} contacts
                                {j.stats.duplicates_skipped ? ` · ${j.stats.duplicates_skipped} dup skips` : ""}
                              </div>
                            ) : j.leads_found === 0 && j.status === "completed" ? (
                              <div className="mt-0.5 text-xs text-amber-700">No new institutes — check query or API warnings below.</div>
                            ) : null}
                          </td>
                          <td className="px-4 py-3 sm:px-5">
                            <span className="inline-flex items-center gap-1.5">
                              {jobIsActive(j.status) ? (
                                <Loader2 className="h-3.5 w-3.5 animate-spin text-amber-600" aria-hidden />
                              ) : null}
                              <Badge tone={jobStatusTone(j.status)}>{jobStatusLabel(j.status)}</Badge>
                            </span>
                          </td>
                          <td
                            className="px-4 py-3 sm:px-5 whitespace-nowrap text-slate-600"
                            title={jobWhenTitle(j)}
                          >
                            {jobWhen(j)}
                          </td>
                          <td className="px-4 py-3 sm:px-5 text-right">
                            <div className="flex justify-end gap-1">
                              <Button variant="ghost" size="sm" onClick={() => setDetailId(j.id)}>
                                Details
                              </Button>
                              {j.leads_found > 0 ? (
                                <ButtonLink to="/admin/outreach/leads" variant="ghost" size="sm">
                                  View leads
                                </ButtonLink>
                              ) : null}
                            </div>
                          </td>
                        </tr>
                        {j.error_message ? (
                          <tr className="border-t border-red-100 bg-red-50/40">
                            <td colSpan={6} className="px-4 py-2 sm:px-5 text-xs text-red-800">
                              {j.error_message}
                            </td>
                          </tr>
                        ) : null}
                      </Fragment>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="border-t border-slate-100 px-4 pb-4 sm:px-5">
                <Pagination
                  page={jobs.data.page}
                  pageSize={jobs.data.page_size}
                  total={jobs.data.total}
                  onPage={setJobsPage}
                />
              </div>
            </>
          )}
        </Card>
      </div>

      <Modal open={Boolean(detailId)} onClose={() => setDetailId(null)} title="Scrape job" size="lg">
        {jobDetail.isLoading ? (
          <Spinner />
        ) : jobDetail.error || !jobDetail.data ? (
          <Alert kind="error">{errorMessage(jobDetail.error)}</Alert>
        ) : (
          <ScrapeJobDetailBody job={jobDetail.data} />
        )}
      </Modal>
    </div>
  );
}

function ScrapeJobDetailBody({ job }: { job: OutreachScrapeJob }) {
  const stats = job.stats ?? {};
  return (
    <div className="space-y-3 text-sm">
      <p><span className="text-slate-500">Search</span> {job.query || "—"}{job.location ? ` · ${job.location}` : ""}</p>
      <p><span className="text-slate-500">Status</span> {jobStatusLabel(job.status)}</p>
      <p><span className="text-slate-500">Sources</span> {(job.sources || []).join(", ") || "google"}</p>
      <p>
        <span className="text-slate-500">Outcomes</span> {job.leads_found} new · {job.leads_updated ?? 0} updated · {job.leads_enriched} enriched
      </p>
      <p>
        <span className="text-slate-500">Crawl</span> {stats.search_results ?? 0} hits · {stats.pages_scraped ?? 0}/{stats.pages_attempted ?? 0} pages
      </p>
      {stats.firecrawl_errors?.length ? (
        <Alert kind="info">{stats.firecrawl_errors.join(" · ")}</Alert>
      ) : null}
      {job.error_message ? <Alert kind="error">{job.error_message}</Alert> : null}
      <p className="text-xs text-slate-500">
        Created {job.created_at ? formatDateTime(job.created_at) : "—"}
        {job.started_at ? ` · started ${formatDateTime(job.started_at)}` : ""}
        {job.finished_at ? ` · finished ${formatDateTime(job.finished_at)}` : ""}
      </p>
    </div>
  );
}
