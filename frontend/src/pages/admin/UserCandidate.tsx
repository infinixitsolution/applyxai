import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, Briefcase, CheckCircle2, Circle, CircleAlert, ExternalLink, FileText, Headphones, Mail, MapPin, Mic, Phone, Target } from "lucide-react";
import { Link, useParams } from "react-router-dom";
import { LiveInterviewReportDashboard } from "../../features/LiveInterviewReportDashboard";
import { Alert, Badge, ButtonLink, Card, cx, Spinner, StatCard, UserAvatar } from "../../components/ui";
import { formatBytes, formatDate, formatDateTime, formatMoney, formatRelative, safeExternalUrl, STATUS_LABELS, STATUS_TONES } from "../../lib/format";
import { errorMessage } from "../../services/api";
import { admin } from "../../services/endpoints";
import type { AdminCandidate, AdminUser } from "../../types";

type Entry = Record<string, unknown>;

const text = (entry: Entry, key: string) => (typeof entry[key] === "string" ? (entry[key] as string).trim() : "");

function scoreTone(score: number | null): "green" | "blue" | "amber" | "red" | "slate" {
  if (score == null) return "slate";
  if (score >= 70) return "green";
  if (score >= 45) return "blue";
  if (score >= 20) return "amber";
  return "red";
}

function Chips({ items, empty = "Not set" }: { items: string[]; empty?: string }) {
  if (!items.length) return <span className="text-sm text-slate-400">{empty}</span>;
  return (
    <div className="flex flex-wrap gap-1.5">
      {items.map((item) => <Badge key={item} tone="slate">{item}</Badge>)}
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <dt className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</dt>
      <dd className="mt-1 text-sm text-slate-800">{children || <span className="text-slate-400">Not set</span>}</dd>
    </div>
  );
}

export function CandidateHeader({ user, candidate }: { user: AdminUser; candidate?: AdminCandidate }) {
  const name = `${user.first_name} ${user.last_name}`.trim();
  const p = candidate?.profile;
  const role = [p?.current_title, p?.current_company].filter(Boolean).join(" at ");
  return (
    <div className="mb-6 overflow-hidden rounded-2xl bg-gradient-to-br from-slate-900 via-slate-800 to-brand-900 p-6 text-white shadow-lg">
      <div className="flex flex-col gap-5 sm:flex-row sm:items-center">
        <div className="shrink-0 scale-150 sm:ml-2 sm:mr-3"><UserAvatar name={name} email={user.email} /></div>
        <div className="min-w-0 flex-1">
          <h2 className="text-xl font-bold sm:text-2xl">{name || user.email}</h2>
          {(p?.headline || role) && <p className="mt-1 text-sm text-slate-200">{p?.headline || role}</p>}
          <div className="mt-3 flex flex-wrap gap-x-5 gap-y-1.5 text-sm text-slate-300">
            <span className="inline-flex items-center gap-1.5"><Mail className="h-4 w-4" aria-hidden />{user.email}</span>
            <span className="inline-flex items-center gap-1.5"><Phone className="h-4 w-4" aria-hidden />{p?.phone || "No mobile number"}</span>
            {role && p?.headline && <span className="inline-flex items-center gap-1.5"><Briefcase className="h-4 w-4" aria-hidden />{role}</span>}
            {candidate?.search?.location && (
              <span className="inline-flex items-center gap-1.5"><MapPin className="h-4 w-4" aria-hidden />{candidate.search.location}</span>
            )}
          </div>
        </div>
        <div className="flex flex-wrap gap-2 sm:flex-col sm:items-end">
          <Badge tone={user.is_active ? "green" : "red"}>{user.is_active ? "Active" : "Disabled"}</Badge>
          <Badge tone={user.is_verified ? "green" : "amber"}>{user.is_verified ? "Email verified" : "Email not verified"}</Badge>
          <Badge tone="brand">{user.plan_name}</Badge>
        </div>
      </div>
    </div>
  );
}

export function CandidateJourney({ journey }: { journey: NonNullable<AdminCandidate["journey"]> }) {
  const percent = Math.round((journey.completed / journey.total) * 100);
  return (
    <section aria-label="Progress after registration" className="mb-6 rounded-2xl bg-white p-5 shadow-sm ring-1 ring-slate-200/80">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Progress after registration</p>
          {journey.stopped_label ? (
            <p className="mt-1 text-base font-semibold text-slate-900">
              Stopped at step {journey.stopped_step}: <span className="text-amber-700">{journey.stopped_label}</span>
            </p>
          ) : (
            <p className="mt-1 text-base font-semibold text-emerald-700">Completed setup and applying to jobs</p>
          )}
          <p className="mt-1 text-sm text-slate-500">
            {journey.completed} of {journey.total} steps done
            {journey.last_activity_at && <> · Last activity {formatRelative(journey.last_activity_at)} ({formatDateTime(journey.last_activity_at)})</>}
          </p>
        </div>
        <div className="w-full sm:w-48">
          <div className="h-2 overflow-hidden rounded-full bg-slate-100">
            <div className="h-full rounded-full bg-brand-600" style={{ width: `${percent}%` }} />
          </div>
          <p className="mt-1 text-right text-xs text-slate-500">{percent}%</p>
        </div>
      </div>
      <ol className="mt-5 grid gap-x-4 gap-y-3 sm:grid-cols-2 lg:grid-cols-5">
        {journey.steps.map((step) => {
          const stopped = step.key === journey.stopped_at;
          return (
            <li key={step.key} className={cx("flex gap-2 rounded-lg p-2", stopped && "bg-amber-50 ring-1 ring-amber-200")}>
              {step.done
                ? <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600" aria-hidden />
                : stopped
                  ? <CircleAlert className="mt-0.5 h-4 w-4 shrink-0 text-amber-600" aria-hidden />
                  : <Circle className="mt-0.5 h-4 w-4 shrink-0 text-slate-300" aria-hidden />}
              <div className="min-w-0">
                <p className={cx("text-sm font-medium", step.done ? "text-slate-900" : stopped ? "text-amber-800" : "text-slate-400")}>
                  {step.label}{step.optional && <span className="font-normal text-slate-400"> (optional)</span>}
                </p>
                <p className="text-xs text-slate-500">
                  {step.done ? (step.at ? formatDateTime(step.at) : "Done") : stopped ? "Stopped here" : "Not yet"}
                </p>
              </div>
            </li>
          );
        })}
      </ol>
    </section>
  );
}

export function CandidateStats({ candidate }: { candidate: AdminCandidate }) {
  const s = candidate.stats;
  return (
    <div className="mb-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      <StatCard icon={<CheckCircle2 className="h-4 w-4" aria-hidden />} label="Applied (all time)" value={s.applied_total}
                sub={`${s.applications_total} jobs tracked`} />
      <StatCard icon={<Target className="h-4 w-4" aria-hidden />} label="Success rate"
                value={s.success_rate == null ? "—" : `${s.success_rate}%`} sub="Applied ÷ (applied + failed)" />
      <StatCard icon={<Mic className="h-4 w-4" aria-hidden />} label="Mock interviews" value={s.mock_interviews_total}
                sub={s.mock_average_score == null ? "No scores yet" : `Average score ${s.mock_average_score}/100`} />
      <StatCard icon={<Headphones className="h-4 w-4" aria-hidden />} label="Live interviews" value={s.live_interviews_total}
                sub={s.live_average_score == null ? "No scores yet" : `Average score ${s.live_average_score}/100`} />
    </div>
  );
}

export function ApplicationsChart({ days }: { days: AdminCandidate["applications_daily"] }) {
  const max = Math.max(1, ...days.map((d) => d.applied + d.failed));
  const applied = days.reduce((n, d) => n + d.applied, 0);
  const failed = days.reduce((n, d) => n + d.failed, 0);
  return (
    <Card title="Applications, last 30 days" actions={
      <div className="flex gap-3 text-xs text-slate-500">
        <span className="inline-flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-brand-500" />Applied {applied}</span>
        <span className="inline-flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-red-300" />Failed {failed}</span>
      </div>
    }>
      <div className="flex h-40 items-end gap-1" role="img" aria-label={`${applied} applied and ${failed} failed in the last 30 days`}>
        {days.map((d) => (
          <div key={d.date} className="flex h-full flex-1 flex-col justify-end" title={`${formatDate(d.date)}: ${d.applied} applied, ${d.failed} failed`}>
            <div className="rounded-t bg-red-300" style={{ height: `${(d.failed / max) * 100}%` }} />
            <div className="bg-brand-500" style={{ height: `${(d.applied / max) * 100}%` }} />
          </div>
        ))}
      </div>
      <div className="mt-2 flex justify-between text-xs text-slate-400">
        <span>{formatDate(days[0]?.date)}</span>
        <span>{formatDate(days[days.length - 1]?.date)}</span>
      </div>
    </Card>
  );
}

export function RecentApplications({ items, limit }: { items: AdminCandidate["recent_applications"]; limit?: number }) {
  const rows = limit ? items.slice(0, limit) : items;
  return (
    <Card title={limit ? "Latest applications" : "Recent applications"}>
      {rows.length === 0 ? <p className="text-sm text-slate-500">No applications yet.</p> : (
        <ul className="divide-y divide-slate-100">
          {rows.map((a) => {
            const url = safeExternalUrl(a.job_url);
            return (
              <li key={a.id} className="flex flex-wrap items-center justify-between gap-3 py-2.5 text-sm">
                <div className="min-w-0 flex-1">
                  <p className="truncate font-medium text-slate-900">
                    {url ? (
                      <a href={url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 hover:text-brand-700">
                        {a.title} <ExternalLink className="h-3 w-3" aria-hidden />
                      </a>
                    ) : a.title}
                  </p>
                  <p className="truncate text-xs text-slate-500">
                    {[a.company, a.location].filter(Boolean).join(" · ")}
                    {a.status === "failed" && a.failure_reason ? ` · ${a.failure_reason}` : ""}
                  </p>
                </div>
                <span className="text-xs text-slate-500">{formatDateTime(a.applied_at || a.created_at)}</span>
                <Badge tone={STATUS_TONES[a.status]}>{STATUS_LABELS[a.status]}</Badge>
              </li>
            );
          })}
        </ul>
      )}
    </Card>
  );
}

export function CandidateProfile({ candidate }: { candidate: AdminCandidate }) {
  const p = candidate.profile;
  const s = candidate.search;
  const salary = s && (s.salary_min || s.salary_max) ? [s.salary_min, s.salary_max].filter(Boolean).join(" – ") : "";
  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <Card title="Profile" className="lg:col-span-2">
        <dl className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          <Field label="Mobile number">{p.phone}</Field>
          <Field label="Headline">{p.headline}</Field>
          <Field label="Current role">{[p.current_title, p.current_company].filter(Boolean).join(" at ")}</Field>
          <Field label="Experience">{p.experience_years != null ? `${p.experience_years} ${p.experience_years === 1 ? "year" : "years"}` : ""}</Field>
          <Field label="Preferred roles"><Chips items={p.preferred_roles} /></Field>
          <Field label="Preferred locations"><Chips items={p.preferred_locations} /></Field>
        </dl>
        {p.summary && (
          <div className="mt-5 border-t border-slate-100 pt-4">
            <p className="text-xs font-medium uppercase tracking-wide text-slate-500">Summary</p>
            <p className="mt-1 whitespace-pre-wrap text-sm leading-relaxed text-slate-700">{p.summary}</p>
          </div>
        )}
        <div className="mt-5 border-t border-slate-100 pt-4">
          <p className="mb-2 text-xs font-medium uppercase tracking-wide text-slate-500">Skills</p>
          <Chips items={p.skills} empty="No skills added" />
        </div>
      </Card>

      <Card title="Work history">
        {p.work_history.length === 0 ? <p className="text-sm text-slate-500">No work history added.</p> : (
          <ol className="space-y-4">
            {p.work_history.map((w, i) => (
              <li key={i} className="border-l-2 border-brand-200 pl-4">
                <p className="text-sm font-medium text-slate-900">{text(w, "title") || "Role"}</p>
                <p className="text-xs text-slate-500">
                  {[text(w, "company"), text(w, "location"), [text(w, "start"), text(w, "end") || "Present"].filter(Boolean).join(" – ")]
                    .filter(Boolean).join(" · ")}
                </p>
                {text(w, "summary") && <p className="mt-1 whitespace-pre-wrap text-sm text-slate-600">{text(w, "summary")}</p>}
              </li>
            ))}
          </ol>
        )}
      </Card>

      <Card title="Education">
        {p.education.length === 0 ? <p className="text-sm text-slate-500">No education added.</p> : (
          <ul className="space-y-3">
            {p.education.map((e, i) => (
              <li key={i}>
                <p className="text-sm font-medium text-slate-900">{text(e, "school") || "School"}</p>
                <p className="text-xs text-slate-500">
                  {[[text(e, "degree"), text(e, "field")].filter(Boolean).join(", "),
                    [text(e, "start_year"), text(e, "end_year")].filter(Boolean).join(" – ")].filter(Boolean).join(" · ")}
                </p>
              </li>
            ))}
          </ul>
        )}
      </Card>

      <Card title="Job search">
        {!s ? <p className="text-sm text-slate-500">No search set up yet.</p> : (
          <dl className="grid gap-4 sm:grid-cols-2">
            <Field label="Keywords"><Chips items={s.keywords} /></Field>
            <Field label="Location">{s.location}</Field>
            <Field label="Experience level"><Chips items={s.experience_level} empty="Any" /></Field>
            <Field label="Job type"><Chips items={s.job_type} empty="Any" /></Field>
            <Field label="Workplace"><Chips items={s.on_site} empty="Any" /></Field>
            <Field label="Date posted">{s.date_posted || "Any time"}</Field>
            <Field label="Easy Apply only">{s.easy_apply_only ? "Yes" : "No"}</Field>
            <Field label="Salary">{salary}</Field>
          </dl>
        )}
      </Card>

      <Card title={`Resumes (${candidate.resume_list.length})`}>
        {candidate.resume_list.length === 0 ? <p className="text-sm text-slate-500">No resumes uploaded.</p> : (
          <ul className="divide-y divide-slate-100">
            {candidate.resume_list.map((r) => (
              <li key={r.id} className="flex items-center justify-between gap-3 py-2 text-sm">
                <span className="inline-flex min-w-0 items-center gap-2">
                  <FileText className="h-4 w-4 shrink-0 text-slate-400" aria-hidden />
                  <span className="truncate font-medium text-slate-800">{r.name}</span>
                </span>
                <span className="flex shrink-0 items-center gap-2 text-xs text-slate-500">
                  {r.file_type.toUpperCase()} · {formatBytes(r.file_size)} · {formatDate(r.created_at)}
                  {r.is_default && <Badge tone="brand">Default</Badge>}
                  {r.tailored && <Badge tone="blue">Tailored</Badge>}
                </span>
              </li>
            ))}
          </ul>
        )}
        <p className="mt-3 text-xs text-slate-500">Resume files stay private to the candidate.</p>
      </Card>
    </div>
  );
}

export function CandidateInterviews({ userId, candidate }: { userId: string; candidate: AdminCandidate }) {
  const t = candidate.live_tokens;
  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard icon={<Headphones className="h-4 w-4" aria-hidden />} label="Live interviews" value={candidate.stats.live_interviews_total}
                  sub={candidate.stats.live_average_score == null ? "No scores yet" : `Average score ${candidate.stats.live_average_score}/100`} />
        <StatCard icon={<CheckCircle2 className="h-4 w-4" aria-hidden />} label="Tokens unused" value={t.unused}
                  sub={`${t.reserved} in progress · ${t.used} used`} />
        <StatCard icon={<Target className="h-4 w-4" aria-hidden />} label="Paid for live interviews"
                  value={t.paid.length ? t.paid.map((p) => formatMoney(p.amount_cents, p.currency)).join(" + ") : "—"} />
        <StatCard icon={<Mic className="h-4 w-4" aria-hidden />} label="Mock interviews" value={candidate.stats.mock_interviews_total}
                  sub={candidate.stats.mock_average_score == null ? "No scores yet" : `Average score ${candidate.stats.mock_average_score}/100`} />
      </div>

      <Card title="Live interviews">
        {candidate.live_interviews.length === 0 ? <p className="text-sm text-slate-500">No live interviews yet.</p> : (
          <ul className="divide-y divide-slate-100">
            {candidate.live_interviews.map((s) => (
              <li key={s.id} className="flex flex-wrap items-center justify-between gap-3 py-3 text-sm">
                <div className="min-w-0 flex-1">
                  <p className="font-medium text-slate-900">{s.job_title || "Live interview"}{s.company ? ` at ${s.company}` : ""}</p>
                  <p className="text-xs text-slate-500">
                    {formatDateTime(s.started_at)} · Token {s.token} · {s.lines} transcript lines
                  </p>
                </div>
                <Badge tone={s.status === "completed" ? "green" : "amber"}>{s.status === "completed" ? "Completed" : "In progress"}</Badge>
                <Badge tone={scoreTone(s.overall_score)}>{s.overall_score == null ? "No score" : `${s.overall_score}/100`}</Badge>
                <ButtonLink size="sm" variant="secondary" to={`/admin/users/${userId}/live-interviews/${s.id}`}>View report</ButtonLink>
              </li>
            ))}
          </ul>
        )}
      </Card>

      <Card title="Mock interviews">
        {candidate.mock_interviews.length === 0 ? <p className="text-sm text-slate-500">No mock interviews yet.</p> : (
          <ul className="divide-y divide-slate-100">
            {candidate.mock_interviews.map((m) => (
              <li key={m.id} className="flex flex-wrap items-center justify-between gap-3 py-3 text-sm">
                <div className="min-w-0 flex-1">
                  <p className="font-medium text-slate-900">{m.job_title || "Mock interview"}{m.company ? ` at ${m.company}` : ""}</p>
                  <p className="text-xs text-slate-500">
                    {formatDateTime(m.created_at)} · {m.turn_count} {m.turn_count === 1 ? "question" : "questions"}{m.interview_types.length ? ` · ${m.interview_types.join(", ")}` : ""}
                  </p>
                </div>
                <Badge tone="slate">{m.status}</Badge>
                <Badge tone={scoreTone(m.overall_score)}>{m.overall_score == null ? "No score" : `${m.overall_score}/100`}</Badge>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}

export function AdminUserLiveInterviewPage() {
  const { id = "", sessionId = "" } = useParams();
  const query = useQuery({
    queryKey: ["admin", "user", id, "live", sessionId],
    queryFn: () => admin.userLiveInterview(id, sessionId),
    enabled: Boolean(id && sessionId),
  });
  if (query.isPending) return <Spinner />;
  if (query.error || !query.data) return <Alert kind="error">{errorMessage(query.error)}</Alert>;
  const { user, session } = query.data;
  return (
    <>
      <Link to={`/admin/users/${id}?tab=interviews`} className="mb-4 inline-flex items-center gap-1 text-sm text-slate-500 hover:text-slate-700">
        <ArrowLeft className="h-4 w-4" aria-hidden /> {user.name || user.email}
      </Link>
      <LiveInterviewReportDashboard session={session} readOnly backTo={`/admin/users/${id}?tab=interviews`} backLabel="Back to candidate" />
    </>
  );
}
