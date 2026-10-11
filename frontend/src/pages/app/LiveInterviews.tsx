import { useQuery } from "@tanstack/react-query";
import { Clock, Headphones, MessageSquare, Target } from "lucide-react";
import { useParams } from "react-router-dom";
import { Alert, Badge, ButtonLink, Card, EmptyState, PageHeader, Spinner, StatCard } from "../../components/ui";
import { LiveInterviewReportDashboard } from "../../features/LiveInterviewReportDashboard";
import { formatDateTime } from "../../lib/format";
import { errorMessage } from "../../services/api";
import { liveInterviews } from "../../services/endpoints";
import type { LiveInterviewSession } from "../../types";

function scoreTone(score: number | null | undefined): "green" | "blue" | "amber" | "red" | "slate" {
  if (score == null) return "slate";
  if (score >= 70) return "green";
  if (score >= 45) return "blue";
  if (score >= 20) return "amber";
  return "red";
}

function durationLabel(start?: string | null, end?: string | null) {
  if (!start || !end) return null;
  const ms = new Date(end).getTime() - new Date(start).getTime();
  if (!Number.isFinite(ms) || ms < 0) return null;
  const minutes = Math.round(ms / 60000);
  return minutes < 1 ? "<1 min" : `${minutes} min`;
}

function InterviewCard({ session }: { session: LiveInterviewSession }) {
  const score = session.feedback?.overall_score;
  const rubric = session.feedback?.rubric_overall;
  const answers = (session.transcript ?? []).filter((turn) => turn.role === "candidate").length;
  const questions = (session.transcript ?? []).filter((turn) => turn.role === "interviewer").length;
  const duration = durationLabel(session.started_at, session.ended_at);
  const ready = session.status === "completed";
  return (
    <article className="flex flex-col rounded-2xl bg-white p-5 shadow-sm ring-1 ring-slate-200/80">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <p className="truncate text-base font-semibold text-slate-900">{session.job_title || "Live interview"}</p>
          <p className="mt-1 truncate text-sm text-slate-500">{session.company || "No job selected"}</p>
        </div>
        <div className="shrink-0 text-right">
          <p className="font-mono text-3xl font-bold tabular-nums text-slate-900">{ready ? (score ?? "—") : "—"}</p>
          <p className="text-xs text-slate-500">out of 100</p>
        </div>
      </div>
      <div className="mt-4 flex flex-wrap items-center gap-2">
        <Badge tone={ready ? "green" : "amber"}>{ready ? "Report ready" : "In progress"}</Badge>
        {ready && score != null && <Badge tone={scoreTone(score)}>{score}/100</Badge>}
        {ready && rubric != null && <Badge tone="slate">Rubric {rubric}</Badge>}
      </div>
      <dl className="mt-4 grid grid-cols-3 gap-2 text-sm">
        <div className="rounded-xl bg-slate-50 px-3 py-2">
          <dt className="text-xs text-slate-500">When</dt>
          <dd className="mt-0.5 font-medium text-slate-800">{session.started_at ? formatDateTime(session.started_at) : "—"}</dd>
        </div>
        <div className="rounded-xl bg-slate-50 px-3 py-2">
          <dt className="text-xs text-slate-500">Length</dt>
          <dd className="mt-0.5 font-medium text-slate-800">{duration || "—"}</dd>
        </div>
        <div className="rounded-xl bg-slate-50 px-3 py-2">
          <dt className="text-xs text-slate-500">You said</dt>
          <dd className="mt-0.5 font-medium text-slate-800">{answers} {answers === 1 ? "line" : "lines"}</dd>
        </div>
      </dl>
      <p className="mt-3 text-xs text-slate-500">{questions} interviewer {questions === 1 ? "question" : "questions"} captured</p>
      <ButtonLink to={`/app/live-interviews/${session.id}/report`} className="mt-4" variant={ready ? "primary" : "secondary"}>
        {ready ? "Open report" : "Open session"}
      </ButtonLink>
    </article>
  );
}

export function LiveInterviewsPage() {
  const query = useQuery({ queryKey: ["live-interviews"], queryFn: liveInterviews.list });
  const sessions = query.data ?? [];
  const completed = sessions.filter((session) => session.status === "completed");
  const scores = completed.map((session) => session.feedback?.overall_score).filter((score): score is number => score != null);
  const average = scores.length ? Math.round(scores.reduce((sum, score) => sum + score, 0) / scores.length) : null;
  return (
    <>
      <PageHeader
        title="Live interviews"
        description="Reports from interviews coached in the desktop agent. Each token from Support is one interview."
        actions={<ButtonLink to="/app/support">Get a token</ButtonLink>}
      />
      {query.isPending ? <Spinner /> : query.error ? <Alert kind="error">{errorMessage(query.error)}</Alert> : sessions.length ? (
        <div className="space-y-6">
          <div className="grid gap-3 sm:grid-cols-3">
            <StatCard icon={<Headphones className="h-4 w-4" aria-hidden />} label="Interviews" value={sessions.length} sub={`${completed.length} with a report`} />
            <StatCard icon={<Target className="h-4 w-4" aria-hidden />} label="Average score" value={average ?? "—"} sub={scores.length ? "Completed interviews" : "End an interview to score it"} />
            <StatCard icon={<MessageSquare className="h-4 w-4" aria-hidden />} label="In progress" value={sessions.length - completed.length} sub="Still open in the desktop agent" />
          </div>
          <div className="grid gap-4 lg:grid-cols-2">
            {sessions.map((session) => <InterviewCard key={session.id} session={session} />)}
          </div>
        </div>
      ) : (
        <Card>
          <EmptyState icon={<Clock className="h-8 w-8" aria-hidden />} title="No live interviews yet">
            Request a token in Support, paste it in the desktop agent, and end the interview to see the report here.
          </EmptyState>
        </Card>
      )}
    </>
  );
}

export function LiveInterviewReportPage() {
  const { id = "" } = useParams();
  const query = useQuery({ queryKey: ["live-interviews", id], queryFn: () => liveInterviews.get(id), enabled: Boolean(id) });
  return (
    <>
      {query.isPending ? <Spinner /> : query.error ? <Alert kind="error">{errorMessage(query.error)}</Alert> : query.data && (
        <LiveInterviewReportDashboard session={query.data} />
      )}
    </>
  );
}
