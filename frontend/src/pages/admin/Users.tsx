import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Search, Users } from "lucide-react";
import { useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { useSession } from "../../auth/session";
import { Select, TextArea, TextInput, Toggle } from "../../components/form";
import { ConfirmDialog, Modal } from "../../components/Modal";
import { Pagination } from "../../components/Pagination";
import { useToast } from "../../components/Toast";
import { Alert, Badge, Button, Card, EmptyState, PageHeader, ProgressBar, Spinner, cx } from "../../components/ui";
import { formatDate, formatDateTime, formatMoney, formatRelative, STATUS_LABELS, STATUS_TONES } from "../../lib/format";
import { useDebounced } from "../../lib/useDebounced";
import { errorMessage } from "../../services/api";
import { admin, plans as plansApi } from "../../services/endpoints";
import { APPLICATION_STATUSES, type AdminUser, type AdminUserDetail } from "../../types";
import { PAGE_SIZE, providerLabel, RUN_TONES, SubBadge, Table, Td, UserLink } from "./shared";

const USER_STATUS_FILTERS = [
  { value: "active", label: "Active" },
  { value: "disabled", label: "Disabled" },
  { value: "admin", label: "Admins" },
  { value: "unverified", label: "Unverified" },
] as const;

type UserListStatus = (typeof USER_STATUS_FILTERS)[number]["value"] | "";

function userStatusLabel(value: UserListStatus): string {
  if (!value) return "All";
  return USER_STATUS_FILTERS.find((f) => f.value === value)?.label ?? value;
}

function AdminUserStatusFilters({ value, onChange }: { value: UserListStatus; onChange: (v: UserListStatus) => void }) {
  return (
    <div>
      <span className="mb-2 block text-sm font-medium text-slate-700">Status</span>
      <div className="flex flex-wrap gap-2">
        <button type="button" aria-pressed={value === ""} onClick={() => onChange("")}
                className={cx("rounded-full px-3 py-1 text-sm ring-1 ring-inset transition-colors",
                  value === "" ? "bg-slate-900 text-white ring-slate-900" : "bg-white text-slate-700 ring-slate-300 hover:bg-slate-50")}>
          All
        </button>
        {USER_STATUS_FILTERS.map((f) => (
          <button key={f.value} type="button" aria-pressed={value === f.value} onClick={() => onChange(value === f.value ? "" : f.value)}
                  className={cx("rounded-full px-3 py-1 text-sm ring-1 ring-inset transition-colors",
                    value === f.value ? "bg-brand-600 text-white ring-brand-600" : "bg-white text-slate-700 ring-slate-300 hover:bg-slate-50")}>
            {f.label}
          </button>
        ))}
      </div>
    </div>
  );
}

function fullName(u: AdminUser): string {
  return [u.first_name, u.last_name].filter(Boolean).join(" ");
}

function usePlanOptions(first: { value: string; label: string }) {
  const { data } = useQuery({ queryKey: ["plans"], queryFn: plansApi.list, staleTime: 5 * 60 * 1000 });
  return [first, ...(data ?? []).map((p) => ({ value: p.code, label: p.name }))];
}

export function AdminUsersPage() {
  const [params] = useSearchParams();
  const [q, setQ] = useState("");
  const [status, setStatus] = useState<UserListStatus>(() => {
    const initial = params.get("status") ?? "";
    return USER_STATUS_FILTERS.some((f) => f.value === initial) ? (initial as UserListStatus) : "";
  });
  const [plan, setPlan] = useState("");
  const [page, setPage] = useState(1);
  const search = useDebounced(q.trim());
  const planOptions = usePlanOptions({ value: "", label: "All plans" });
  const query = { q: search || undefined, status: status || undefined, plan: plan || undefined, page, page_size: PAGE_SIZE };
  const { data, isLoading, isFetching, error } = useQuery({
    queryKey: ["admin", "users", query], queryFn: () => admin.users(query), placeholderData: keepPreviousData,
  });
  const resetPage = () => setPage(1);
  const hasFilters = Boolean(search || status || plan);
  const planLabel = planOptions.find((o) => o.value === plan)?.label;

  return (
    <>
      <PageHeader title="Users" description="Accounts, plans, and activity across the platform." />
      <Card>
        <div className="relative mb-6 max-w-xl">
          <TextInput label="Search" value={q} onChange={(v) => { setQ(v); resetPage(); }}
                     placeholder="Email or name" maxLength={200} className="pl-9" />
          <Search className="pointer-events-none absolute bottom-2.5 left-3 h-4 w-4 text-slate-400" aria-hidden />
        </div>
        <div className="grid gap-6 lg:grid-cols-[1fr_minmax(0,14rem)] lg:items-end">
          <AdminUserStatusFilters value={status} onChange={(v) => { setStatus(v); resetPage(); }} />
          <Select label="Plan" value={plan} onChange={(v) => { setPlan(v); resetPage(); }} options={planOptions} />
        </div>
        {hasFilters && (
          <p className="mt-3 text-xs text-slate-500">
            Filtering{search ? ` for “${search}”` : ""}{status ? ` · ${userStatusLabel(status)}` : ""}{plan ? ` · ${planLabel ?? plan}` : ""}.{" "}
            <button type="button" className="font-medium text-brand-700 hover:underline"
                    onClick={() => { setQ(""); setStatus(""); setPlan(""); resetPage(); }}>Clear filters</button>
          </p>
        )}
      </Card>

      <div className="mt-6">
        {isLoading ? <Spinner /> : error || !data ? <Alert kind="error">{errorMessage(error)}</Alert> : data.total === 0 ? (
          <Card>
            <EmptyState icon={<Users className="h-10 w-10" />} title="No users found">
              {hasFilters ? "Try different search terms or clear filters." : "Users appear here when someone creates an account."}
            </EmptyState>
          </Card>
        ) : (
          <Card className={cx(isFetching && "opacity-70 transition-opacity")}>
            <p className="mb-4 text-sm text-slate-600">
              Showing <span className="font-medium text-slate-900">{data.items.length}</span> of{" "}
              <span className="font-medium text-slate-900">{data.total.toLocaleString()}</span> users
            </p>
            <Table head={["User", "Plan", "Applications", "Joined", "Last sign-in", "Account"]} dim={isFetching}>
              {data.items.map((u) => (
                <tr key={u.id} className="hover:bg-slate-50/80">
                  <Td>
                    <UserLink id={u.id} email={u.email} />
                    {fullName(u) && <p className="text-sm text-slate-500">{fullName(u)}</p>}
                  </Td>
                  <Td>
                    <p className="font-medium text-slate-900">{u.plan_name}</p>
                    <p className="text-xs text-slate-500">{u.plan}</p>
                  </Td>
                  <Td className="tabular-nums text-slate-700">{u.applications_this_month.toLocaleString()}</Td>
                  <Td className="whitespace-nowrap text-slate-600">{formatDate(u.created_at)}</Td>
                  <Td className="whitespace-nowrap text-slate-600">
                    {u.last_login_at ? (
                      <>
                        <p>{formatRelative(u.last_login_at)}</p>
                        <p className="text-xs text-slate-500">{formatDateTime(u.last_login_at)}</p>
                      </>
                    ) : (
                      <span className="text-slate-400">Never</span>
                    )}
                  </Td>
                  <Td>
                    <div className="flex flex-wrap gap-1">
                      {!u.is_active && <Badge tone="red">Disabled</Badge>}
                      {u.is_admin && <Badge tone="brand">Admin</Badge>}
                      {!u.is_verified && <Badge tone="amber">Unverified</Badge>}
                    </div>
                  </Td>
                </tr>
              ))}
            </Table>
            <Pagination page={data.page} pageSize={data.page_size} total={data.total} onPage={setPage} />
          </Card>
        )}
      </div>
    </>
  );
}

// ------------------------------------------------------------------------------------------ detail
type Pending = { title: string; message: string; confirm: string; danger: boolean; run: () => void };

export function AdminUserPage() {
  const { id = "" } = useParams();
  const { data: me } = useSession();
  const client = useQueryClient();
  const toast = useToast();
  const [confirm, setConfirm] = useState<Pending | null>(null);
  const [granting, setGranting] = useState(false);
  const key = ["admin", "user", id];
  const { data, isLoading, error } = useQuery({ queryKey: key, queryFn: () => admin.user(id) });

  const onDone = (message: string) => (detail: AdminUserDetail) => {
    client.setQueryData(key, detail);
    void client.invalidateQueries({ queryKey: ["admin", "users"] });
    setConfirm(null);
    setGranting(false);
    toast.success(message);
  };
  const onError = (e: unknown) => { setConfirm(null); toast.error(errorMessage(e)); };
  const update = useMutation({
    mutationFn: (body: { is_active?: boolean; is_admin?: boolean }) => admin.updateUser(id, body),
    onSuccess: onDone("Saved."), onError,
  });
  const revoke = useMutation({ mutationFn: () => admin.revokePlan(id), onSuccess: onDone("Complimentary plan ended."), onError });
  const verify = useMutation({ mutationFn: () => admin.verifyEmail(id), onSuccess: onDone("Email marked as verified."), onError });
  const resend = useMutation({
    mutationFn: () => admin.resendVerification(id), onSuccess: onDone("Verification email sent. Earlier links no longer work."), onError,
  });

  if (isLoading) return <Spinner />;
  if (error || !data) return <Alert kind="error">{errorMessage(error)}</Alert>;
  const { user: u, usage, subscription: sub } = data;
  const self = me?.id === u.id;
  const complimentary = sub?.provider === "admin";

  const refuseSelf = () => toast.error("Ask another admin to change your own account.");
  const askActive = (value: boolean) => setConfirm(value
    ? { title: "Enable this account?", message: `${u.email} will be able to sign in again.`, confirm: "Enable", danger: false,
        run: () => update.mutate({ is_active: true }) }
    : { title: "Disable this account?", danger: true, confirm: "Disable account",
        message: `${u.email} is signed out everywhere, their desktop agents are disconnected, and any run in progress stops after its current job. They can't sign in until you enable the account again.`,
        run: () => update.mutate({ is_active: false }) });
  const askAdmin = (value: boolean) => setConfirm({
    title: value ? "Make this user an admin?" : "Remove admin access?", danger: value, confirm: value ? "Make admin" : "Remove access",
    message: value ? `${u.email} will see every user's account, runs, and billing, and can change plans and disable accounts.`
      : `${u.email} will no longer be able to open the admin area.`,
    run: () => update.mutate({ is_admin: value }),
  });

  return (
    <>
      <Link to="/admin/users" className="mb-4 inline-flex items-center gap-1 text-sm text-slate-500 hover:text-slate-700">
        <ArrowLeft className="h-4 w-4" aria-hidden /> All users
      </Link>
      <PageHeader title={u.email} description={[fullName(u), `Joined ${formatDate(u.created_at)}`,
        u.last_login_at ? `last signed in ${formatRelative(u.last_login_at)}` : "never signed in"].filter(Boolean).join(" \u00b7 ")} />

      <div className="grid gap-6 lg:grid-cols-3">
        <Card title="Account">
          <div className="space-y-4">
            <Toggle label="Can sign in" checked={u.is_active} onChange={self ? refuseSelf : askActive}
                    hint={self ? "You can't disable your own account." : u.is_verified ? "Email verified." : "Email not verified yet."} />
            <Toggle label="Admin" checked={u.is_admin} onChange={self ? refuseSelf : askAdmin}
                    hint={self ? "You can't remove your own admin access." : "Opens this admin area."} />
          </div>
          {!u.is_verified && (
            <div className="mt-4 border-t border-slate-100 pt-4">
              <p className="text-sm text-slate-600">This email address isn't verified, so they can't sign in yet.</p>
              <div className="mt-3 flex flex-wrap gap-2">
                <Button size="sm" variant="secondary" loading={resend.isPending} disabled={!u.is_active}
                        onClick={() => resend.mutate()}>Resend verification email</Button>
                <Button size="sm" variant="ghost" onClick={() => setConfirm({
                  title: "Mark this email as verified?", danger: false, confirm: "Mark verified",
                  message: `Only do this if you're sure ${u.email} belongs to this person. They can sign in straight away.`,
                  run: () => verify.mutate(),
                })}>Mark verified</Button>
              </div>
            </div>
          )}
        </Card>

        <Card title="Plan">
          <div className="flex items-center justify-between gap-2">
            <p className="text-xl font-semibold">{usage.plan_name}</p>
            {sub && (complimentary ? <Badge tone="brand">Complimentary</Badge> : <SubBadge sub={sub} />)}
          </div>
          <p className="mt-1 text-sm text-slate-600">
            {!sub ? "Free plan." : complimentary ? `Given until ${formatDate(sub.current_period_end)}.`
              : sub.cancel_at_period_end ? `Paid; ends ${formatDate(sub.current_period_end)}.`
              : `Paid through ${providerLabel(sub.provider)}; renews ${formatDate(sub.current_period_end)}.`}
          </p>
          <div className="mt-4 flex flex-wrap gap-2">
            {(!sub || complimentary) && (
              <Button size="sm" variant="secondary" onClick={() => setGranting(true)}>
                {complimentary ? "Change complimentary plan" : "Give a plan"}
              </Button>
            )}
            {complimentary && (
              <Button size="sm" variant="ghost" onClick={() => setConfirm({
                title: "End the complimentary plan?", danger: true, confirm: "End plan",
                message: `${u.email} moves to the Free plan now.`, run: () => revoke.mutate(),
              })}>End it now</Button>
            )}
          </div>
          {sub && !complimentary && <p className="mt-3 text-xs text-slate-500">They pay for this plan, so it can only be changed or cancelled by them.</p>}
        </Card>

        <Card title={`Usage (${usage.period})`}>
          <div className="space-y-4">
            <ProgressBar label="Applications" value={usage.applications.used} max={usage.applications.limit} />
            <ProgressBar label="Resumes" value={data.resumes} max={usage.resumes.limit} />
            <div className="flex flex-wrap gap-1">
              {APPLICATION_STATUSES.filter((s) => data.applications_by_status[s] > 0).map((s) => (
                <Badge key={s} tone={STATUS_TONES[s]}>{STATUS_LABELS[s]}: {data.applications_by_status[s]}</Badge>
              ))}
            </div>
          </div>
        </Card>
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <Card title="Recent runs">
          {data.runs.length === 0 ? <p className="text-sm text-slate-500">No runs yet.</p> : (
            <ul className="divide-y divide-slate-100 text-sm">
              {data.runs.map((r) => (
                <li key={r.id} className="flex items-center justify-between gap-3 py-2">
                  <span className="text-slate-600">{formatDateTime(r.created_at)}{r.dry_run && " (dry run)"}</span>
                  <span className="text-slate-500">{r.successful_count} applied &middot; {r.failed_count} failed</span>
                  <Badge tone={RUN_TONES[r.status]}>{r.status}</Badge>
                </li>
              ))}
            </ul>
          )}
        </Card>
        <Card title="Computers">
          {data.devices.length === 0 ? <p className="text-sm text-slate-500">No desktop agent connected.</p> : (
            <ul className="divide-y divide-slate-100 text-sm">
              {data.devices.map((d) => (
                <li key={d.id} className="flex items-center justify-between gap-3 py-2">
                  <span className="font-medium text-slate-800">{d.name || "Unnamed computer"}</span>
                  <span className="text-slate-500">{d.platform} &middot; v{d.agent_version || "?"}</span>
                  <Badge tone={d.online ? "green" : "slate"}>{d.online ? "Online" : "Offline"}</Badge>
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
                  <span className="text-slate-500">{providerLabel(s.provider)} &middot; {formatDate(s.created_at)} to {formatDate(s.current_period_end)}</span>
                  <SubBadge sub={s} />
                </li>
              ))}
            </ul>
          )}
        </Card>
        <Card title="Payments">
          {data.payments.length === 0 ? <p className="text-sm text-slate-500">No payments.</p> : (
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
      </div>

      {confirm && (
        <ConfirmDialog open title={confirm.title} message={confirm.message} confirmLabel={confirm.confirm} danger={confirm.danger}
                       loading={update.isPending || revoke.isPending || verify.isPending} onConfirm={confirm.run} onClose={() => setConfirm(null)} />
      )}
      <GrantDialog open={granting} userId={u.id} email={u.email} onClose={() => setGranting(false)}
                   onGranted={onDone("Complimentary plan given.")} />
    </>
  );
}

function GrantDialog({ open, userId, email, onClose, onGranted }: {
  open: boolean; userId: string; email: string; onClose: () => void; onGranted: (detail: AdminUserDetail) => void;
}) {
  const toast = useToast();
  const options = usePlanOptions({ value: "", label: "Choose a plan" }).filter((o) => o.value !== "free");
  const [plan, setPlan] = useState("");
  const [months, setMonths] = useState("1");
  const [note, setNote] = useState("");
  const grant = useMutation({
    mutationFn: () => admin.grantPlan(userId, { plan, months: Number(months), note: note.trim() }),
    onSuccess: (detail) => { setPlan(""); setMonths("1"); setNote(""); onGranted(detail); },
    onError: (e) => toast.error(errorMessage(e)),
  });
  const monthOptions = Array.from({ length: 24 }, (_, i) => ({ value: String(i + 1), label: `${i + 1} month${i ? "s" : ""}` }));

  return (
    <Modal open={open} onClose={onClose} title="Give a complimentary plan" footer={
      <>
        <Button variant="secondary" onClick={onClose}>Cancel</Button>
        <Button disabled={!plan} loading={grant.isPending} onClick={() => grant.mutate()}>Give plan</Button>
      </>
    }>
      <div className="space-y-4">
        <p>{email} gets the plan's limits right away, with no payment. It ends by itself; nothing renews. A plan you gave earlier is replaced.</p>
        <Select label="Plan" value={plan} onChange={setPlan} options={options} />
        <Select label="For" value={months} onChange={setMonths} options={monthOptions} />
        <TextArea label="Note (only admins see this)" value={note} onChange={setNote} maxLength={500} rows={2}
                  placeholder="Why, for the audit log" />
      </div>
    </Modal>
  );
}
