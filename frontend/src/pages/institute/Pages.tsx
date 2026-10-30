import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowRight,
  Bell,
  Briefcase,
  Building2,
  Check,
  CheckCircle2,
  Clock,
  CreditCard,
  Eye,
  FileText,
  Mail,
  MinusCircle,
  Package,
  Phone,
  Plus,
  Search,
  UserPlus,
  Users,
  XCircle,
} from "lucide-react";
import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { useSession } from "../../auth/session";
import { Select, TextArea, TextInput, Toggle } from "../../components/form";
import { DailyChart } from "../../components/BarChart";
import { ConfirmDialog, Modal } from "../../components/Modal";
import { useToast } from "../../components/Toast";
import {
  Alert,
  Badge,
  Button,
  ButtonLink,
  Card,
  EmptyState,
  PageHeader,
  ProgressBar,
  Spinner,
  StatCard,
  UserAvatar,
  cx,
} from "../../components/ui";
import { Pagination } from "../../components/Pagination";
import { formatDate, formatMoney, formatRelative } from "../../lib/format";
import { formatResumeLimit, RESUMES_UNLIMITED } from "../../lib/planLimits";
import { CheckoutError, openRazorpayCheckout } from "../../lib/razorpay";
import { errorMessage } from "../../services/api";
import { billing, institute } from "../../services/endpoints";
import type { Institute, InstituteAssignment, InstituteSeat, InstituteSettings, Plan, Subscription } from "../../types";
import {
  AssignmentBadge,
  FilterChips,
  InstitutePending,
  RELEASE_CANDIDATE_TITLE,
  RELEASE_CANDIDATE_TOAST,
  assignmentStatus,
  prettyStatus,
  releaseCandidateMessage,
  studentPrimary,
  studentSecondary,
} from "./campusUi";

const INSTITUTE_TYPE_LABELS: Record<string, string> = {
  TRAINING_CENTRE: "Training centre",
  COLLEGE: "College",
  SCHOOL: "School",
  IT_TRAINING: "IT training",
  COACHING: "Coaching",
  UNIVERSITY: "University",
  CORPORATE_LEARNING: "Corporate learning",
  OTHER: "Other",
};

function settingsOf(row: Institute): InstituteSettings {
  const s = row.settings as Partial<InstituteSettings>;
  return {
    timezone: String(s.timezone || "Asia/Kolkata"),
    notify_invites: s.notify_invites !== false,
    notify_acceptances: s.notify_acceptances !== false,
    notify_low_seats: s.notify_low_seats !== false,
    low_seat_threshold: Number(s.low_seat_threshold ?? 3),
    invite_expiry_days: Number(s.invite_expiry_days ?? 7),
    invite_note: String(s.invite_note || ""),
  };
}

function checkoutError(e: unknown): string {
  return e instanceof CheckoutError ? e.message : errorMessage(e);
}

function seatStatusTone(status: string): "green" | "brand" | "amber" | "slate" {
  const s = status.toLowerCase();
  if (s === "purchased" || s === "available" || s === "open" || s === "free") return "green";
  if (s === "assigned" || s === "occupied" || s === "active") return "brand";
  if (s === "suspended" || s === "reserved" || s === "held") return "amber";
  return "slate";
}

function seatStatusLabel(status: string): string {
  if (status === "purchased") return "Available";
  return prettyStatus(status);
}

function planLine(sub: Subscription | null): string {
  if (!sub) return "No campus plan yet. Choose a package to create student seats.";
  const end = formatDate(sub.current_period_end);
  if (sub.cancel_at_period_end) return `Active until ${end}. You will not be charged again.`;
  return `Renews on ${end} for ${formatMoney(sub.plan.price_cents, sub.plan.currency)}.`;
}

export function InstituteDashboardPage() {
  const { data: user } = useSession();
  const { data, isLoading, error } = useQuery({ queryKey: ["institute", "dashboard"], queryFn: institute.dashboard });
  if (isLoading) return <Spinner />;
  if (error || !data) return <Alert kind="error">{errorMessage(error)}</Alert>;
  const pending = user?.institute_status === "pending";
  const seats = data.seats;
  const occupancy = seats.total > 0 ? Math.round((seats.assigned / seats.total) * 100) : 0;
  const activity = data.activity;
  const across = data.students === 1 ? "1 active student" : `${data.students} active students`;

  return (
    <>
      <PageHeader
        title="Dashboard"
        description={`Campus workspace for ${data.institute.name}. You pay for seats; students keep those limits until you release them.`}
        actions={
          <ButtonLink to="/institute/students">
            <UserPlus className="h-4 w-4" aria-hidden /> Add student
          </ButtonLink>
        }
      />
      {pending && <InstitutePending />}

      <div className="mb-6 overflow-hidden rounded-2xl bg-gradient-to-br from-brand-700 to-slate-900 p-6 text-white shadow-sm ring-1 ring-brand-700/40 sm:p-8">
        <p className="text-sm font-medium text-brand-100">Institute pays</p>
        <h2 className="mt-1 text-2xl font-bold tracking-tight">{data.institute.name}</h2>
        <p className="mt-2 max-w-xl text-sm text-blue-100">
          {data.subscription
            ? `${data.subscription.plan.name} · ${planLine(data.subscription)}`
            : "Choose a campus plan to open seats, then invite students by name, phone, and email."}
        </p>
      </div>

      <div className="mb-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard
          icon={<Users className="h-4 w-4" aria-hidden />}
          label="Active students"
          value={data.students}
          sub="Assigned to a campus seat"
        />
        <StatCard
          icon={<Mail className="h-4 w-4" aria-hidden />}
          label="Open invitations"
          value={data.pending_invites}
          sub="Waiting to accept"
        />
        <StatCard
          icon={<Package className="h-4 w-4" aria-hidden />}
          label="Seats available"
          value={`${seats.available} / ${seats.total}`}
          sub={`${occupancy}% occupied`}
        />
        <StatCard
          icon={<CreditCard className="h-4 w-4" aria-hidden />}
          label="Campus plan"
          value={data.subscription?.plan.name ?? "None"}
          sub={data.subscription ? prettyStatus(data.subscription.status) : "Buy seats to invite"}
        />
      </div>

      {seats.total > 0 && (
        <Card className="mb-6" title="Seat occupancy">
          <ProgressBar value={seats.assigned} max={seats.total} label="Assigned seats" usageKind="applications" />
        </Card>
      )}

      {activity && (
        <Card
          className="mb-6"
          title="Student activity"
          actions={<span className="text-sm text-slate-500">{across}</span>}
        >
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <StatCard
              icon={<Briefcase className="h-4 w-4" aria-hidden />}
              label="Jobs searched"
              value={activity.searched.toLocaleString()}
              sub="Jobs found by all students"
            />
            <StatCard
              icon={<CheckCircle2 className="h-4 w-4" aria-hidden />}
              label="Applied"
              value={activity.applied.toLocaleString()}
              sub={
                activity.success_rate == null
                  ? "Easy Apply submitted"
                  : `${Math.round(activity.success_rate * 100)}% of applied + failed`
              }
            />
            <StatCard
              icon={<MinusCircle className="h-4 w-4" aria-hidden />}
              label="Skipped"
              value={activity.skipped.toLocaleString()}
              sub="Passed over during runs"
            />
            <StatCard
              icon={<XCircle className="h-4 w-4" aria-hidden />}
              label="Failed"
              value={activity.failed.toLocaleString()}
              sub="Apply attempts that did not go through"
            />
          </div>
          {activity.searched > 0 && (
            <div className="mt-6">
              <DailyChart
                data={activity.daily}
                ariaLabel="Applied and failed jobs by all students over the last 30 days"
              />
            </div>
          )}
        </Card>
      )}

      <section className="mb-6 grid gap-3 sm:grid-cols-3">
        {[
          {
            to: "/institute/students",
            icon: Users,
            title: "Students",
            description: "Add people to seats and suspend or release them later.",
            accent: "from-brand-600 to-brand-700",
          },
          {
            to: "/institute/invitations",
            icon: Mail,
            title: "Invitations",
            description: "Track who still needs to accept a campus seat.",
            accent: "from-emerald-600 to-teal-700",
          },
          {
            to: "/institute/subscription",
            icon: CreditCard,
            title: "Subscription",
            description: "Buy or switch campus plans. Billing stays on the institute.",
            accent: "from-slate-700 to-slate-900",
          },
        ].map((item) => (
          <Link
            key={item.to}
            to={item.to}
            className="group flex flex-col rounded-xl bg-white p-4 shadow-sm ring-1 ring-slate-200/80 transition hover:shadow-md sm:p-5"
          >
            <span className={cx("mb-3 inline-flex h-10 w-10 items-center justify-center rounded-lg bg-gradient-to-br text-white", item.accent)}>
              <item.icon className="h-5 w-5" aria-hidden />
            </span>
            <span className="font-semibold text-slate-900 group-hover:text-brand-700">{item.title}</span>
            <span className="mt-1 flex-1 text-sm text-slate-500">{item.description}</span>
            <span className="mt-3 inline-flex items-center gap-1 text-sm font-medium text-brand-600">
              Open <ArrowRight className="h-4 w-4 transition group-hover:translate-x-0.5" aria-hidden />
            </span>
          </Link>
        ))}
      </section>

      <Card
        title="Recent assignments"
        actions={
          <Link to="/institute/students" className="text-sm font-medium text-brand-600 hover:underline">
            All students
          </Link>
        }
      >
        {data.recent_assignments.length === 0 ? (
          <EmptyState icon={<Users className="h-8 w-8" aria-hidden />} title="No students yet">
            Invite students once your institute is approved and you have seats.
          </EmptyState>
        ) : (
          <ul className="divide-y divide-slate-100">
            {data.recent_assignments.map((a) => (
              <AssignmentRow key={a.id} row={a} compact />
            ))}
          </ul>
        )}
      </Card>
    </>
  );
}

function AssignmentRow({
  row,
  compact,
  actions,
}: {
  row: InstituteAssignment;
  compact?: boolean;
  actions?: ReactNode;
}) {
  const secondary = studentSecondary(row);
  const name = studentPrimary(row);
  return (
    <li className="flex flex-wrap items-center justify-between gap-3 py-3">
      <div className="flex min-w-0 items-center gap-3">
        <UserAvatar name={name} email={row.candidate_email} />
        <div className="min-w-0">
          <Link to={`/institute/students/${row.id}`} className="font-medium text-slate-900 hover:text-brand-700">
            {name}
          </Link>
          <p className="truncate text-xs text-slate-500">
            {secondary ? `${secondary} · ` : null}
            {formatDate(row.created_at)}
          </p>
        </div>
      </div>
      <div className="flex items-center gap-2">
        <AssignmentBadge status={row.status} />
        {!compact && actions}
      </div>
    </li>
  );
}

const EMPTY_ACTIVITY = { searched: 0, applied: 0, skipped: 0, failed: 0 };

function CampusPersonCard({
  row,
  actions,
  dateLabel,
  children,
}: {
  row: InstituteAssignment;
  actions: ReactNode;
  dateLabel: string;
  children?: ReactNode;
}) {
  const name = studentPrimary(row);
  return (
    <article className="rounded-2xl bg-white p-5 shadow-sm ring-1 ring-slate-200/80 transition hover:shadow-md hover:ring-slate-300">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="flex min-w-0 gap-4">
          <UserAvatar name={name} email={row.candidate_email} />
          <div className="min-w-0">
            <Link to={`/institute/students/${row.id}`} className="text-base font-semibold text-slate-900 hover:text-brand-700">
              {name}
            </Link>
            <div className="mt-1.5 flex flex-wrap gap-x-4 gap-y-1 text-sm text-slate-500">
              <span className="inline-flex items-center gap-1.5">
                <Mail className="h-3.5 w-3.5 shrink-0" aria-hidden />
                {row.candidate_email}
              </span>
              {row.candidate_phone ? (
                <span className="inline-flex items-center gap-1.5">
                  <Phone className="h-3.5 w-3.5 shrink-0" aria-hidden />
                  {row.candidate_phone}
                </span>
              ) : null}
              <span>{dateLabel} {formatDate(row.created_at)}</span>
            </div>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2 lg:flex-col lg:items-end">
          <AssignmentBadge status={row.status} />
          <div className="flex flex-wrap items-center gap-2">{actions}</div>
        </div>
      </div>
      {children}
    </article>
  );
}

function StudentRosterCard({
  row,
  actions,
}: {
  row: InstituteAssignment;
  actions: ReactNode;
}) {
  const activity = row.activity ?? EMPTY_ACTIVITY;
  return (
    <CampusPersonCard row={row} actions={actions} dateLabel="Joined">
      <dl className="mt-5 grid grid-cols-2 gap-3 border-t border-slate-100 pt-4 sm:grid-cols-4">
        {[
          { label: "Searched", value: activity.searched },
          { label: "Applied", value: activity.applied },
          { label: "Skipped", value: activity.skipped },
          { label: "Failed", value: activity.failed },
        ].map((stat) => (
          <div key={stat.label} className="rounded-xl bg-slate-50 px-3 py-2.5">
            <dt className="text-xs font-medium uppercase tracking-wide text-slate-500">{stat.label}</dt>
            <dd className="mt-0.5 text-lg font-semibold tabular-nums text-slate-900">{stat.value.toLocaleString()}</dd>
          </div>
        ))}
      </dl>
    </CampusPersonCard>
  );
}

function InvitationCard({
  row,
  actions,
}: {
  row: InstituteAssignment;
  actions: ReactNode;
}) {
  const waiting = row.status === "pending_candidate_acceptance";
  return (
    <CampusPersonCard row={row} actions={actions} dateLabel="Sent">
      <dl className="mt-5 grid gap-3 border-t border-slate-100 pt-4 sm:grid-cols-3">
        <div className="rounded-xl bg-slate-50 px-3 py-2.5">
          <dt className="text-xs font-medium uppercase tracking-wide text-slate-500">Status</dt>
          <dd className="mt-0.5 text-sm font-semibold text-slate-900">
            {waiting ? "Waiting for the student to accept" : "Invitation sent"}
          </dd>
        </div>
        <div className="rounded-xl bg-slate-50 px-3 py-2.5">
          <dt className="text-xs font-medium uppercase tracking-wide text-slate-500">Sent</dt>
          <dd className="mt-0.5 text-sm font-semibold text-slate-900">{formatRelative(row.created_at)}</dd>
        </div>
        <div className="rounded-xl bg-slate-50 px-3 py-2.5">
          <dt className="text-xs font-medium uppercase tracking-wide text-slate-500">Expires</dt>
          <dd className="mt-0.5 inline-flex items-center gap-1.5 text-sm font-semibold text-slate-900">
            <Clock className="h-3.5 w-3.5 text-slate-400" aria-hidden />
            {row.expires_at ? formatDate(row.expires_at) : "No expiry on file"}
          </dd>
        </div>
      </dl>
      {row.note ? <p className="mt-3 text-sm text-slate-600">{row.note}</p> : null}
    </CampusPersonCard>
  );
}

const STUDENT_STATUS_FILTERS = [
  { value: "", label: "All" },
  { value: "invited", label: "Invited" },
  { value: "pending_candidate_acceptance", label: "Waiting" },
  { value: "active", label: "Active" },
  { value: "suspended", label: "Suspended" },
  { value: "released", label: "Released" },
];

export function InstituteStudentsPage() {
  const toast = useToast();
  const client = useQueryClient();
  const [addOpen, setAddOpen] = useState(false);
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [email, setEmail] = useState("");
  const [status, setStatus] = useState("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [confirm, setConfirm] = useState<{ id: string; title: string; message: string; confirm: string; danger: boolean; run: () => void } | null>(null);
  const dash = useQuery({ queryKey: ["institute", "dashboard"], queryFn: institute.dashboard });
  const { data, isLoading } = useQuery({
    queryKey: ["institute", "students", status, page],
    queryFn: () => institute.students({ status: status || undefined, page, page_size: 20 }),
  });
  const invite = useMutation({
    mutationFn: () => institute.invite({ name: name.trim(), phone: phone.trim(), email: email.trim() }),
    onSuccess: () => {
      setName("");
      setPhone("");
      setEmail("");
      setAddOpen(false);
      client.invalidateQueries({ queryKey: ["institute"] });
      toast.success("Student added. Login details were emailed.");
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  const release = useMutation({
    mutationFn: institute.release,
    onSuccess: () => { setConfirm(null); client.invalidateQueries({ queryKey: ["institute"] }); toast.success(RELEASE_CANDIDATE_TOAST); },
    onError: (e) => { setConfirm(null); toast.error(errorMessage(e)); },
  });
  const suspend = useMutation({
    mutationFn: institute.suspend,
    onSuccess: () => { setConfirm(null); client.invalidateQueries({ queryKey: ["institute"] }); toast.success("Student suspended."); },
    onError: (e) => { setConfirm(null); toast.error(errorMessage(e)); },
  });
  const busy = release.isPending || suspend.isPending;
  const canInvite = name.trim().length > 0 && phone.trim().length >= 5 && email.includes("@");
  const query = search.trim().toLowerCase();
  const items = (data?.items ?? []).filter((a) => {
    if (!query) return true;
    return [a.candidate_name, a.candidate_email, a.candidate_phone].some((value) =>
      (value || "").toLowerCase().includes(query),
    );
  });
  const seats = dash.data?.seats;
  const occupancy = seats && seats.total > 0 ? Math.round((seats.assigned / seats.total) * 100) : 0;

  function openAdd() {
    setName("");
    setPhone("");
    setEmail("");
    setAddOpen(true);
  }

  function submitInvite(e: FormEvent) {
    e.preventDefault();
    if (!canInvite || invite.isPending) return;
    invite.mutate();
  }

  function setStatusFilter(next: string) {
    setStatus(next);
    setPage(1);
  }

  return (
    <>
      <PageHeader
        title="Students"
        description="Campus roster. Add a student to a seat and email login details. Releasing a candidate unbinds them from campus billing; your seats stay with the institute."
        actions={
          <Button onClick={openAdd}>
            <Plus className="h-4 w-4" aria-hidden /> Add student
          </Button>
        }
      />

      <div className="mb-6 overflow-hidden rounded-2xl bg-gradient-to-br from-brand-700 to-slate-900 p-6 text-white shadow-sm ring-1 ring-brand-700/40 sm:p-8">
        <p className="text-sm font-medium text-brand-100">Campus roster</p>
        <h2 className="mt-1 text-2xl font-bold tracking-tight">
          {dash.data ? `${dash.data.students} active ${dash.data.students === 1 ? "student" : "students"}` : "Students on campus seats"}
        </h2>
        <p className="mt-2 max-w-xl text-sm text-blue-100">
          {seats
            ? `${seats.available} of ${seats.total} seats open${occupancy ? ` · ${occupancy}% occupied` : ""}. Login details go out by email when you add someone.`
            : "Add students with name, phone, and email. Each one uses an open campus seat."}
        </p>
      </div>

      <div className="mb-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard icon={<Users className="h-4 w-4" aria-hidden />} label="Active students" value={dash.data?.students ?? "—"} sub="Assigned to a campus seat" />
        <StatCard icon={<Mail className="h-4 w-4" aria-hidden />} label="Open invitations" value={dash.data?.pending_invites ?? "—"} sub="Waiting to accept" />
        <StatCard icon={<Package className="h-4 w-4" aria-hidden />} label="Seats available" value={seats ? `${seats.available} / ${seats.total}` : "—"} sub="Ready to assign" />
        <StatCard icon={<CheckCircle2 className="h-4 w-4" aria-hidden />} label="Jobs applied" value={dash.data ? dash.data.activity.applied.toLocaleString() : "—"} sub="Across active students" />
      </div>

      <Card className="mb-6">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div className="relative w-full max-w-md">
            <Search className="pointer-events-none absolute bottom-2.5 left-3 h-4 w-4 text-slate-400" aria-hidden />
            <TextInput
              label="Search"
              value={search}
              onChange={setSearch}
              placeholder="Name, email, or phone"
              className="pl-9"
            />
          </div>
          <FilterChips options={STUDENT_STATUS_FILTERS} value={status} onChange={setStatusFilter} className="mb-0" />
        </div>
      </Card>

      {isLoading ? <Spinner /> : !data?.items.length ? (
        <Card>
          <EmptyState icon={<Users className="h-8 w-8" aria-hidden />} title="No students yet">
            <p className="mb-4">Add a student with name, phone, and email to reserve a campus seat and send login details.</p>
            <Button onClick={openAdd}>
              <Plus className="h-4 w-4" aria-hidden /> Add student
            </Button>
          </EmptyState>
        </Card>
      ) : items.length === 0 ? (
        <Card>
          <EmptyState icon={<Search className="h-8 w-8" aria-hidden />} title="No matching students">
            <p>Try a different name, email, or phone, or clear the search.</p>
          </EmptyState>
        </Card>
      ) : (
        <>
          <p className="mb-4 text-sm text-slate-600">
            Showing <span className="font-medium text-slate-900">{items.length}</span>
            {query ? " match" : ""} of{" "}
            <span className="font-medium text-slate-900">{data.total.toLocaleString()}</span> students
          </p>
          <ul className="grid gap-4">
            {items.map((a) => (
              <li key={a.id}>
                <StudentRosterCard
                  row={a}
                  actions={
                    <>
                      <ButtonLink to={`/institute/students/${a.id}`} size="sm">
                        <Eye className="h-4 w-4" aria-hidden /> View
                      </ButtonLink>
                      {a.status === "active" && (
                        <Button size="sm" variant="ghost" onClick={() => setConfirm({
                          id: a.id, title: "Suspend this student?", confirm: "Suspend", danger: true,
                          message: `${a.candidate_email} loses this campus seat until you invite them again or they are reassigned.`,
                          run: () => suspend.mutate(a.id),
                        })}>Suspend</Button>
                      )}
                      {(a.status === "active" || a.status === "invited" || a.status === "pending_candidate_acceptance" || a.status === "suspended") && (
                        <Button size="sm" variant="secondary" onClick={() => setConfirm({
                          id: a.id, title: RELEASE_CANDIDATE_TITLE, confirm: "Release", danger: true,
                          message: releaseCandidateMessage(a.candidate_email),
                          run: () => release.mutate(a.id),
                        })}>Release</Button>
                      )}
                    </>
                  }
                />
              </li>
            ))}
          </ul>
          {data.total > data.page_size && (
            <Pagination page={data.page} pageSize={data.page_size} total={data.total} onPage={setPage} />
          )}
        </>
      )}
      <Modal
        open={addOpen}
        onClose={() => { if (!invite.isPending) setAddOpen(false); }}
        title="Add student"
        footer={
          <>
            <Button variant="secondary" onClick={() => setAddOpen(false)} disabled={invite.isPending}>Cancel</Button>
            <Button type="submit" form="add-student-form" loading={invite.isPending} disabled={!canInvite}>
              Add student
            </Button>
          </>
        }
      >
        <form id="add-student-form" onSubmit={submitInvite} className="space-y-4">
          <TextInput
            label="Name"
            value={name}
            onChange={setName}
            required
            autoFocus
            placeholder="Student full name"
          />
          <TextInput
            label="Number"
            type="tel"
            value={phone}
            onChange={setPhone}
            required
            placeholder="Phone number"
          />
          <TextInput
            label="Email ID"
            type="email"
            value={email}
            onChange={setEmail}
            required
            placeholder="student@example.com"
          />
          <p className="text-xs text-slate-500">
            Uses one available seat. New students get login credentials by email; existing accounts stay on their
            current password. Their plan is billed through your institute until you release the seat.
          </p>
        </form>
      </Modal>
      {confirm && (
        <ConfirmDialog open title={confirm.title} message={confirm.message} confirmLabel={confirm.confirm}
                       danger={confirm.danger} loading={busy} onConfirm={confirm.run} onClose={() => setConfirm(null)} />
      )}
    </>
  );
}

const INVITE_STATUS_FILTERS = [
  { value: "", label: "All" },
  { value: "invited", label: "Invited" },
  { value: "pending_candidate_acceptance", label: "Waiting" },
];

export function InstituteInvitationsPage() {
  const toast = useToast();
  const client = useQueryClient();
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [confirm, setConfirm] = useState<{ id: string; email: string } | null>(null);
  const dash = useQuery({ queryKey: ["institute", "dashboard"], queryFn: institute.dashboard });
  const { data, isLoading } = useQuery({ queryKey: ["institute", "invitations"], queryFn: institute.invitations });
  const release = useMutation({
    mutationFn: institute.release,
    onSuccess: () => {
      setConfirm(null);
      client.invalidateQueries({ queryKey: ["institute"] });
      toast.success("Invitation cancelled.");
    },
    onError: (e) => { setConfirm(null); toast.error(errorMessage(e)); },
  });
  const query = search.trim().toLowerCase();
  const items = (data?.items ?? []).filter((a) => {
    if (status && a.status !== status) return false;
    if (!query) return true;
    return [a.candidate_name, a.candidate_email, a.candidate_phone].some((value) =>
      (value || "").toLowerCase().includes(query),
    );
  });
  const invited = (data?.items ?? []).filter((a) => a.status === "invited").length;
  const waiting = (data?.items ?? []).filter((a) => a.status === "pending_candidate_acceptance").length;
  const openCount = data?.items.length ?? dash.data?.pending_invites ?? 0;
  const seats = dash.data?.seats;

  return (
    <>
      <PageHeader
        title="Invitations"
        description="Open seat invitations. Cancel one to free the seat before the student accepts."
        actions={
          <ButtonLink to="/institute/students">
            <Plus className="h-4 w-4" aria-hidden /> Add student
          </ButtonLink>
        }
      />

      <div className="mb-6 overflow-hidden rounded-2xl bg-gradient-to-br from-brand-700 to-slate-900 p-6 text-white shadow-sm ring-1 ring-brand-700/40 sm:p-8">
        <p className="text-sm font-medium text-brand-100">Waiting to join</p>
        <h2 className="mt-1 text-2xl font-bold tracking-tight">
          {openCount} open {openCount === 1 ? "invitation" : "invitations"}
        </h2>
        <p className="mt-2 max-w-xl text-sm text-blue-100">
          {seats
            ? `${seats.available} of ${seats.total} seats still open. Cancelling an invite returns that seat to the pool.`
            : "Each open invitation holds a campus seat until the student accepts or you cancel it."}
        </p>
      </div>

      <div className="mb-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard icon={<Mail className="h-4 w-4" aria-hidden />} label="Open invitations" value={openCount} sub="Seats on hold" />
        <StatCard icon={<UserPlus className="h-4 w-4" aria-hidden />} label="Invited" value={invited} sub="Invite sent" />
        <StatCard icon={<Clock className="h-4 w-4" aria-hidden />} label="Waiting" value={waiting} sub="Student has not accepted" />
        <StatCard icon={<Package className="h-4 w-4" aria-hidden />} label="Seats available" value={seats ? `${seats.available} / ${seats.total}` : "—"} sub="Ready to assign" />
      </div>

      <Card className="mb-6">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div className="relative w-full max-w-md">
            <Search className="pointer-events-none absolute bottom-2.5 left-3 h-4 w-4 text-slate-400" aria-hidden />
            <TextInput
              label="Search"
              value={search}
              onChange={setSearch}
              placeholder="Name, email, or phone"
              className="pl-9"
            />
          </div>
          <FilterChips options={INVITE_STATUS_FILTERS} value={status} onChange={setStatus} />
        </div>
      </Card>

      {isLoading ? <Spinner /> : !data?.items.length ? (
        <Card>
          <EmptyState icon={<Mail className="h-8 w-8" aria-hidden />} title="No open invitations">
            <p className="mb-4">New students are added from the Students page. If an invite is still waiting, it appears here until they join or you cancel it.</p>
            <ButtonLink to="/institute/students">
              <Plus className="h-4 w-4" aria-hidden /> Add student
            </ButtonLink>
          </EmptyState>
        </Card>
      ) : items.length === 0 ? (
        <Card>
          <EmptyState icon={<Search className="h-8 w-8" aria-hidden />} title="No matching invitations">
            <p>Try a different name, email, or phone, or clear the filter.</p>
          </EmptyState>
        </Card>
      ) : (
        <>
          <p className="mb-4 text-sm text-slate-600">
            Showing <span className="font-medium text-slate-900">{items.length}</span>
            {query || status ? " match" : ""} of{" "}
            <span className="font-medium text-slate-900">{data.items.length}</span> invitations
          </p>
          <ul className="grid gap-4">
            {items.map((a) => (
              <li key={a.id}>
                <InvitationCard
                  row={a}
                  actions={
                    <>
                      <ButtonLink to={`/institute/students/${a.id}`} size="sm">
                        <Eye className="h-4 w-4" aria-hidden /> View
                      </ButtonLink>
                      <Button size="sm" variant="secondary" onClick={() => setConfirm({ id: a.id, email: a.candidate_email })}>
                        Cancel
                      </Button>
                    </>
                  }
                />
              </li>
            ))}
          </ul>
        </>
      )}
      {confirm && (
        <ConfirmDialog
          open
          title="Cancel this invitation?"
          message={`${confirm.email} loses this campus seat and the seat becomes available again.`}
          confirmLabel="Cancel invite"
          danger
          loading={release.isPending}
          onConfirm={() => release.mutate(confirm.id)}
          onClose={() => setConfirm(null)}
        />
      )}
    </>
  );
}

const SEAT_STATUS_FILTERS = [
  { value: "", label: "All" },
  { value: "purchased", label: "Available" },
  { value: "assigned", label: "Assigned" },
  { value: "suspended", label: "Suspended" },
  { value: "released", label: "Released" },
  { value: "expired", label: "Expired" },
];

function seatNumberLabel(n: number): string {
  return `Seat ${String(n).padStart(2, "0")}`;
}

export function InstituteSeatsPage() {
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const dash = useQuery({ queryKey: ["institute", "dashboard"], queryFn: institute.dashboard });
  const { data, isLoading } = useQuery({ queryKey: ["institute", "seats"], queryFn: institute.seats });
  const counts = data?.counts;
  const assigned = counts?.assigned ?? 0;
  const total = counts?.total ?? 0;
  const available = counts?.available ?? 0;
  const occupancy = total > 0 ? Math.round((assigned / total) * 100) : 0;
  const query = search.trim().toLowerCase();
  const numbered = (data?.items ?? []).map((seat, i) => ({ seat, number: i + 1 }));
  const items = numbered.filter(({ seat, number }) => {
    if (status && seat.status !== status) return false;
    if (!query) return true;
    const occupant = seat.assignment;
    return [
      seatNumberLabel(number),
      String(number),
      seat.id,
      occupant?.candidate_name,
      occupant?.candidate_email,
      occupant?.candidate_phone,
    ].some((value) => (value || "").toLowerCase().includes(query));
  });
  const inUse = items.filter(({ seat }) => seat.status === "assigned");
  const open = items.filter(({ seat }) => seat.status === "purchased");
  const other = items.filter(({ seat }) => seat.status !== "assigned" && seat.status !== "purchased");
  const planName = dash.data?.subscription?.plan.name;

  return (
    <>
      <PageHeader
        title="Seats"
        description="Campus seats you pay for. Releasing a candidate frees the seat back to this inventory; your purchased seats stay with the institute."
        actions={
          <div className="flex flex-wrap gap-2">
            {available > 0 && (
              <ButtonLink to="/institute/students">
                <Plus className="h-4 w-4" aria-hidden /> Add student
              </ButtonLink>
            )}
            <ButtonLink to="/institute/subscription" variant="secondary">
              <CreditCard className="h-4 w-4" aria-hidden /> Manage plan
            </ButtonLink>
          </div>
        }
      />

      <div className="mb-6 overflow-hidden rounded-2xl bg-gradient-to-br from-brand-700 to-slate-900 p-6 text-white shadow-sm ring-1 ring-brand-700/40 sm:p-8">
        <p className="text-sm font-medium text-brand-100">Seat inventory</p>
        <h2 className="mt-1 text-2xl font-bold tracking-tight">
          {assigned} of {total} seats in use
        </h2>
        <p className="mt-2 max-w-xl text-sm text-blue-100">
          {total === 0
            ? "Buy a campus plan to create seats, then add students."
            : `${available} open · ${occupancy}% occupied${planName ? ` · ${planName}` : ""}`}
        </p>
        {total > 0 && (
          <div className="mt-5 h-2 overflow-hidden rounded-full bg-white/15" aria-hidden>
            <div className="h-full rounded-full bg-white" style={{ width: `${occupancy}%` }} />
          </div>
        )}
      </div>

      {isLoading ? <Spinner /> : (
        <>
          <div className="mb-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <StatCard icon={<Package className="h-4 w-4" aria-hidden />} label="Total seats" value={total} sub={planName ?? "Campus plan"} />
            <StatCard icon={<Users className="h-4 w-4" aria-hidden />} label="Assigned" value={assigned} sub="Held by students" />
            <StatCard icon={<UserPlus className="h-4 w-4" aria-hidden />} label="Available" value={available} sub="Ready to assign" />
            <StatCard icon={<CheckCircle2 className="h-4 w-4" aria-hidden />} label="Occupancy" value={`${occupancy}%`} sub="Assigned ÷ total" />
          </div>

          {total > 0 && (
            <Card className="mb-6" title="Occupancy">
              <ProgressBar value={assigned} max={total} label="Assigned seats" usageKind="applications" />
            </Card>
          )}

          <Card className="mb-6">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
              <div className="relative w-full max-w-md">
                <Search className="pointer-events-none absolute bottom-2.5 left-3 h-4 w-4 text-slate-400" aria-hidden />
                <TextInput
                  label="Search"
                  value={search}
                  onChange={setSearch}
                  placeholder="Seat number, name, or email"
                  className="pl-9"
                />
              </div>
              <FilterChips options={SEAT_STATUS_FILTERS} value={status} onChange={setStatus} />
            </div>
          </Card>

          {!data?.items.length ? (
            <Card>
              <EmptyState icon={<Package className="h-8 w-8" aria-hidden />} title="No seats yet">
                <p className="mb-4">Buy a campus plan to create seats, then add students from the roster.</p>
                <ButtonLink to="/institute/subscription">
                  <CreditCard className="h-4 w-4" aria-hidden /> Manage plan
                </ButtonLink>
              </EmptyState>
            </Card>
          ) : items.length === 0 ? (
            <Card>
              <EmptyState icon={<Search className="h-8 w-8" aria-hidden />} title="No matching seats">
                <p>Try a different seat number, name, or email, or clear the filter.</p>
              </EmptyState>
            </Card>
          ) : (
            <div className="space-y-8">
              {inUse.length > 0 && (
                <section>
                  <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-slate-500">
                    In use · {inUse.length}
                  </h2>
                  <ul className="grid gap-4">
                    {inUse.map(({ seat, number }) => (
                      <li key={seat.id}>
                        <AssignedSeatCard seat={seat} number={number} />
                      </li>
                    ))}
                  </ul>
                </section>
              )}
              {open.length > 0 && (
                <section>
                  <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-slate-500">
                    Open seats · {open.length}
                  </h2>
                  <ul className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                    {open.map(({ seat, number }) => (
                      <li key={seat.id}>
                        <OpenSeatTile seat={seat} number={number} />
                      </li>
                    ))}
                  </ul>
                </section>
              )}
              {other.length > 0 && (
                <section>
                  <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-slate-500">
                    Other · {other.length}
                  </h2>
                  <ul className="grid gap-3">
                    {other.map(({ seat, number }) => (
                      <li key={seat.id} className="flex flex-wrap items-center justify-between gap-3 rounded-2xl bg-white p-4 shadow-sm ring-1 ring-slate-200/80">
                        <div>
                          <p className="font-semibold text-slate-900">{seatNumberLabel(number)}</p>
                          <p className="text-xs text-slate-500">Added {formatDate(seat.created_at)}</p>
                        </div>
                        <Badge tone={seatStatusTone(seat.status)}>{seatStatusLabel(seat.status)}</Badge>
                      </li>
                    ))}
                  </ul>
                </section>
              )}
            </div>
          )}
        </>
      )}
    </>
  );
}

function AssignedSeatCard({ seat, number }: { seat: InstituteSeat; number: number }) {
  const occupant = seat.assignment;
  const name = occupant ? studentPrimary(occupant) : "Assigned student";
  return (
    <article className="rounded-2xl bg-white p-5 shadow-sm ring-1 ring-slate-200/80 transition hover:shadow-md hover:ring-slate-300">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="flex min-w-0 gap-4">
          <UserAvatar name={name} email={occupant?.candidate_email} />
          <div className="min-w-0">
            <p className="text-xs font-medium uppercase tracking-wide text-slate-500">{seatNumberLabel(number)}</p>
            {occupant ? (
              <Link to={`/institute/students/${occupant.id}`} className="text-base font-semibold text-slate-900 hover:text-brand-700">
                {name}
              </Link>
            ) : (
              <p className="text-base font-semibold text-slate-900">{name}</p>
            )}
            <div className="mt-1.5 flex flex-wrap gap-x-4 gap-y-1 text-sm text-slate-500">
              {occupant?.candidate_email && (
                <span className="inline-flex items-center gap-1.5">
                  <Mail className="h-3.5 w-3.5 shrink-0" aria-hidden />
                  {occupant.candidate_email}
                </span>
              )}
              {occupant?.candidate_phone ? (
                <span className="inline-flex items-center gap-1.5">
                  <Phone className="h-3.5 w-3.5 shrink-0" aria-hidden />
                  {occupant.candidate_phone}
                </span>
              ) : null}
              <span>Assigned {formatDate(occupant?.accepted_at || occupant?.created_at || seat.created_at)}</span>
            </div>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2 lg:flex-col lg:items-end">
          <Badge tone={seatStatusTone(seat.status)}>{seatStatusLabel(seat.status)}</Badge>
          {occupant && (
            <div className="flex flex-wrap items-center gap-2">
              {occupant.status !== "active" && <AssignmentBadge status={occupant.status} />}
              <ButtonLink to={`/institute/students/${occupant.id}`} size="sm">
                <Eye className="h-4 w-4" aria-hidden /> View
              </ButtonLink>
            </div>
          )}
        </div>
      </div>
    </article>
  );
}

function OpenSeatTile({ seat, number }: { seat: InstituteSeat; number: number }) {
  return (
    <article className="flex h-full flex-col justify-between rounded-2xl bg-white p-4 shadow-sm ring-1 ring-slate-200/80">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="font-semibold text-slate-900">{seatNumberLabel(number)}</p>
          <p className="mt-1 text-xs text-slate-500">Added {formatDate(seat.created_at)}</p>
        </div>
        <Badge tone="green">{seatStatusLabel(seat.status)}</Badge>
      </div>
      <ButtonLink to="/institute/students" variant="secondary" size="sm" className="mt-4">
        <Plus className="h-4 w-4" aria-hidden /> Add student
      </ButtonLink>
    </article>
  );
}

function subStatusTone(status: string): "green" | "amber" | "red" | "slate" | "brand" {
  const s = status.toLowerCase();
  if (s === "active" || s === "trialing") return "green";
  if (s === "pending") return "amber";
  if (s === "past_due") return "red";
  if (s === "cancelled" || s === "expired") return "slate";
  return "brand";
}

function subscriptionBadge(sub: Subscription): { tone: "green" | "amber" | "red" | "slate" | "brand"; label: string } {
  if (sub.cancel_at_period_end) return { tone: "amber", label: "Ending" };
  return { tone: subStatusTone(sub.status), label: prettyStatus(sub.status) };
}

function packageCents(plan: Plan): number {
  return plan.price_cents * (plan.limits.seats ?? 0);
}

export function InstituteSubscriptionPage() {
  const toast = useToast();
  const client = useQueryClient();
  const { data, isLoading } = useQuery({ queryKey: ["institute", "subscription"], queryFn: institute.subscription });
  const { data: plans, isLoading: plansLoading } = useQuery({ queryKey: ["institute", "plans"], queryFn: institute.plans });
  const checkout = useMutation({
    mutationFn: async (plan: Plan) => {
      const started = await institute.checkout(plan.code);
      if (started.checkout?.url) {
        window.location.assign(started.checkout.url);
        return { plan, status: "pending" as const };
      }
      if (!started.checkout?.key || !started.checkout?.subscription_id) {
        throw new CheckoutError(
          "Razorpay Checkout did not start. Enable Razorpay under Admin → Settings → Payments "
          + "(save rzp_test_ or rzp_live_ keys, Test API keys, Sync plans), then try again.",
        );
      }
      const paid = await openRazorpayCheckout(started.checkout);
      if (!paid) return { plan, status: "dismissed" as const };
      const confirmed = await billing.confirm({
        payment_id: paid.razorpay_payment_id, subscription_id: paid.razorpay_subscription_id,
        signature: paid.razorpay_signature,
      });
      return { plan, status: confirmed.subscription.status };
    },
    onSuccess: ({ plan, status }) => {
      void client.invalidateQueries({ queryKey: ["institute"] });
      if (status === "active" || status === "trialing") toast.success(`${plan.name} is active. Seats are ready to assign.`);
      else if (status !== "dismissed") toast.success("Payment received. Confirming seats…");
    },
    onError: (e) => toast.error(checkoutError(e)),
  });

  const sub = data?.subscription ?? null;
  const seats = data?.seats;
  const assigned = seats?.assigned ?? 0;
  const total = seats?.total ?? 0;
  const available = seats?.available ?? 0;
  const occupancy = total > 0 ? Math.round((assigned / total) * 100) : 0;
  const catalog = (plans ?? []).find((p) => p.code === sub?.plan.code);
  const starter = catalog ?? (plans ?? [])[0];
  const billed = starter ? packageCents(starter) : (sub?.plan.price_cents ?? 0);
  const currency = starter?.currency ?? sub?.plan.currency ?? "INR";
  const amountLabel = billed > 0 ? formatMoney(billed, currency) : "—";
  const badge = sub ? subscriptionBadge(sub) : null;

  return (
    <>
      <PageHeader
        title="Subscription"
        description="Campus plans include a pool of student seats. Students do not pay while they are assigned."
        actions={
          <div className="flex flex-wrap gap-2">
            {available > 0 && (
              <ButtonLink to="/institute/students">
                <Plus className="h-4 w-4" aria-hidden /> Add student
              </ButtonLink>
            )}
            <ButtonLink to="/institute/seats" variant="secondary">
              <Package className="h-4 w-4" aria-hidden /> View seats
            </ButtonLink>
          </div>
        }
      />

      {isLoading || plansLoading ? <Spinner /> : (
        <>
          <div className="mb-6 overflow-hidden rounded-2xl bg-gradient-to-br from-brand-700 to-slate-900 p-6 text-white shadow-sm ring-1 ring-brand-700/40 sm:p-8">
            <p className="text-sm font-medium text-brand-100">Campus plan</p>
            <h2 className="mt-1 text-2xl font-bold tracking-tight">
              {sub?.plan.name ?? "No campus plan yet"}
            </h2>
            <p className="mt-2 max-w-xl text-sm text-blue-100">
              {sub
                ? `${assigned} of ${total} seats in use · ${planLine(sub)}`
                : "Buy a package to create seats, then add students from the roster."}
            </p>
            {total > 0 && (
              <div className="mt-5 h-2 overflow-hidden rounded-full bg-white/15" aria-hidden>
                <div className="h-full rounded-full bg-white" style={{ width: `${occupancy}%` }} />
              </div>
            )}
          </div>

          <div className="mb-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <StatCard
              icon={<CreditCard className="h-4 w-4" aria-hidden />}
              label="Current plan"
              value={sub?.plan.name ?? "None"}
              sub={badge ? badge.label : "Choose a package below"}
            />
            <StatCard
              icon={<Package className="h-4 w-4" aria-hidden />}
              label="Total seats"
              value={total}
              sub={catalog ? `${catalog.limits.seats ?? 0} in this package` : "From your campus plan"}
            />
            <StatCard
              icon={<Users className="h-4 w-4" aria-hidden />}
              label="Assigned"
              value={assigned}
              sub={`${available} ready to assign`}
            />
            <StatCard
              icon={<Clock className="h-4 w-4" aria-hidden />}
              label={sub ? "Package amount" : "Starting at"}
              value={amountLabel}
              sub={
                !sub ? "Billed monthly"
                  : sub.cancel_at_period_end ? `Ends ${formatDate(sub.current_period_end)}`
                    : `Renews ${formatDate(sub.current_period_end)}`
              }
            />
          </div>

          {total > 0 && (
            <Card className="mb-6" title="Seat occupancy" actions={<ButtonLink to="/institute/seats" variant="ghost" size="sm">View seats</ButtonLink>}>
              <ProgressBar value={assigned} max={total} label="Assigned seats" usageKind="applications" />
            </Card>
          )}

          <div className="mb-4 flex flex-col gap-1 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <h2 className="text-base font-semibold text-slate-900">Campus packages</h2>
              <p className="mt-1 text-sm text-slate-500">
                Institute pays. Assigned students keep these limits until you release them.
              </p>
            </div>
            {badge && <Badge tone={badge.tone}>{badge.label}</Badge>}
          </div>

          {(plans ?? []).length === 0 ? (
            <Card>
              <EmptyState icon={<CreditCard className="h-8 w-8" aria-hidden />} title="No campus packages">
                <p>Campus plans will show here once they are published.</p>
              </EmptyState>
            </Card>
          ) : (
            <div className="grid gap-4 lg:grid-cols-2">
              {(plans ?? []).map((p) => (
                <CampusPlanCard
                  key={p.code}
                  plan={p}
                  sub={sub}
                  busy={checkout.isPending}
                  loading={checkout.isPending && checkout.variables?.code === p.code}
                  onChoose={() => checkout.mutate(p)}
                />
              ))}
            </div>
          )}
        </>
      )}
    </>
  );
}

function CampusPlanCard({ plan: p, sub, busy, loading, onChoose }: {
  plan: Plan; sub: Subscription | null; busy: boolean; loading: boolean; onChoose: () => void;
}) {
  const current = sub?.plan.code === p.code;
  const seats = p.limits.seats ?? 0;
  const features = [
    `${seats.toLocaleString()} student seats`,
    `${formatMoney(p.price_cents, p.currency)} per student / ${p.interval}`,
    `${p.limits.applications_per_month.toLocaleString()} applications / student / month`,
    `${formatResumeLimit(p.limits.resumes)} resumes / student / month`,
    p.limits.mock_interviews_per_month
      ? `${p.limits.mock_interviews_per_month.toLocaleString()} mock interviews / student / month`
      : null,
    `Package: ${(p.limits.applications_per_month * seats).toLocaleString()} applications / month · ${
      p.limits.resumes >= RESUMES_UNLIMITED
        ? "unlimited resumes"
        : `${(p.limits.resumes * seats).toLocaleString()} resumes / month`
    }`,
  ].filter((row): row is string => Boolean(row));

  return (
    <article className={cx(
      "flex h-full flex-col rounded-2xl bg-white p-6 shadow-sm ring-1 transition",
      current ? "ring-2 ring-brand-600 shadow-md" : "ring-slate-200/80 hover:shadow-md hover:ring-slate-300",
    )}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-lg font-semibold text-slate-900">{p.name}</p>
          <p className="mt-1 text-sm text-slate-500">{seats.toLocaleString()} minimum students</p>
        </div>
        {current ? <Badge tone="brand">Current</Badge> : null}
      </div>
      <p className="mt-4 text-3xl font-bold tracking-tight text-slate-900">
        {formatMoney(packageCents(p), p.currency)}
        {p.price_cents > 0 && <span className="text-sm font-normal text-slate-500"> / {p.interval}</span>}
      </p>
      <ul className="mt-5 flex-1 space-y-2.5">
        {features.map((row) => (
          <li key={row} className="flex gap-2 text-sm text-slate-600">
            <Check className="mt-0.5 h-4 w-4 shrink-0 text-brand-600" aria-hidden />
            <span>{row}</span>
          </li>
        ))}
        <li className="flex gap-2 text-sm text-slate-600">
          <Check className="mt-0.5 h-4 w-4 shrink-0 text-brand-600" aria-hidden />
          <span>Institute pays — students keep these limits until you release them</span>
        </li>
      </ul>
      {current ? (
        <p className="mt-6 text-sm font-medium text-brand-700">This is your active campus plan.</p>
      ) : (
        <Button className="mt-6 w-full" onClick={onChoose} loading={loading} disabled={busy}>
          {sub ? `Switch to ${p.name}` : "Choose"}
        </Button>
      )}
    </article>
  );
}

const ASSIGNMENT_REPORT_ORDER = [
  "active", "invited", "pending_candidate_acceptance", "suspended", "released", "rejected", "expired", "cancelled",
];
const SEAT_REPORT_ORDER = ["assigned", "purchased", "suspended", "released", "expired"];
const TONE_BAR: Record<string, string> = {
  green: "bg-emerald-500",
  red: "bg-red-400",
  amber: "bg-amber-400",
  blue: "bg-sky-500",
  slate: "bg-slate-400",
  brand: "bg-brand-600",
};

function orderedCounts(source: Record<string, number> | undefined, order: string[]) {
  const map = source ?? {};
  const seen = new Set<string>();
  const rows: { key: string; count: number }[] = [];
  for (const key of order) {
    if (key in map) {
      rows.push({ key, count: map[key] ?? 0 });
      seen.add(key);
    }
  }
  for (const [key, count] of Object.entries(map)) {
    if (!seen.has(key)) rows.push({ key, count });
  }
  return rows;
}

function assignmentHref(status: string): string {
  if (status === "invited" || status === "pending_candidate_acceptance") return "/institute/invitations";
  return "/institute/students";
}

export function InstituteReportsPage() {
  const reports = useQuery({ queryKey: ["institute", "reports"], queryFn: institute.reports });
  const dash = useQuery({ queryKey: ["institute", "dashboard"], queryFn: institute.dashboard });
  const seats = reports.data?.seats ?? dash.data?.seats;
  const assigned = seats?.assigned ?? 0;
  const total = seats?.total ?? 0;
  const available = seats?.available ?? 0;
  const occupancy = total > 0 ? Math.round((assigned / total) * 100) : 0;
  const activity = dash.data?.activity;
  const planName = dash.data?.subscription?.plan.name;
  const students = dash.data?.students ?? 0;
  const pending = dash.data?.pending_invites ?? 0;
  const assignments = orderedCounts(reports.data?.assignments_by_status, ASSIGNMENT_REPORT_ORDER);
  const assignmentTotal = assignments.reduce((sum, row) => sum + row.count, 0);
  const liveAssignments = assignments.filter((row) => row.count > 0);
  const seatRows = orderedCounts(seats?.by_status, SEAT_REPORT_ORDER).filter((row) => row.count > 0);
  const across = students === 1 ? "1 active student" : `${students} active students`;

  return (
    <>
      <PageHeader
        title="Reports"
        description="Seat occupancy, assignment mix, and job activity across students on this campus."
        actions={
          <div className="flex flex-wrap gap-2">
            <ButtonLink to="/institute/students">
              <Users className="h-4 w-4" aria-hidden /> Students
            </ButtonLink>
            <ButtonLink to="/institute/seats" variant="secondary">
              <Package className="h-4 w-4" aria-hidden /> View seats
            </ButtonLink>
          </div>
        }
      />

      {reports.isLoading ? <Spinner /> : reports.error && !reports.data ? (
        <Alert kind="error">{errorMessage(reports.error)}</Alert>
      ) : (
        <>
          <div className="mb-6 overflow-hidden rounded-2xl bg-gradient-to-br from-brand-700 to-slate-900 p-6 text-white shadow-sm ring-1 ring-brand-700/40 sm:p-8">
            <p className="text-sm font-medium text-brand-100">Campus report</p>
            <h2 className="mt-1 text-2xl font-bold tracking-tight">
              {assigned} of {total} seats in use
            </h2>
            <p className="mt-2 max-w-xl text-sm text-blue-100">
              {total === 0
                ? "Buy a campus plan to create seats, then add students."
                : `${students} active · ${pending} open invitation${pending === 1 ? "" : "s"} · ${occupancy}% occupied${planName ? ` · ${planName}` : ""}`}
            </p>
            {total > 0 && (
              <div className="mt-5 h-2 overflow-hidden rounded-full bg-white/15" aria-hidden>
                <div className="h-full rounded-full bg-white" style={{ width: `${occupancy}%` }} />
              </div>
            )}
          </div>

          <div className="mb-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <StatCard icon={<Package className="h-4 w-4" aria-hidden />} label="Total seats" value={total} sub={planName ?? "Campus plan"} />
            <StatCard icon={<Users className="h-4 w-4" aria-hidden />} label="Assigned" value={assigned} sub="Held by students" />
            <StatCard icon={<UserPlus className="h-4 w-4" aria-hidden />} label="Available" value={available} sub="Ready to assign" />
            <StatCard icon={<CheckCircle2 className="h-4 w-4" aria-hidden />} label="Occupancy" value={`${occupancy}%`} sub="Assigned ÷ total" />
          </div>

          {total > 0 && (
            <Card className="mb-6" title="Seat occupancy" actions={<ButtonLink to="/institute/seats" variant="ghost" size="sm">View seats</ButtonLink>}>
              <ProgressBar value={assigned} max={total} label="Assigned seats" usageKind="applications" />
            </Card>
          )}

          {activity && (
            <Card className="mb-6" title="Student activity" actions={<span className="text-sm text-slate-500">{across}</span>}>
              <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                <StatCard
                  icon={<Briefcase className="h-4 w-4" aria-hidden />}
                  label="Jobs searched"
                  value={activity.searched.toLocaleString()}
                  sub="Jobs found by all students"
                />
                <StatCard
                  icon={<CheckCircle2 className="h-4 w-4" aria-hidden />}
                  label="Applied"
                  value={activity.applied.toLocaleString()}
                  sub={
                    activity.success_rate == null
                      ? "Easy Apply submitted"
                      : `${Math.round(activity.success_rate * 100)}% of applied + failed`
                  }
                />
                <StatCard
                  icon={<MinusCircle className="h-4 w-4" aria-hidden />}
                  label="Skipped"
                  value={activity.skipped.toLocaleString()}
                  sub="Passed over during runs"
                />
                <StatCard
                  icon={<XCircle className="h-4 w-4" aria-hidden />}
                  label="Failed"
                  value={activity.failed.toLocaleString()}
                  sub="Apply attempts that did not go through"
                />
              </div>
              {activity.searched > 0 && (
                <div className="mt-6">
                  <DailyChart
                    data={activity.daily}
                    ariaLabel="Applied and failed jobs by all students over the last 30 days"
                  />
                </div>
              )}
            </Card>
          )}

          <Card
            className="mb-6"
            title="Assignments by status"
            actions={
              assignmentTotal > 0
                ? <span className="text-sm text-slate-500">{assignmentTotal} total</span>
                : undefined
            }
          >
            {liveAssignments.length === 0 ? (
              <EmptyState icon={<FileText className="h-8 w-8" aria-hidden />} title="No assignment data yet">
                <p>Add students to see how roster seats break down by status.</p>
              </EmptyState>
            ) : (
              <>
                <div className="mb-5 flex h-3 overflow-hidden rounded-full bg-slate-100" aria-hidden>
                  {liveAssignments.map((row) => (
                    <div
                      key={row.key}
                      className={TONE_BAR[assignmentStatus(row.key).tone] ?? TONE_BAR.slate}
                      style={{ width: `${assignmentTotal > 0 ? (row.count / assignmentTotal) * 100 : 0}%` }}
                    />
                  ))}
                </div>
                <ul className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                  {liveAssignments.map((row) => {
                    const meta = assignmentStatus(row.key);
                    const share = assignmentTotal > 0 ? Math.round((row.count / assignmentTotal) * 100) : 0;
                    return (
                      <li key={row.key}>
                        <Link
                          to={assignmentHref(row.key)}
                          className="flex h-full flex-col items-start rounded-2xl bg-slate-50 p-4 ring-1 ring-slate-200/80 transition hover:bg-white hover:shadow-sm hover:ring-slate-300"
                        >
                          <Badge tone={meta.tone}>{meta.label}</Badge>
                          <p className="mt-3 text-2xl font-bold tabular-nums tracking-tight text-slate-900">{row.count}</p>
                          <p className="mt-1 text-xs text-slate-500">{share}% of assignments</p>
                        </Link>
                      </li>
                    );
                  })}
                </ul>
              </>
            )}
          </Card>

          {seatRows.length > 0 && (
            <Card title="Seat inventory" actions={<ButtonLink to="/institute/seats" variant="ghost" size="sm">View seats</ButtonLink>}>
              <div className="mb-5 flex h-3 overflow-hidden rounded-full bg-slate-100" aria-hidden>
                {seatRows.map((row) => (
                  <div
                    key={row.key}
                    className={TONE_BAR[seatStatusTone(row.key)] ?? TONE_BAR.slate}
                    style={{ width: `${total > 0 ? (row.count / total) * 100 : 0}%` }}
                  />
                ))}
              </div>
              <ul className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                {seatRows.map((row) => {
                  const share = total > 0 ? Math.round((row.count / total) * 100) : 0;
                  return (
                    <li key={row.key} className="flex flex-col items-start rounded-2xl bg-slate-50 p-4 ring-1 ring-slate-200/80">
                      <Badge tone={seatStatusTone(row.key)}>{seatStatusLabel(row.key)}</Badge>
                      <p className="mt-3 text-2xl font-bold tabular-nums tracking-tight text-slate-900">{row.count}</p>
                      <p className="mt-1 text-xs text-slate-500">{share}% of seats</p>
                    </li>
                  );
                })}
              </ul>
            </Card>
          )}
        </>
      )}
    </>
  );
}

function instituteStatusTone(status: string): "green" | "amber" | "red" | "slate" {
  const s = status.toLowerCase();
  if (s === "active") return "green";
  if (s === "pending") return "amber";
  if (s === "suspended" || s === "rejected") return "red";
  return "slate";
}

export function InstituteProfilePage() {
  const toast = useToast();
  const client = useQueryClient();
  const { data, isLoading, error } = useQuery({ queryKey: ["institute", "profile"], queryFn: institute.profile });
  const [form, setForm] = useState({ name: "", contact_name: "", phone: "", gstin: "", pan_number: "", institute_type: "OTHER" });
  useEffect(() => {
    if (!data) return;
    setForm({
      name: data.name, contact_name: data.contact_name, phone: data.phone,
      gstin: data.gstin, pan_number: data.pan_number, institute_type: data.institute_type || "OTHER",
    });
  }, [data]);
  const save = useMutation({
    mutationFn: () => institute.saveProfile(form),
    onSuccess: (updated) => {
      client.setQueryData(["institute", "profile"], updated);
      void client.invalidateQueries({ queryKey: ["institute"] });
      toast.success("Profile saved.");
    },
    onError: (e) => toast.error(errorMessage(e)),
  });

  const displayName = form.name.trim() || data?.name || "Campus";
  const typeLabel = INSTITUTE_TYPE_LABELS[form.institute_type] ?? prettyStatus(form.institute_type || "other");
  const seats = data?.seats;
  const assigned = seats?.assigned ?? 0;
  const total = seats?.total ?? 0;
  const occupancy = total > 0 ? Math.round((assigned / total) * 100) : 0;
  const legalFilled = [form.gstin, form.pan_number].filter((value) => value.trim()).length;
  const legalSub = legalFilled === 2 ? "GSTIN and PAN on file" : legalFilled === 1 ? "1 of 2 tax IDs" : "Add GSTIN and PAN";

  return (
    <>
      <PageHeader
        title="Profile"
        description="Campus identity and tax details shown on invoices and student invitations."
        actions={
          <ButtonLink to="/institute/settings" variant="secondary">
            Settings
          </ButtonLink>
        }
      />

      {isLoading ? <Spinner /> : error || !data ? (
        <Alert kind="error">{errorMessage(error)}</Alert>
      ) : (
        <>
          <div className="mb-6 overflow-hidden rounded-2xl bg-gradient-to-br from-brand-700 to-slate-900 p-6 text-white shadow-sm ring-1 ring-brand-700/40 sm:p-8">
            <p className="text-sm font-medium text-brand-100">Campus profile</p>
            <div className="mt-3 flex items-start gap-4">
              <span className="inline-flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl bg-white/15 text-lg font-bold text-white ring-1 ring-white/20" aria-hidden>
                {displayName.replace(/@.*/, "").split(/\s+/).filter(Boolean).slice(0, 2).map((part) => part[0]).join("").toUpperCase() || "C"}
              </span>
              <div className="min-w-0">
                <h2 className="text-2xl font-bold tracking-tight">{displayName}</h2>
                <p className="mt-2 max-w-xl text-sm text-blue-100">
                  {typeLabel}
                  {form.contact_name.trim() ? ` · ${form.contact_name.trim()}` : ""}
                  {total > 0 ? ` · ${assigned} of ${total} seats in use` : ""}
                </p>
              </div>
            </div>
            {total > 0 && (
              <div className="mt-5 h-2 overflow-hidden rounded-full bg-white/15" aria-hidden>
                <div className="h-full rounded-full bg-white" style={{ width: `${occupancy}%` }} />
              </div>
            )}
          </div>

          <div className="mb-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <StatCard icon={<Building2 className="h-4 w-4" aria-hidden />} label="Type" value={typeLabel} sub="Shown on invitations" />
            <StatCard
              icon={<Users className="h-4 w-4" aria-hidden />}
              label="Contact"
              value={form.contact_name.trim() || "—"}
              sub={form.phone.trim() || data.email}
            />
            <StatCard icon={<FileText className="h-4 w-4" aria-hidden />} label="Tax IDs" value={`${legalFilled} / 2`} sub={legalSub} />
            <StatCard
              icon={<CheckCircle2 className="h-4 w-4" aria-hidden />}
              label="Campus status"
              value={prettyStatus(data.status)}
              sub={data.created_at ? `Added ${formatDate(data.created_at)}` : "Campus record"}
            />
          </div>

          <form onSubmit={(e) => { e.preventDefault(); save.mutate(); }} className="space-y-6">
            <div className="grid gap-6 lg:grid-cols-2">
              <Card title="Campus identity">
                <div className="space-y-4">
                  <TextInput label="Name" required value={form.name} onChange={(name) => setForm((f) => ({ ...f, name }))} maxLength={190} />
                  <Select
                    label="Type"
                    value={form.institute_type}
                    onChange={(institute_type) => setForm((f) => ({ ...f, institute_type }))}
                    options={Object.entries(INSTITUTE_TYPE_LABELS).map(([value, label]) => ({ value, label }))}
                  />
                  <TextInput label="Contact" value={form.contact_name} onChange={(contact_name) => setForm((f) => ({ ...f, contact_name }))} maxLength={190} />
                  <TextInput label="Phone" value={form.phone} onChange={(phone) => setForm((f) => ({ ...f, phone }))} maxLength={32} />
                  <TextInput
                    label="Email"
                    value={data.email}
                    onChange={() => undefined}
                    readOnly
                    hint="Login email for this campus. It cannot be changed here."
                  />
                </div>
              </Card>
              <Card title="Legal details">
                <p className="mb-4 text-sm text-slate-500">
                  GSTIN and PAN appear on invoices. Leave blank if this campus does not have them yet.
                </p>
                <div className="space-y-4">
                  <TextInput
                    label="GSTIN"
                    value={form.gstin}
                    onChange={(gstin) => setForm((f) => ({ ...f, gstin: gstin.toUpperCase() }))}
                    maxLength={15}
                    hint="15 characters"
                  />
                  <TextInput
                    label="PAN"
                    value={form.pan_number}
                    onChange={(pan_number) => setForm((f) => ({ ...f, pan_number: pan_number.toUpperCase() }))}
                    maxLength={10}
                    hint="10 characters"
                  />
                </div>
                <div className="mt-6 flex flex-wrap gap-2">
                  <Badge tone={instituteStatusTone(data.status)}>{prettyStatus(data.status)}</Badge>
                  {legalFilled === 2 ? <Badge tone="green">Tax IDs complete</Badge> : <Badge tone="amber">Tax IDs incomplete</Badge>}
                </div>
              </Card>
            </div>
            <div className="flex justify-end">
              <Button type="submit" loading={save.isPending} disabled={!form.name.trim()}>Save</Button>
            </div>
          </form>
        </>
      )}
    </>
  );
}

export function InstituteSettingsPage() {
  const toast = useToast();
  const client = useQueryClient();
  const { data, isLoading, error } = useQuery({ queryKey: ["institute", "profile"], queryFn: institute.profile });
  const [form, setForm] = useState<InstituteSettings>({
    timezone: "Asia/Kolkata", notify_invites: true, notify_acceptances: true, notify_low_seats: true,
    low_seat_threshold: 3, invite_expiry_days: 7, invite_note: "",
  });
  useEffect(() => { if (data) setForm(settingsOf(data)); }, [data]);
  const save = useMutation({
    mutationFn: () => institute.saveSettings({ ...form }),
    onSuccess: (updated) => {
      client.setQueryData(["institute", "profile"], updated);
      toast.success("Settings saved.");
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  const alertsOn = [form.notify_invites, form.notify_acceptances, form.notify_low_seats].filter(Boolean).length;
  const available = data?.seats.available ?? 0;
  const total = data?.seats.total ?? 0;
  const lowSeats = total > 0 && available <= form.low_seat_threshold;
  const expiryLabel = form.invite_expiry_days === 1 ? "1 day" : `${form.invite_expiry_days} days`;

  return (
    <>
      <PageHeader
        title="Settings"
        description="Invitation defaults and email alerts for this campus. Students do not pay while they are assigned."
        actions={
          <ButtonLink to="/institute/profile" variant="secondary">
            Profile
          </ButtonLink>
        }
      />

      {isLoading ? <Spinner /> : error || !data ? (
        <Alert kind="error">{errorMessage(error)}</Alert>
      ) : (
        <>
          <div className="mb-6 overflow-hidden rounded-2xl bg-gradient-to-br from-brand-700 to-slate-900 p-6 text-white shadow-sm ring-1 ring-brand-700/40 sm:p-8">
            <p className="text-sm font-medium text-brand-100">Campus settings</p>
            <h2 className="mt-1 text-2xl font-bold tracking-tight">Invitation defaults</h2>
            <p className="mt-2 max-w-xl text-sm text-blue-100">
              {form.timezone} · Invites expire in {expiryLabel} · {alertsOn} of 3 email alerts on
            </p>
            <div className="mt-5 h-2 overflow-hidden rounded-full bg-white/15" aria-hidden>
              <div className="h-full rounded-full bg-white" style={{ width: `${Math.round((alertsOn / 3) * 100)}%` }} />
            </div>
          </div>

          <div className="mb-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <StatCard icon={<Clock className="h-4 w-4" aria-hidden />} label="Timezone" value={form.timezone} sub="Used on invitation emails" />
            <StatCard icon={<Mail className="h-4 w-4" aria-hidden />} label="Invite expiry" value={form.invite_expiry_days} sub={form.invite_expiry_days === 1 ? "Day until the invite lapses" : "Days until the invite lapses"} />
            <StatCard
              icon={<Package className="h-4 w-4" aria-hidden />}
              label="Low-seat warning"
              value={form.low_seat_threshold}
              sub={total > 0 ? `${available} seats available now` : "Email when open seats drop to this"}
            />
            <StatCard icon={<Bell className="h-4 w-4" aria-hidden />} label="Email alerts" value={`${alertsOn} / 3`} sub={alertsOn === 3 ? "All alerts on" : `${3 - alertsOn} turned off`} />
          </div>

          {lowSeats && form.notify_low_seats && (
            <div className="mb-6">
              <Alert kind="info">
                {available} open seat{available === 1 ? "" : "s"} — at or below the warning of {form.low_seat_threshold}.
                A low-seat email will go out when this campus hits that threshold.
              </Alert>
            </div>
          )}

          <form onSubmit={(e) => { e.preventDefault(); save.mutate(); }} className="space-y-6">
            <div className="grid gap-6 lg:grid-cols-2">
              <Card title="Invitations">
                <p className="mb-4 text-sm text-slate-500">
                  These defaults apply to new invitations. Billing stays on the institute until you release a student.
                </p>
                <div className="space-y-4">
                  <TextInput
                    label="Timezone"
                    value={form.timezone}
                    onChange={(timezone) => setForm((f) => ({ ...f, timezone }))}
                    hint="IANA name, for example Asia/Kolkata"
                  />
                  <TextInput
                    label="Invite expiry (days)"
                    type="number"
                    min={1}
                    max={30}
                    value={String(form.invite_expiry_days)}
                    onChange={(v) => setForm((f) => ({ ...f, invite_expiry_days: Number(v) || 7 }))}
                    hint="1–30 days"
                  />
                  <TextInput
                    label="Low-seat warning at"
                    type="number"
                    min={1}
                    max={50}
                    value={String(form.low_seat_threshold)}
                    onChange={(v) => setForm((f) => ({ ...f, low_seat_threshold: Number(v) || 3 }))}
                    hint="Email when available seats drop to this number"
                  />
                  <TextArea
                    label="Default invite note"
                    value={form.invite_note}
                    onChange={(invite_note) => setForm((f) => ({ ...f, invite_note }))}
                    maxLength={500}
                    hint="Optional line included in invitation emails"
                  />
                </div>
              </Card>
              <Card title="Email alerts">
                <p className="mb-4 text-sm text-slate-500">
                  Alerts go to the campus contact. Turn off any you do not need.
                </p>
                <div className="space-y-3">
                  <div className="rounded-xl bg-slate-50 p-4 ring-1 ring-slate-200/80">
                    <Toggle
                      label="Email when an invitation is sent"
                      checked={form.notify_invites}
                      onChange={(notify_invites) => setForm((f) => ({ ...f, notify_invites }))}
                      hint="Confirms each invite from this campus"
                    />
                  </div>
                  <div className="rounded-xl bg-slate-50 p-4 ring-1 ring-slate-200/80">
                    <Toggle
                      label="Email when a student accepts"
                      checked={form.notify_acceptances}
                      onChange={(notify_acceptances) => setForm((f) => ({ ...f, notify_acceptances }))}
                      hint="When someone takes a seat"
                    />
                  </div>
                  <div className="rounded-xl bg-slate-50 p-4 ring-1 ring-slate-200/80">
                    <Toggle
                      label="Email when seats run low"
                      checked={form.notify_low_seats}
                      onChange={(notify_low_seats) => setForm((f) => ({ ...f, notify_low_seats }))}
                      hint={`Fires at ${form.low_seat_threshold} open seat${form.low_seat_threshold === 1 ? "" : "s"}`}
                    />
                  </div>
                </div>
                <div className="mt-6 flex flex-wrap gap-2">
                  <Badge tone={form.notify_invites ? "green" : "slate"}>Invites {form.notify_invites ? "on" : "off"}</Badge>
                  <Badge tone={form.notify_acceptances ? "green" : "slate"}>Acceptances {form.notify_acceptances ? "on" : "off"}</Badge>
                  <Badge tone={form.notify_low_seats ? "green" : "slate"}>Low seats {form.notify_low_seats ? "on" : "off"}</Badge>
                </div>
              </Card>
            </div>
            <div className="flex justify-end">
              <Button type="submit" loading={save.isPending}>Save settings</Button>
            </div>
          </form>
        </>
      )}
    </>
  );
}
