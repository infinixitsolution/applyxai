import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { Download, Eye, ListChecks, Paperclip, Search } from "lucide-react";
import { useState } from "react";
import { ChipSelect, Select, TextInput } from "../../components/form";
import { Pagination } from "../../components/Pagination";
import { Modal } from "../../components/Modal";
import { Alert, Badge, buttonClass, Button, Card, EmptyState, PageHeader, Spinner } from "../../components/ui";
import { ApplicationDetailModal, resumeKindLabel } from "../../features/ApplicationDetailModal";
import { formatDate, STATUS_LABELS, STATUS_TONES } from "../../lib/format";
import { useDebounced } from "../../lib/useDebounced";
import { errorMessage } from "../../services/api";
import { applications, resumes as resumesApi, type ApplicationFilters } from "../../services/endpoints";
import { APPLICATION_STATUSES, type Application, type ApplicationStatus } from "../../types";

const PAGE_SIZE = 20;

const SORTS = [
  { value: "-created_at", label: "Newest first" },
  { value: "created_at", label: "Oldest first" },
  { value: "-applied_at", label: "Recently applied" },
  { value: "company", label: "Company A–Z" },
  { value: "title", label: "Title A–Z" },
];

export function ApplicationsPage() {
  const [q, setQ] = useState("");
  const [status, setStatus] = useState<ApplicationStatus[]>([]);
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [sort, setSort] = useState("-created_at");
  const [page, setPage] = useState(1);
  const [openId, setOpenId] = useState<string | null>(null);
  const [resumeFor, setResumeFor] = useState<Application | null>(null);
  const search = useDebounced(q.trim());

  const filters: ApplicationFilters = {
    q: search || undefined, status, applied_from: from || undefined, applied_to: to || undefined, sort, page, page_size: PAGE_SIZE,
  };
  const { data, isLoading, isFetching, error } = useQuery({
    queryKey: ["applications", "list", filters],
    queryFn: () => applications.list(filters),
    placeholderData: keepPreviousData,
  });
  const resetPage = <T,>(setter: (v: T) => void) => (v: T) => { setter(v); setPage(1); };
  const labels = Object.fromEntries(APPLICATION_STATUSES.map((s) => [STATUS_LABELS[s], s])) as Record<string, ApplicationStatus>;

  return (
    <>
      <PageHeader title="Applications" description="Every job the automation has applied to, skipped, or couldn't complete."
                  actions={
                    <a href={applications.exportUrl(filters)} className={buttonClass("secondary")} download>
                      <Download className="h-4 w-4" aria-hidden /> Export CSV
                    </a>
                  } />
      <Card>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <div className="relative sm:col-span-2">
            <TextInput label="Search" value={q} onChange={resetPage(setQ)} placeholder="Title, company, or location" maxLength={200} className="pl-9" />
            <Search className="pointer-events-none absolute bottom-2.5 left-3 h-4 w-4 text-slate-400" aria-hidden />
          </div>
          <TextInput label="Applied from" type="date" value={from} onChange={resetPage(setFrom)} max={to || undefined} />
          <TextInput label="Applied to" type="date" value={to} onChange={resetPage(setTo)} min={from || undefined} />
        </div>
        <div className="mt-4 flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <ChipSelect label="Status" options={APPLICATION_STATUSES.map((s) => STATUS_LABELS[s])}
                      value={status.map((s) => STATUS_LABELS[s])} onChange={(v) => { setStatus(v.map((l) => labels[l])); setPage(1); }} />
          <div className="w-full lg:w-56"><Select label="Sort" value={sort} onChange={resetPage(setSort)} options={SORTS} /></div>
        </div>
      </Card>

      <div className="mt-6">
        {isLoading ? <Spinner /> : error || !data ? <Alert kind="error">{errorMessage(error)}</Alert> : data.total === 0 ? (
          <Card><EmptyState icon={<ListChecks className="h-10 w-10" />} title="No applications found">
            {search || status.length || from || to ? "Try clearing some filters." : "Run the automation to start applying."}
          </EmptyState></Card>
        ) : (
          <Card className={isFetching ? "opacity-70 transition-opacity" : ""}>
            <ul className="-mx-4 divide-y divide-slate-100 sm:-mx-5">
              {data.items.map((a) => {
                const meta = [a.job.company, a.job.location].filter(Boolean).join(" · ");
                return (
                  <li key={a.id}>
                    <div className="flex min-w-0 flex-col gap-3 px-4 py-4 hover:bg-slate-50 sm:px-5 lg:flex-row lg:items-start lg:justify-between">
                      <button type="button" className="w-full min-w-0 flex-1 text-left" onClick={() => setOpenId(a.id)}>
                        <span className="line-clamp-2 font-medium text-slate-900">{a.job.title}</span>
                        <span className="mt-1 block truncate text-sm text-slate-500">{meta || "Location not listed"}</span>
                      </button>
                      <div className="flex shrink-0 flex-wrap items-center gap-3 lg:justify-end">
                        <Badge tone={STATUS_TONES[a.status]}>{STATUS_LABELS[a.status]}</Badge>
                        <span className="inline-flex items-center gap-1 whitespace-nowrap text-sm text-slate-500">
                          {formatDate(a.applied_at)}
                          {a.resume && (
                            <button type="button" title={a.resume.name} aria-label={`Open resume ${a.resume.name}`}
                                    className="rounded-md p-1 text-brand-600 hover:bg-brand-50"
                                    onClick={() => setResumeFor(a)}>
                              <Paperclip className="h-4 w-4" aria-hidden />
                            </button>
                          )}
                        </span>
                        <Button size="sm" variant="secondary" onClick={() => setOpenId(a.id)}>
                          <Eye className="h-4 w-4" aria-hidden /> View
                        </Button>
                      </div>
                    </div>
                  </li>
                );
              })}
            </ul>
            <Pagination page={data.page} pageSize={data.page_size} total={data.total} onPage={setPage} />
          </Card>
        )}
      </div>
      <ApplicationDetailModal id={openId} onClose={() => setOpenId(null)} />
      <Modal open={!!resumeFor} onClose={() => setResumeFor(null)} title="Resume" footer={
        <Button variant="secondary" onClick={() => setResumeFor(null)}>Close</Button>
      }>
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
            <a href={resumesApi.downloadUrl(resumeFor.resume.id)}
               className="inline-flex items-center gap-1 font-medium text-brand-600 hover:underline">
              <Download className="h-4 w-4" aria-hidden /> Download resume
            </a>
            {(resumeFor.generated_resumes?.length ?? 0) > 1 && (
              <ul className="divide-y divide-slate-100 rounded-lg ring-1 ring-slate-200">
                {resumeFor.generated_resumes!.filter((item) => item.id !== resumeFor.resume!.id).map((item) => (
                  <li key={item.id} className="flex items-center justify-between gap-3 px-3 py-2">
                    <span className="min-w-0 truncate text-sm text-slate-700">{item.name}</span>
                    <a href={resumesApi.downloadUrl(item.id)} className="shrink-0 text-sm font-medium text-brand-600 hover:underline">Download</a>
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
