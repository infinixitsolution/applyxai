import { useQuery } from "@tanstack/react-query";
import {
  Bot,
  FileText,
  Sparkles,
  Star,
  Upload,
  Wand2,
} from "lucide-react";
import { Link } from "react-router-dom";
import {
  Alert,
  ButtonLink,
  Card,
  PageHeader,
  ProgressBar,
  Spinner,
  StatCard,
} from "../components/ui";
import { formatBytes, formatDate, isUnlimitedUsageCap } from "../lib/format";
import { errorMessage } from "../services/api";
import { automation, dashboard, resumes as resumesApi } from "../services/endpoints";
import type { Resume } from "../types";
import { ResumeManager } from "./ResumeManager";

function generatedCount(resumes: Resume[]): number {
  return resumes.filter((r) => {
    const by = (r.ai_metadata?.generated_by as string | undefined) ?? "";
    return by === "ai" || by === "style" || by === "automation";
  }).length;
}

export function ResumesDashboard() {
  const { data, isLoading, error } = useQuery({ queryKey: ["resumes"], queryFn: resumesApi.list });
  const dashQuery = useQuery({ queryKey: ["dashboard"], queryFn: dashboard.stats, staleTime: 60_000 });
  const autoQuery = useQuery({ queryKey: ["automation"], queryFn: automation.overview, staleTime: 30_000 });

  const usage = dashQuery.data?.usage;
  const tailor = autoQuery.data?.resume_tailor;
  const list = data?.resumes ?? [];
  const defaultResume = list.find((r) => r.is_default) ?? list[0];
  const limit = data?.limit ?? 0;
  const atLimit = list.length >= limit && limit > 0;

  return (
    <>
      <PageHeader
        title="Resumes"
        description="Upload, style, and tailor CVs — your default is used on automation runs unless you choose per-job tailoring."
        actions={
          <>
            <ButtonLink to="/app/profile" variant="secondary" className="w-full sm:w-auto">
              Profile
            </ButtonLink>
            <ButtonLink to="/app/automation" variant="secondary" className="w-full sm:w-auto">
              <Bot className="h-4 w-4" aria-hidden /> Automation
            </ButtonLink>
          </>
        }
      />

      {error ? (
        <Alert kind="error">{errorMessage(error)}</Alert>
      ) : (
        <>
          {isLoading ? (
            <div className="mb-6"><Spinner label="Loading resumes…" /></div>
          ) : (
            <>
          <ResumesHero
            defaultResume={defaultResume}
            count={list.length}
            limit={limit}
            atLimit={atLimit}
            tailorReady={tailor?.can_tailor}
            masterSkillsReady={tailor?.master_skills_ready}
          />

          <div className="mb-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <StatCard
              icon={<FileText className="h-4 w-4" aria-hidden />}
              label="Resume slots"
              value={`${list.length} / ${isUnlimitedUsageCap(limit, "resumes") ? "∞" : limit}`}
              sub={atLimit ? "Limit reached" : `${limit - list.length} slot${limit - list.length === 1 ? "" : "s"} free`}
            />
            <StatCard
              icon={<Star className="h-4 w-4" aria-hidden />}
              label="Default resume"
              value={defaultResume ? "Set" : "None"}
              sub={defaultResume ? defaultResume.name : "Upload to attach on runs"}
            />
            <StatCard
              icon={<Wand2 className="h-4 w-4" aria-hidden />}
              label="Master skills"
              value={defaultResume?.master_skills?.length ?? 0}
              sub={tailor?.master_skills_ready ? "Ready for automation tailor" : "Run Analyze skills on default"}
            />
            <StatCard
              icon={<Upload className="h-4 w-4" aria-hidden />}
              label="AI / styled copies"
              value={generatedCount(list)}
              sub={tailor?.resume_ai_available ? "Tailor & style enabled" : "AI tailoring needs admin setup"}
            />
          </div>

          {data && defaultResume && (
            <section className="mb-6 rounded-xl bg-gradient-to-r from-brand-50 to-white p-4 ring-1 ring-brand-200/80 sm:p-5">
              <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                <div className="flex min-w-0 items-start gap-3">
                  <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-brand-600 text-white">
                    <FileText className="h-6 w-6" aria-hidden />
                  </span>
                  <div className="min-w-0">
                    <p className="text-xs font-medium uppercase tracking-wide text-brand-700">Default for automation</p>
                    <p className="truncate text-lg font-semibold text-slate-900">{defaultResume.name}</p>
                    <p className="mt-0.5 text-sm text-slate-600">
                      {defaultResume.file_type.toUpperCase()} · {formatBytes(defaultResume.file_size)} · uploaded {formatDate(defaultResume.created_at)}
                    </p>
                  </div>
                </div>
                <a
                  href={resumesApi.downloadUrl(defaultResume.id)}
                  className="inline-flex shrink-0 items-center justify-center rounded-lg bg-white px-4 py-2 text-sm font-medium text-brand-700 ring-1 ring-brand-200 hover:bg-brand-50"
                >
                  Download default
                </a>
              </div>
            </section>
          )}
            </>
          )}

          <div className="mb-6 grid gap-6 lg:grid-cols-3">
            <div className="lg:col-span-2">
              <ResumeManager dashboardShell />
            </div>
            <div className="space-y-6">
              {usage && (
                <Card title="Plan usage">
                  <ProgressBar label="Resumes" usageKind="resumes" value={usage.resumes.used} max={usage.resumes.limit} />
                  <p className="mt-3 text-xs text-slate-500">
                    {usage.plan_name} · resets {formatDate(usage.resets_at)}
                  </p>
                  <ButtonLink to="/app/billing" variant="secondary" size="sm" className="mt-3 w-full">
                    Manage plan
                  </ButtonLink>
                </Card>
              )}
              <section className="rounded-xl bg-white p-4 shadow-sm ring-1 ring-slate-200/80 sm:p-5">
                <h2 className="text-sm font-semibold text-slate-900">Automation & tailoring</h2>
                <ul className="mt-3 space-y-2 text-sm text-slate-600">
                  <li>
                    {tailor?.resume_ai_available ? "✓ Platform AI available" : "○ AI tailoring not configured"}
                  </li>
                  <li>
                    {tailor?.master_skills_ready ? "✓ Master skills analyzed" : "○ Analyze skills on your default resume"}
                  </li>
                  <li>
                    {tailor?.can_tailor ? "✓ Per-job tailor enabled on runs" : "○ Enable tailor_if_gate on automation runs"}
                  </li>
                </ul>
                <Link to="/app/automation" className="mt-3 inline-block text-sm font-medium text-brand-600 hover:underline">
                  Open automation
                </Link>
              </section>
              <section className="rounded-xl bg-slate-50 p-4 ring-1 ring-slate-200/80">
                <h2 className="text-sm font-semibold text-slate-900">Tips</h2>
                <ul className="mt-2 list-disc space-y-1 pl-4 text-sm text-slate-600">
                  <li>PDF or DOCX up to 5 MB; scanned PDFs use OCR.</li>
                  <li>Re-run intake from Profile after a major CV update.</li>
                  <li>Tailor manually with a pasted job description (≥60% match gate).</li>
                </ul>
              </section>
            </div>
          </div>
        </>
      )}
    </>
  );
}

function ResumesHero({
  defaultResume,
  count,
  limit,
  atLimit,
  tailorReady,
  masterSkillsReady,
}: {
  defaultResume?: Resume;
  count: number;
  limit: number;
  atLimit: boolean;
  tailorReady?: boolean;
  masterSkillsReady?: boolean;
}) {
  let headline = "Your resume workspace";
  let detail = "Upload CVs, pick a visual style, and build job-specific versions for LinkedIn Easy Apply.";

  if (count === 0) {
    headline = "Add your first resume";
    detail = "Automation needs at least one file — usually your main CV as the default.";
  } else if (atLimit) {
    headline = "Resume limit reached";
    detail = "Delete an old copy or upgrade your plan before uploading or saving styled versions.";
  } else if (!masterSkillsReady && defaultResume) {
    headline = "Analyze skills on your default resume";
    detail = "Master skills power AI tailoring during automation runs (tailor_if_gate mode).";
  } else if (tailorReady && defaultResume) {
    headline = "Ready to tailor on automation runs";
    detail = `"${defaultResume.name}" is your default · ${count} of ${limit} slots used.`;
  } else if (defaultResume) {
    headline = defaultResume.name;
    detail = `Default resume · ${count} file${count === 1 ? "" : "s"} in your library.`;
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
