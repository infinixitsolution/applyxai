import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BarChart3, BookOpen, Briefcase, Clock, Download, MessageSquare, Mic, RefreshCw, Target } from "lucide-react";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Alert, Badge, Button, ButtonLink, Card, cx } from "../components/ui";
import { formatDateTime } from "../lib/format";
import { errorMessage } from "../services/api";
import { liveInterviews } from "../services/endpoints";
import type { LiveInterviewSession, MockInterviewFeedback } from "../types";
import { exportLiveInterviewReportPdf } from "./exportLiveInterviewReportPdf";
import { MockInterviewRubricReport } from "./MockInterviewRubricReport";

const SECTIONS = [
  { id: "overview", label: "Overview" },
  { id: "categories", label: "Categories" },
  { id: "questions", label: "Q&A review" },
  { id: "coaching", label: "Coaching" },
  { id: "rubric", label: "100 parameters" },
  { id: "transcript", label: "Transcript" },
] as const;

const ROLE_LABEL = {
  interviewer: "Interviewer",
  suggestion: "Suggested answer",
  candidate: "You said",
} as const;

function scoreTone(score: number | null | undefined): "green" | "blue" | "amber" | "red" | "slate" {
  if (score == null) return "slate";
  if (score >= 70) return "green";
  if (score >= 45) return "blue";
  if (score >= 20) return "amber";
  return "red";
}

function durationLabel(start?: string | null, end?: string | null) {
  if (!start || !end) return "—";
  const ms = new Date(end).getTime() - new Date(start).getTime();
  if (!Number.isFinite(ms) || ms < 0) return "—";
  const minutes = Math.round(ms / 60000);
  return minutes < 1 ? "<1 min" : `${minutes} min`;
}

function KpiCard({
  label,
  value,
  sub,
  icon: Icon,
}: {
  label: string;
  value: string | number;
  sub?: string;
  icon: typeof BarChart3;
}) {
  return (
    <div className="rounded-2xl bg-white p-4 shadow-sm ring-1 ring-slate-200/80">
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</p>
          <p className="mt-1 font-mono text-2xl font-bold tabular-nums text-slate-900">{value}</p>
          {sub && <p className="mt-1 text-xs text-slate-500">{sub}</p>}
        </div>
        <div className="rounded-xl bg-brand-50 p-2 text-brand-600">
          <Icon className="h-5 w-5" aria-hidden />
        </div>
      </div>
    </div>
  );
}

function ScoreBar({ label, score }: { label: string; score: number }) {
  return (
    <div>
      <div className="mb-1 flex justify-between text-sm">
        <span className="font-medium text-slate-800">{label}</span>
        <span className="font-mono text-slate-600">{score}/100</span>
      </div>
      <div className="h-2.5 overflow-hidden rounded-full bg-slate-100">
        <div
          className={cx(
            "h-full rounded-full",
            score >= 70 ? "bg-emerald-500" : score >= 45 ? "bg-brand-500" : score >= 20 ? "bg-amber-500" : "bg-red-400",
          )}
          style={{ width: `${Math.min(100, Math.max(0, score))}%` }}
        />
      </div>
    </div>
  );
}

export function LiveInterviewReportDashboard({
  session,
  readOnly = false,
  backTo = "/app/live-interviews",
  backLabel = "All interviews",
}: {
  session: LiveInterviewSession;
  readOnly?: boolean;
  backTo?: string;
  backLabel?: string;
}) {
  const [navActive, setNavActive] = useState<string>("overview");
  const [exportingPdf, setExportingPdf] = useState(false);
  const [exportPdfError, setExportPdfError] = useState<string | null>(null);
  const [applicationId, setApplicationId] = useState("");
  const queryClient = useQueryClient();
  const needsJob = !readOnly && !session.job_title && !session.company;
  const applications = useQuery({
    queryKey: ["live-interview-applications"],
    queryFn: liveInterviews.applications,
    enabled: needsJob,
  });
  const attachJob = useMutation({
    mutationFn: () => liveInterviews.attach(session.id, applicationId),
    onSuccess: async (next) => {
      queryClient.setQueryData(["live-interviews", session.id], next);
      await queryClient.invalidateQueries({ queryKey: ["live-interviews"] });
    },
  });
  const regenerate = useMutation({
    mutationFn: () => liveInterviews.regenerate(session.id),
    onSuccess: async (next) => {
      queryClient.setQueryData(["live-interviews", session.id], next);
      await queryClient.invalidateQueries({ queryKey: ["live-interviews"] });
    },
  });
  const fb = session.feedback;
  const stats = useMemo(() => {
    const transcript = session.transcript ?? [];
    const scored = (fb?.rubric_scores ?? []).filter((row) => row.score != null).length;
    return {
      candidate: transcript.filter((t) => t.role === "candidate").length,
      interviewer: transcript.filter((t) => t.role === "interviewer").length,
      suggestions: transcript.filter((t) => t.role === "suggestion").length,
      scored,
    };
  }, [session.transcript, fb?.rubric_scores]);

  if (session.status !== "completed" || !fb) {
    return (
      <Card title="Report">
        <p className="text-sm text-slate-600">
          {readOnly
            ? "This interview is still running in the candidate's desktop agent. The report appears when they end it."
            : "This interview is still running in the desktop agent. End it there to generate the report."}
        </p>
        {readOnly && <ButtonLink to={backTo} variant="secondary" className="mt-4">{backLabel}</ButtonLink>}
      </Card>
    );
  }

  const summary = fb.knowledge_summary || fb.summary;
  const tips = fb.suggestions ?? [];

  async function handleExportPdf() {
    setExportPdfError(null);
    setExportingPdf(true);
    try {
      await exportLiveInterviewReportPdf(session);
    } catch {
      setExportPdfError("Could not generate PDF. Try again or use your browser print dialog.");
    } finally {
      setExportingPdf(false);
    }
  }

  return (
    <div className="pb-12">
      <div className="mb-6 overflow-hidden rounded-2xl bg-gradient-to-br from-slate-900 via-slate-800 to-brand-900 text-white shadow-lg">
        <div className="p-6 sm:p-8">
          <div className="flex flex-col gap-6 lg:flex-row lg:items-start lg:justify-between">
            <div className="min-w-0 flex-1">
              <p className="text-xs font-semibold uppercase tracking-wider text-brand-200">Live interview report</p>
              <h1 className="mt-1 text-2xl font-bold sm:text-3xl">{session.job_title || "Live interview"}</h1>
              <p className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-slate-300">
                <span className="inline-flex items-center gap-1">
                  <Briefcase className="h-4 w-4" aria-hidden /> {session.company || "No job selected"}
                </span>
                <span className="inline-flex items-center gap-1">
                  <Clock className="h-4 w-4" aria-hidden /> {formatDateTime(session.ended_at || session.started_at)}
                </span>
                <span className="inline-flex items-center gap-1">
                  <Mic className="h-4 w-4" aria-hidden /> {durationLabel(session.started_at, session.ended_at)}
                </span>
              </p>
              {summary && <p className="mt-4 max-w-3xl text-sm leading-relaxed text-slate-200">{summary}</p>}
            </div>
            <div className="flex flex-col items-start gap-3 lg:items-end">
              <div className="rounded-2xl bg-white/10 px-5 py-3 text-center">
                <p className="text-xs uppercase tracking-wide text-brand-200">Overall</p>
                <p className="font-mono text-4xl font-bold">{fb.overall_score ?? "—"}</p>
                <p className="text-xs text-slate-300">out of 100</p>
              </div>
              <div className="flex flex-wrap gap-2">
                {!readOnly && (
                  <Button
                    variant="secondary"
                    className="border-white/20 bg-white/10 text-white hover:bg-white/20"
                    loading={regenerate.isPending}
                    onClick={() => regenerate.mutate()}
                  >
                    <RefreshCw className="h-4 w-4" aria-hidden /> Regenerate
                  </Button>
                )}
                <Button
                  variant="secondary"
                  className="border-white/20 bg-white/10 text-white hover:bg-white/20"
                  loading={exportingPdf}
                  onClick={() => void handleExportPdf()}
                >
                  <Download className="h-4 w-4" aria-hidden /> Export PDF
                </Button>
                <ButtonLink to={backTo} variant="secondary" className="border-white/20 bg-white/10 text-white hover:bg-white/20">
                  {backLabel}
                </ButtonLink>
              </div>
            </div>
          </div>
        </div>
      </div>

      {needsJob && (
        <div className="mb-4 rounded-xl bg-white p-4 shadow-sm ring-1 ring-slate-200/80">
          <p className="text-sm font-medium text-slate-900">No job was attached when this interview started.</p>
          <p className="mt-1 text-sm text-slate-600">Choose an auto-applied job so the report names the role. Regenerating the score uses that job.</p>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <select
              className="min-w-0 flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm"
              value={applicationId}
              onChange={(event) => setApplicationId(event.target.value)}
            >
              <option value="">Select an auto-applied job</option>
              {(applications.data ?? []).map((job) => (
                <option key={job.id} value={job.id}>{job.title} · {job.company}</option>
              ))}
            </select>
            <Button variant="secondary" loading={attachJob.isPending} disabled={!applicationId} onClick={() => attachJob.mutate()}>
              Use this job
            </Button>
          </div>
          {applications.error && <div className="mt-3"><Alert kind="error">{errorMessage(applications.error)}</Alert></div>}
          {attachJob.error && <div className="mt-3"><Alert kind="error">{errorMessage(attachJob.error)}</Alert></div>}
        </div>
      )}

      {(exportPdfError || regenerate.error) && (
        <div className="mb-4">
          <Alert kind="error">{exportPdfError || errorMessage(regenerate.error)}</Alert>
        </div>
      )}

      <nav className="sticky top-0 z-20 -mx-1 mb-6 overflow-x-auto border-b border-slate-200/80 bg-app-page/95 px-1 py-2 backdrop-blur">
        <ul className="flex min-w-max gap-1">
          {SECTIONS.map((section) => (
            <li key={section.id}>
              <a
                href={`#${section.id}`}
                onClick={() => setNavActive(section.id)}
                className={cx(
                  "rounded-lg px-3 py-1.5 text-sm font-medium transition",
                  navActive === section.id ? "bg-brand-100 text-brand-800" : "text-slate-600 hover:bg-slate-100 hover:text-slate-900",
                )}
              >
                {section.label}
              </a>
            </li>
          ))}
        </ul>
      </nav>

      <section id="overview" className="scroll-mt-24">
        <p className="mb-4 text-sm text-slate-600">
          Scores use the same 100-parameter mock-interview rubric and count only what you said aloud. Suggested answers are coaching and are not scored. On-camera behavior is not part of a live interview, because the desktop agent does not record a camera.
          {fb.rubric_version != null && <span className="text-slate-500"> Rubric v{fb.rubric_version}.</span>}
        </p>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <KpiCard label="Overall score" value={fb.overall_score ?? "—"} sub="From your spoken answers" icon={Target} />
          <KpiCard label="Answer rubric" value={fb.rubric_overall ?? "—"} sub={`${stats.scored}/100 parameters scored`} icon={BarChart3} />
          <KpiCard label="Your answers" value={stats.candidate} sub={`${stats.interviewer} interviewer lines`} icon={MessageSquare} />
          <KpiCard label="Coaching lines" value={stats.suggestions} sub="Shown in the desktop window" icon={BookOpen} />
          <KpiCard label="Duration" value={durationLabel(session.started_at, session.ended_at)} sub={session.started_at ? formatDateTime(session.started_at) : "Start time unavailable"} icon={Clock} />
          <KpiCard label="Questions reviewed" value={fb.question_breakdown?.length ?? 0} sub="Each interviewer prompt" icon={Mic} />
        </div>
      </section>

      <div className="mt-6 grid gap-6 lg:grid-cols-3">
        <section id="categories" className="scroll-mt-24 lg:col-span-2">
          <Card title="Category performance" className="h-full">
            <p className="mb-4 text-sm text-slate-600">Average scores across the 10 analysis categories.</p>
            {(fb.rubric_categories ?? []).length ? (
              <ul className="space-y-3">
                {fb.rubric_categories!.map((cat) => (
                  <li key={cat.category_id}>
                    <div className="mb-1 flex justify-between gap-2 text-xs">
                      <span className="font-medium text-slate-800">{cat.category_label}</span>
                      <span className="shrink-0 font-mono text-slate-500">
                        {cat.average_score != null ? `${cat.average_score}/100` : "N/A"} · {cat.parameters_scored}/{cat.parameters_total}
                      </span>
                    </div>
                    <div className="h-2 overflow-hidden rounded-full bg-slate-100">
                      <div className="h-full rounded-full bg-gradient-to-r from-brand-400 to-brand-600" style={{ width: `${cat.average_score ?? 0}%` }} />
                    </div>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-slate-500">Category scores appear after the 100-parameter analysis is saved.</p>
            )}
          </Card>
        </section>
        <section className="scroll-mt-24">
          <Card title="Core dimensions" className="h-full">
            <div className="space-y-4">
              {(fb.dimensions ?? []).map((d) => (
                <ScoreBar key={d.key || d.label} label={d.label || d.key || "Dimension"} score={d.score ?? 0} />
              ))}
              {!fb.dimensions?.length && <p className="text-sm text-slate-500">No dimension scores in this report.</p>}
            </div>
            {(fb.dimensions ?? []).map((d) =>
              d.notes ? (
                <p key={`${d.key}-n`} className="mt-4 border-t border-slate-100 pt-3 text-xs text-slate-600">
                  <strong className="text-slate-800">{d.label}:</strong> {d.notes}
                </p>
              ) : null,
            )}
          </Card>
        </section>
      </div>

      <section id="questions" className="mt-6 scroll-mt-24">
        <Card title="Question-by-question review">
          {(fb.question_breakdown ?? []).length ? (
            <ol className="relative space-y-0 border-l-2 border-brand-200 pl-6">
              {fb.question_breakdown!.map((row, i) => (
                <li key={`${i}-${row.question}`} className="relative pb-8 last:pb-0">
                  <span className="absolute -left-[1.35rem] flex h-6 w-6 items-center justify-center rounded-full bg-brand-600 text-xs font-bold text-white">
                    {i + 1}
                  </span>
                  <div className="rounded-xl border border-slate-100 bg-white p-4 shadow-sm">
                    <div className="flex flex-wrap items-start justify-between gap-2">
                      <p className="text-sm font-medium text-slate-900">{row.question}</p>
                      <Badge tone={scoreTone(row.answer_quality === "strong" ? 80 : row.answer_quality === "adequate" ? 55 : row.answer_quality === "weak" ? 30 : 5)}>
                        {row.answer_quality || "unrated"}
                      </Badge>
                    </div>
                    {row.notes && <p className="mt-2 text-sm text-slate-600">{row.notes}</p>}
                  </div>
                </li>
              ))}
            </ol>
          ) : (
            <p className="text-sm text-slate-500">No per-question breakdown was saved for this interview.</p>
          )}
        </Card>
      </section>

      <section id="coaching" className="mt-6 scroll-mt-24">
        <div className="grid gap-6 lg:grid-cols-2">
          <Card title="Strengths">
            {(fb.strengths ?? []).length ? (
              <ul className="space-y-2">
                {fb.strengths!.map((item) => (
                  <li key={item} className="flex gap-2 rounded-lg bg-emerald-50/80 px-3 py-2 text-sm text-emerald-900">
                    <span className="text-emerald-600" aria-hidden>+</span>
                    {item}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-slate-500">No strengths were recorded from the spoken answers.</p>
            )}
          </Card>
          <Card title="Improve next time">
            {tips.length ? (
              <ul className="space-y-2">
                {tips.map((item) => (
                  <li key={item} className="flex gap-2 rounded-lg bg-amber-50/80 px-3 py-2 text-sm text-amber-950">
                    <span className="text-amber-600" aria-hidden>→</span>
                    {item}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-slate-500">No improvement tips were saved.</p>
            )}
          </Card>
        </div>
        {(fb.sample_answers ?? []).length > 0 && (
          <Card title="Stronger answer examples" className="mt-6">
            <ul className="grid gap-4 md:grid-cols-2">
              {fb.sample_answers!.map((item) => (
                <li key={item.question} className="rounded-xl border border-slate-100 p-4">
                  <p className="flex items-start gap-2 text-sm font-medium text-slate-900">
                    <BookOpen className="mt-0.5 h-4 w-4 shrink-0 text-brand-600" aria-hidden />
                    {item.question}
                  </p>
                  <p className="mt-2 text-sm leading-relaxed text-slate-600">{item.suggestion}</p>
                </li>
              ))}
            </ul>
          </Card>
        )}
      </section>

      <section id="rubric" className="mt-6 scroll-mt-24">
        <Card title="Detailed rubric (100 parameters)">
          {(fb.rubric_scores ?? []).length ? (
            <MockInterviewRubricReport feedback={fb as MockInterviewFeedback} embedded />
          ) : (
            <p className="text-sm text-slate-500">This report was saved before the 100-parameter rubric. End a new interview to generate it.</p>
          )}
        </Card>
      </section>

      <section id="transcript" className="mt-6 scroll-mt-24">
        <Card title="Conversation">
          <div className="max-h-[32rem] space-y-3 overflow-y-auto pr-1">
            {(session.transcript ?? []).map((turn, index) => (
              <div
                key={`${turn.at || index}-${turn.role}`}
                className={cx(
                  "rounded-xl px-4 py-3 text-sm",
                  turn.role === "interviewer" && "bg-slate-100 text-slate-800",
                  turn.role === "candidate" && "ml-4 border border-brand-100 bg-brand-50/50 text-brand-950",
                  turn.role === "suggestion" && "border border-emerald-100 bg-emerald-50 text-emerald-950",
                )}
              >
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">{ROLE_LABEL[turn.role] || turn.role}</p>
                <p className="mt-1 whitespace-pre-wrap leading-relaxed">{turn.text}</p>
              </div>
            ))}
            {!session.transcript?.length && <p className="text-sm text-slate-500">No lines captured.</p>}
          </div>
          {!readOnly && (
            <p className="mt-4 text-center text-xs text-slate-500">
              <Link to="/app/support" className="text-brand-700 underline">Request another token</Link> for the next live interview.
            </p>
          )}
        </Card>
      </section>
    </div>
  );
}
