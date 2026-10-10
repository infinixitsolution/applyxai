import {
  BarChart3,
  BookOpen,
  Briefcase,
  Clock,
  MessageSquare,
  Mic,
  Download,
  RefreshCw,
  ScanEye,
  Sparkles,
  Target,
  User,
  Video,
} from "lucide-react";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Alert, Badge, Button, ButtonLink, Card, cx } from "../components/ui";
import { formatDateTime } from "../lib/format";
import type { MockInterviewFeedback, MockInterviewSessionDetail } from "../types";
import { exportMockInterviewReportPdf } from "./exportMockInterviewReportPdf";
import { MockInterviewBehaviorReport } from "./MockInterviewBehaviorReport";
import { MockInterviewRubricReport } from "./MockInterviewRubricReport";
import { buildMockInterviewReportStats } from "./mockInterviewReportMetrics";

const CONDUCT_LABELS: Record<string, string> = {
  smoking: "Smoking on camera",
  vaping: "Vaping on camera",
  eating: "Eating during interview",
  drinking_alcohol: "Alcohol visible",
  phone_use: "Phone use on camera",
  inappropriate_background: "Unprofessional background",
  off_camera_behavior: "Unprofessional on-camera behavior",
};

const AUTHENTICITY_LABELS: Record<string, string> = {
  human: "Naturally spoken",
  mixed: "Mixed style",
  bookish: "Textbook / formal",
  ai_like: "AI-like phrasing",
  missing: "No answers",
  unknown: "Unknown",
};

const SECTIONS = [
  { id: "overview", label: "Overview" },
  { id: "categories", label: "Categories" },
  { id: "presence", label: "Presence & style" },
  { id: "behavior", label: "On-camera behavior" },
  { id: "questions", label: "Q&A review" },
  { id: "coaching", label: "Coaching" },
  { id: "rubric", label: "100 parameters" },
  { id: "transcript", label: "Transcript" },
] as const;

function scoreTone(score: number | null | undefined): "green" | "blue" | "amber" | "red" | "slate" {
  if (score == null) return "slate";
  if (score >= 70) return "green";
  if (score >= 45) return "blue";
  if (score >= 20) return "amber";
  return "red";
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
            "h-full rounded-full transition-all",
            score >= 70 ? "bg-emerald-500" : score >= 45 ? "bg-brand-500" : score >= 20 ? "bg-amber-500" : "bg-red-400",
          )}
          style={{ width: `${Math.min(100, Math.max(0, score))}%` }}
        />
      </div>
    </div>
  );
}

function CategoryChart({ feedback }: { feedback: MockInterviewFeedback }) {
  const cats = feedback.rubric_categories ?? [];
  if (!cats.length) return <p className="text-sm text-slate-500">Regenerate analysis to load category scores.</p>;
  return (
    <ul className="space-y-3">
      {cats.map((cat) => {
        const avg = cat.average_score;
        const width = avg != null ? avg : 0;
        return (
          <li key={cat.category_id}>
            <div className="mb-1 flex justify-between gap-2 text-xs">
              <span className="font-medium text-slate-800">{cat.category_label}</span>
              <span className="shrink-0 font-mono text-slate-500">
                {avg != null ? `${avg}/100` : "N/A"} · {cat.parameters_scored}/{cat.parameters_total}
              </span>
            </div>
            <div className="h-2 overflow-hidden rounded-full bg-slate-100">
              <div
                className="h-full rounded-full bg-gradient-to-r from-brand-400 to-brand-600"
                style={{ width: `${width}%` }}
              />
            </div>
          </li>
        );
      })}
    </ul>
  );
}

export function MockInterviewReportDashboard({
  session,
  feedback: fb,
  onRegenerate,
  regenerating,
  regenerateError,
}: {
  session: MockInterviewSessionDetail;
  feedback: MockInterviewFeedback;
  onRegenerate: () => void;
  regenerating: boolean;
  regenerateError?: string | null;
}) {
  const [navActive, setNavActive] = useState<string>("overview");
  const [exportingPdf, setExportingPdf] = useState(false);
  const [exportPdfError, setExportPdfError] = useState<string | null>(null);

  const handleExportPdf = async () => {
    setExportPdfError(null);
    setExportingPdf(true);
    try {
      await exportMockInterviewReportPdf(session, fb);
    } catch {
      setExportPdfError("Could not generate PDF. Try again or use your browser print dialog.");
    } finally {
      setExportingPdf(false);
    }
  };

  const stats = useMemo(() => buildMockInterviewReportStats(session, fb), [session, fb]);

  const snap = session.context_snapshot;

  return (
    <div className="pb-12">
      {/* Hero */}
      <div className="mb-6 overflow-hidden rounded-2xl bg-gradient-to-br from-slate-900 via-slate-800 to-brand-900 text-white shadow-lg">
        <div className="p-6 sm:p-8">
          <div className="flex flex-col gap-6 lg:flex-row lg:items-start lg:justify-between">
            <div className="min-w-0 flex-1">
              <p className="text-xs font-semibold uppercase tracking-wider text-brand-200">Mock interview dashboard</p>
              <h1 className="mt-1 text-2xl font-bold sm:text-3xl">{snap.job_title || "Practice session"}</h1>
              <p className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-slate-300">
                <span className="inline-flex items-center gap-1">
                  <Briefcase className="h-4 w-4" aria-hidden /> {snap.company || "Company"}
                </span>
                <span className="inline-flex items-center gap-1">
                  <Clock className="h-4 w-4" aria-hidden /> {formatDateTime(session.updated_at)}
                </span>
                <span className="inline-flex items-center gap-1">
                  <Mic className="h-4 w-4" aria-hidden /> {stats.types}
                </span>
              </p>
              {fb.knowledge_summary && (
                <p className="mt-4 max-w-3xl text-sm leading-relaxed text-slate-200">{fb.knowledge_summary}</p>
              )}
            </div>
            <div className="flex flex-wrap gap-2 lg:shrink-0">
              <Button
                variant="secondary"
                className="border-white/20 bg-white/10 text-white hover:bg-white/20"
                loading={exportingPdf}
                onClick={() => void handleExportPdf()}
              >
                <Download className="h-4 w-4" aria-hidden /> Export PDF
              </Button>
              <Button
                variant="secondary"
                className="border-white/20 bg-white/10 text-white hover:bg-white/20"
                loading={regenerating}
                onClick={onRegenerate}
              >
                <RefreshCw className="h-4 w-4" aria-hidden /> Regenerate
              </Button>
              <ButtonLink to="/app/mock-interview" variant="secondary" className="border-white/20 bg-white/10 text-white hover:bg-white/20">
                New interview
              </ButtonLink>
              <ButtonLink to={`/app/mock-interview/${session.id}`} variant="secondary" className="hidden border-white/20 bg-white/10 text-white hover:bg-white/20 sm:inline-flex">
                Session
              </ButtonLink>
            </div>
          </div>
        </div>
      </div>

      {(regenerateError || exportPdfError) && (
        <div className="mb-4 space-y-2">
          {regenerateError && <Alert kind="error">{regenerateError}</Alert>}
          {exportPdfError && <Alert kind="error">{exportPdfError}</Alert>}
        </div>
      )}
      {fb.error && (
        <div className="mb-4">
          <Alert kind="info">{fb.error}</Alert>
        </div>
      )}

      {/* Sticky nav */}
      <nav className="sticky top-0 z-20 -mx-1 mb-6 overflow-x-auto border-b border-slate-200/80 bg-app-page/95 px-1 py-2 backdrop-blur supports-[backdrop-filter]:bg-app-page/80">
        <ul className="flex min-w-max gap-1">
          {SECTIONS.map((s) => (
            <li key={s.id}>
              <a
                href={`#${s.id}`}
                onClick={() => setNavActive(s.id)}
                className={cx(
                  "rounded-lg px-3 py-1.5 text-sm font-medium transition",
                  navActive === s.id ? "bg-brand-100 text-brand-800" : "text-slate-600 hover:bg-slate-100 hover:text-slate-900",
                )}
              >
                {s.label}
              </a>
            </li>
          ))}
        </ul>
      </nav>

      {/* KPIs */}
      <section id="overview" className="scroll-mt-24">
        {fb.analysis_meta && (
          <div className="mb-4 rounded-xl border border-slate-200/80 bg-white px-4 py-3 text-sm text-slate-600 shadow-sm">
            <p>
              <strong className="text-slate-800">Analysis pipeline</strong> — transcript coaching, 100-parameter answer
              rubric, 55-parameter on-camera behavior
              {stats.framesAnalyzed != null && stats.framesAnalyzed > 0
                ? ` (${stats.framesAnalyzed} camera snapshot${stats.framesAnalyzed === 1 ? "" : "s"})`
                : ""}
              , and authenticity review.
            </p>
            <p className="mt-1 text-xs text-slate-500">
              Generated {formatDateTime(stats.generatedAt ?? session.updated_at)}
              {fb.analysis_meta.rubric_version != null && ` · Rubric v${fb.analysis_meta.rubric_version}`}
              {fb.analysis_meta.behavior_analysis_version != null &&
                ` · Behavior v${fb.analysis_meta.behavior_analysis_version}`}
              {stats.behaviorConcerns > 0 && (
                <span className="font-medium text-red-600"> · {stats.behaviorConcerns} on-camera concern(s)</span>
              )}
            </p>
            <p className="mt-1 text-xs text-slate-500">
              Regenerate re-runs answer and coaching AI from the saved transcript; on-camera sections need camera frames
              from the live session (not stored after the first report).
            </p>
          </div>
        )}
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <KpiCard label="Overall score" value={fb.overall_score ?? "—"} sub="Interview performance" icon={Target} />
          <KpiCard
            label="Answer rubric"
            value={fb.rubric_overall ?? "—"}
            sub={`${stats.rubricScored}/100 parameters scored`}
            icon={BarChart3}
          />
          <KpiCard
            label="On-camera behavior"
            value={stats.behaviorOverall ?? "—"}
            sub={
              stats.behaviorConcerns > 0
                ? `${stats.behaviorConcerns} concern(s) · 55 parameters`
                : "55 parameters from snapshots"
            }
            icon={ScanEye}
          />
          <KpiCard
            label="Presentation"
            value={stats.presentationScore ?? "—"}
            sub={stats.presentationScore != null ? "Expression, gaze, grooming" : "No camera data"}
            icon={Video}
          />
          <KpiCard
            label="Your answers"
            value={stats.candidateAnswers}
            sub={`${stats.questions} prompts · ${stats.turns} turns`}
            icon={MessageSquare}
          />
          <KpiCard
            label="Conduct flags"
            value={stats.conductIssueCount > 0 ? stats.conductIssueCount : "0"}
            sub={stats.conductIssueCount > 0 ? "See presence & behavior sections" : "No prohibited activity flagged"}
            icon={User}
          />
        </div>
      </section>

      <div className="mt-6 grid gap-6 lg:grid-cols-3">
        <section id="categories" className="scroll-mt-24 lg:col-span-2">
          <Card title="Category performance" className="h-full">
            <p className="mb-4 text-sm text-slate-600">Average scores across the 10 analysis categories.</p>
            <CategoryChart feedback={fb} />
          </Card>
        </section>
        <section className="scroll-mt-24">
          <Card title="Core dimensions" className="h-full">
            <div className="space-y-4">
              {(fb.dimensions ?? []).map((d) => (
                <ScoreBar key={d.key} label={d.label} score={d.score} />
              ))}
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

      <section id="presence" className="mt-6 scroll-mt-24">
        <div className="grid gap-6 md:grid-cols-2">
          <Card title="On-camera presence">
            {fb.presentation?.available && fb.presentation.overall_score != null ? (
              <>
                {(fb.presentation.professional_conduct?.issues ?? []).length > 0 && (
                  <div className="mb-4">
                  <Alert kind="error">
                    <p className="font-semibold">Interview conduct flagged on camera</p>
                    <ul className="mt-2 list-inside list-disc text-sm">
                      {fb.presentation.professional_conduct!.issues!.map((code) => (
                        <li key={code}>{CONDUCT_LABELS[code] ?? code.replace(/_/g, " ")}</li>
                      ))}
                    </ul>
                    {fb.presentation.professional_conduct?.notes && (
                      <p className="mt-2 text-sm opacity-90">{fb.presentation.professional_conduct.notes}</p>
                    )}
                  </Alert>
                  </div>
                )}
                {fb.presentation.professional_conduct?.score != null &&
                  (fb.presentation.professional_conduct.issues ?? []).length > 0 && (
                    <ScoreBar label="Professional conduct" score={fb.presentation.professional_conduct.score} />
                  )}
                <ScoreBar label="Presentability" score={fb.presentation.overall_score} />
                <div className="mt-4 grid gap-3 sm:grid-cols-3">
                  {fb.presentation.facial_expression && (
                    <div className="rounded-xl bg-slate-50 p-3 text-center">
                      <User className="mx-auto h-5 w-5 text-slate-500" aria-hidden />
                      <p className="mt-1 text-xs font-medium text-slate-500">Expression</p>
                      <p className="font-mono text-lg font-bold text-slate-900">{fb.presentation.facial_expression.score}</p>
                    </div>
                  )}
                  {fb.presentation.eye_contact && (
                    <div className="rounded-xl bg-slate-50 p-3 text-center">
                      <Target className="mx-auto h-5 w-5 text-slate-500" aria-hidden />
                      <p className="mt-1 text-xs font-medium text-slate-500">Eye contact</p>
                      <p className="font-mono text-lg font-bold text-slate-900">{fb.presentation.eye_contact.score}</p>
                    </div>
                  )}
                  {fb.presentation.grooming && (
                    <div className="rounded-xl bg-slate-50 p-3 text-center">
                      <Sparkles className="mx-auto h-5 w-5 text-slate-500" aria-hidden />
                      <p className="mt-1 text-xs font-medium text-slate-500">Grooming</p>
                      <p className="font-mono text-lg font-bold text-slate-900">{fb.presentation.grooming.score}</p>
                    </div>
                  )}
                </div>
                <div className="mt-4 space-y-2 text-sm text-slate-600">
                  {fb.presentation.facial_expression?.notes && <p>{fb.presentation.facial_expression.notes}</p>}
                  {fb.presentation.eye_contact?.notes && <p>{fb.presentation.eye_contact.notes}</p>}
                  {fb.presentation.grooming?.notes && <p>{fb.presentation.grooming.notes}</p>}
                </div>
              </>
            ) : (
              <p className="text-sm text-slate-600">
                {fb.presentation?.presentability_summary ??
                  "Enable your camera during the next session for expression, eye contact, and grooming feedback."}
              </p>
            )}
          </Card>
          <Card title="Answer authenticity">
            {fb.answer_authenticity ? (
              <>
                <div className="flex flex-wrap items-center gap-2">
                  <Badge tone={scoreTone(fb.answer_authenticity.confidence ?? 50)}>
                    {AUTHENTICITY_LABELS[fb.answer_authenticity.overall] ?? fb.answer_authenticity.overall}
                  </Badge>
                  {fb.answer_authenticity.confidence != null && (
                    <span className="text-sm text-slate-500">{fb.answer_authenticity.confidence}% confidence</span>
                  )}
                </div>
                {fb.answer_authenticity.notes && (
                  <p className="mt-3 text-sm leading-relaxed text-slate-600">{fb.answer_authenticity.notes}</p>
                )}
                {(fb.answer_authenticity.signals ?? []).length > 0 && (
                  <ul className="mt-3 space-y-2">
                    {fb.answer_authenticity.signals!.map((s) => (
                      <li key={s} className="rounded-lg bg-slate-50 px-3 py-2 text-sm text-slate-700">
                        {s}
                      </li>
                    ))}
                  </ul>
                )}
              </>
            ) : (
              <p className="text-sm text-slate-500">No authenticity analysis yet.</p>
            )}
          </Card>
        </div>
      </section>

      <section id="behavior" className="mt-6 scroll-mt-24">
        <Card title="On-camera behavioral analysis (55 parameters)">
          <p className="mb-4 text-sm text-slate-600">
            Eye contact, expression, posture, gestures, video quality, prohibited activities, distracting habits, and
            integrity signals—inferred from camera snapshots during your session.
          </p>
          <MockInterviewBehaviorReport feedback={fb} />
        </Card>
      </section>

      <section id="questions" className="mt-6 scroll-mt-24">
        {(fb.question_breakdown ?? []).length > 0 ? (
          <Card title="Question-by-question review">
            <ol className="relative space-y-0 border-l-2 border-brand-200 pl-6">
              {fb.question_breakdown!.map((row, i) => (
                <li key={`${i}-${row.question.slice(0, 32)}`} className="relative pb-8 last:pb-0">
                  <span className="absolute -left-[1.35rem] flex h-6 w-6 items-center justify-center rounded-full bg-brand-600 text-xs font-bold text-white">
                    {i + 1}
                  </span>
                  <div className="rounded-xl border border-slate-100 bg-white p-4 shadow-sm">
                    <div className="flex flex-wrap items-start justify-between gap-2">
                      <p className="text-sm font-medium text-slate-900">{row.question}</p>
                      <Badge
                        tone={
                          row.answer_quality === "strong"
                            ? "green"
                            : row.answer_quality === "adequate"
                              ? "blue"
                              : row.answer_quality === "weak"
                                ? "amber"
                                : "red"
                        }
                      >
                        {row.answer_quality}
                      </Badge>
                    </div>
                    {row.notes && <p className="mt-2 text-sm text-slate-600">{row.notes}</p>}
                  </div>
                </li>
              ))}
            </ol>
          </Card>
        ) : (
          <Card title="Question-by-question review">
            <p className="text-sm text-slate-500">No per-question breakdown in this report. Try regenerating analysis.</p>
          </Card>
        )}
      </section>

      <section id="coaching" className="mt-6 scroll-mt-24">
        <div className="grid gap-6 lg:grid-cols-2">
          <Card title="Strengths">
            {(fb.strengths ?? []).length > 0 ? (
              <ul className="space-y-2">
                {fb.strengths!.map((s) => (
                  <li key={s} className="flex gap-2 rounded-lg bg-emerald-50/80 px-3 py-2 text-sm text-emerald-900">
                    <span className="text-emerald-600" aria-hidden>
                      +
                    </span>
                    {s}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-slate-500">No strengths listed.</p>
            )}
          </Card>
          <Card title="Improve next time">
            {(fb.improvements ?? []).length > 0 ? (
              <ul className="space-y-2">
                {fb.improvements!.map((s) => (
                  <li key={s} className="flex gap-2 rounded-lg bg-amber-50/80 px-3 py-2 text-sm text-amber-950">
                    <span className="text-amber-600" aria-hidden>
                      →
                    </span>
                    {s}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-slate-500">No improvement tips listed.</p>
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
          <MockInterviewRubricReport feedback={fb} embedded />
        </Card>
      </section>

      <section id="transcript" className="mt-6 scroll-mt-24">
        <Card title="Full transcript">
          <div className="max-h-[28rem] space-y-3 overflow-y-auto pr-1">
            {session.messages.map((m) => (
              <div
                key={m.id}
                className={cx(
                  "rounded-xl px-4 py-3 text-sm",
                  m.role === "interviewer" ? "bg-slate-100 text-slate-800" : "ml-4 border border-brand-100 bg-brand-50/50 text-brand-950",
                )}
              >
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                  {m.role === "interviewer" ? "Interviewer" : "You"}
                </p>
                <p className="mt-1 leading-relaxed">{m.content}</p>
              </div>
            ))}
          </div>
          <p className="mt-4 text-center text-xs text-slate-500">
            <Link to="/app/mock-interview" className="text-brand-700 underline">
              Start another mock interview
            </Link>{" "}
            to improve your scores.
          </p>
        </Card>
      </section>
    </div>
  );
}
