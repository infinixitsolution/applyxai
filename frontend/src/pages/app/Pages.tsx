import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bell, Bot, Laptop, ShieldCheck } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useSession, useSetSession } from "../../auth/session";
import { appLink } from "../../components/NotificationBell";
import { ConfirmDialog } from "../../components/Modal";
import { Pagination } from "../../components/Pagination";
import { useToast } from "../../components/Toast";
import { Alert, Badge, Button, ButtonLink, Card, cx, EmptyState, PageHeader, ProgressBar, Spinner } from "../../components/ui";
import { ApplicationPreferencesForm } from "../../features/ApplicationPreferencesForm";
import { ProfileForm } from "../../features/ProfileForm";
import { ResumeManager } from "../../features/ResumeManager";
import { SearchPreferencesForm } from "../../features/SearchPreferencesForm";
import { formatDate, formatDateTime, formatMoney, formatRelative } from "../../lib/format";
import { errorMessage } from "../../services/api";
import { auth, dashboard, notifications, plans as plansApi } from "../../services/endpoints";

export function ResumesPage() {
  return (
    <>
      <PageHeader title="Resumes" description="Your default resume is attached to applications unless a run says otherwise." />
      <ResumeManager />
    </>
  );
}

export function PreferencesPage() {
  const [tab, setTab] = useState<"search" | "application">("search");
  const tabs = [
    { id: "search" as const, label: "Job search" },
    { id: "application" as const, label: "Application answers" },
  ];
  return (
    <>
      <PageHeader title="Preferences" description="What to search for, and how to answer application questions." />
      <div role="tablist" className="mb-6 flex gap-1 rounded-lg bg-slate-100 p-1 sm:inline-flex">
        {tabs.map((t) => (
          <button key={t.id} role="tab" type="button" aria-selected={tab === t.id} onClick={() => setTab(t.id)}
                  className={cx("flex-1 rounded-md px-4 py-1.5 text-sm font-medium sm:flex-none",
                    tab === t.id ? "bg-white text-slate-900 shadow-sm" : "text-slate-600 hover:text-slate-900")}>
            {t.label}
          </button>
        ))}
      </div>
      {tab === "search" ? <Card><SearchPreferencesForm /></Card> : <ApplicationPreferencesForm />}
    </>
  );
}

export function ProfilePage() {
  return (
    <>
      <PageHeader title="Profile" description="Details used to fill in application forms." />
      <Card><ProfileForm /></Card>
    </>
  );
}

export function AutomationPage() {
  const { data } = useQuery({ queryKey: ["dashboard"], queryFn: dashboard.stats });
  const run = data?.automation.active ?? data?.automation.last;
  return (
    <>
      <PageHeader title="Automation" description="Start, pause, and monitor your job applications." />
      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2" title="Run from your computer">
          <div className="space-y-4 text-sm text-slate-600">
            <div className="flex gap-3">
              <Laptop className="h-6 w-6 shrink-0 text-brand-600" aria-hidden />
              <p>
                The automation runs in a browser on <strong>your own computer</strong>, using your saved preferences,
                answers, and default resume. You sign in to LinkedIn there, so ApplyXAI never receives your password.
              </p>
            </div>
            <div className="flex gap-3">
              <ShieldCheck className="h-6 w-6 shrink-0 text-brand-600" aria-hidden />
              <p>You can watch every step, and pause or stop at any time. Results sync to your dashboard as they happen.</p>
            </div>
            <Alert kind="info">
              The ApplyXAI desktop agent, with start, pause, and stop controls on this page, is coming soon.
              Until then, use the classic control panel (<code>python app.py</code>) on your computer.
            </Alert>
            <div className="flex flex-wrap gap-2">
              <ButtonLink to="/app/preferences" variant="secondary">Review preferences</ButtonLink>
              <ButtonLink to="/app/resumes" variant="secondary">Manage resumes</ButtonLink>
            </div>
          </div>
        </Card>
        <Card title={data?.automation.active ? "Current run" : "Last run"}>
          {run ? (
            <dl className="space-y-2 text-sm">
              <div className="flex justify-between"><dt className="text-slate-500">Status</dt><dd><Badge>{run.status}</Badge></dd></div>
              <div className="flex justify-between"><dt className="text-slate-500">Applied</dt><dd>{run.successful_count}</dd></div>
              <div className="flex justify-between"><dt className="text-slate-500">Failed</dt><dd>{run.failed_count}</dd></div>
              <div className="flex justify-between"><dt className="text-slate-500">Skipped</dt><dd>{run.skipped_count}</dd></div>
              <div className="flex justify-between"><dt className="text-slate-500">Started</dt><dd>{formatDateTime(run.started_at)}</dd></div>
            </dl>
          ) : <EmptyState icon={<Bot className="h-10 w-10" />} title="No runs yet" />}
        </Card>
      </div>
    </>
  );
}

export function BillingPage() {
  const usage = useQuery({ queryKey: ["usage"], queryFn: dashboard.usage });
  const plans = useQuery({ queryKey: ["plans"], queryFn: plansApi.list, staleTime: 10 * 60 * 1000 });
  if (usage.isLoading || plans.isLoading) return <Spinner />;
  if (!usage.data || !plans.data) return <Alert kind="error">{errorMessage(usage.error ?? plans.error)}</Alert>;
  const u = usage.data;
  return (
    <>
      <PageHeader title="Billing" description="Your plan and this month's usage." />
      <div className="grid gap-6 lg:grid-cols-3">
        <Card title="Current plan">
          <p className="text-2xl font-semibold">{u.plan_name}</p>
          <div className="mt-4 space-y-4">
            <ProgressBar label="Applications this month" value={u.applications.used} max={u.applications.limit} />
            <ProgressBar label="Resumes" value={u.resumes.used} max={u.resumes.limit} />
          </div>
          <p className="mt-4 text-xs text-slate-500">Usage resets on {formatDate(u.resets_at)}.</p>
        </Card>
        <div className="lg:col-span-2">
          <Alert kind="info">Online payments are coming soon. Plan changes will be available here once they're live.</Alert>
          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            {plans.data.map((p) => (
              <div key={p.code} className={cx("rounded-xl bg-white p-5 ring-1", p.code === u.plan ? "ring-2 ring-brand-600" : "ring-slate-200")}>
                <div className="flex items-center justify-between">
                  <p className="font-semibold">{p.name}</p>
                  {p.code === u.plan && <Badge tone="brand">Current</Badge>}
                </div>
                <p className="mt-2 text-xl font-semibold">
                  {p.price_cents === 0 ? "Free" : formatMoney(p.price_cents, p.currency)}
                  {p.price_cents > 0 && <span className="text-sm font-normal text-slate-500"> / {p.interval}</span>}
                </p>
                <p className="mt-2 text-sm text-slate-600">
                  {p.limits.applications_per_month.toLocaleString()} applications / month · {p.limits.resumes} resume{p.limits.resumes === 1 ? "" : "s"}
                </p>
                {p.code !== u.plan && <Button className="mt-4 w-full" variant="secondary" disabled>Upgrade (coming soon)</Button>}
              </div>
            ))}
          </div>
        </div>
      </div>
    </>
  );
}

export function SettingsPage() {
  const { data: user } = useSession();
  const setSession = useSetSession();
  const navigate = useNavigate();
  const toast = useToast();
  const [confirmAll, setConfirmAll] = useState(false);
  const reset = useMutation({
    mutationFn: () => auth.forgotPassword(user!.email),
    onSuccess: () => toast.success("Check your email for a link to set a new password."),
    onError: (e) => toast.error(errorMessage(e)),
  });
  const logoutAll = useMutation({
    mutationFn: auth.logoutAll,
    onSuccess: () => { setSession(null); navigate("/login", { replace: true }); },
    onError: (e) => toast.error(errorMessage(e)),
  });
  if (!user) return <Spinner />;
  return (
    <>
      <PageHeader title="Settings" description="Your account and security." />
      <div className="space-y-6">
        <Card title="Account">
          <dl className="grid gap-4 text-sm sm:grid-cols-2">
            <div><dt className="text-slate-500">Email</dt><dd className="font-medium">{user.email}</dd></div>
            <div><dt className="text-slate-500">Member since</dt><dd>{formatDate(user.created_at)}</dd></div>
            <div><dt className="text-slate-500">Last login</dt><dd>{formatDateTime(user.last_login_at)}</dd></div>
          </dl>
          <p className="mt-4 text-sm text-slate-500">To change your name or phone number, edit your <Link to="/app/profile" className="font-medium text-brand-600 hover:underline">profile</Link>.</p>
        </Card>
        <Card title="Password">
          <p className="mb-4 text-sm text-slate-600">We'll email you a secure link to choose a new password.</p>
          <Button variant="secondary" onClick={() => reset.mutate()} loading={reset.isPending}>Email me a reset link</Button>
        </Card>
        <Card title="Sessions">
          <p className="mb-4 text-sm text-slate-600">Signed in somewhere you don't recognise? Sign out everywhere, including this browser.</p>
          <Button variant="danger" onClick={() => setConfirmAll(true)}>Log out of all devices</Button>
        </Card>
      </div>
      <ConfirmDialog open={confirmAll} onClose={() => setConfirmAll(false)} title="Log out everywhere?" danger
                     confirmLabel="Log out everywhere" loading={logoutAll.isPending} onConfirm={() => logoutAll.mutate()}
                     message="Every session, including this one, will end. You'll need to log in again." />
    </>
  );
}

export function NotificationsPage() {
  const [page, setPage] = useState(1);
  const client = useQueryClient();
  const navigate = useNavigate();
  const { data, isLoading, error } = useQuery({
    queryKey: ["notifications", "page", page], queryFn: () => notifications.list({ page, page_size: 20 }),
  });
  const invalidate = () => client.invalidateQueries({ queryKey: ["notifications"] });
  const readAll = useMutation({ mutationFn: notifications.readAll, onSuccess: invalidate });
  const readOne = useMutation({ mutationFn: notifications.read, onSuccess: invalidate });

  return (
    <>
      <PageHeader title="Notifications" actions={data && data.unread_count > 0 && (
        <Button variant="secondary" onClick={() => readAll.mutate()} loading={readAll.isPending}>Mark all as read</Button>
      )} />
      {isLoading ? <Spinner /> : error || !data ? <Alert kind="error">{errorMessage(error)}</Alert> : data.total === 0 ? (
        <Card><EmptyState icon={<Bell className="h-10 w-10" />} title="No notifications">We'll let you know when a run finishes or something needs your attention.</EmptyState></Card>
      ) : (
        <Card>
          <ul className="-my-2 divide-y divide-slate-100">
            {data.items.map((n) => (
              <li key={n.id}>
                <button type="button" className="flex w-full gap-3 py-3 text-left"
                        onClick={() => { if (!n.read_at) readOne.mutate(n.id); if (n.link) navigate(appLink(n.link)); }}>
                  <span className={cx("mt-1.5 h-2 w-2 shrink-0 rounded-full", n.read_at ? "bg-transparent" : "bg-brand-600")} aria-hidden />
                  <span className="flex-1">
                    <span className="block font-medium text-slate-900">{n.title}</span>
                    {n.body && <span className="block text-sm text-slate-600">{n.body}</span>}
                    <span className="block text-xs text-slate-400">{formatRelative(n.created_at)}</span>
                  </span>
                  {!n.read_at && <span className="sr-only">Unread</span>}
                </button>
              </li>
            ))}
          </ul>
          <Pagination page={data.page} pageSize={data.page_size} total={data.total} onPage={setPage} />
        </Card>
      )}
    </>
  );
}

export function NotFoundPage() {
  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center gap-4 px-4 text-center">
      <p className="text-5xl font-bold text-brand-600">404</p>
      <h1 className="text-xl font-semibold">Page not found</h1>
      <p className="text-sm text-slate-500">The page you're looking for doesn't exist or has moved.</p>
      <ButtonLink to="/">Go home</ButtonLink>
    </div>
  );
}
