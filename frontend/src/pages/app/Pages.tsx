import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bell } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useSession, useSetSession } from "../../auth/session";
import { appLink } from "../../components/NotificationBell";
import { ConfirmDialog } from "../../components/Modal";
import { Pagination } from "../../components/Pagination";
import { useToast } from "../../components/Toast";
import { Alert, Button, ButtonLink, Card, cx, EmptyState, PageHeader, Spinner } from "../../components/ui";
import { ApplicationPreferencesForm } from "../../features/ApplicationPreferencesForm";
import { ProfileForm } from "../../features/ProfileForm";
import { ResumeManager } from "../../features/ResumeManager";
import { SearchPreferencesForm } from "../../features/SearchPreferencesForm";
import { formatDate, formatDateTime, formatRelative } from "../../lib/format";
import { errorMessage } from "../../services/api";
import { auth, notifications } from "../../services/endpoints";

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

function NotificationEmailPrefs() {
  const qc = useQueryClient();
  const { data, isLoading, error } = useQuery({ queryKey: ["notifications", "preferences"], queryFn: notifications.preferences });
  const [local, setLocal] = useState<Record<string, boolean>>({});
  useEffect(() => {
    if (data) setLocal(Object.fromEntries(Object.entries(data.types).map(([k, v]) => [k, v.email])));
  }, [data]);
  const save = useMutation({
    mutationFn: () => notifications.updatePreferences({
      types: Object.fromEntries(Object.entries(local).map(([k, email]) => [k, { email }])),
    }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["notifications", "preferences"] }),
  });
  if (isLoading) return <Spinner />;
  if (error || !data) return <Alert kind="error">{errorMessage(error)}</Alert>;
  return (
    <Card title="Email notifications">
      <p className="mb-4 text-sm text-slate-600">In-app notifications always appear in the bell. Choose which events may also email you (when the platform has email enabled).</p>
      <ul className="divide-y divide-slate-100">
        {Object.entries(data.types).map(([key, row]) => (
          <li key={key} className="flex items-start gap-3 py-3">
            <input type="checkbox" className="mt-1" checked={local[key] ?? row.email} aria-label={`Email for ${row.label}`}
                   onChange={(e) => setLocal((n) => ({ ...n, [key]: e.target.checked }))} />
            <span>
              <span className="block font-medium text-slate-900">{row.label}</span>
              <span className="block text-sm text-slate-500">{row.description}</span>
            </span>
          </li>
        ))}
      </ul>
      <div className="mt-4">
        <Button loading={save.isPending} onClick={() => save.mutate()}>Save preferences</Button>
        {save.isSuccess && <span className="ml-3 text-sm text-green-700">Saved.</span>}
        {save.error && <Alert kind="error">{errorMessage(save.error)}</Alert>}
      </div>
    </Card>
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
        <NotificationEmailPrefs />
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
