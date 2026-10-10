import { useQuery } from "@tanstack/react-query";
import { Building2, Download, ExternalLink, FileText, MapPin } from "lucide-react";
import { Modal } from "../components/Modal";
import { Alert, Badge, Button, Spinner } from "../components/ui";
import { formatDateTime, safeExternalUrl, STATUS_LABELS, STATUS_TONES } from "../lib/format";
import { errorMessage } from "../services/api";
import { applications, resumes as resumesApi } from "../services/endpoints";
import type { ResumeVersion } from "../types";

export function resumeKindLabel(resume: { generated_by?: string | null; is_default?: boolean } | null | undefined): string {
  if (!resume) return "";
  if (resume.generated_by === "ai") return "AI tailored for this job";
  if (resume.generated_by === "automation") return "Generated for this job";
  if (resume.is_default) return "Master resume";
  return "Resume";
}

function ResumeCard({ resume, featured }: { resume: ResumeVersion; featured?: boolean }) {
  const preparedFor = [resume.job_title, resume.company].filter(Boolean).join(" at ");
  return (
    <div className={featured
      ? "flex flex-wrap items-center justify-between gap-3 rounded-xl border border-brand-200 bg-brand-50/60 p-4"
      : "flex items-center justify-between gap-3 px-3 py-2"}>
      <div className="flex min-w-0 items-start gap-3">
        <span className={featured
          ? "mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-white text-brand-600 ring-1 ring-brand-100"
          : "mt-0.5 text-slate-400"}>
          <FileText className="h-4 w-4" aria-hidden />
        </span>
        <div className="min-w-0">
          {featured && <p className="text-xs font-medium uppercase tracking-wide text-brand-700">Resume added</p>}
          <p className="truncate font-medium text-slate-900">{resume.name}</p>
          <p className="mt-0.5 text-xs text-slate-600">{resumeKindLabel(resume)}</p>
          <p className="mt-1 truncate text-xs text-slate-500">{resume.filename}</p>
          {preparedFor && <p className="mt-1 text-xs text-slate-600">Prepared for {preparedFor}</p>}
          <p className="mt-1 text-xs text-slate-500">
            Saved {formatDateTime(resume.created_at)}
            {resume.match_score != null ? ` · Match ${resume.match_score}%` : ""}
            {resume.fit_score != null ? ` · Fit ${resume.fit_score}%` : ""}
          </p>
        </div>
      </div>
      <a href={resumesApi.downloadUrl(resume.id)}
         className="inline-flex shrink-0 items-center gap-1 self-center text-sm font-medium text-brand-600 hover:underline">
        <Download className="h-4 w-4" aria-hidden /> Download
      </a>
    </div>
  );
}

export function ApplicationDetailModal({ id, onClose }: { id: string | null; onClose: () => void }) {
  const { data, isLoading, error } = useQuery({
    queryKey: ["applications", "detail", id],
    queryFn: () => applications.get(id!),
    enabled: !!id,
  });
  const url = safeExternalUrl(data?.job.job_url);
  const added = data?.resume ?? null;
  const others = (data?.generated_resumes ?? []).filter((resume) => resume.id !== added?.id);
  return (
    <Modal open={!!id} onClose={onClose} title={data ? data.job.title : "Application"} size="xl" footer={
      <Button variant="secondary" onClick={onClose}>Close</Button>
    }>
      {isLoading ? <Spinner /> : error || !data ? <Alert kind="error">{errorMessage(error)}</Alert> : (
        <div className="space-y-5">
          <div className="rounded-xl bg-slate-50 p-4 ring-1 ring-slate-200">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="text-base font-semibold text-slate-900">{data.job.title}</p>
                <p className="mt-1 flex items-center gap-1.5 text-slate-600">
                  <Building2 className="h-4 w-4 shrink-0" aria-hidden />
                  {data.job.company || "Company not listed"}
                </p>
                {(data.job.location || data.job.work_setting) && (
                  <p className="mt-1 flex items-center gap-1.5 text-slate-600">
                    <MapPin className="h-4 w-4 shrink-0" aria-hidden />
                    {[data.job.location, data.job.work_setting].filter(Boolean).join(" · ")}
                  </p>
                )}
              </div>
              <Badge tone={STATUS_TONES[data.status]}>{STATUS_LABELS[data.status]}</Badge>
            </div>
          </div>

          <dl className="grid grid-cols-1 gap-3 text-sm sm:grid-cols-2">
            <div className="rounded-lg bg-white px-3 py-2 ring-1 ring-slate-200">
              <dt className="text-slate-500">Discovered</dt>
              <dd className="font-medium text-slate-900">{formatDateTime(data.created_at)}</dd>
            </div>
            <div className="rounded-lg bg-white px-3 py-2 ring-1 ring-slate-200">
              <dt className="text-slate-500">Applied</dt>
              <dd className="font-medium text-slate-900">{formatDateTime(data.applied_at)}</dd>
            </div>
            {data.job.experience_level && (
              <div className="rounded-lg bg-white px-3 py-2 ring-1 ring-slate-200">
                <dt className="text-slate-500">Experience</dt>
                <dd className="font-medium text-slate-900">{data.job.experience_level}</dd>
              </div>
            )}
            {data.job.employment_type && (
              <div className="rounded-lg bg-white px-3 py-2 ring-1 ring-slate-200">
                <dt className="text-slate-500">Job type</dt>
                <dd className="font-medium text-slate-900">{data.job.employment_type}</dd>
              </div>
            )}
          </dl>

          <section>
            <h3 className="mb-2 font-medium text-slate-900">Resume added</h3>
            {added ? (
              <ResumeCard resume={added} featured />
            ) : (
              <p className="rounded-xl bg-slate-50 px-4 py-3 text-slate-600 ring-1 ring-slate-200">
                No resume was attached to this application.
              </p>
            )}
          </section>

          {others.length > 0 && (
            <section>
              <h3 className="mb-2 font-medium text-slate-900">Other resumes for this job</h3>
              <ul className="divide-y divide-slate-100 rounded-lg ring-1 ring-slate-200">
                {others.map((resume) => (
                  <li key={resume.id}><ResumeCard resume={resume} /></li>
                ))}
              </ul>
            </section>
          )}

          {data.failure_reason && (data.status === "skipped" || data.status === "failed") && (
            <Alert kind="error">
              <strong>{data.status === "skipped" ? "Why it was skipped:" : "Why it failed:"}</strong>
              <span className="mt-1 block whitespace-pre-wrap break-all">{data.failure_reason}</span>
            </Alert>
          )}

          {url && (
            <a href={url} target="_blank" rel="noopener noreferrer nofollow"
               className="inline-flex items-center gap-1 font-medium text-brand-600 hover:underline">
              View the job posting <ExternalLink className="h-4 w-4" aria-hidden />
            </a>
          )}

          {data.job.description && (
            <section>
              <h3 className="mb-2 font-medium text-slate-900">Job description</h3>
              <p className="max-h-64 overflow-y-auto whitespace-pre-wrap rounded-lg bg-slate-50 p-3 text-slate-600 ring-1 ring-slate-200">
                {data.job.description}
              </p>
            </section>
          )}
        </div>
      )}
    </Modal>
  );
}
