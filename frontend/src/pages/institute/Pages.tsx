import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState, type FormEvent } from "react";
import { useSession } from "../../auth/session";
import { Select, TextArea, TextInput, Toggle } from "../../components/form";
import { ConfirmDialog } from "../../components/Modal";
import { useToast } from "../../components/Toast";
import { Alert, Badge, Button, Card, EmptyState, PageHeader, Spinner } from "../../components/ui";
import { formatDate, formatMoney } from "../../lib/format";
import { CheckoutError, openRazorpayCheckout } from "../../lib/razorpay";
import { errorMessage } from "../../services/api";
import { billing, institute } from "../../services/endpoints";
import type { Institute, InstituteSettings, Plan } from "../../types";

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

function Pending() {
  return (
    <Card>
      <Alert kind="info">Your institute application is waiting for ApplyXAI review. You can look around, but inviting students and buying seats unlocks after approval.</Alert>
    </Card>
  );
}

export function InstituteDashboardPage() {
  const { data: user } = useSession();
  const { data, isLoading, error } = useQuery({ queryKey: ["institute", "dashboard"], queryFn: institute.dashboard });
  if (isLoading) return <Spinner />;
  if (error || !data) return <Alert kind="error">{errorMessage(error)}</Alert>;
  const pending = user?.institute_status === "pending";
  return (
    <>
      <PageHeader title={data.institute.name} description="Seat inventory, invitations, and campus subscription." />
      {pending && <div className="mb-6"><Pending /></div>}
      <div className="grid gap-4 sm:grid-cols-3">
        <Card><p className="text-sm text-slate-500">Active students</p><p className="mt-1 text-2xl font-semibold">{data.students}</p></Card>
        <Card><p className="text-sm text-slate-500">Open invitations</p><p className="mt-1 text-2xl font-semibold">{data.pending_invites}</p></Card>
        <Card><p className="text-sm text-slate-500">Seats available</p><p className="mt-1 text-2xl font-semibold">{data.seats.available} / {data.seats.total}</p></Card>
      </div>
      <div className="mt-6">
        <h2 className="mb-3 text-sm font-semibold text-slate-700">Recent assignments</h2>
        {data.recent_assignments.length === 0 ? <EmptyState title="No students yet">Invite students once your institute is approved and you have seats.</EmptyState> : (
          <Card>
            <ul className="divide-y divide-slate-100">
              {data.recent_assignments.map((a) => (
                <li key={a.id} className="flex items-center justify-between py-3 text-sm">
                  <span>{a.candidate_email}</span>
                  <Badge>{a.status}</Badge>
                </li>
              ))}
            </ul>
          </Card>
        )}
      </div>
    </>
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
  const [email, setEmail] = useState("");
  const [status, setStatus] = useState("");
  const [confirm, setConfirm] = useState<{ id: string; title: string; message: string; confirm: string; danger: boolean; run: () => void } | null>(null);
  const { data, isLoading } = useQuery({
    queryKey: ["institute", "students", status],
    queryFn: () => institute.students({ status: status || undefined }),
  });
  const invite = useMutation({
    mutationFn: () => institute.invite(email),
    onSuccess: () => { setEmail(""); client.invalidateQueries({ queryKey: ["institute"] }); toast.success("Invitation sent."); },
    onError: (e) => toast.error(errorMessage(e)),
  });
  const release = useMutation({
    mutationFn: institute.release,
    onSuccess: () => { setConfirm(null); client.invalidateQueries({ queryKey: ["institute"] }); toast.success("Seat released."); },
    onError: (e) => { setConfirm(null); toast.error(errorMessage(e)); },
  });
  const suspend = useMutation({
    mutationFn: institute.suspend,
    onSuccess: () => { setConfirm(null); client.invalidateQueries({ queryKey: ["institute"] }); toast.success("Student suspended."); },
    onError: (e) => { setConfirm(null); toast.error(errorMessage(e)); },
  });
  const busy = release.isPending || suspend.isPending;

  return (
    <>
      <PageHeader title="Students" description="Invite by email. Students keep their own ApplyXAI account." />
      <Card className="mb-6">
        <form onSubmit={(e: FormEvent) => { e.preventDefault(); invite.mutate(); }} className="flex flex-col gap-3 sm:flex-row sm:items-end">
          <div className="flex-1"><TextInput label="Student email" type="email" value={email} onChange={setEmail} required /></div>
          <Button type="submit" loading={invite.isPending} disabled={!email.includes("@")}>Invite</Button>
        </form>
      </Card>
      <div className="mb-4 flex flex-wrap gap-2">
        {STUDENT_STATUS_FILTERS.map((f) => (
          <button key={f.value} type="button" aria-pressed={status === f.value} onClick={() => setStatus(f.value)}
                  className={`rounded-full px-3 py-1 text-sm ring-1 ring-inset ${status === f.value ? "bg-slate-900 text-white ring-slate-900" : "bg-white text-slate-700 ring-slate-300"}`}>
            {f.label}
          </button>
        ))}
      </div>
      {isLoading ? <Spinner /> : !data?.items.length ? <EmptyState title="No students">Invited students appear here.</EmptyState> : (
        <Card>
          <ul className="divide-y divide-slate-100">
            {data.items.map((a) => (
              <li key={a.id} className="flex flex-wrap items-center justify-between gap-3 py-3 text-sm">
                <div>
                  <p className="font-medium">{a.candidate_email}</p>
                  <p className="text-xs text-slate-500">{formatDate(a.created_at)}</p>
                </div>
                <div className="flex items-center gap-2">
                  <Badge>{a.status}</Badge>
                  {a.status === "active" && (
                    <Button size="sm" variant="ghost" onClick={() => setConfirm({
                      id: a.id, title: "Suspend this student?", confirm: "Suspend", danger: true,
                      message: `${a.candidate_email} loses this campus seat until you invite them again or they are reassigned.`,
                      run: () => suspend.mutate(a.id),
                    })}>Suspend</Button>
                  )}
                  {(a.status === "active" || a.status === "invited" || a.status === "pending_candidate_acceptance" || a.status === "suspended") && (
                    <Button size="sm" variant="secondary" onClick={() => setConfirm({
                      id: a.id, title: "Release this seat?", confirm: "Release", danger: true,
                      message: `${a.candidate_email} is removed from this campus and the seat becomes available again.`,
                      run: () => release.mutate(a.id),
                    })}>Release</Button>
                  )}
                </div>
              </li>
            ))}
          </ul>
        </Card>
      )}
      {confirm && (
        <ConfirmDialog open title={confirm.title} message={confirm.message} confirmLabel={confirm.confirm}
                       danger={confirm.danger} loading={busy} onConfirm={confirm.run} onClose={() => setConfirm(null)} />
      )}
    </>
  );
}

export function InstituteInvitationsPage() {
  const toast = useToast();
  const client = useQueryClient();
  const { data, isLoading } = useQuery({ queryKey: ["institute", "invitations"], queryFn: institute.invitations });
  const release = useMutation({
    mutationFn: institute.release,
    onSuccess: () => { client.invalidateQueries({ queryKey: ["institute"] }); toast.success("Invitation cancelled."); },
    onError: (e) => toast.error(errorMessage(e)),
  });
  return (
    <>
      <PageHeader title="Invitations" description="Pending seat invitations." />
      {isLoading ? <Spinner /> : !data?.items.length ? <EmptyState title="No open invitations" /> : (
        <Card>
          <ul className="divide-y divide-slate-100">
            {data.items.map((a) => (
              <li key={a.id} className="flex flex-wrap items-center justify-between gap-3 py-3 text-sm">
                <div>
                  <p>{a.candidate_email}</p>
                  <p className="text-xs text-slate-500">{formatDate(a.created_at)}</p>
                </div>
                <div className="flex items-center gap-2">
                  <Badge>{a.status}</Badge>
                  <Button size="sm" variant="secondary" loading={release.isPending} onClick={() => release.mutate(a.id)}>Cancel</Button>
                </div>
              </li>
            ))}
          </ul>
        </Card>
      )}
    </>
  );
}

export function InstituteSeatsPage() {
  const { data, isLoading } = useQuery({ queryKey: ["institute", "seats"], queryFn: institute.seats });
  return (
    <>
      <PageHeader title="Seat inventory" description="Purchased seats reserved for students." />
      {isLoading ? <Spinner /> : (
        <>
          <p className="mb-4 text-sm text-slate-600">{data?.counts.available ?? 0} available of {data?.counts.total ?? 0}</p>
          {!data?.items.length ? <EmptyState title="No seats yet">Buy a campus plan to create seats.</EmptyState> : (
            <Card>
              <ul className="divide-y divide-slate-100">
                {data.items.map((s) => (
                  <li key={s.id} className="flex justify-between py-3 text-sm"><span className="font-mono text-xs">{s.id.slice(0, 8)}</span><Badge>{s.status}</Badge></li>
                ))}
              </ul>
            </Card>
          )}
        </>
      )}
    </>
  );
}

export function InstituteSubscriptionPage() {
  const toast = useToast();
  const client = useQueryClient();
  const { data, isLoading } = useQuery({ queryKey: ["institute", "subscription"], queryFn: institute.subscription });
  const { data: plans } = useQuery({ queryKey: ["institute", "plans"], queryFn: institute.plans });
  const checkout = useMutation({
    mutationFn: async (plan: Plan) => {
      const started = await institute.checkout(plan.code);
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

  const sub = data?.subscription;

  return (
    <>
      <PageHeader title="Subscription" description="Campus plans include a pool of student seats." />
      {isLoading ? <Spinner /> : (
        <Card className="mb-6">
          {sub ? (
            <p className="text-sm">
              Current plan: <strong>{sub.plan.name}</strong> ({sub.status})
              {sub.current_period_end ? ` · ${sub.cancel_at_period_end ? "ends" : "renews"} ${formatDate(sub.current_period_end)}` : ""}
            </p>
          ) : <p className="text-sm text-slate-600">No campus plan yet.</p>}
        </Card>
      )}
      <div className="grid gap-4 sm:grid-cols-2">
        {(plans ?? []).map((p) => {
          const current = sub?.plan.code === p.code;
          return (
            <Card key={p.code}>
              <h3 className="font-semibold">{p.name}{current ? " · Current" : ""}</h3>
              <p className="mt-2 text-2xl font-bold">
                Amount = {formatMoney(p.price_cents * (p.limits.seats ?? 0), p.currency)}
                <span className="text-sm font-normal text-slate-500"> / {p.interval}</span>
              </p>
              <p className="mt-1 text-sm text-slate-600">
                {(p.limits.seats ?? 0).toLocaleString()} minimum students · {formatMoney(p.price_cents, p.currency)} / student
              </p>
              <p className="mt-3 text-sm text-slate-600">
                Per student: {p.limits.applications_per_month.toLocaleString()} applications / month · {p.limits.resumes} resumes
              </p>
              <p className="mt-1 text-sm text-slate-600">
                Package: {(p.limits.applications_per_month * (p.limits.seats ?? 0)).toLocaleString()} applications / month ·{" "}
                {(p.limits.resumes * (p.limits.seats ?? 0)).toLocaleString()} resumes
              </p>
              {!current && (
                <Button className="mt-4" onClick={() => checkout.mutate(p)} loading={checkout.isPending && checkout.variables?.code === p.code}
                        disabled={checkout.isPending}>
                  {sub ? `Switch to ${p.name}` : "Choose"}
                </Button>
              )}
            </Card>
          );
        })}
      </div>
    </>
  );
}

export function InstituteReportsPage() {
  const { data, isLoading } = useQuery({ queryKey: ["institute", "reports"], queryFn: institute.reports });
  if (isLoading) return <Spinner />;
  return (
    <>
      <PageHeader title="Reports" description="Seat and assignment totals." />
      <Card>
        <ul className="space-y-2 text-sm">
          {Object.entries(data?.assignments_by_status ?? {}).map(([k, v]) => (
            <li key={k} className="flex justify-between"><span className="capitalize">{k.replaceAll("_", " ")}</span><span>{v}</span></li>
          ))}
        </ul>
      </Card>
    </>
  );
}

export function InstituteProfilePage() {
  const toast = useToast();
  const client = useQueryClient();
  const { data, isLoading } = useQuery({ queryKey: ["institute", "profile"], queryFn: institute.profile });
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
  if (isLoading || !data) return <Spinner />;
  return (
    <>
      <PageHeader title="Institute profile" />
      <Card>
        <form onSubmit={(e) => { e.preventDefault(); save.mutate(); }} className="space-y-4">
          <TextInput label="Name" required value={form.name} onChange={(name) => setForm((f) => ({ ...f, name }))} maxLength={190} />
          <TextInput label="Contact" value={form.contact_name} onChange={(contact_name) => setForm((f) => ({ ...f, contact_name }))} maxLength={190} />
          <TextInput label="Phone" value={form.phone} onChange={(phone) => setForm((f) => ({ ...f, phone }))} maxLength={32} />
          <Select label="Type" value={form.institute_type} onChange={(institute_type) => setForm((f) => ({ ...f, institute_type }))}
                  options={Object.entries(INSTITUTE_TYPE_LABELS).map(([value, label]) => ({ value, label }))} />
          <TextInput label="GSTIN" value={form.gstin} onChange={(gstin) => setForm((f) => ({ ...f, gstin }))} maxLength={15} />
          <TextInput label="PAN" value={form.pan_number} onChange={(pan_number) => setForm((f) => ({ ...f, pan_number }))} maxLength={10} />
          <Button type="submit" loading={save.isPending} disabled={!form.name.trim()}>Save</Button>
        </form>
      </Card>
    </>
  );
}

export function InstituteSettingsPage() {
  const toast = useToast();
  const client = useQueryClient();
  const { data, isLoading } = useQuery({ queryKey: ["institute", "profile"], queryFn: institute.profile });
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
  if (isLoading || !data) return <Spinner />;
  return (
    <>
      <PageHeader title="Settings" description="Invitation defaults for this campus." />
      <Card>
        <form onSubmit={(e) => { e.preventDefault(); save.mutate(); }} className="space-y-4">
          <TextInput label="Timezone" value={form.timezone} onChange={(timezone) => setForm((f) => ({ ...f, timezone }))} />
          <TextInput label="Invite expiry (days)" type="number" min={1} max={30} value={String(form.invite_expiry_days)}
                     onChange={(v) => setForm((f) => ({ ...f, invite_expiry_days: Number(v) || 7 }))} />
          <TextInput label="Low-seat warning at" type="number" min={1} max={50} value={String(form.low_seat_threshold)}
                     onChange={(v) => setForm((f) => ({ ...f, low_seat_threshold: Number(v) || 3 }))} />
          <TextArea label="Default invite note" value={form.invite_note} onChange={(invite_note) => setForm((f) => ({ ...f, invite_note }))} maxLength={500} />
          <Toggle label="Email when an invitation is sent" checked={form.notify_invites}
                  onChange={(notify_invites) => setForm((f) => ({ ...f, notify_invites }))} />
          <Toggle label="Email when a student accepts" checked={form.notify_acceptances}
                  onChange={(notify_acceptances) => setForm((f) => ({ ...f, notify_acceptances }))} />
          <Toggle label="Email when seats run low" checked={form.notify_low_seats}
                  onChange={(notify_low_seats) => setForm((f) => ({ ...f, notify_low_seats }))} />
          <Button type="submit" loading={save.isPending}>Save settings</Button>
        </form>
      </Card>
    </>
  );
}
