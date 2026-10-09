import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { Download, FileText, ListChecks, Search } from "lucide-react";
import { useState } from "react";
import { ChipSelect, Select, TextInput } from "../../components/form";
import { Pagination } from "../../components/Pagination";
import { Alert, Badge, buttonClass, Card, EmptyState, PageHeader, Spinner } from "../../components/ui";
import { ApplicationDetailModal } from "../../features/ApplicationDetailModal";
import { formatDate, STATUS_LABELS, STATUS_TONES } from "../../lib/format";
import { useDebounced } from "../../lib/useDebounced";
import { errorMessage } from "../../services/api";
import { applications, resumes as resumesApi, type ApplicationFilters } from "../../services/endpoints";
import { APPLICATION_STATUSES, type ApplicationStatus } from "../../types";

const PAGE_SIZE = 20;

function resumeKindLabel(resume: { generated_by?: string | null; is_default?: boolean } | null | undefined): string {
  if (!resume) return "";
  if (resume.generated_by === "ai") return "AI tailored";
  if (resume.generated_by === "automation") return "Generated";
  if (resume.is_default) return "Master resume";
  return "Resume";
}
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
            <div className="-mx-5 overflow-x-auto">
              <table className="min-w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-200 text-left text-xs font-medium uppercase tracking-wide text-slate-500">
                    <th className="px-5 py-3">Job</th>
                    <th className="px-5 py-3">Location</th>
                    <th className="px-5 py-3">Status</th>
                    <th className="px-5 py-3">Resume</th>
                    <th className="px-5 py-3">Applied</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {data.items.map((a) => (
                    <tr key={a.id} className="cursor-pointer hover:bg-slate-50" onClick={() => setOpenId(a.id)}>
                      <td className="max-w-xs px-5 py-3">
                        <button type="button" className="text-left" onClick={(e) => { e.stopPropagation(); setOpenId(a.id); }}>
                          <span className="block truncate font-medium text-slate-900">{a.job.title}</span>
                          <span className="block truncate text-slate-500">{a.job.company}</span>
                        </button>
                      </td>
                      <td className="px-5 py-3 text-slate-600">{a.job.location || "—"}</td>
                      <td className="px-5 py-3"><Badge tone={STATUS_TONES[a.status]}>{STATUS_LABELS[a.status]}</Badge></td>
                      <td className="max-w-[200px] px-5 py-3" onClick={(e) => e.stopPropagation()}>
                        {(a.generated_resumes?.length ?? 0) > 0 || a.resume ? (
                          <div className="space-y-1">
                            {a.resume && (
                              <div className="min-w-0">
                                <a href={resumesApi.downloadUrl(a.resume.id)} className="flex items-center gap-1 truncate text-brand-600 hover:underline"
                                   title={a.resume.name}>
                                  <FileText className="h-3.5 w-3.5 shrink-0" aria-hidden />
                                  <span className="truncate">{a.resume.name}</span>
                                </a>
                                <p className="text-xs text-slate-500">{resumeKindLabel(a.resume)}</p>
                              </div>
                            )}
                            {(a.generated_resumes?.length ?? 0) > 1 && (
                              <span className="text-xs text-slate-500">+{(a.generated_resumes?.length ?? 0) - 1} more in details</span>
                            )}
                          </div>
                        ) : (
                          <span className="text-slate-400">—</span>
                        )}
                      </td>
                      <td className="whitespace-nowrap px-5 py-3 text-slate-600">{formatDate(a.applied_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Pagination page={data.page} pageSize={data.page_size} total={data.total} onPage={setPage} />
          </Card>
        )}
      </div>
      <ApplicationDetailModal id={openId} onClose={() => setOpenId(null)} />
    </>
  );
}
