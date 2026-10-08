import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { useSession } from "../../auth/session";
import { ChipSelect, TextInput, Toggle } from "../../components/form";
import { Pagination } from "../../components/Pagination";
import { Alert, Badge, Button, Card, PageHeader, Spinner, cx } from "../../components/ui";
import { formatDateTime, formatRelative } from "../../lib/format";
import { useDebounced } from "../../lib/useDebounced";
import { errorMessage } from "../../services/api";
import { admin } from "../../services/endpoints";
import type { AdminPlatformSettings, LogLevel, PlatformCms } from "../../types";
import { FilterBar, PAGE_SIZE, Table, Td, UserLink } from "./shared";

const SETTINGS_KEY = ["admin", "settings"] as const;
const TABS = [
  { id: "cms", label: "General & CMS" },
  { id: "smtp", label: "Email & SMTP" },
  { id: "auth", label: "Auth & verification" },
  { id: "notifications", label: "Notifications" },
  { id: "integrations", label: "Integrations" },
  { id: "operations", label: "Operations" },
] as const;

type TabId = (typeof TABS)[number]["id"];

export function AdminSettingsPage() {
  const [tab, setTab] = useState<TabId>("cms");
  const query = useQuery({ queryKey: SETTINGS_KEY, queryFn: admin.settings });
  return (
    <>
      <PageHeader title="Settings" description="CMS, email, auth policy, notifications, and platform operations." />
      <nav className="mb-6 flex flex-wrap gap-2 border-b border-slate-200 pb-2">
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            onClick={() => setTab(t.id)}
            className={cx(
              "rounded-lg px-3 py-1.5 text-sm font-medium transition-colors",
              tab === t.id ? "bg-brand-50 text-brand-700" : "text-slate-600 hover:bg-slate-100",
            )}
          >
            {t.label}
          </button>
        ))}
      </nav>
      {query.isLoading ? <Spinner /> : query.error || !query.data ? (
        <Alert kind="error">{errorMessage(query.error)}</Alert>
      ) : (
        <>
          {tab === "cms" && <CmsTab data={query.data.cms} />}
          {tab === "smtp" && <SmtpTab smtp={query.data.smtp} auth={query.data.auth_email} unverified={query.data.unverified_users} />}
          {tab === "auth" && <AuthTab auth={query.data.auth_email} unverified={query.data.unverified_users} />}
          {tab === "notifications" && <NotificationsTab notifications={query.data.notifications} />}
          {tab === "integrations" && <IntegrationsTab infra={query.data.infrastructure} smtp={query.data.smtp} />}
          {tab === "operations" && <OperationsTab />}
        </>
      )}
    </>
  );
}

function SaveBar({ saving, saved, onSave }: { saving: boolean; saved: boolean; onSave: () => void }) {
  return (
    <div className="mt-4 flex items-center gap-3">
      <Button loading={saving} onClick={onSave}>Save changes</Button>
      {saved && <span className="text-sm text-green-700">Saved.</span>}
    </div>
  );
}

function CmsTab({ data }: { data: PlatformCms }) {
  const qc = useQueryClient();
  const [cms, setCms] = useState(data);
  const [saved, setSaved] = useState(false);
  useEffect(() => setCms(data), [data]);
  const save = useMutation({
    mutationFn: () => admin.updateCms(cms),
    onSuccess: () => { qc.invalidateQueries({ queryKey: SETTINGS_KEY }); qc.invalidateQueries({ queryKey: ["site", "public"] }); setSaved(true); },
  });

  const setBranding = (patch: Partial<PlatformCms["branding"]>) =>
    setCms((c) => ({ ...c, branding: { ...c.branding, ...patch } }));
  const setBanner = (patch: Partial<PlatformCms["banner"]>) =>
    setCms((c) => ({ ...c, banner: { ...c.banner, ...patch } }));
  const setLanding = (patch: Partial<PlatformCms["landing"]>) =>
    setCms((c) => ({ ...c, landing: { ...c.landing, ...patch } }));
  const setLegal = (patch: Partial<PlatformCms["legal"]>) =>
    setCms((c) => ({ ...c, legal: { ...c.legal, ...patch } }));

  return (
    <div className="space-y-6">
      <Card title="Branding">
        <div className="grid gap-4 sm:grid-cols-2">
          <TextInput label="App name" value={cms.branding.app_name} onChange={(v) => setBranding({ app_name: v })} maxLength={120} />
          <TextInput label="Contact email" type="email" value={cms.branding.contact_email} onChange={(v) => setBranding({ contact_email: v })} maxLength={320} />
          <TextInput label="Footer line" className="sm:col-span-2" value={cms.branding.footer_line} onChange={(v) => setBranding({ footer_line: v })} maxLength={500} />
        </div>
      </Card>
      <Card title="Announcement banner">
        <Toggle label="Show banner on public pages" checked={cms.banner.enabled} onChange={(v) => setBanner({ enabled: v })} />
        <div className="mt-3 grid gap-4 sm:grid-cols-2">
          <TextInput label="Message" value={cms.banner.message} onChange={(v) => setBanner({ message: v })} maxLength={500} />
          <label className="block text-sm">
            <span className="mb-1 block font-medium text-slate-700">Tone</span>
            <select className="w-full rounded-lg border border-slate-300 px-3 py-2" value={cms.banner.tone}
                    onChange={(e) => setBanner({ tone: e.target.value as PlatformCms["banner"]["tone"] })}>
              <option value="info">Info</option>
              <option value="warning">Warning</option>
              <option value="success">Success</option>
            </select>
          </label>
        </div>
      </Card>
      <Card title="Landing page — hero">
        <div className="grid gap-4 sm:grid-cols-2">
          <TextInput label="Badge" value={cms.landing.hero_badge} onChange={(v) => setLanding({ hero_badge: v })} maxLength={200} />
          <TextInput label="Primary CTA" value={cms.landing.hero_cta_primary} onChange={(v) => setLanding({ hero_cta_primary: v })} maxLength={80} />
          <TextInput label="Headline" className="sm:col-span-2" value={cms.landing.hero_title} onChange={(v) => setLanding({ hero_title: v })} maxLength={300} />
          <TextInput label="Subheadline" className="sm:col-span-2" value={cms.landing.hero_subtitle} onChange={(v) => setLanding({ hero_subtitle: v })} maxLength={2000} />
        </div>
      </Card>
      <Card title="Features & FAQ" actions={<Button variant="secondary" size="sm" onClick={() => setLanding({
        features: [...cms.landing.features, { icon: "bot", title: "New feature", text: "Description" }],
      })}>Add feature</Button>}>
        {cms.landing.features.map((f, i) => (
          <div key={i} className="mb-4 rounded-lg border border-slate-100 p-3">
            <div className="grid gap-2 sm:grid-cols-3">
              <TextInput label="Icon key" value={f.icon} onChange={(v) => {
                const features = [...cms.landing.features]; features[i] = { ...f, icon: v }; setLanding({ features });
              }} maxLength={32} />
              <TextInput label="Title" className="sm:col-span-2" value={f.title} onChange={(v) => {
                const features = [...cms.landing.features]; features[i] = { ...f, title: v }; setLanding({ features });
              }} maxLength={200} />
              <TextInput label="Text" className="sm:col-span-3" value={f.text} onChange={(v) => {
                const features = [...cms.landing.features]; features[i] = { ...f, text: v }; setLanding({ features });
              }} maxLength={2000} />
            </div>
            <Button variant="ghost" size="sm" className="mt-2" onClick={() => setLanding({ features: cms.landing.features.filter((_, j) => j !== i) })}>Remove</Button>
          </div>
        ))}
        <p className="text-xs text-slate-500">Icon keys: sliders, bot, filter, file-text, bar-chart, shield</p>
      </Card>
      <Card title="Legal pages (Markdown)">
        <label className="mb-3 block text-sm"><span className="font-medium">Privacy</span>
          <textarea className="mt-1 w-full rounded-lg border border-slate-300 p-2 font-mono text-xs" rows={8}
                    value={cms.legal.privacy_md} onChange={(e) => setLegal({ privacy_md: e.target.value })} />
        </label>
        <label className="mb-3 block text-sm"><span className="font-medium">Terms</span>
          <textarea className="mt-1 w-full rounded-lg border border-slate-300 p-2 font-mono text-xs" rows={8}
                    value={cms.legal.terms_md} onChange={(e) => setLegal({ terms_md: e.target.value })} />
        </label>
        <label className="block text-sm"><span className="font-medium">Refund policy</span>
          <textarea className="mt-1 w-full rounded-lg border border-slate-300 p-2 font-mono text-xs" rows={6}
                    value={cms.legal.refund_md} onChange={(e) => setLegal({ refund_md: e.target.value })} />
        </label>
        <p className="mt-2 text-xs text-slate-500">Preview on <Link to="/privacy" className="text-brand-600 underline">/privacy</Link>, <Link to="/terms" className="text-brand-600 underline">/terms</Link>, <Link to="/refund-policy" className="text-brand-600 underline">/refund-policy</Link>.</p>
      </Card>
      <SaveBar saving={save.isPending} saved={saved} onSave={() => { setSaved(false); save.mutate(); }} />
      {save.error && <Alert kind="error">{errorMessage(save.error)}</Alert>}
    </div>
  );
}

function SmtpTab({ smtp, auth, unverified }: { smtp: AdminPlatformSettings["smtp"]; auth: AdminPlatformSettings["auth_email"]; unverified: number }) {
  const qc = useQueryClient();
  const { data: me } = useSession();
  const [host, setHost] = useState(smtp.host);
  const [port, setPort] = useState(String(smtp.port || 587));
  const [username, setUsername] = useState(smtp.username);
  const [from, setFrom] = useState(smtp.from_address);
  const [password, setPassword] = useState("");
  const [enabled, setEnabled] = useState(smtp.enabled);
  const [to, setTo] = useState("");
  const [saved, setSaved] = useState(false);
  useEffect(() => { setHost(smtp.host); setPort(String(smtp.port || 587)); setUsername(smtp.username); setFrom(smtp.from_address); setEnabled(smtp.enabled); }, [smtp]);
  const save = useMutation({
    mutationFn: () => admin.updateSmtp({ enabled, host, port: Number(port), username, password, from_address: from }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: SETTINGS_KEY }); setPassword(""); setSaved(true); },
  });
  const test = useMutation({ mutationFn: () => admin.testEmail(to.trim()) });

  return (
    <div className="space-y-6">
      <Card title="SMTP delivery" actions={<Badge tone={smtp.mode === "smtp" ? "green" : "amber"}>{smtp.mode === "smtp" ? "SMTP active" : "Console only"}</Badge>}>
        <p className="mb-4 text-sm text-slate-600">Source: {smtp.source === "database" ? "saved here" : "environment (.env)"}. Password is never shown after save.</p>
        <Toggle label="Use these SMTP settings" checked={enabled} onChange={setEnabled} />
        <div className="mt-4 grid gap-4 sm:grid-cols-2">
          <TextInput label="Host" value={host} onChange={setHost} maxLength={255} />
          <TextInput label="Port (587=STARTTLS, 465=SSL)" value={port} onChange={setPort} maxLength={5} />
          <TextInput label="Username" value={username} onChange={setUsername} maxLength={320} />
          <TextInput label="From address" value={from} onChange={setFrom} maxLength={320} />
          <TextInput label={smtp.password_configured ? "New password (leave blank to keep)" : "Password"} type="password" value={password} onChange={setPassword} maxLength={200} />
        </div>
        <SaveBar saving={save.isPending} saved={saved} onSave={() => { setSaved(false); save.mutate(); }} />
        {save.error && <Alert kind="error">{errorMessage(save.error)}</Alert>}
      </Card>
      <Card title="Send test email">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
          <div className="flex-1">
            <TextInput label="To" type="email" value={to} onChange={setTo} placeholder={me?.email} maxLength={320} />
          </div>
          <Button variant="secondary" loading={test.isPending} onClick={() => test.mutate()}>Send test</Button>
        </div>
        {test.error && <Alert kind="error">{errorMessage(test.error)}</Alert>}
        {test.data && (
          !test.data.delivered ? <Alert kind="error">Refused: {test.data.error}</Alert>
            : test.data.mode === "console" ? <Alert kind="info">Printed in the API console.</Alert>
            : <Alert kind="success">Accepted by the mail server.</Alert>
        )}
      </Card>
      <Card title="Quick reference">
        <dl className="text-sm divide-y divide-slate-100">
          <Row label="Verification required">{auth.require_verification ? "Yes" : "No"}</Row>
          <Row label="Unverified users">{unverified > 0 ? <Link to="/admin/users?status=unverified" className="text-brand-700 underline">{unverified}</Link> : 0}</Row>
        </dl>
      </Card>
    </div>
  );
}

function AuthTab({ auth, unverified }: { auth: AdminPlatformSettings["auth_email"]; unverified: number }) {
  const qc = useQueryClient();
  const [form, setForm] = useState(auth);
  const [saved, setSaved] = useState(false);
  useEffect(() => setForm(auth), [auth]);
  const save = useMutation({
    mutationFn: () => admin.updateAuthEmail(form),
    onSuccess: () => { qc.invalidateQueries({ queryKey: SETTINGS_KEY }); setSaved(true); },
  });
  return (
    <Card title="Auth & email verification">
      <Toggle label="New accounts must verify email before login" checked={form.require_verification}
              onChange={(v) => setForm((f) => ({ ...f, require_verification: v }))} />
      <div className="mt-4 grid gap-4 sm:grid-cols-2">
        <TextInput label="Verification link lifetime (hours)" value={String(form.verification_hours)}
                   onChange={(v) => setForm((f) => ({ ...f, verification_hours: Number(v) || 24 }))} maxLength={3} />
        <TextInput label="Password reset link (minutes)" value={String(form.password_reset_minutes)}
                   onChange={(v) => setForm((f) => ({ ...f, password_reset_minutes: Number(v) || 60 }))} maxLength={4} />
        <TextInput label="Frontend URL for email links" className="sm:col-span-2" value={form.frontend_url}
                   onChange={(v) => setForm((f) => ({ ...f, frontend_url: v }))} maxLength={512} />
      </div>
      <p className="mt-3 text-sm text-slate-600">Transactional emails (verify, reset, duplicate registration) always send when SMTP is configured. Unverified accounts: {unverified}.</p>
      <SaveBar saving={save.isPending} saved={saved} onSave={() => { setSaved(false); save.mutate(); }} />
      {save.error && <Alert kind="error">{errorMessage(save.error)}</Alert>}
    </Card>
  );
}

function NotificationsTab({ notifications }: { notifications: AdminPlatformSettings["notifications"] }) {
  const qc = useQueryClient();
  const [local, setLocal] = useState(notifications);
  const [saved, setSaved] = useState(false);
  useEffect(() => setLocal(notifications), [notifications]);
  const save = useMutation({
    mutationFn: () => admin.updateNotifications({
      types: Object.fromEntries(Object.entries(local).map(([k, v]) => [k, { email: v.email }])),
    }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: SETTINGS_KEY }); setSaved(true); },
  });
  return (
    <Card title="Email notifications">
      <p className="mb-4 text-sm text-slate-600">In-app notifications are always on. Enable email per event when SMTP is configured and the user is verified.</p>
      <Table head={["Event", "Description", "Email"]}>
        {Object.entries(local).map(([key, row]) => (
          <tr key={key}>
            <Td><p className="font-medium">{row.label}</p><p className="text-xs text-slate-500">{key}</p></Td>
            <Td className="max-w-md text-sm text-slate-600">{row.description}</Td>
            <Td>
              <input type="checkbox" checked={row.email} aria-label={`Email for ${key}`}
                     onChange={(e) => setLocal((n) => ({ ...n, [key]: { ...row, email: e.target.checked } }))} />
            </Td>
          </tr>
        ))}
      </Table>
      <SaveBar saving={save.isPending} saved={saved} onSave={() => { setSaved(false); save.mutate(); }} />
      {save.error && <Alert kind="error">{errorMessage(save.error)}</Alert>}
    </Card>
  );
}

function IntegrationsTab({ infra, smtp }: { infra: AdminPlatformSettings["infrastructure"]; smtp: AdminPlatformSettings["smtp"] }) {
  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <Card title="Infrastructure (read-only)">
        <dl className="divide-y divide-slate-100 text-sm">
          <Row label="Environment">{infra.app_env}</Row>
          <Row label="API version">{infra.app_version}</Row>
          <Row label="Database">{infra.database}</Row>
          <Row label="Redis configured">{infra.redis_url_set ? "Yes" : "No"}</Row>
          <Row label="CORS origins">{infra.cors_origins.join(", ") || "—"}</Row>
          <Row label="Payment provider">{infra.payment_provider}</Row>
          <Row label="Payment keys">{infra.payment_keys_configured ? "Set in .env" : "Not set"}</Row>
        </dl>
        <p className="mt-3 text-xs text-slate-500">Change secrets via <code>.env</code> and restart the API.</p>
      </Card>
      <Card title="Email status">
        <dl className="divide-y divide-slate-100 text-sm">
          <Row label="Mode">{smtp.mode}</Row>
          <Row label="Host">{smtp.host || "—"}</Row>
          <Row label="From">{smtp.from_address}</Row>
        </dl>
      </Card>
    </div>
  );
}

function OperationsTab() {
  return (
    <div className="space-y-6">
      <Workers />
      <Logs />
      <AuditLog />
    </div>
  );
}

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex justify-between gap-4 py-1.5">
      <dt className="text-slate-500">{label}</dt>
      <dd className="text-right font-medium text-slate-800">{children}</dd>
    </div>
  );
}

function Workers() {
  const { data, isLoading, error } = useQuery({ queryKey: ["admin", "workers"], queryFn: admin.workers, refetchInterval: 30_000 });
  if (isLoading) return <Card title="Workers"><Spinner /></Card>;
  if (error || !data) return <Alert kind="error">{errorMessage(error)}</Alert>;
  const { celery, devices } = data;
  return (
    <div className="grid gap-6 lg:grid-cols-3">
      <Card title="Background workers">
        <div className="flex items-center gap-2 text-sm">
          <span className="text-slate-600">Redis</span>
          <Badge tone={celery.broker === "ok" ? "green" : "red"}>{celery.broker === "ok" ? "Connected" : "Unreachable"}</Badge>
        </div>
        {celery.workers.length ? (
          <ul className="mt-3 space-y-1 text-sm text-slate-700">{celery.workers.map((w) => <li key={w}>{w}</li>)}</ul>
        ) : (
          <p className="mt-3 text-sm text-slate-500">No Celery worker answered.</p>
        )}
      </Card>
      <Card title={`Desktop agents (${devices.filter((d) => d.online).length} online)`} className="lg:col-span-2">
        {devices.length === 0 ? <p className="text-sm text-slate-500">No computers are paired.</p> : (
          <Table head={["Computer", "User", "Version", "Last seen", ""]}>
            {devices.map((d) => (
              <tr key={d.id}>
                <Td><p className="font-medium text-slate-900">{d.name || "Unnamed"}</p><p className="text-xs text-slate-500">{d.platform}</p></Td>
                <Td><UserLink id={d.user_id} email={d.user_email} /></Td>
                <Td>{d.agent_version || "\u2014"}</Td>
                <Td className="whitespace-nowrap">{d.last_seen_at ? formatRelative(d.last_seen_at) : "Never"}</Td>
                <Td>
                  <div className="flex gap-1">
                    <Badge tone={d.online ? "green" : "slate"}>{d.online ? "Online" : "Offline"}</Badge>
                    {d.running && <Badge tone="blue">Running</Badge>}
                  </div>
                </Td>
              </tr>
            ))}
          </Table>
        )}
      </Card>
    </div>
  );
}

const LEVELS: LogLevel[] = ["error", "warning", "info"];
const LEVEL_TONES = { error: "red", warning: "amber", info: "slate" } as const;
const LEVEL_LABELS: Record<LogLevel, string> = { error: "Errors", warning: "Warnings", info: "Info" };

function Logs() {
  const [levels, setLevels] = useState<LogLevel[]>(["error", "warning"]);
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const search = useDebounced(q.trim());
  const query = { level: levels.length ? levels : LEVELS, q: search || undefined, page, page_size: PAGE_SIZE };
  const { data, isLoading, isFetching, error } = useQuery({
    queryKey: ["admin", "logs", query], queryFn: () => admin.logs(query), placeholderData: keepPreviousData,
  });
  const byLabel = Object.fromEntries(LEVELS.map((l) => [LEVEL_LABELS[l], l])) as Record<string, LogLevel>;

  return (
    <Card title="Automation logs">
      <FilterBar>
        <div className="sm:col-span-2">
          <ChipSelect label="Level" options={LEVELS.map((l) => LEVEL_LABELS[l])} value={levels.map((l) => LEVEL_LABELS[l])}
                      onChange={(v) => { setLevels(v.map((label) => byLabel[label])); setPage(1); }} />
        </div>
        <div className="sm:col-span-2">
          <TextInput label="Search messages" value={q} onChange={(v) => { setQ(v); setPage(1); }} maxLength={200} />
        </div>
      </FilterBar>
      {isLoading ? <Spinner /> : error || !data ? <Alert kind="error">{errorMessage(error)}</Alert> : data.total === 0 ? (
        <p className="text-sm text-slate-500">No log lines match.</p>
      ) : (
        <>
          <Table head={["Time", "Level", "User", "Message"]} dim={isFetching}>
            {data.items.map((l) => (
              <tr key={`${l.run_id}-${l.ts}-${l.event}`}>
                <Td className="whitespace-nowrap">{formatDateTime(l.ts)}</Td>
                <Td><Badge tone={LEVEL_TONES[l.level] ?? "slate"}>{l.level}</Badge></Td>
                <Td><UserLink id={l.user_id} email={l.user_email} /></Td>
                <Td className="max-w-xl break-words">{l.message}</Td>
              </tr>
            ))}
          </Table>
          <Pagination page={data.page} pageSize={data.page_size} total={data.total} onPage={setPage} />
        </>
      )}
    </Card>
  );
}

const ACTION_LABELS: Record<string, string> = {
  "user.update": "Changed account", "plan.grant": "Gave a plan", "plan.revoke": "Ended a complimentary plan",
  "plan.update": "Edited a plan", "run.stop": "Stopped a run", "email.test": "Sent a test email",
  "user.verify": "Marked email verified", "user.resend_verification": "Resent verification email",
  "settings.cms": "Updated CMS", "settings.smtp": "Updated SMTP", "settings.auth_email": "Updated auth email",
  "settings.notifications": "Updated notification toggles",
};

function describe(details: Record<string, unknown>): string {
  return Object.entries(details)
    .filter(([, v]) => v !== "" && v !== null)
    .map(([k, v]) => Array.isArray(v) && v.length === 2 && k !== "plans"
      ? `${k}: ${JSON.stringify(v[0])} \u2192 ${JSON.stringify(v[1])}` : `${k}: ${typeof v === "string" ? v : JSON.stringify(v)}`)
    .join("; ");
}

function AuditLog() {
  const [page, setPage] = useState(1);
  const { data, isLoading, error } = useQuery({
    queryKey: ["admin", "audit", page], queryFn: () => admin.audit({ page, page_size: PAGE_SIZE }), placeholderData: keepPreviousData,
  });
  return (
    <Card title="Admin audit log">
      {isLoading ? <Spinner /> : error || !data ? <Alert kind="error">{errorMessage(error)}</Alert> : data.total === 0 ? (
        <p className="text-sm text-slate-500">No admin changes yet.</p>
      ) : (
        <>
          <Table head={["Time", "Admin", "Action", "Target", "Details"]}>
            {data.items.map((a) => (
              <tr key={a.id}>
                <Td className="whitespace-nowrap">{formatDateTime(a.created_at)}</Td>
                <Td>{a.admin_email}</Td>
                <Td>{ACTION_LABELS[a.action] ?? a.action}</Td>
                <Td>{a.target_user_id ? <UserLink id={a.target_user_id} email={a.target} /> : a.target}</Td>
                <Td className="max-w-md break-words text-xs text-slate-500">{describe(a.details)}</Td>
              </tr>
            ))}
          </Table>
          <Pagination page={data.page} pageSize={data.page_size} total={data.total} onPage={setPage} />
        </>
      )}
    </Card>
  );
}
