import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Building2, GraduationCap, Layers, Mail, MousePointerClick, Percent, Search, Users, Wallet } from "lucide-react";
import { useState, type ReactNode } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { forgetUser, homeFor, useSetSession } from "../../auth/session";
import { Select, TextInput, Toggle } from "../../components/form";
import { ConfirmDialog, Modal } from "../../components/Modal";
import { Pagination } from "../../components/Pagination";
import { useToast } from "../../components/Toast";
import { Alert, Badge, Button, ButtonLink, Card, EmptyState, PageHeader, ProgressBar, Spinner, cx } from "../../components/ui";
import { formatDate, formatDateTime, formatMoney, formatRelative } from "../../lib/format";
import { useDebounced } from "../../lib/useDebounced";
import { errorMessage, fieldErrors } from "../../services/api";
import { admin } from "../../services/endpoints";
import type { Institute, InstituteSettings, Partner } from "../../types";
import { providerLabel, Stat, SubBadge, Table, Td, UserLink } from "./shared";

const INSTITUTE_STATUS_TONES: Record<string, "green" | "amber" | "red" | "slate"> = {
  pending: "amber", active: "green", suspended: "red", closed: "slate",
};

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

const SOURCE_LABELS: Record<string, string> = {
  admin: "Created by admin",
  direct: "Self-registered",
  partner: "Partner enrolled",
  referral: "Referral",
};

const ASSIGNMENT_TONES: Record<string, "green" | "amber" | "blue" | "red" | "slate"> = {
  invited: "blue",
  pending_candidate_acceptance: "amber",
  active: "green",
  rejected: "red",
  suspended: "red",
  released: "slate",
  expired: "slate",
  cancelled: "slate",
};

const ASSIGNMENT_LABELS: Record<string, string> = {
  invited: "Invited",
  pending_candidate_acceptance: "Waiting to accept",
  active: "Active",
  rejected: "Rejected",
  suspended: "Suspended",
  released: "Released",
  expired: "Expired",
  cancelled: "Cancelled",
};

const SEAT_TONES: Record<string, "green" | "amber" | "blue" | "red" | "slate"> = {
  purchased: "blue", assigned: "green", suspended: "red", released: "slate", expired: "slate",
};

const SEAT_LABELS: Record<string, string> = {
  purchased: "Available", assigned: "Assigned", suspended: "Suspended", released: "Released", expired: "Expired",
};

function statusBadge(status: string) {
  return <Badge tone={INSTITUTE_STATUS_TONES[status] ?? "slate"}>{status}</Badge>;
}

function assignmentBadge(status: string) {
  return <Badge tone={ASSIGNMENT_TONES[status] ?? "slate"}>{ASSIGNMENT_LABELS[status] ?? status}</Badge>;
}

function settingsOf(institute: Institute): InstituteSettings {
  const s = institute.settings as Partial<InstituteSettings>;
  return {
    timezone: String(s.timezone || "Asia/Kolkata"),
    notify_invites: Boolean(s.notify_invites),
    notify_acceptances: Boolean(s.notify_acceptances),
    notify_low_seats: Boolean(s.notify_low_seats),
    low_seat_threshold: Number(s.low_seat_threshold ?? 3),
    invite_expiry_days: Number(s.invite_expiry_days ?? 7),
    invite_note: String(s.invite_note || ""),
  };
}

const INSTITUTE_STATUS_FILTERS = [
  { value: "pending", label: "Pending" },
  { value: "active", label: "Active" },
  { value: "suspended", label: "Suspended" },
  { value: "closed", label: "Closed" },
] as const;

type InstituteListStatus = (typeof INSTITUTE_STATUS_FILTERS)[number]["value"] | "";

function instituteEnabled(status: string): boolean {
  return status === "active";
}

function InstituteStatusFilters({ value, onChange }: { value: InstituteListStatus; onChange: (v: InstituteListStatus) => void }) {
  return (
    <div>
      <span className="mb-2 block text-sm font-medium text-slate-700">Status</span>
      <div className="flex flex-wrap gap-2">
        <button type="button" aria-pressed={value === ""} onClick={() => onChange("")}
                className={cx("rounded-full px-3 py-1 text-sm ring-1 ring-inset transition-colors",
                  value === "" ? "bg-slate-900 text-white ring-slate-900" : "bg-white text-slate-700 ring-slate-300 hover:bg-slate-50")}>
          All
        </button>
        {INSTITUTE_STATUS_FILTERS.map((f) => (
          <button key={f.value} type="button" aria-pressed={value === f.value}
                  onClick={() => onChange(value === f.value ? "" : f.value)}
                  className={cx("rounded-full px-3 py-1 text-sm ring-1 ring-inset transition-colors",
                    value === f.value ? "bg-brand-600 text-white ring-brand-600" : "bg-white text-slate-700 ring-slate-300 hover:bg-slate-50")}>
            {f.label}
          </button>
        ))}
      </div>
    </div>
  );
}

export function AdminInstitutesPage() {
  const toast = useToast();
  const client = useQueryClient();
  const [q, setQ] = useState("");
  const [status, setStatus] = useState<InstituteListStatus>("");
  const [page, setPage] = useState(1);
  const [adding, setAdding] = useState(false);
  const [editing, setEditing] = useState<Institute | null>(null);
  const [confirm, setConfirm] = useState<Pending | null>(null);
  const search = useDebounced(q.trim());
  const { data, isLoading, isFetching, error } = useQuery({
    queryKey: ["admin", "institutes", search, status, page],
    queryFn: () => admin.institutes({ q: search || undefined, status: status || undefined, page, page_size: 20 }),
    placeholderData: keepPreviousData,
  });
  const resetPage = () => setPage(1);
  const hasFilters = Boolean(search || status);
  const statusLabel = INSTITUTE_STATUS_FILTERS.find((f) => f.value === status)?.label;
  const setStatusMut = useMutation({
    mutationFn: ({ id, next }: { id: string; next: string }) => admin.setInstituteStatus(id, next),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ["admin", "institutes"] });
      setConfirm(null);
      toast.success("Status updated.");
    },
    onError: (e) => { setConfirm(null); toast.error(errorMessage(e)); },
  });

  return (
    <>
      <PageHeader
        title="Institutes"
        description="Campuses that buy seats and invite students. Approve new applications, then open a campus to manage seats."
        actions={<Button onClick={() => setAdding(true)}>Add institute</Button>}
      />
      <Card>
        <div className="relative max-w-xl">
          <TextInput label="Search" value={q} onChange={(v) => { setQ(v); resetPage(); }}
                     placeholder="Name or email" maxLength={200} className="pl-9" />
          <Search className="pointer-events-none absolute bottom-2.5 left-3 h-4 w-4 text-slate-400" aria-hidden />
        </div>
        <div className="mt-6">
          <InstituteStatusFilters value={status} onChange={(v) => { setStatus(v); resetPage(); }} />
        </div>
        {hasFilters && (
          <p className="mt-3 text-xs text-slate-500">
            Filtering{search ? ` for “${search}”` : ""}{status ? ` · ${statusLabel}` : ""}.{" "}
            <button type="button" className="font-medium text-brand-700 hover:underline"
                    onClick={() => { setQ(""); setStatus(""); resetPage(); }}>Clear filters</button>
          </p>
        )}
      </Card>

      <div className="mt-6">
        {isLoading ? <Spinner /> : error || !data ? <Alert kind="error">{errorMessage(error)}</Alert> : data.total === 0 ? (
          <Card>
            <EmptyState icon={<GraduationCap className="h-10 w-10" />} title="No institutes found">
              {hasFilters
                ? "Try a different name, email, or status."
                : "Add a campus here, or wait for one to apply from the public register page."}
            </EmptyState>
          </Card>
        ) : (
          <Card className={cx(isFetching && "opacity-70 transition-opacity")}>
            <p className="mb-4 text-sm text-slate-600">
              Showing <span className="font-medium text-slate-900">{data.items.length}</span> of{" "}
              <span className="font-medium text-slate-900">{data.total.toLocaleString()}</span> campuses
            </p>
            <Table head={["Campus", "Seats", "Joined", "Status", "Actions"]} dim={isFetching}>
              {data.items.map((i) => (
                <tr key={i.id} className="hover:bg-slate-50/80">
                  <Td>
                    <p className="font-medium text-slate-900">{i.name}</p>
                    <p className="text-sm text-slate-500">{i.email}</p>
                    {i.contact_name && (
                      <p className="text-xs text-slate-400">Contact {i.contact_name}{i.phone ? ` · ${i.phone}` : ""}</p>
                    )}
                    <p className="text-xs text-slate-400">
                      {INSTITUTE_TYPE_LABELS[i.institute_type] ?? i.institute_type}
                      {" · "}
                      {SOURCE_LABELS[i.source] ?? i.source}
                    </p>
                  </Td>
                  <Td className="tabular-nums text-slate-700">
                    {i.seats.total ? `${i.seats.available} / ${i.seats.total}` : "None yet"}
                  </Td>
                  <Td className="whitespace-nowrap text-slate-600">{formatDate(i.created_at)}</Td>
                  <Td>{statusBadge(i.status)}</Td>
                  <Td className="whitespace-nowrap">
                    <div className="flex justify-end gap-2">
                      <ButtonLink to={`/admin/institutes/${i.id}`} size="sm" variant="secondary">View</ButtonLink>
                      <Button size="sm" variant="secondary" onClick={() => setEditing(i)}>Edit</Button>
                      {instituteEnabled(i.status) ? (
                        <Button size="sm" variant="ghost" onClick={() => setConfirm({
                          title: "Disable this campus?",
                          danger: true,
                          confirm: "Disable",
                          message: `Open invitations and active student seats for ${i.name} are closed. They cannot invite students until you enable the campus again.`,
                          run: () => setStatusMut.mutate({ id: i.id, next: "suspended" }),
                        })}>Disable</Button>
                      ) : (
                        <Button size="sm" loading={setStatusMut.isPending}
                                onClick={() => setStatusMut.mutate({ id: i.id, next: "active" })}>Enable</Button>
                      )}
                    </div>
                  </Td>
                </tr>
              ))}
            </Table>
            <Pagination page={data.page} pageSize={data.page_size} total={data.total} onPage={setPage} />
          </Card>
        )}
      </div>
      {adding && <AddInstituteDialog onClose={() => setAdding(false)} />}
      {editing && <EditInstituteDialog institute={editing} onClose={() => setEditing(null)} />}
      {confirm && (
        <ConfirmDialog open title={confirm.title} message={confirm.message} confirmLabel={confirm.confirm}
                       danger={confirm.danger} loading={setStatusMut.isPending} onConfirm={confirm.run}
                       onClose={() => setConfirm(null)} />
      )}
    </>
  );
}

function AddInstituteDialog({ onClose }: { onClose: () => void }) {
  const client = useQueryClient();
  const toast = useToast();
  const navigate = useNavigate();
  const [form, setForm] = useState({
    name: "", email: "", password: "", contact_name: "", phone: "", approve: true,
  });
  const set = (key: keyof typeof form) => (value: string | boolean) => setForm((f) => ({ ...f, [key]: value }));
  const save = useMutation({
    mutationFn: () => admin.createInstitute({
      name: form.name.trim(),
      email: form.email.trim(),
      password: form.password,
      contact_name: form.contact_name.trim(),
      phone: form.phone.trim(),
      approve: form.approve,
    }),
    onSuccess: (institute) => {
      toast.success(`${institute.name} added.`);
      void client.invalidateQueries({ queryKey: ["admin", "institutes"] });
      onClose();
      navigate(`/admin/institutes/${institute.id}`);
    },
  });
  const errors = fieldErrors(save.error);
  const invalid = !form.name.trim() || !form.email.trim() || form.password.length < 10;

  return (
    <Modal open onClose={onClose} title="Add institute" footer={
      <>
        <Button variant="secondary" onClick={onClose}>Cancel</Button>
        <Button disabled={invalid} loading={save.isPending} onClick={() => save.mutate()}>Add institute</Button>
      </>
    }>
      <div className="space-y-4">
        {save.error && !Object.keys(errors).length && <Alert kind="error">{errorMessage(save.error)}</Alert>}
        <TextInput label="Institute name" required value={form.name} onChange={set("name")} maxLength={190} error={errors.name} />
        <TextInput label="Contact name" value={form.contact_name} onChange={set("contact_name")} maxLength={190} error={errors.contact_name} />
        <TextInput label="Email" type="email" required value={form.email} onChange={set("email")} error={errors.email}
                   hint="This is the login for the institute admin." />
        <TextInput label="Phone" value={form.phone} onChange={set("phone")} maxLength={32} error={errors.phone} />
        <TextInput label="Password" type="password" required value={form.password} onChange={set("password")}
                   error={errors.password} hint="At least 10 characters. Share this with the campus contact." />
        <Toggle label="Approve now" checked={form.approve} onChange={set("approve")}
                hint="Approved campuses can invite students and buy seats." />
      </div>
    </Modal>
  );
}

function EditInstituteDialog({ institute, onClose }: { institute: Institute; onClose: () => void }) {
  const client = useQueryClient();
  const toast = useToast();
  const [form, setForm] = useState({
    name: institute.name,
    contact_name: institute.contact_name,
    phone: institute.phone,
  });
  const set = (key: keyof typeof form) => (value: string) => setForm((f) => ({ ...f, [key]: value }));
  const save = useMutation({
    mutationFn: () => admin.updateInstitute(institute.id, {
      name: form.name.trim(),
      contact_name: form.contact_name.trim(),
      phone: form.phone.trim(),
    }),
    onSuccess: (updated) => {
      toast.success(`${updated.name} updated.`);
      void client.invalidateQueries({ queryKey: ["admin", "institutes"] });
      void client.invalidateQueries({ queryKey: ["admin", "institute", institute.id] });
      onClose();
    },
  });
  const errors = fieldErrors(save.error);
  const invalid = !form.name.trim();

  return (
    <Modal open onClose={onClose} title="Edit institute" footer={
      <>
        <Button variant="secondary" onClick={onClose}>Cancel</Button>
        <Button disabled={invalid} loading={save.isPending} onClick={() => save.mutate()}>Save changes</Button>
      </>
    }>
      <div className="space-y-4">
        {save.error && !Object.keys(errors).length && <Alert kind="error">{errorMessage(save.error)}</Alert>}
        <TextInput label="Institute name" required value={form.name} onChange={set("name")} maxLength={190} error={errors.name} />
        <TextInput label="Contact name" value={form.contact_name} onChange={set("contact_name")} maxLength={190} error={errors.contact_name} />
        <TextInput label="Phone" value={form.phone} onChange={set("phone")} maxLength={32} error={errors.phone} />
      </div>
    </Modal>
  );
}

type Pending = { title: string; message: string; confirm: string; danger: boolean; run: () => void };

export function AdminInstitutePage() {
  const { id = "" } = useParams();
  const toast = useToast();
  const navigate = useNavigate();
  const setSession = useSetSession();
  const client = useQueryClient();
  const [confirm, setConfirm] = useState<Pending | null>(null);
  const [resetting, setResetting] = useState(false);
  const key = ["admin", "institute", id];
  const { data, isLoading, error } = useQuery({ queryKey: key, queryFn: () => admin.institute(id) });
  const status = useMutation({
    mutationFn: (s: string) => admin.setInstituteStatus(id, s),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: key });
      void client.invalidateQueries({ queryKey: ["admin", "institutes"] });
      setConfirm(null);
      toast.success("Status updated.");
    },
    onError: (e) => { setConfirm(null); toast.error(errorMessage(e)); },
  });
  const loginAs = useMutation({
    mutationFn: () => admin.instituteLoginAs(id),
    onSuccess: (r) => {
      forgetUser(client);
      setSession(r.user);
      navigate(homeFor(r.user), { replace: true });
    },
    onError: (e) => toast.error(errorMessage(e)),
  });

  if (isLoading) return <Spinner />;
  if (error || !data) return <Alert kind="error">{errorMessage(error)}</Alert>;

  const inst = data.institute;
  const seats = data.seats.counts;
  const settings = settingsOf(inst);
  const loginName = [data.login?.first_name, data.login?.last_name].filter(Boolean).join(" ");
  const assignedPct = seats.total ? Math.round((seats.assigned / seats.total) * 100) : 0;
  const byStatus = data.reports.assignments_by_status;

  return (
    <>
      <Link to="/admin/institutes" className="mb-4 inline-flex items-center gap-1 text-sm text-slate-500 hover:text-slate-700">
        <ArrowLeft className="h-4 w-4" aria-hidden /> All institutes
      </Link>
      <PageHeader
        title={inst.name}
        description={[
          inst.email,
          INSTITUTE_TYPE_LABELS[inst.institute_type] ?? inst.institute_type,
          SOURCE_LABELS[inst.source] ?? inst.source,
          `joined ${formatDate(inst.created_at)}`,
        ].filter(Boolean).join(" · ")}
        actions={statusBadge(inst.status)}
      />

      <div className="mb-6 flex flex-wrap gap-2">
        {inst.status !== "active" && (
          <Button onClick={() => status.mutate("active")} loading={status.isPending}>
            {inst.status === "pending" ? "Approve" : "Reactivate"}
          </Button>
        )}
        {inst.status === "active" && (
          <Button variant="secondary" onClick={() => setConfirm({
            title: "Suspend this campus?",
            danger: true,
            confirm: "Suspend",
            message: `Open invitations and active student seats for ${inst.name} are closed. They cannot invite students until you reactivate the campus.`,
            run: () => status.mutate("suspended"),
          })}>Suspend</Button>
        )}
        {inst.status !== "closed" && (
          <Button variant="ghost" onClick={() => setConfirm({
            title: "Close this campus?",
            danger: true,
            confirm: "Close campus",
            message: `${inst.name} is marked closed and open assignments are cancelled. Use this only if the campus should no longer operate.`,
            run: () => status.mutate("closed"),
          })}>Close</Button>
        )}
        <Button variant="secondary" onClick={() => loginAs.mutate()} loading={loginAs.isPending}>Log in as</Button>
        <Button variant="ghost" onClick={() => setResetting(true)}>Reset password</Button>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Stat icon={<Users className="h-4 w-4" />} label="Active students" value={data.dashboard.students}
              sub={`${data.dashboard.pending_invites} open invitation${data.dashboard.pending_invites === 1 ? "" : "s"}`} />
        <Stat icon={<Layers className="h-4 w-4" />} label="Seats available" value={`${seats.available} / ${seats.total}`}
              sub={seats.total ? `${assignedPct}% assigned` : "No campus plan yet"} />
        <Stat icon={<GraduationCap className="h-4 w-4" />} label="Campus plan"
              value={data.subscription?.plan.name ?? "None"}
              sub={data.subscription
                ? `${providerLabel(data.subscription.provider)} · ${data.subscription.cancel_at_period_end ? "ends" : "renews"} ${formatDate(data.subscription.current_period_end)}`
                : "Buy seats from the campus portal"} />
        <Stat icon={<Mail className="h-4 w-4" />} label="Login"
              value={data.login ? (data.login.is_active ? "Active" : "Disabled") : "Missing"}
              sub={data.login?.last_login_at ? `Last signed in ${formatRelative(data.login.last_login_at)}` : "Never signed in"} />
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-3">
        <Card title="Campus">
          <dl className="space-y-3 text-sm">
            <Row label="Status">{statusBadge(inst.status)}</Row>
            <Row label="Contact">{inst.contact_name || "—"}</Row>
            <Row label="Phone">{inst.phone || "—"}</Row>
            <Row label="GSTIN">{inst.gstin || "—"}</Row>
            <Row label="PAN">{inst.pan_number || "—"}</Row>
          </dl>
        </Card>

        <Card title="Subscription">
          {data.subscription ? (
            <>
              <div className="flex items-center justify-between gap-2">
                <p className="text-xl font-semibold">{data.subscription.plan.name}</p>
                {data.subscription.provider === "admin"
                  ? <Badge tone="brand">Complimentary</Badge>
                  : <SubBadge sub={data.subscription} />}
              </div>
              <p className="mt-1 text-sm text-slate-600">
                {formatMoney(data.subscription.plan.price_cents, data.subscription.plan.currency)} / {data.subscription.plan.interval}
                {" · "}{providerLabel(data.subscription.provider)}
              </p>
              <p className="mt-2 text-sm text-slate-600">
                {data.subscription.cancel_at_period_end
                  ? `Ends ${formatDate(data.subscription.current_period_end)}.`
                  : `Renews ${formatDate(data.subscription.current_period_end)}.`}
              </p>
            </>
          ) : (
            <p className="text-sm text-slate-500">No campus plan. Seats are created when the institute buys a campus package.</p>
          )}
        </Card>

        <Card title="Seat inventory">
          {seats.total === 0 ? (
            <p className="text-sm text-slate-500">No seats purchased.</p>
          ) : (
            <>
              <ProgressBar label="Assigned" value={seats.assigned} max={seats.total} />
              <div className="mt-4 flex flex-wrap gap-1">
                {Object.entries(seats.by_status).filter(([, n]) => n > 0).map(([s, n]) => (
                  <Badge key={s} tone={SEAT_TONES[s] ?? "slate"}>{SEAT_LABELS[s] ?? s}: {n}</Badge>
                ))}
              </div>
            </>
          )}
        </Card>
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <Card title="Login account">
          {!data.login ? <p className="text-sm text-slate-500">No campus admin user is linked.</p> : (
            <dl className="space-y-3 text-sm">
              <Row label="Email"><UserLink id={data.login.id} email={data.login.email} /></Row>
              {loginName && <Row label="Name">{loginName}</Row>}
              <Row label="Verified">{data.login.is_verified ? "Yes" : "No"}</Row>
              <Row label="Can sign in">{data.login.is_active ? "Yes" : "No"}</Row>
              <Row label="Last sign-in">
                {data.login.last_login_at
                  ? `${formatRelative(data.login.last_login_at)} · ${formatDateTime(data.login.last_login_at)}`
                  : "Never"}
              </Row>
            </dl>
          )}
        </Card>

        <Card title="Partner">
          {!data.partner ? (
            <p className="text-sm text-slate-500">Not attributed to a partner.</p>
          ) : (
            <dl className="space-y-3 text-sm">
              <Row label="Organisation">
                <Link to={`/admin/partners/${data.partner.id}`} className="font-medium text-brand-700 hover:underline">
                  {data.partner.organization}
                </Link>
              </Row>
              <Row label="Code">{data.partner.referral_code}</Row>
              <Row label="Status"><Badge>{data.partner.status}</Badge></Row>
              <Row label="KYC"><Badge>{data.partner.kyc_status}</Badge></Row>
            </dl>
          )}
        </Card>

        <Card title="Invite settings">
          <dl className="space-y-3 text-sm">
            <Row label="Timezone">{settings.timezone}</Row>
            <Row label="Invite expiry">{settings.invite_expiry_days} days</Row>
            <Row label="Low-seat alert">{settings.low_seat_threshold} remaining</Row>
            <Row label="Email on invite">{settings.notify_invites ? "On" : "Off"}</Row>
            <Row label="Email on accept">{settings.notify_acceptances ? "On" : "Off"}</Row>
            {settings.invite_note && <Row label="Invite note">{settings.invite_note}</Row>}
          </dl>
        </Card>

        <Card title="Assignments by status">
          {Object.values(byStatus).every((n) => n === 0) ? (
            <p className="text-sm text-slate-500">No invitations yet.</p>
          ) : (
            <div className="flex flex-wrap gap-1">
              {Object.entries(byStatus).filter(([, n]) => n > 0).map(([s, n]) => (
                <Badge key={s} tone={ASSIGNMENT_TONES[s] ?? "slate"}>{ASSIGNMENT_LABELS[s] ?? s}: {n}</Badge>
              ))}
            </div>
          )}
        </Card>
      </div>

      <div className="mt-6">
        <Card title="Students">
          {data.students.length === 0 ? (
            <p className="text-sm text-slate-500">No students invited yet.</p>
          ) : (
            <Table head={["Student", "Status", "Invited", "Accepted", "Released"]}>
              {data.students.map((a) => (
                <tr key={a.id} className="hover:bg-slate-50/80">
                  <Td>
                    {a.student_user_id
                      ? <UserLink id={a.student_user_id} email={a.candidate_email} />
                      : <span className="font-medium text-slate-900">{a.candidate_email}</span>}
                    {a.note && <p className="text-xs text-slate-500">{a.note}</p>}
                  </Td>
                  <Td>{assignmentBadge(a.status)}</Td>
                  <Td className="whitespace-nowrap text-slate-600">{formatDate(a.created_at)}</Td>
                  <Td className="whitespace-nowrap text-slate-600">{formatDate(a.accepted_at)}</Td>
                  <Td className="whitespace-nowrap text-slate-600">{formatDate(a.released_at)}</Td>
                </tr>
              ))}
            </Table>
          )}
        </Card>
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <Card title="Open invitations">
          {data.invitations.length === 0 ? <p className="text-sm text-slate-500">No open invitations.</p> : (
            <ul className="divide-y divide-slate-100 text-sm">
              {data.invitations.map((a) => (
                <li key={a.id} className="flex items-center justify-between gap-3 py-2">
                  <span className="font-medium text-slate-800">{a.candidate_email}</span>
                  <span className="text-slate-500">{formatDate(a.created_at)}</span>
                  {assignmentBadge(a.status)}
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card title="Staff">
          {data.members.length === 0 ? <p className="text-sm text-slate-500">No campus staff linked.</p> : (
            <ul className="divide-y divide-slate-100 text-sm">
              {data.members.map((m) => (
                <li key={m.id} className="flex items-center justify-between gap-3 py-2">
                  <span>
                    <UserLink id={m.user_id} email={m.email || "Unknown"} />
                    {m.name && <span className="ml-2 text-slate-500">{m.name}</span>}
                  </span>
                  <Badge>{m.role}</Badge>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card title="Subscription history">
          {data.subscriptions.length === 0 ? <p className="text-sm text-slate-500">Never subscribed.</p> : (
            <ul className="divide-y divide-slate-100 text-sm">
              {data.subscriptions.map((s) => (
                <li key={s.id} className="flex items-center justify-between gap-3 py-2">
                  <span className="font-medium text-slate-800">{s.plan.name}</span>
                  <span className="text-slate-500">{providerLabel(s.provider)} · {formatDate(s.created_at)} to {formatDate(s.current_period_end)}</span>
                  <SubBadge sub={s} />
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card title="Payments">
          {data.payments.length === 0 ? <p className="text-sm text-slate-500">No campus payments.</p> : (
            <ul className="divide-y divide-slate-100 text-sm">
              {data.payments.map((p) => (
                <li key={p.id} className="flex items-center justify-between gap-3 py-2">
                  <span className="text-slate-600">{formatDate(p.paid_at)}</span>
                  <span className="font-medium">{formatMoney(p.amount_cents, p.currency)}</span>
                  <Badge tone={p.status === "captured" ? "green" : p.status === "failed" ? "red" : "slate"}>{p.status}</Badge>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card title="Seat list">
          {data.seats.items.length === 0 ? <p className="text-sm text-slate-500">No seats issued.</p> : (
            <ul className="divide-y divide-slate-100 text-sm">
              {data.seats.items.map((s) => (
                <li key={s.id} className="flex items-center justify-between gap-3 py-2">
                  <span className="font-mono text-xs text-slate-600">{s.id.slice(0, 8)}</span>
                  <span className="text-slate-500">{formatDate(s.created_at)}</span>
                  <Badge tone={SEAT_TONES[s.status] ?? "slate"}>{SEAT_LABELS[s.status] ?? s.status}</Badge>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card title="Partner commissions">
          {data.commissions.length === 0 ? <p className="text-sm text-slate-500">No commissions on this campus.</p> : (
            <ul className="divide-y divide-slate-100 text-sm">
              {data.commissions.map((c) => (
                <li key={c.id} className="flex items-center justify-between gap-3 py-2">
                  <span className="text-slate-600">{c.note || formatDate(c.created_at)}</span>
                  <span className="font-medium">{formatMoney(c.amount_cents, c.currency)}</span>
                  <Badge>{c.status}</Badge>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>

      {confirm && (
        <ConfirmDialog open title={confirm.title} message={confirm.message} confirmLabel={confirm.confirm}
                       danger={confirm.danger} loading={status.isPending} onConfirm={confirm.run}
                       onClose={() => setConfirm(null)} />
      )}
      {resetting && (
        <ResetInstitutePasswordDialog instituteId={id} email={data.login?.email ?? inst.email}
                                      onClose={() => setResetting(false)} />
      )}
    </>
  );
}

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex justify-between gap-4">
      <dt className="text-slate-500">{label}</dt>
      <dd className="text-right font-medium text-slate-900">{children}</dd>
    </div>
  );
}

function ResetInstitutePasswordDialog({ instituteId, email, onClose }: {
  instituteId: string; email: string; onClose: () => void;
}) {
  const toast = useToast();
  const [password, setPassword] = useState("");
  const save = useMutation({
    mutationFn: () => admin.institutePassword(instituteId, password),
    onSuccess: () => { toast.success("Password updated."); onClose(); },
    onError: (e) => toast.error(errorMessage(e)),
  });
  return (
    <Modal open onClose={onClose} title="Reset campus password" footer={
      <>
        <Button variant="secondary" onClick={onClose}>Cancel</Button>
        <Button disabled={password.length < 10} loading={save.isPending} onClick={() => save.mutate()}>Save password</Button>
      </>
    }>
      <div className="space-y-4">
        <p className="text-sm text-slate-600">
          Sets a new password for <span className="font-medium text-slate-900">{email}</span>. Share it with the campus contact.
        </p>
        <TextInput label="New password" type="password" value={password} onChange={setPassword}
                   hint="At least 10 characters." />
      </div>
    </Modal>
  );
}

const PARTNER_STATUS_FILTERS = [
  { value: "pending", label: "Pending" },
  { value: "approved", label: "Approved" },
  { value: "active", label: "Active" },
  { value: "suspended", label: "Suspended" },
  { value: "closed", label: "Closed" },
] as const;

const PARTNER_KYC_OPTIONS = [
  { value: "pending", label: "Pending" },
  { value: "verified", label: "Verified" },
  { value: "rejected", label: "Rejected" },
  { value: "not_required", label: "Not required" },
] as const;

type PartnerListStatus = (typeof PARTNER_STATUS_FILTERS)[number]["value"] | "";

function partnerEnabled(status: string): boolean {
  return status === "approved" || status === "active";
}

function PartnerStatusFilters({ value, onChange }: { value: PartnerListStatus; onChange: (v: PartnerListStatus) => void }) {
  return (
    <div>
      <span className="mb-2 block text-sm font-medium text-slate-700">Status</span>
      <div className="flex flex-wrap gap-2">
        <button type="button" aria-pressed={value === ""} onClick={() => onChange("")}
                className={cx("rounded-full px-3 py-1 text-sm ring-1 ring-inset transition-colors",
                  value === "" ? "bg-slate-900 text-white ring-slate-900" : "bg-white text-slate-700 ring-slate-300 hover:bg-slate-50")}>
          All
        </button>
        {PARTNER_STATUS_FILTERS.map((f) => (
          <button key={f.value} type="button" aria-pressed={value === f.value}
                  onClick={() => onChange(value === f.value ? "" : f.value)}
                  className={cx("rounded-full px-3 py-1 text-sm ring-1 ring-inset transition-colors",
                    value === f.value ? "bg-brand-600 text-white ring-brand-600" : "bg-white text-slate-700 ring-slate-300 hover:bg-slate-50")}>
            {f.label}
          </button>
        ))}
      </div>
    </div>
  );
}

export function AdminPartnersPage() {
  const toast = useToast();
  const client = useQueryClient();
  const [q, setQ] = useState("");
  const [status, setStatus] = useState<PartnerListStatus>("");
  const [page, setPage] = useState(1);
  const [adding, setAdding] = useState(false);
  const [editing, setEditing] = useState<Partner | null>(null);
  const [confirm, setConfirm] = useState<Pending | null>(null);
  const search = useDebounced(q.trim());
  const { data, isLoading, isFetching, error } = useQuery({
    queryKey: ["admin", "partners", search, status, page],
    queryFn: () => admin.partners({ q: search || undefined, status: status || undefined, page, page_size: 20 }),
    placeholderData: keepPreviousData,
  });
  const resetPage = () => setPage(1);
  const hasFilters = Boolean(search || status);
  const statusLabel = PARTNER_STATUS_FILTERS.find((f) => f.value === status)?.label;
  const setStatusMut = useMutation({
    mutationFn: ({ id, next }: { id: string; next: string }) => admin.setPartnerStatus(id, next),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ["admin", "partners"] });
      setConfirm(null);
      toast.success("Status updated.");
    },
    onError: (e) => { setConfirm(null); toast.error(errorMessage(e)); },
  });

  return (
    <>
      <PageHeader
        title="Partners"
        description="Referral partners who enroll campuses and earn commission on seat payments."
        actions={<Button onClick={() => setAdding(true)}>Add partner</Button>}
      />
      <Card>
        <div className="relative max-w-xl">
          <TextInput label="Search" value={q} onChange={(v) => { setQ(v); resetPage(); }}
                     placeholder="Organisation or referral code" maxLength={200} className="pl-9" />
          <Search className="pointer-events-none absolute bottom-2.5 left-3 h-4 w-4 text-slate-400" aria-hidden />
        </div>
        <div className="mt-6">
          <PartnerStatusFilters value={status} onChange={(v) => { setStatus(v); resetPage(); }} />
        </div>
        {hasFilters && (
          <p className="mt-3 text-xs text-slate-500">
            Filtering{search ? ` for “${search}”` : ""}{status ? ` · ${statusLabel}` : ""}.{" "}
            <button type="button" className="font-medium text-brand-700 hover:underline"
                    onClick={() => { setQ(""); setStatus(""); resetPage(); }}>Clear filters</button>
          </p>
        )}
      </Card>

      <div className="mt-6">
        {isLoading ? <Spinner /> : error || !data ? <Alert kind="error">{errorMessage(error)}</Alert> : data.total === 0 ? (
          <Card>
            <EmptyState icon={<Building2 className="h-10 w-10" />} title="No partners found">
              {hasFilters
                ? "Try a different organisation, code, or status."
                : "Add a partner here, or wait for one to apply from the public register page."}
            </EmptyState>
          </Card>
        ) : (
          <Card className={cx(isFetching && "opacity-70 transition-opacity")}>
            <p className="mb-4 text-sm text-slate-600">
              Showing <span className="font-medium text-slate-900">{data.items.length}</span> of{" "}
              <span className="font-medium text-slate-900">{data.total.toLocaleString()}</span> partners
            </p>
            <Table head={["Partner", "KYC", "Rate", "Joined", "Status", "Actions"]} dim={isFetching}>
              {data.items.map((p) => (
                <tr key={p.id} className="hover:bg-slate-50/80">
                  <Td>
                    <p className="font-medium text-slate-900">{p.organization}</p>
                    <p className="text-sm text-slate-500">{p.contact_name || p.referral_code}</p>
                    <p className="text-xs text-slate-400">Code {p.referral_code}</p>
                  </Td>
                  <Td>{kycBadge(p.kyc_status)}</Td>
                  <Td className="tabular-nums text-slate-700">{commissionSummary(p)}</Td>
                  <Td className="whitespace-nowrap text-slate-600">{formatDate(p.created_at)}</Td>
                  <Td>{partnerBadge(p.status)}</Td>
                  <Td className="whitespace-nowrap">
                    <div className="flex justify-end gap-2">
                      <ButtonLink to={`/admin/partners/${p.id}`} size="sm" variant="secondary">View</ButtonLink>
                      <Button size="sm" variant="secondary" onClick={() => setEditing(p)}>Edit</Button>
                      {partnerEnabled(p.status) ? (
                        <Button size="sm" variant="ghost" onClick={() => setConfirm({
                          title: "Disable this partner?",
                          danger: true,
                          confirm: "Disable",
                          message: `${p.organization} cannot enroll campuses until you enable them again. Existing referred institutes stay in place.`,
                          run: () => setStatusMut.mutate({ id: p.id, next: "suspended" }),
                        })}>Disable</Button>
                      ) : (
                        <Button size="sm" loading={setStatusMut.isPending}
                                onClick={() => setStatusMut.mutate({ id: p.id, next: "approved" })}>Enable</Button>
                      )}
                    </div>
                  </Td>
                </tr>
              ))}
            </Table>
            <Pagination page={data.page} pageSize={data.page_size} total={data.total} onPage={setPage} />
          </Card>
        )}
      </div>
      {adding && <AddPartnerDialog onClose={() => setAdding(false)} />}
      {editing && <EditPartnerDialog partner={editing} onClose={() => setEditing(null)} />}
      {confirm && (
        <ConfirmDialog open title={confirm.title} message={confirm.message} confirmLabel={confirm.confirm}
                       danger={confirm.danger} loading={setStatusMut.isPending} onConfirm={confirm.run}
                       onClose={() => setConfirm(null)} />
      )}
    </>
  );
}

function AddPartnerDialog({ onClose }: { onClose: () => void }) {
  const client = useQueryClient();
  const toast = useToast();
  const navigate = useNavigate();
  const [form, setForm] = useState({
    organization: "", email: "", password: "", contact_name: "", phone: "", approve: true,
    commission_mode: "percent_payment" as CommissionMode, commission_percent: "20", commission_inr: "",
  });
  const set = (key: keyof typeof form) => (value: string | boolean) => setForm((f) => ({ ...f, [key]: value }));
  const commissionBps = percentInputToBps(form.commission_percent);
  const commissionFlatCents = inrInputToCents(form.commission_inr);
  const isPercent = form.commission_mode === "percent_payment";
  const save = useMutation({
    mutationFn: () => admin.createPartner({
      organization: form.organization.trim(),
      email: form.email.trim(),
      password: form.password,
      contact_name: form.contact_name.trim(),
      phone: form.phone.trim(),
      approve: form.approve,
      commission_mode: form.commission_mode,
      commission_bps: isPercent ? (commissionBps ?? 2000) : 0,
      commission_flat_cents: isPercent ? 0 : commissionFlatCents!,
    }),
    onSuccess: (partner) => {
      toast.success(`${partner.organization} added.`);
      void client.invalidateQueries({ queryKey: ["admin", "partners"] });
      onClose();
      navigate(`/admin/partners/${partner.id}`);
    },
  });
  const errors = fieldErrors(save.error);
  const invalid = !form.organization.trim() || !form.email.trim() || form.password.length < 10
    || (isPercent ? commissionBps === null : commissionFlatCents === null);

  return (
    <Modal open onClose={onClose} title="Add partner" footer={
      <>
        <Button variant="secondary" onClick={onClose}>Cancel</Button>
        <Button disabled={invalid} loading={save.isPending} onClick={() => save.mutate()}>Add partner</Button>
      </>
    }>
      <div className="space-y-4">
        {save.error && !Object.keys(errors).length && <Alert kind="error">{errorMessage(save.error)}</Alert>}
        <TextInput label="Organisation" required value={form.organization} onChange={set("organization")} maxLength={190} error={errors.organization} />
        <TextInput label="Contact name" value={form.contact_name} onChange={set("contact_name")} maxLength={190} error={errors.contact_name} />
        <TextInput label="Email" type="email" required value={form.email} onChange={set("email")} error={errors.email}
                   hint="This is the login for the partner." />
        <TextInput label="Phone" value={form.phone} onChange={set("phone")} maxLength={32} error={errors.phone} />
        <TextInput label="Password" type="password" required value={form.password} onChange={set("password")}
                   error={errors.password} hint="At least 10 characters. Share this with the partner." />
        <PartnerCommissionFields
          mode={form.commission_mode}
          onModeChange={(v) => setForm((f) => ({ ...f, commission_mode: v }))}
          commissionPercent={form.commission_percent}
          onCommissionPercent={set("commission_percent")}
          commissionInr={form.commission_inr}
          onCommissionInr={set("commission_inr")}
          percentError={isPercent && commissionBps === null ? "Enter a percentage from 0 to 100." : undefined}
          inrError={!isPercent && commissionFlatCents === null ? "Enter a positive amount in INR." : undefined}
        />
        <Toggle label="Approve now" checked={form.approve} onChange={set("approve")}
                hint="Approved partners can enroll institutes. KYC is marked as not required." />
      </div>
    </Modal>
  );
}

function EditPartnerDialog({ partner, onClose, loginEmail }: {
  partner: Partner;
  onClose: () => void;
  loginEmail?: string | null;
}) {
  const client = useQueryClient();
  const toast = useToast();
  const [form, setForm] = useState({
    organization: partner.organization,
    contact_name: partner.contact_name,
    phone: partner.phone,
    commission_mode: (partner.commission_mode || "percent_payment") as CommissionMode,
    commission_percent: bpsToPercentInput(partner.commission_bps),
    commission_inr: centsToInrInput(partner.commission_flat_cents),
    status: partner.status,
    kyc_status: partner.kyc_status,
    gstin: partner.gstin,
    pan_number: partner.pan_number,
    payout_account: partner.payout_account,
    payout_ifsc: partner.payout_ifsc,
    email: typeof loginEmail === "string" ? loginEmail : "",
  });
  const set = (key: keyof typeof form) => (value: string) => setForm((f) => ({ ...f, [key]: value }));
  const commissionBps = percentInputToBps(form.commission_percent);
  const commissionFlatCents = inrInputToCents(form.commission_inr);
  const isPercent = form.commission_mode === "percent_payment";
  const canEditLoginEmail = typeof loginEmail === "string";
  const save = useMutation({
    mutationFn: () => admin.updatePartner(partner.id, {
      organization: form.organization.trim(),
      contact_name: form.contact_name.trim(),
      phone: form.phone.trim(),
      commission_mode: form.commission_mode,
      commission_bps: isPercent ? commissionBps! : 0,
      commission_flat_cents: isPercent ? 0 : commissionFlatCents!,
      status: form.status,
      kyc_status: form.kyc_status,
      gstin: form.gstin.trim(),
      pan_number: form.pan_number.trim(),
      payout_account: form.payout_account.trim(),
      payout_ifsc: form.payout_ifsc.trim(),
      email: canEditLoginEmail ? form.email.trim() : undefined,
    }),
    onSuccess: (updated) => {
      toast.success(`${updated.organization} updated.`);
      void client.invalidateQueries({ queryKey: ["admin", "partners"] });
      void client.invalidateQueries({ queryKey: ["admin", "partner", partner.id] });
      onClose();
    },
  });
  const errors = fieldErrors(save.error);
  const invalid = !form.organization.trim()
    || (isPercent ? commissionBps === null : commissionFlatCents === null)
    || (canEditLoginEmail && !form.email.trim());

  return (
    <Modal open onClose={onClose} title="Edit partner" wide footer={
      <>
        <Button variant="secondary" onClick={onClose}>Cancel</Button>
        <Button disabled={invalid} loading={save.isPending} onClick={() => save.mutate()}>Save changes</Button>
      </>
    }>
      <div className="space-y-6">
        {save.error && !Object.keys(errors).length && <Alert kind="error">{errorMessage(save.error)}</Alert>}
        <section className="space-y-4">
          <h3 className="text-sm font-semibold text-slate-900">Organisation</h3>
          <TextInput label="Organisation" required value={form.organization} onChange={set("organization")} maxLength={190} error={errors.organization} />
          <TextInput label="Contact name" value={form.contact_name} onChange={set("contact_name")} maxLength={190} error={errors.contact_name} />
          <TextInput label="Phone" value={form.phone} onChange={set("phone")} maxLength={32} error={errors.phone} />
          <TextInput label="Referral code" value={partner.referral_code} readOnly
                     hint="System-assigned. Share the partner detail link for the full referral URL." />
        </section>
        <section className="space-y-4">
          <h3 className="text-sm font-semibold text-slate-900">Account &amp; status</h3>
          {canEditLoginEmail ? (
            <TextInput label="Login email" type="email" required value={form.email} onChange={set("email")} error={errors.email}
                       hint="Partner sign-in address." />
          ) : loginEmail === null ? (
            <p className="text-sm text-slate-500">No login account is linked to this partner.</p>
          ) : (
            <p className="text-sm text-slate-500">Open the partner detail page to edit the login email.</p>
          )}
          <div className="grid gap-4 sm:grid-cols-2">
            <Select label="Partner status" value={form.status} onChange={set("status")}
                    options={PARTNER_STATUS_FILTERS.map((o) => ({ value: o.value, label: o.label }))} />
            <Select label="KYC status" value={form.kyc_status} onChange={set("kyc_status")}
                    options={PARTNER_KYC_OPTIONS.map((o) => ({ value: o.value, label: o.label }))} />
          </div>
        </section>
        <section className="space-y-4">
          <h3 className="text-sm font-semibold text-slate-900">Commission</h3>
          <PartnerCommissionFields
            mode={form.commission_mode}
            onModeChange={(v) => setForm((f) => ({ ...f, commission_mode: v }))}
            commissionPercent={form.commission_percent}
            onCommissionPercent={set("commission_percent")}
            commissionInr={form.commission_inr}
            onCommissionInr={set("commission_inr")}
            percentError={isPercent && commissionBps === null ? "Enter a percentage from 0 to 100." : undefined}
            inrError={!isPercent && commissionFlatCents === null ? "Enter a positive amount in INR." : undefined}
          />
        </section>
        <section className="space-y-4">
          <h3 className="text-sm font-semibold text-slate-900">Tax &amp; payout</h3>
          <div className="grid gap-4 sm:grid-cols-2">
            <TextInput label="GSTIN" value={form.gstin} onChange={set("gstin")} maxLength={15} error={errors.gstin} />
            <TextInput label="PAN" value={form.pan_number} onChange={set("pan_number")} maxLength={10} error={errors.pan_number} />
          </div>
          <TextInput label="Payout account" value={form.payout_account} onChange={set("payout_account")} maxLength={255} error={errors.payout_account} />
          <TextInput label="Payout IFSC" value={form.payout_ifsc} onChange={set("payout_ifsc")} maxLength={20} error={errors.payout_ifsc} />
        </section>
      </div>
    </Modal>
  );
}

const PARTNER_STATUS_TONES: Record<string, "green" | "amber" | "blue" | "red" | "slate"> = {
  pending: "amber", approved: "blue", active: "green", suspended: "red", closed: "slate",
};

const KYC_TONES: Record<string, "green" | "amber" | "red" | "slate"> = {
  pending: "amber", verified: "green", rejected: "red", not_required: "slate",
};

const KYC_LABELS: Record<string, string> = {
  pending: "Pending", verified: "Verified", rejected: "Rejected", not_required: "Not required",
};

const COMMISSION_TONES: Record<string, "green" | "amber" | "slate"> = {
  accrued: "amber", approved: "green", void: "slate",
};

const PAYOUT_TONES: Record<string, "green" | "amber" | "blue" | "red"> = {
  requested: "amber", approved: "blue", paid: "green", rejected: "red",
};

function partnerBadge(status: string) {
  return <Badge tone={PARTNER_STATUS_TONES[status] ?? "slate"}>{status}</Badge>;
}

function kycBadge(status: string) {
  return <Badge tone={KYC_TONES[status] ?? "slate"}>{KYC_LABELS[status] ?? status}</Badge>;
}

const COMMISSION_MODES = [
  { value: "percent_payment", label: "Percent of campus payment" },
  { value: "flat_payment", label: "Fixed INR per payment" },
  { value: "flat_seat", label: "Fixed INR per seat purchased" },
  { value: "flat_candidate", label: "Fixed INR per active candidate" },
] as const;

type CommissionMode = (typeof COMMISSION_MODES)[number]["value"];

function rateLabel(bps: number): string {
  return `${(bps / 100).toFixed(bps % 100 === 0 ? 0 : 1)}%`;
}

function commissionSummary(p: Pick<Partner, "commission_mode" | "commission_bps" | "commission_flat_cents">): string {
  switch (p.commission_mode) {
    case "flat_payment":
      return `${formatMoney(p.commission_flat_cents, "INR")} / payment`;
    case "flat_seat":
      return `${formatMoney(p.commission_flat_cents, "INR")} / seat`;
    case "flat_candidate":
      return `${formatMoney(p.commission_flat_cents, "INR")} / candidate`;
    default:
      return rateLabel(p.commission_bps ?? 0);
  }
}

function bpsToPercentInput(bps: number): string {
  const p = bps / 100;
  return Number.isInteger(p) ? String(p) : p.toFixed(2).replace(/\.?0+$/, "");
}

function percentInputToBps(raw: string): number | null {
  const n = parseFloat(raw.trim());
  if (!Number.isFinite(n) || n < 0 || n > 100) return null;
  return Math.round(n * 100);
}

function centsToInrInput(cents: number): string {
  if (!cents) return "";
  const rupees = cents / 100;
  return Number.isInteger(rupees) ? String(rupees) : rupees.toFixed(2).replace(/\.?0+$/, "");
}

function inrInputToCents(raw: string): number | null {
  const n = parseFloat(raw.trim());
  if (!Number.isFinite(n) || n <= 0) return null;
  return Math.round(n * 100);
}

function PartnerCommissionFields({ mode, onModeChange, commissionPercent, onCommissionPercent, commissionInr, onCommissionInr,
  percentError, inrError }: {
  mode: CommissionMode;
  onModeChange: (value: CommissionMode) => void;
  commissionPercent: string;
  onCommissionPercent: (value: string) => void;
  commissionInr: string;
  onCommissionInr: (value: string) => void;
  percentError?: string;
  inrError?: string;
}) {
  const isPercent = mode === "percent_payment";
  const flatHint = mode === "flat_payment"
    ? "Paid once per successful referred campus subscription payment."
    : mode === "flat_seat"
      ? "Multiplied by seats in the campus plan for each payment."
      : "Paid when a referred campus student accepts their seat and becomes active.";
  return (
    <div className="space-y-4">
      <Select label="Commission basis" value={mode} onChange={(v) => onModeChange(v as CommissionMode)}
              options={COMMISSION_MODES.map((o) => ({ value: o.value, label: o.label }))}
              hint="Choose one basis. Changes apply to new accruals only." />
      {isPercent ? (
        <TextInput label="Commission rate (%)" required value={commissionPercent} onChange={onCommissionPercent}
                   error={percentError} hint="Share of referred campus payment amount (0–100)." />
      ) : (
        <TextInput label="Commission amount (INR)" required value={commissionInr} onChange={onCommissionInr}
                   error={inrError} hint={flatHint} />
      )}
    </div>
  );
}

export function AdminPartnerPage() {
  const { id = "" } = useParams();
  const toast = useToast();
  const navigate = useNavigate();
  const setSession = useSetSession();
  const client = useQueryClient();
  const [confirm, setConfirm] = useState<Pending | null>(null);
  const [resetting, setResetting] = useState(false);
  const [editing, setEditing] = useState(false);
  const key = ["admin", "partner", id];
  const { data, isLoading, error } = useQuery({ queryKey: key, queryFn: () => admin.partner(id) });

  const refresh = (message: string) => {
    void client.invalidateQueries({ queryKey: key });
    void client.invalidateQueries({ queryKey: ["admin", "partners"] });
    setConfirm(null);
    toast.success(message);
  };
  const status = useMutation({
    mutationFn: (s: string) => admin.setPartnerStatus(id, s),
    onSuccess: () => refresh("Status updated."),
    onError: (e) => { setConfirm(null); toast.error(errorMessage(e)); },
  });
  const kyc = useMutation({
    mutationFn: (s: string) => admin.setPartnerKyc(id, s),
    onSuccess: () => refresh("KYC updated."),
    onError: (e) => toast.error(errorMessage(e)),
  });
  const loginAs = useMutation({
    mutationFn: () => admin.partnerLoginAs(id),
    onSuccess: (r) => {
      forgetUser(client);
      setSession(r.user);
      navigate(homeFor(r.user), { replace: true });
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  const commission = useMutation({
    mutationFn: ({ cid, next }: { cid: string; next: string }) => admin.setCommissionStatus(cid, next),
    onSuccess: () => refresh("Commission updated."),
    onError: (e) => toast.error(errorMessage(e)),
  });
  const payout = useMutation({
    mutationFn: ({ pid, next }: { pid: string; next: string }) => admin.setPayoutStatus(pid, next),
    onSuccess: () => refresh("Payout updated."),
    onError: (e) => toast.error(errorMessage(e)),
  });

  if (isLoading) return <Spinner />;
  if (error || !data) return <Alert kind="error">{errorMessage(error)}</Alert>;

  const p = data.partner;
  const loginName = [data.login?.first_name, data.login?.last_name].filter(Boolean).join(" ");
  const origin = typeof window !== "undefined" ? window.location.origin : "";

  return (
    <>
      <Link to="/admin/partners" className="mb-4 inline-flex items-center gap-1 text-sm text-slate-500 hover:text-slate-700">
        <ArrowLeft className="h-4 w-4" aria-hidden /> All partners
      </Link>
      <PageHeader
        title={p.organization}
        description={[p.contact_name, `code ${p.referral_code}`, `joined ${formatDate(p.created_at)}`].filter(Boolean).join(" · ")}
        actions={
          <span className="flex flex-wrap items-center gap-2">
            {partnerBadge(p.status)}
            {kycBadge(p.kyc_status)}
            <Button size="sm" variant="secondary" onClick={() => setEditing(true)}>Edit partner</Button>
          </span>
        }
      />

      <div className="mb-6 flex flex-wrap gap-2">
        {p.status !== "approved" && p.status !== "active" && (
          <Button onClick={() => status.mutate("approved")} loading={status.isPending}>
            {p.status === "pending" ? "Approve" : "Reapprove"}
          </Button>
        )}
        {p.status === "approved" && (
          <Button variant="secondary" onClick={() => status.mutate("active")} loading={status.isPending}>Mark active</Button>
        )}
        {(p.status === "approved" || p.status === "active") && (
          <Button variant="secondary" onClick={() => setConfirm({
            title: "Suspend this partner?",
            danger: true,
            confirm: "Suspend",
            message: `${p.organization} cannot enroll campuses until you reapprove them. Existing referred institutes stay in place.`,
            run: () => status.mutate("suspended"),
          })}>Suspend</Button>
        )}
        {p.status !== "closed" && (
          <Button variant="ghost" onClick={() => setConfirm({
            title: "Close this partner?",
            danger: true,
            confirm: "Close partner",
            message: `${p.organization} is marked closed and can no longer use the partner portal.`,
            run: () => status.mutate("closed"),
          })}>Close</Button>
        )}
        {p.kyc_status !== "verified" && (
          <Button variant="secondary" onClick={() => kyc.mutate("verified")} loading={kyc.isPending}>Verify KYC</Button>
        )}
        {p.kyc_status !== "not_required" && (
          <Button variant="ghost" onClick={() => kyc.mutate("not_required")} loading={kyc.isPending}>KYC not required</Button>
        )}
        {p.kyc_status !== "rejected" && p.kyc_status !== "verified" && (
          <Button variant="ghost" onClick={() => kyc.mutate("rejected")} loading={kyc.isPending}>Reject KYC</Button>
        )}
        <Button variant="secondary" onClick={() => loginAs.mutate()} loading={loginAs.isPending}>Log in as</Button>
        <Button variant="ghost" onClick={() => setResetting(true)}>Reset password</Button>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Stat icon={<Building2 className="h-4 w-4" />} label="Campuses" value={data.institutes}
              sub={Object.entries(data.reports.institutes_by_status).filter(([, n]) => n > 0).map(([s, n]) => `${n} ${s}`).join(" · ") || "None referred yet"} />
        <Stat icon={<MousePointerClick className="h-4 w-4" />} label="Referral clicks" value={p.click_count}
              sub={`${data.campaigns.length} campaign${data.campaigns.length === 1 ? "" : "s"}`} />
        <Stat icon={<Wallet className="h-4 w-4" />} label="Available" value={formatMoney(p.wallet.available_cents, "INR")}
              sub={`${formatMoney(p.wallet.accrued_cents, "INR")} accrued · ${formatMoney(p.wallet.approved_cents, "INR")} approved`} />
        <Stat icon={<Percent className="h-4 w-4" />} label="Commission" value={commissionSummary(p)}
              sub={data.login?.last_login_at ? `Last signed in ${formatRelative(data.login.last_login_at)}` : "Never signed in"} />
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-3">
        <Card title="Organisation">
          <dl className="space-y-3 text-sm">
            <Row label="Status">{partnerBadge(p.status)}</Row>
            <Row label="KYC">{kycBadge(p.kyc_status)}</Row>
            <Row label="Contact">{p.contact_name || "—"}</Row>
            <Row label="Phone">{p.phone || "—"}</Row>
            <Row label="GSTIN">{p.gstin || "—"}</Row>
            <Row label="PAN">{p.pan_number || "—"}</Row>
            <Row label="Commission">{commissionSummary(p)}</Row>
          </dl>
        </Card>

        <Card title="Payout account">
          <dl className="space-y-3 text-sm">
            <Row label="Account">{p.payout_account || "—"}</Row>
            <Row label="IFSC">{p.payout_ifsc || "—"}</Row>
            <Row label="Accrued">{formatMoney(p.wallet.accrued_cents, "INR")}</Row>
            <Row label="Approved">{formatMoney(p.wallet.approved_cents, "INR")}</Row>
            <Row label="Available">{formatMoney(p.wallet.available_cents, "INR")}</Row>
          </dl>
        </Card>

        <Card title="Referral">
          <p className="font-mono text-sm break-all text-slate-800">{origin}{data.referral_path}</p>
          <p className="mt-2 text-sm text-slate-500">Code {p.referral_code} · {p.click_count} clicks</p>
          <div className="mt-4 flex flex-wrap gap-1">
            {Object.entries(data.reports.commissions_by_status).filter(([, n]) => n > 0).map(([s, n]) => (
              <Badge key={s} tone={COMMISSION_TONES[s] ?? "slate"}>{s}: {n}</Badge>
            ))}
            {Object.values(data.reports.commissions_by_status).every((n) => n === 0) && (
              <span className="text-sm text-slate-500">No commissions yet.</span>
            )}
          </div>
        </Card>
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <Card title="Login account">
          {!data.login ? <p className="text-sm text-slate-500">No partner login is linked.</p> : (
            <dl className="space-y-3 text-sm">
              <Row label="Email"><UserLink id={data.login.id} email={data.login.email} /></Row>
              {loginName && <Row label="Name">{loginName}</Row>}
              <Row label="Verified">{data.login.is_verified ? "Yes" : "No"}</Row>
              <Row label="Can sign in">{data.login.is_active ? "Yes" : "No"}</Row>
              <Row label="Last sign-in">
                {data.login.last_login_at
                  ? `${formatRelative(data.login.last_login_at)} · ${formatDateTime(data.login.last_login_at)}`
                  : "Never"}
              </Row>
            </dl>
          )}
        </Card>

        <Card title="KYC documents">
          {p.kyc_documents.length === 0 ? <p className="text-sm text-slate-500">No documents recorded.</p> : (
            <ul className="divide-y divide-slate-100 text-sm">
              {p.kyc_documents.map((d) => (
                <li key={`${d.filename}-${d.uploaded_at}`} className="flex items-center justify-between gap-3 py-2">
                  <span>
                    <span className="font-medium text-slate-800">{d.filename}</span>
                    {d.note && <span className="ml-2 text-slate-500">{d.note}</span>}
                  </span>
                  <span className="text-slate-500">{formatDate(d.uploaded_at)}</span>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>

      <div className="mt-6">
        <Card title="Campuses">
          {data.institute_list.length === 0 ? (
            <p className="text-sm text-slate-500">No institutes referred or enrolled yet.</p>
          ) : (
            <Table head={["Campus", "Status", "Seats", "Source", "Joined"]}>
              {data.institute_list.map((i) => (
                <tr key={i.id} className="hover:bg-slate-50/80">
                  <Td>
                    <Link to={`/admin/institutes/${i.id}`} className="font-medium text-brand-700 hover:underline">{i.name}</Link>
                    <p className="text-xs text-slate-500">{i.email}</p>
                  </Td>
                  <Td>{statusBadge(i.status)}</Td>
                  <Td className="tabular-nums text-slate-600">{i.seats.available} / {i.seats.total}</Td>
                  <Td className="text-slate-600">{SOURCE_LABELS[i.source] ?? i.source}</Td>
                  <Td className="whitespace-nowrap text-slate-600">{formatDate(i.created_at)}</Td>
                </tr>
              ))}
            </Table>
          )}
        </Card>
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <Card title="Commissions">
          {data.commissions.length === 0 ? <p className="text-sm text-slate-500">No commissions yet.</p> : (
            <ul className="divide-y divide-slate-100 text-sm">
              {data.commissions.map((c) => (
                <li key={c.id} className="flex flex-wrap items-center justify-between gap-3 py-2">
                  <span>
                    <span className="font-medium text-slate-800">{formatMoney(c.amount_cents, c.currency)}</span>
                    <span className="ml-2 text-slate-500">
                      {c.institute_id
                        ? <Link to={`/admin/institutes/${c.institute_id}`} className="text-brand-700 hover:underline">{c.institute_name || "Campus"}</Link>
                        : (c.note || "Commission")}
                      {c.institute_name && c.note ? ` · ${c.note}` : ""}
                    </span>
                    <span className="ml-2 text-slate-400">{formatDate(c.created_at)}</span>
                  </span>
                  <span className="flex items-center gap-2">
                    <Badge tone={COMMISSION_TONES[c.status] ?? "slate"}>{c.status}</Badge>
                    {c.status === "accrued" && (
                      <>
                        <Button size="sm" variant="secondary" loading={commission.isPending}
                                onClick={() => commission.mutate({ cid: c.id, next: "approved" })}>Approve</Button>
                        <Button size="sm" variant="ghost" loading={commission.isPending}
                                onClick={() => commission.mutate({ cid: c.id, next: "void" })}>Void</Button>
                      </>
                    )}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card title="Payouts">
          {data.payouts.length === 0 ? <p className="text-sm text-slate-500">No payout requests.</p> : (
            <ul className="divide-y divide-slate-100 text-sm">
              {data.payouts.map((row) => (
                <li key={row.id} className="flex flex-wrap items-center justify-between gap-3 py-2">
                  <span>
                    <span className="font-medium text-slate-800">{formatMoney(row.amount_cents, row.currency)}</span>
                    <span className="ml-2 text-slate-500">{formatDate(row.created_at)}</span>
                    {row.note && <span className="ml-2 text-slate-400">{row.note}</span>}
                  </span>
                  <span className="flex items-center gap-2">
                    <Badge tone={PAYOUT_TONES[row.status] ?? "slate"}>{row.status}</Badge>
                    {row.status === "requested" && (
                      <>
                        <Button size="sm" variant="secondary" loading={payout.isPending}
                                onClick={() => payout.mutate({ pid: row.id, next: "approved" })}>Approve</Button>
                        <Button size="sm" variant="ghost" loading={payout.isPending}
                                onClick={() => payout.mutate({ pid: row.id, next: "rejected" })}>Reject</Button>
                      </>
                    )}
                    {row.status === "approved" && (
                      <Button size="sm" variant="secondary" loading={payout.isPending}
                              onClick={() => payout.mutate({ pid: row.id, next: "paid" })}>Mark paid</Button>
                    )}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card title="Campaigns">
          {data.campaigns.length === 0 ? <p className="text-sm text-slate-500">No tracking campaigns.</p> : (
            <ul className="divide-y divide-slate-100 text-sm">
              {data.campaigns.map((c) => (
                <li key={c.id} className="flex items-center justify-between gap-3 py-2">
                  <span>
                    <span className="font-medium text-slate-800">{c.name}</span>
                    <span className="ml-2 font-mono text-xs text-slate-500">{c.path}</span>
                  </span>
                  <span className="text-slate-500">{c.click_count} clicks</span>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card title="Assignment breakdown">
          {Object.values(data.reports.institutes_by_status).every((n) => n === 0)
            && Object.values(data.reports.payouts_by_status).every((n) => n === 0) ? (
            <p className="text-sm text-slate-500">No campuses or payouts yet.</p>
          ) : (
            <div className="space-y-3">
              <div className="flex flex-wrap gap-1">
                {Object.entries(data.reports.institutes_by_status).filter(([, n]) => n > 0).map(([s, n]) => (
                  <Badge key={s} tone={INSTITUTE_STATUS_TONES[s] ?? "slate"}>{s}: {n}</Badge>
                ))}
              </div>
              <div className="flex flex-wrap gap-1">
                {Object.entries(data.reports.payouts_by_status).filter(([, n]) => n > 0).map(([s, n]) => (
                  <Badge key={s} tone={PAYOUT_TONES[s] ?? "slate"}>{s}: {n}</Badge>
                ))}
              </div>
            </div>
          )}
        </Card>
      </div>

      {confirm && (
        <ConfirmDialog open title={confirm.title} message={confirm.message} confirmLabel={confirm.confirm}
                       danger={confirm.danger} loading={status.isPending} onConfirm={confirm.run}
                       onClose={() => setConfirm(null)} />
      )}
      {resetting && (
        <ResetPartnerPasswordDialog partnerId={id} email={data.login?.email ?? p.contact_name}
                                    onClose={() => setResetting(false)} />
      )}
      {editing && (
        <EditPartnerDialog
          partner={p}
          loginEmail={data.login ? data.login.email : null}
          onClose={() => setEditing(false)}
        />
      )}
    </>
  );
}

function ResetPartnerPasswordDialog({ partnerId, email, onClose }: {
  partnerId: string; email: string; onClose: () => void;
}) {
  const toast = useToast();
  const [password, setPassword] = useState("");
  const save = useMutation({
    mutationFn: () => admin.partnerPassword(partnerId, password),
    onSuccess: () => { toast.success("Password updated."); onClose(); },
    onError: (e) => toast.error(errorMessage(e)),
  });
  return (
    <Modal open onClose={onClose} title="Reset partner password" footer={
      <>
        <Button variant="secondary" onClick={onClose}>Cancel</Button>
        <Button disabled={password.length < 10} loading={save.isPending} onClick={() => save.mutate()}>Save password</Button>
      </>
    }>
      <div className="space-y-4">
        <p className="text-sm text-slate-600">
          Sets a new password for <span className="font-medium text-slate-900">{email}</span>. Share it with the partner.
        </p>
        <TextInput label="New password" type="password" value={password} onChange={setPassword}
                   hint="At least 10 characters." />
      </div>
    </Modal>
  );
}
