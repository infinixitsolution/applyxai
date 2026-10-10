import { useMutation, useQuery } from "@tanstack/react-query";
import {
  BarChart3,
  Briefcase,
  Globe,
  Clock,
  Mic,
  Play,
  Sparkles,
  Target,
  TrendingUp,
  Video,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Select } from "../components/form";
import { Pagination } from "../components/Pagination";
import { FilterChipBrand } from "../pages/admin/shared";
import {
  Alert,
  Badge,
  Button,
  ButtonLink,
  Card,
  EmptyState,
  PageHeader,
  Spinner,
  StatCard,
  Tabs,
} from "../components/ui";
import { formatDateTime, formatRelative } from "../lib/format";
import { ApiError, errorMessage } from "../services/api";
import { applications, mockInterviews } from "../services/endpoints";
import type {
  Application,
  ApplicationStatus,
  InterviewType,
  MockInterviewFeedback,
  MockInterviewSessionStatus,
  MockInterviewSessionSummary,
} from "../types";

const TYPE_OPTIONS: { id: InterviewType; label: string; hint: string }[] = [
  { id: "behavioral", label: "Behavioral", hint: "STAR, past experience" },
  { id: "technical", label: "Technical", hint: "Skills & problem-solving" },
  { id: "hr", label: "HR / culture", hint: "Motivation & fit" },
  { id: "mixed", label: "Mixed", hint: "Rotate all styles" },
];

const STATUS_TABS = [
  { id: "all", label: "All" },
  { id: "completed", label: "Completed" },
  { id: "active", label: "In progress" },
  { id: "abandoned", label: "Abandoned" },
] as const;

type StatusTab = (typeof STATUS_TABS)[number]["id"];

const SESSION_PAGE = 8;

function mockInterviewStartError(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.code === "AI_DISABLED") {
      return "Mock interview AI is not enabled. Ask an admin to turn on Platform AI and Mock interview under Admin → Settings → AI.";
    }
    if (error.code === "AI_AUTH_FAILED" || (error.code === "AI_ERROR" && error.message.includes("(401)"))) {
      return "The platform AI API key was rejected (401). An admin must save a valid OpenAI (or compatible) key under Admin → Settings → AI and run Test AI.";
    }
    if (error.code === "INTERNAL_ERROR") {
      return "The server could not start a session. Run database migrations: python -m alembic -c backend/alembic.ini upgrade head";
    }
    return error.message;
  }
  return errorMessage(error);
}

export function sessionScore(session: MockInterviewSessionSummary): number | null {
  if (session.overall_score != null) return session.overall_score;
  const fb = (session.feedback ?? {}) as MockInterviewFeedback;
  if (fb.rubric_overall != null) return fb.rubric_overall;
  if (fb.overall_score != null) return fb.overall_score;
  return null;
}

function statusTone(status: MockInterviewSessionStatus): "green" | "blue" | "amber" | "slate" {
  if (status === "completed") return "green";
  if (status === "active") return "blue";
  if (status === "abandoned") return "amber";
  return "slate";
}

function statusLabel(status: MockInterviewSessionStatus): string {
  if (status === "active") return "In progress";
  if (status === "completed") return "Completed";
  return "Abandoned";
}

function typeLabels(types: InterviewType[]): string {
  if (types.includes("mixed")) return "Mixed";
  return types.map((t) => TYPE_OPTIONS.find((o) => o.id === t)?.label ?? t).join(", ");
}

function aggregateStats(items: MockInterviewSessionSummary[]) {
  const completed = items.filter((s) => s.status === "completed");
  const active = items.filter((s) => s.status === "active");
  const scores = completed.map(sessionScore).filter((n): n is number => n != null);
  const avg = scores.length ? Math.round(scores.reduce((a, b) => a + b, 0) / scores.length) : null;
  const weekAgo = Date.now() - 7 * 86_400_000;
  const thisWeek = items.filter((s) => new Date(s.created_at).getTime() >= weekAgo).length;
  const best = scores.length ? Math.max(...scores) : null;
  return { total: items.length, completed: completed.length, active: active.length, avg, thisWeek, best };
}

type SessionKpiPoint = {
  id: string;
  label: string;
  title: string;
  overall: number | null;
  rubric: number | null;
  behavior: number | null;
};

function sessionKpiPoint(s: MockInterviewSessionSummary): SessionKpiPoint {
  const fb = (s.feedback ?? {}) as MockInterviewFeedback;
  return {
    id: s.id,
    label: s.created_at.slice(5, 10),
    title: s.context_snapshot?.job_title || "Session",
    overall: sessionScore(s),
    rubric: fb.rubric_overall ?? null,
    behavior: fb.presentation?.behavior_overall ?? null,
  };
}

/** Grouped bars: overall, answer rubric, on-camera behavior per completed session. */
export function MockInterviewKpiGraph({
  sessions,
  avg,
}: {
  sessions: MockInterviewSessionSummary[];
  avg: number | null;
}) {
  const points = useMemo(() => {
    return [...sessions]
      .filter((s) => s.status === "completed")
      .sort((a, b) => a.created_at.localeCompare(b.created_at))
      .slice(-10)
      .map(sessionKpiPoint)
      .filter((p) => p.overall != null || p.rubric != null || p.behavior != null);
  }, [sessions]);

  if (points.length === 0) {
    return (
      <section className="mb-6 rounded-xl bg-white p-4 shadow-sm ring-1 ring-slate-200/80 sm:p-5">
        <h2 className="text-base font-semibold text-slate-900">Interview KPIs</h2>
        <p className="mt-1 text-sm text-slate-500">Complete a session to see score trends across overall, rubric, and on-camera behavior.</p>
      </section>
    );
  }

  const max = 100;
  const width = 640;
  const height = 168;
  const padX = 8;
  const padTop = 8;
  const chartW = width - padX * 2;
  const chartH = height - padTop - 28;
  const groupW = chartW / points.length;
  const barW = Math.min(14, (groupW - 10) / 3);
  const gap = 3;

  const barHeight = (score: number | null) => (score == null ? 0 : (score / max) * chartH);

  const avgY = avg != null ? padTop + chartH - (avg / max) * chartH : null;

  return (
    <section className="mb-6 rounded-xl bg-white p-4 shadow-sm ring-1 ring-slate-200/80 sm:p-5">
      <div className="mb-4 flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h2 className="text-base font-semibold text-slate-900">Interview KPI graph</h2>
          <p className="mt-0.5 text-sm text-slate-500">
            Last {points.length} completed session{points.length === 1 ? "" : "s"} — overall, answer rubric, and on-camera behavior (0–100).
          </p>
        </div>
        {avg != null && (
          <p className="text-sm text-slate-600">
            Average overall: <span className="font-mono font-semibold text-violet-700">{avg}/100</span>
          </p>
        )}
      </div>
      <figure>
        <svg viewBox={`0 0 ${width} ${height}`} className="h-44 w-full" role="img" aria-label="Mock interview KPI scores by session">
          {[25, 50, 75, 100].map((tick) => {
            const y = padTop + chartH - (tick / max) * chartH;
            return (
              <g key={tick}>
                <line x1={padX} x2={width - padX} y1={y} y2={y} className="stroke-slate-100" strokeDasharray="4 4" />
                <text x={4} y={y + 3} className="fill-slate-400 text-[9px]">
                  {tick}
                </text>
              </g>
            );
          })}
          {avgY != null && (
            <line x1={padX} x2={width - padX} y1={avgY} y2={avgY} className="stroke-violet-400" strokeWidth={1.5} strokeDasharray="6 4" />
          )}
          <line x1={padX} x2={width - padX} y1={padTop + chartH} y2={padTop + chartH} className="stroke-slate-200" />
          {points.map((p, i) => {
            const gx = padX + i * groupW + groupW / 2;
            const bars: { score: number | null; fill: string; name: string }[] = [
              { score: p.overall, fill: "#7c3aed", name: "Overall" },
              { score: p.rubric, fill: "#2563eb", name: "Rubric" },
              { score: p.behavior, fill: "#059669", name: "Behavior" },
            ];
            const totalBarSpan = bars.length * barW + (bars.length - 1) * gap;
            let bx = gx - totalBarSpan / 2;
            return (
              <g key={p.id}>
                {bars.map((b) => {
                  const h = barHeight(b.score);
                  const x = bx;
                  bx += barW + gap;
                  if (b.score == null) return null;
                  return (
                    <g key={b.name}>
                      <rect
                        x={x}
                        y={padTop + chartH - h}
                        width={barW}
                        height={h}
                        rx={2}
                        fill={b.fill}
                        opacity={0.92}
                      />
                      <title>{`${p.title} (${p.label}) · ${b.name}: ${b.score}/100`}</title>
                    </g>
                  );
                })}
                <text x={gx} y={height - 6} textAnchor="middle" className="fill-slate-500 text-[9px]">
                  {p.label}
                </text>
              </g>
            );
          })}
        </svg>
        <figcaption className="mt-3 flex flex-wrap gap-x-5 gap-y-1 text-xs text-slate-600">
          <span className="flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded-sm bg-violet-600" aria-hidden /> Overall score
          </span>
          <span className="flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded-sm bg-brand-600" aria-hidden /> Answer rubric
          </span>
          <span className="flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded-sm bg-emerald-600" aria-hidden /> On-camera behavior
          </span>
          {avg != null && (
            <span className="flex items-center gap-1.5 text-violet-700">
              <span className="h-0.5 w-4 border-t-2 border-dashed border-violet-400" aria-hidden /> Session average
            </span>
          )}
        </figcaption>
      </figure>
    </section>
  );
}

function ScoreTrend({ sessions }: { sessions: MockInterviewSessionSummary[] }) {
  const points = useMemo(() => {
    return [...sessions]
      .filter((s) => s.status === "completed" && sessionScore(s) != null)
      .sort((a, b) => a.created_at.localeCompare(b.created_at))
      .slice(-12)
      .map((s) => ({ label: s.created_at.slice(5, 10), score: sessionScore(s)! }));
  }, [sessions]);

  if (points.length < 2) {
    return (
      <p className="text-sm text-slate-500">
        Complete two or more interviews to see your score trend.
      </p>
    );
  }

  const max = 100;
  const width = 280;
  const height = 100;
  const step = width / (points.length - 1);

  const path = points
    .map((p, i) => {
      const x = i * step;
      const y = height - (p.score / max) * height;
      return `${i === 0 ? "M" : "L"}${x},${y}`;
    })
    .join(" ");

  return (
    <figure>
      <svg viewBox={`0 0 ${width} ${height + 24}`} className="h-32 w-full" role="img" aria-label="Recent interview scores">
        <line x1={0} x2={width} y1={height} y2={height} className="stroke-slate-200" />
        <path d={path} fill="none" className="stroke-brand-600" strokeWidth={2.5} strokeLinecap="round" strokeLinejoin="round" />
        {points.map((p, i) => {
          const x = i * step;
          const y = height - (p.score / max) * height;
          return (
            <g key={p.label}>
              <circle cx={x} cy={y} r={4} className="fill-brand-600" />
              <title>{`${p.label}: ${p.score}/100`}</title>
            </g>
          );
        })}
        <text x={0} y={height + 18} className="fill-slate-400 text-[10px]">{points[0].label}</text>
        <text x={width} y={height + 18} textAnchor="end" className="fill-slate-400 text-[10px]">{points[points.length - 1].label}</text>
      </svg>
    </figure>
  );
}

export function MockInterviewDashboard() {
  const [statusTab, setStatusTab] = useState<StatusTab>("all");
  const [sessionPage, setSessionPage] = useState(1);

  const { data: aiStatus } = useQuery({
    queryKey: ["mock-interview", "availability"],
    queryFn: () => mockInterviews.availability(),
  });

  const statsQuery = useQuery({
    queryKey: ["mock-interview", "list", "stats"],
    queryFn: () => mockInterviews.listSessions({ page: 1, page_size: 100 }),
    staleTime: 30_000,
  });

  const listQuery = useQuery({
    queryKey: ["mock-interview", "list", sessionPage, statusTab],
    queryFn: () => mockInterviews.listSessions({ page: sessionPage, page_size: SESSION_PAGE }),
    staleTime: 15_000,
  });

  const statsItems = statsQuery.data?.items ?? [];
  const stats = useMemo(() => aggregateStats(statsItems), [statsItems]);

  const filteredItems = useMemo(() => {
    if (statusTab === "all") return listQuery.data?.items ?? [];
    const pool = statsItems.filter((s) => s.status === statusTab);
    const start = (sessionPage - 1) * SESSION_PAGE;
    return pool.slice(start, start + SESSION_PAGE);
  }, [listQuery.data?.items, statsItems, statusTab, sessionPage]);

  const filteredTotal = useMemo(() => {
    if (statusTab === "all") return listQuery.data?.total ?? 0;
    return statsItems.filter((s) => s.status === statusTab).length;
  }, [statusTab, statsItems, listQuery.data?.total]);

  const resumeSession = statsItems.find((s) => s.status === "active");

  return (
    <>
      <PageHeader
        title="Mock interview"
        description="Your practice hub — start a session, track scores, and review AI feedback reports."
        actions={
          <>
            <ButtonLink to="/app/applications" variant="secondary" className="w-full sm:w-auto">
              Applications
            </ButtonLink>
            {resumeSession && (
              <ButtonLink to={`/app/mock-interview/${resumeSession.id}`} className="w-full sm:w-auto">
                <Play className="h-4 w-4" aria-hidden /> Continue interview
              </ButtonLink>
            )}
          </>
        }
      />

      {aiStatus && !aiStatus.available && (
        <div className="mb-4">
          <Alert kind="error">{aiStatus.message}</Alert>
        </div>
      )}

      <DashboardHero stats={stats} aiAvailable={aiStatus?.available ?? false} resumeSession={resumeSession} />

      {statsQuery.isLoading ? (
        <div className="mb-6 flex justify-center rounded-xl bg-white py-10 ring-1 ring-slate-200/80">
          <Spinner label="Loading KPI graph…" />
        </div>
      ) : (
        <MockInterviewKpiGraph sessions={statsItems} avg={stats.avg} />
      )}

      <div className="mb-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard
          icon={<Mic className="h-4 w-4" aria-hidden />}
          label="Total sessions"
          value={stats.total.toLocaleString()}
          sub={`${stats.thisWeek} in the last 7 days`}
        />
        <StatCard
          icon={<Target className="h-4 w-4" aria-hidden />}
          label="Completed"
          value={stats.completed.toLocaleString()}
          sub={stats.active > 0 ? `${stats.active} in progress` : "Ready for your next run"}
        />
        <StatCard
          icon={<BarChart3 className="h-4 w-4" aria-hidden />}
          label="Average score"
          value={stats.avg == null ? "—" : `${stats.avg}/100`}
          sub={stats.best != null ? `Best: ${stats.best}/100` : "Scores appear after feedback"}
        />
        <StatCard
          icon={<Clock className="h-4 w-4" aria-hidden />}
          label="Session limit"
          value="30 min"
          sub="Hands-free voice · up to ~12 answers"
        />
      </div>

      <div className="mb-6 grid gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <NewSessionPanel aiAvailable={aiStatus?.available ?? false} />
        </div>
        <div className="space-y-6">
          <ReadinessCard aiStatus={aiStatus} />
          <Card title="Score trend">
            {statsQuery.isLoading ? <Spinner label="Loading…" /> : <ScoreTrend sessions={statsItems} />}
          </Card>
        </div>
      </div>

      <section className="mb-6 rounded-xl bg-white shadow-sm ring-1 ring-slate-200/80">
        <header className="border-b border-slate-100 px-4 py-4 sm:px-5">
          <h2 className="text-base font-semibold text-slate-900">Session history</h2>
          <p className="mt-0.5 text-sm text-slate-500">Open reports to review rubric scores, coaching, and transcripts.</p>
        </header>
        <div className="px-4 py-4 sm:px-5">
          <Tabs tabs={[...STATUS_TABS]} value={statusTab} onChange={(id) => { setStatusTab(id); setSessionPage(1); }} className="mb-4" />
          {listQuery.isLoading ? (
            <Spinner label="Loading sessions…" />
          ) : listQuery.error ? (
            <Alert kind="error">{errorMessage(listQuery.error)}</Alert>
          ) : filteredItems.length === 0 ? (
            <EmptyState title="No sessions here">
              {statusTab === "all"
                ? "Start your first mock interview above."
                : `No ${statusTab === "active" ? "in progress" : statusTab} sessions.`}
            </EmptyState>
          ) : (
            <>
              <ul className="divide-y divide-slate-100">
                {filteredItems.map((s) => (
                  <SessionRow key={s.id} session={s} />
                ))}
              </ul>
              {filteredTotal > SESSION_PAGE && (
                <Pagination
                  page={sessionPage}
                  pageSize={SESSION_PAGE}
                  total={filteredTotal}
                  onPage={setSessionPage}
                />
              )}
            </>
          )}
        </div>
      </section>

      <div className="grid gap-4 md:grid-cols-3">
        <TipCard
          icon={Briefcase}
          title="Prepare"
          body="Pick an application you applied to so questions match the job description and your resume."
        />
        <TipCard
          icon={Video}
          title="Practice live"
          body="Use Chrome or Edge, allow mic and camera. Take thinking pauses — tap Done speaking or stay silent ~3–4s when finished."
        />
        <TipCard
          icon={TrendingUp}
          title="Improve"
          body="Read the 100-parameter rubric report and regenerate analysis after updating how you answer."
        />
      </div>
    </>
  );
}

function DashboardHero({
  stats,
  aiAvailable,
  resumeSession,
}: {
  stats: ReturnType<typeof aggregateStats>;
  aiAvailable: boolean;
  resumeSession?: MockInterviewSessionSummary;
}) {
  let headline = "Build interview confidence";
  let detail = "Video-style practice with an AI interviewer, tailored to your real job applications.";

  if (resumeSession) {
    headline = "You have an interview in progress";
    detail = `${resumeSession.context_snapshot.job_title || "Session"} · pick up where you left off before the 30-minute limit.`;
  } else if (stats.completed > 0 && stats.avg != null) {
    headline = `Average score ${stats.avg}/100 across ${stats.completed} sessions`;
    detail = stats.avg >= 70
      ? "Strong momentum — keep practicing weak rubric categories from your reports."
      : "Review coaching notes in your latest report, then run another session.";
  } else if (!aiAvailable) {
    headline = "Mock interview AI is unavailable";
    detail = "An admin must enable Platform AI and mock interviews before you can start.";
  } else if (stats.total === 0) {
    headline = "Ready for your first mock interview?";
    detail =
      "Choose a job below and start — video-call layout, voice Q&A, and a full feedback report when you finish.";
  }

  return (
    <section className="mb-6 rounded-xl bg-gradient-to-br from-violet-950 via-violet-900 to-slate-900 p-4 text-white shadow-sm ring-1 ring-violet-800/50 sm:p-5">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex min-w-0 items-start gap-3">
          <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-white/10">
            <Sparkles className="h-5 w-5 text-violet-200" aria-hidden />
          </span>
          <div className="min-w-0">
            <p className="text-lg font-semibold tracking-tight">{headline}</p>
            <p className="mt-1 text-sm text-violet-100/90">{detail}</p>
          </div>
        </div>
        {resumeSession && (
          <ButtonLink
            to={`/app/mock-interview/${resumeSession.id}`}
            variant="secondary"
            size="sm"
            className="shrink-0 border-white/20 bg-white/10 text-white hover:bg-white/20"
          >
            Continue session
          </ButtonLink>
        )}
      </div>
    </section>
  );
}

function NewSessionPanel({ aiAvailable }: { aiAvailable: boolean }) {
  const navigate = useNavigate();
  const [showAll, setShowAll] = useState(false);
  const [selectedApp, setSelectedApp] = useState("");
  const [types, setTypes] = useState<InterviewType[]>(["mixed"]);

  const filters = showAll
    ? { sort: "-created_at", page_size: 50 }
    : { status: ["applied", "external"] as ApplicationStatus[], sort: "-applied_at", page_size: 50 };

  const { data, isLoading, error } = useQuery({
    queryKey: ["applications", "mock-setup", filters],
    queryFn: () => applications.list(filters),
  });

  const start = useMutation({
    mutationFn: () =>
      mockInterviews.createSession({
        application_id: selectedApp,
        interview_types: types.includes("mixed") ? ["mixed"] : types,
      }),
    onSuccess: (session) => navigate(`/app/mock-interview/${session.id}`),
  });

  const applicationOptions =
    data?.items.map((a: Application) => ({
      value: a.id,
      label: `${a.job.title} · ${a.job.company} (${a.status.replace(/_/g, " ")})`,
    })) ?? [];

  const selectedApplication = data?.items.find((a: Application) => a.id === selectedApp);

  useEffect(() => {
    if (!data?.items.length) return;
    const valid = data.items.some((a: Application) => a.id === selectedApp);
    if (!valid) setSelectedApp(data.items[0].id);
  }, [data?.items, selectedApp]);

  const toggleType = (id: InterviewType) => {
    if (id === "mixed") {
      setTypes(["mixed"]);
      return;
    }
    setTypes((prev) => {
      const withoutMixed = prev.filter((t) => t !== "mixed");
      if (withoutMixed.includes(id)) {
        const next = withoutMixed.filter((t) => t !== id);
        return next.length ? next : ["mixed"];
      }
      return [...withoutMixed, id];
    });
  };

  return (
    <section className="rounded-xl bg-white p-4 shadow-sm ring-1 ring-slate-200/80 sm:p-5">
      <header className="mb-4">
        <h2 className="text-base font-semibold text-slate-900">Start a new session</h2>
        <p className="mt-0.5 text-sm text-slate-500">
          Job context, resume, and interview style feed the AI interviewer.
        </p>
      </header>
      {isLoading ? (
        <Spinner />
      ) : error || !data ? (
        <Alert kind="error">{errorMessage(error)}</Alert>
      ) : data.total === 0 ? (
        <EmptyState title="No applications yet">
          <Link to="/app/automation" className="text-brand-600 underline">Run automation</Link> or show all jobs once you have activity.
        </EmptyState>
      ) : (
        <>
          <div className="grid gap-8 md:grid-cols-2">
            <div className="space-y-4">
              <Select
                label="Job to practice"
                value={selectedApp}
                onChange={setSelectedApp}
                options={applicationOptions}
                hint={
                  selectedApplication ? (
                    <span className="inline-flex flex-wrap items-center gap-2">
                      <Badge tone="slate">{selectedApplication.status.replace(/_/g, " ")}</Badge>
                      <span>{selectedApplication.job.company}</span>
                    </span>
                  ) : undefined
                }
              />
              <button
                type="button"
                className="text-sm text-brand-700 underline"
                onClick={() => {
                  setShowAll((v) => !v);
                  setSelectedApp("");
                }}
              >
                {showAll ? "Show applied only" : "Show all applications"}
              </button>
            </div>
            <div className="space-y-4 md:border-l md:border-slate-200/80 md:pl-8">
              <p className="text-sm font-semibold text-slate-900">Interview style</p>
              <div className="flex flex-wrap gap-2" role="group" aria-label="Interview style">
                {TYPE_OPTIONS.map((opt) => (
                  <FilterChipBrand key={opt.id} active={types.includes(opt.id)} onClick={() => toggleType(opt.id)}>
                    {opt.label}
                  </FilterChipBrand>
                ))}
              </div>
              <p className="text-xs text-slate-500">
                {types.includes("mixed")
                  ? "Mixed rotates behavioral, technical, and HR-style questions."
                  : types.map((t) => TYPE_OPTIONS.find((o) => o.id === t)?.hint).join(" · ")}
              </p>
            </div>
          </div>
          <div className="mt-6 flex flex-col gap-3 border-t border-slate-100 pt-6 sm:flex-row sm:flex-wrap sm:items-center">
            <Button
              disabled={!selectedApp || start.isPending || !aiAvailable}
              loading={start.isPending}
              onClick={() => start.mutate()}
            >
              <Play className="h-4 w-4" aria-hidden /> Start interview
            </Button>
            {selectedApplication && (
              <p className="text-sm text-slate-600">
                <span className="font-medium text-slate-900">{selectedApplication.job.title}</span>
                {" · "}
                {types.includes("mixed") ? "Mixed" : types.map((t) => TYPE_OPTIONS.find((o) => o.id === t)?.label).join(", ")}
              </p>
            )}
            {start.error && (
              <div className="w-full sm:basis-full">
                <Alert kind="error">{mockInterviewStartError(start.error)}</Alert>
              </div>
            )}
          </div>
        </>
      )}
    </section>
  );
}

function ReadinessCard({ aiStatus }: { aiStatus?: { available: boolean; message: string; voice?: boolean } }) {
  return (
    <section className="rounded-xl bg-white p-4 shadow-sm ring-1 ring-slate-200/80 sm:p-5">
      <h2 className="text-sm font-semibold text-slate-900">Before you go live</h2>
      <ul className="mt-4 space-y-3 text-sm text-slate-600">
        <li className="flex gap-2">
          <Globe className="h-4 w-4 shrink-0 text-slate-400 mt-0.5" aria-hidden />
          Chrome or Edge for hands-free speech-to-text
        </li>
        <li className="flex gap-2">
          <Mic className="h-4 w-4 shrink-0 text-slate-400 mt-0.5" aria-hidden />
          Microphone required; allow when prompted
        </li>
        <li className="flex gap-2">
          <Video className="h-4 w-4 shrink-0 text-slate-400 mt-0.5" aria-hidden />
          Camera recommended for presence coaching (stills not stored)
        </li>
        <li className="flex gap-2">
          <Clock className="h-4 w-4 shrink-0 text-slate-400 mt-0.5" aria-hidden />
          30-minute countdown from session start
        </li>
      </ul>
      {aiStatus && (
        <div className="mt-4">
          <Alert kind={aiStatus.available ? "success" : "error"}>{aiStatus.message}</Alert>
        </div>
      )}
    </section>
  );
}

function SessionRow({ session }: { session: MockInterviewSessionSummary }) {
  const score = sessionScore(session);
  const title = session.context_snapshot.job_title || "Mock interview";
  const company = session.context_snapshot.company || "";

  return (
    <li className="flex flex-col gap-3 py-4 sm:flex-row sm:items-center sm:justify-between">
      <div className="min-w-0 flex-1">
        <p className="font-medium text-slate-900">{title}</p>
        <p className="mt-0.5 text-sm text-slate-500">
          {company && <span>{company} · </span>}
          {typeLabels(session.interview_types)} · {formatRelative(session.created_at)}
        </p>
        <p className="mt-0.5 text-xs text-slate-400">
          {formatDateTime(session.created_at)} · {session.turn_count} answers
        </p>
      </div>
      <div className="flex flex-wrap items-center gap-2 sm:justify-end">
        {score != null && (
          <span className="rounded-lg bg-slate-100 px-2.5 py-1 font-mono text-sm font-semibold tabular-nums text-slate-800">
            {Math.round(score)}/100
          </span>
        )}
        <Badge tone={statusTone(session.status)}>{statusLabel(session.status)}</Badge>
        {session.status === "completed" ? (
          <ButtonLink to={`/app/mock-interview/${session.id}/report`} size="sm" variant="secondary">
            View report
          </ButtonLink>
        ) : session.status === "active" ? (
          <ButtonLink to={`/app/mock-interview/${session.id}`} size="sm">
            Continue
          </ButtonLink>
        ) : (
          <ButtonLink to={`/app/mock-interview/${session.id}/report`} size="sm" variant="ghost">
            Details
          </ButtonLink>
        )}
      </div>
    </li>
  );
}

function TipCard({
  icon: Icon,
  title,
  body,
}: {
  icon: typeof Briefcase;
  title: string;
  body: string;
}) {
  return (
    <div className="rounded-xl bg-slate-50/80 p-4 ring-1 ring-slate-200/80">
      <div className="flex items-center gap-2 text-sm font-semibold text-slate-900">
        <Icon className="h-4 w-4 text-brand-600" aria-hidden />
        {title}
      </div>
      <p className="mt-2 text-sm text-slate-600">{body}</p>
    </div>
  );
}
