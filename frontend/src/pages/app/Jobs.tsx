import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { Briefcase, ExternalLink } from "lucide-react";
import { useState } from "react";
import { Select, TextInput } from "../../components/form";
import { Pagination } from "../../components/Pagination";
import { Alert, Badge, Card, EmptyState, PageHeader, Spinner } from "../../components/ui";
import { ApplicationDetailModal } from "../../features/ApplicationDetailModal";
import { formatRelative, safeExternalUrl, STATUS_LABELS, STATUS_TONES } from "../../lib/format";
import { useDebounced } from "../../lib/useDebounced";
import { errorMessage } from "../../services/api";
import { jobs, preferences } from "../../services/endpoints";

export function JobsPage() {
  const [q, setQ] = useState("");
  const [workSetting, setWorkSetting] = useState("");
  const [page, setPage] = useState(1);
  const [openId, setOpenId] = useState<string | null>(null);
  const search = useDebounced(q.trim());
  const options = useQuery({ queryKey: ["preferences", "options"], queryFn: preferences.options, staleTime: Infinity });
  const query = { q: search || undefined, work_setting: workSetting || undefined, page, page_size: 20 };
  const { data, isLoading, error } = useQuery({
    queryKey: ["jobs", query], queryFn: () => jobs.list(query), placeholderData: keepPreviousData,
  });

  return (
    <>
      <PageHeader title="Jobs" description="Jobs the automation has found for you, newest first." />
      <Card>
        <div className="grid gap-4 sm:grid-cols-3">
          <div className="sm:col-span-2">
            <TextInput label="Search" value={q} onChange={(v) => { setQ(v); setPage(1); }} placeholder="Title, company, or description" maxLength={200} />
          </div>
          <Select label="Work setting" value={workSetting} onChange={(v) => { setWorkSetting(v); setPage(1); }}
                  options={[{ value: "", label: "Any" }, ...(options.data?.search.on_site ?? []).map((o) => ({ value: o, label: o }))]} />
        </div>
      </Card>
      <div className="mt-6">
        {isLoading ? <Spinner /> : error || !data ? <Alert kind="error">{errorMessage(error)}</Alert> : data.total === 0 ? (
          <Card><EmptyState icon={<Briefcase className="h-10 w-10" />} title="No jobs yet">
            {search || workSetting ? "No jobs match these filters." : "Jobs appear here as the automation finds them."}
          </EmptyState></Card>
        ) : (
          <>
            <ul className="grid gap-4 md:grid-cols-2">
              {data.items.map((job) => {
                const url = safeExternalUrl(job.job_url);
                return (
                  <li key={job.id} className="flex flex-col rounded-xl bg-white p-5 shadow-sm ring-1 ring-slate-200">
                    <div className="flex items-start justify-between gap-3">
                      <button type="button" onClick={() => setOpenId(job.application.id)} className="min-w-0 text-left">
                        <p className="truncate font-medium text-slate-900 hover:text-brand-700">{job.title}</p>
                        <p className="truncate text-sm text-slate-500">{job.company}</p>
                      </button>
                      <Badge tone={STATUS_TONES[job.application.status]}>{STATUS_LABELS[job.application.status]}</Badge>
                    </div>
                    <div className="mt-3 flex flex-wrap gap-2 text-xs text-slate-500">
                      {job.location && <span>{job.location}</span>}
                      {job.work_setting && <Badge>{job.work_setting}</Badge>}
                      {job.employment_type && <Badge>{job.employment_type}</Badge>}
                    </div>
                    <div className="mt-4 flex items-center justify-between text-xs text-slate-400">
                      <span>Found {formatRelative(job.discovered_at)}</span>
                      {url && (
                        <a href={url} target="_blank" rel="noopener noreferrer nofollow" className="inline-flex items-center gap-1 font-medium text-brand-600 hover:underline">
                          Posting <ExternalLink className="h-3.5 w-3.5" aria-hidden />
                        </a>
                      )}
                    </div>
                  </li>
                );
              })}
            </ul>
            <Pagination page={data.page} pageSize={data.page_size} total={data.total} onPage={setPage} />
          </>
        )}
      </div>
      <ApplicationDetailModal id={openId} onClose={() => setOpenId(null)} />
    </>
  );
}
