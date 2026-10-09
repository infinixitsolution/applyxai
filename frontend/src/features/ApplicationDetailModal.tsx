import { useQuery } from "@tanstack/react-query";
import { Download, ExternalLink, FileText } from "lucide-react";
import { Modal } from "../components/Modal";
import { Alert, Badge, Spinner } from "../components/ui";
import { formatDateTime, safeExternalUrl, STATUS_LABELS, STATUS_TONES } from "../lib/format";
import { errorMessage } from "../services/api";
import { applications, resumes as resumesApi } from "../services/endpoints";

export function ApplicationDetailModal({ id, onClose }: { id: string | null; onClose: () => void }) {
  const { data, isLoading, error } = useQuery({
    queryKey: ["applications", "detail", id],
    queryFn: () => applications.get(id!),
    enabled: !!id,
  });
  const url = safeExternalUrl(data?.job.job_url);
  return (
    <Modal open={!!id} onClose={onClose} title={data ? data.job.title : "Application"} wide>
      {isLoading ? <Spinner /> : error || !data ? <Alert kind="error">{errorMessage(error)}</Alert> : (
        <div className="space-y-5">
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone={STATUS_TONES[data.status]}>{STATUS_LABELS[data.status]}</Badge>
            <span className="text-slate-600">{[data.job.company, data.job.location, data.job.work_setting].filter(Boolean).join(" · ")}</span>
          </div>
          <dl className="grid grid-cols-1 gap-3 text-sm xs:grid-cols-2 sm:grid-cols-2">
            <div><dt className="text-slate-500">Discovered</dt><dd>{formatDateTime(data.created_at)}</dd></div>
            <div><dt className="text-slate-500">Applied</dt><dd>{formatDateTime(data.applied_at)}</dd></div>
            {data.job.experience_level && <div><dt className="text-slate-500">Experience</dt><dd>{data.job.experience_level}</dd></div>}
            {data.job.employment_type && <div><dt className="text-slate-500">Job type</dt><dd>{data.job.employment_type}</dd></div>}
          </dl>
          {(data.generated_resumes?.length ?? 0) > 0 && (
            <div>
              <h3 className="mb-2 font-medium text-slate-900">Generated resumes</h3>
              <ul className="divide-y divide-slate-100 rounded-lg ring-1 ring-slate-200">
                {(data.generated_resumes ?? []).map((r) => (
                  <li key={r.id} className="flex items-center justify-between gap-3 px-3 py-2 text-sm">
                    <div className="min-w-0 flex items-center gap-2">
                      <FileText className="h-4 w-4 shrink-0 text-slate-400" aria-hidden />
                      <div className="min-w-0">
                        <p className="truncate font-medium text-slate-900">{r.name}</p>
                        <p className="truncate text-xs text-slate-500">{r.filename} · {formatDateTime(r.created_at)}</p>
                      </div>
                    </div>
                    <a href={resumesApi.downloadUrl(r.id)} className="inline-flex shrink-0 items-center gap-1 text-brand-600 hover:underline">
                      <Download className="h-4 w-4" aria-hidden /> Download
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          )}
          {data.failure_reason && <Alert kind="error"><strong>Why it failed:</strong> {data.failure_reason}</Alert>}
          {url && (
            <a href={url} target="_blank" rel="noopener noreferrer nofollow"
               className="inline-flex items-center gap-1 font-medium text-brand-600 hover:underline">
              View the job posting <ExternalLink className="h-4 w-4" aria-hidden />
            </a>
          )}
          {data.job.description && (
            <div>
              <h3 className="mb-2 font-medium text-slate-900">Job description</h3>
              {/* Third-party text: rendered as plain text, never as HTML. */}
              <p className="whitespace-pre-wrap text-slate-600">{data.job.description}</p>
            </div>
          )}
        </div>
      )}
    </Modal>
  );
}
