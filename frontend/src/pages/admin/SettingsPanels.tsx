import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { useSession } from "../../auth/session";
import { ChipSelect, TextArea, TextInput, Toggle } from "../../components/form";
import { ConfirmDialog, Modal } from "../../components/Modal";
import { Pagination } from "../../components/Pagination";
import { Alert, Badge, Button, Card, PageHeader, Spinner, cx } from "../../components/ui";
import { formatDateTime, formatRelative } from "../../lib/format";
import { useDebounced } from "../../lib/useDebounced";
import { agentServerUrl } from "../../lib/config";
import { ApiError, errorMessage } from "../../services/api";
import { admin } from "../../services/endpoints";
import type { AdminPlatformSettings, AuthEmailTemplate, EmailTemplates, EventNotificationTemplate, LogLevel, PlatformCms } from "../../types";
import { FilterBar, PAGE_SIZE, Table, Td, UserLink } from "./shared";

const SETTINGS_KEY = ["admin", "settings"] as const;
const TABS = [
  { id: "cms", label: "General & CMS" },
  { id: "smtp", label: "Email & SMTP" },
  { id: "auth", label: "Auth & verification" },
  { id: "notifications", label: "Notifications" },
  { id: "templates", label: "Templates" },
  { id: "ai", label: "AI" },
  { id: "payments", label: "Payments" },
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
      {query.isPending ? <Spinner /> : query.error ? (
        <Alert kind="error">
          {errorMessage(query.error)}
          {query.error instanceof ApiError && query.error.status > 0 && (
            <span className="mt-1 block text-xs text-slate-500">HTTP {query.error.status} · {query.error.code}</span>
          )}
        </Alert>
      ) : !query.data ? (
        <Alert kind="error">Settings data was empty. Restart the API after pulling the latest code.</Alert>
      ) : (
        <>
          {tab === "cms" && <CmsTab data={query.data.cms} />}
          {tab === "smtp" && <SmtpTab smtp={query.data.smtp} auth={query.data.auth_email} unverified={query.data.unverified_users} />}
          {tab === "auth" && <AuthTab auth={query.data.auth_email} unverified={query.data.unverified_users} />}
          {tab === "notifications" && <NotificationsTab notifications={query.data.notifications} />}
          {tab === "templates" && (
            <TemplatesTab
              templates={query.data.email_templates ?? { auth: {}, events: {} }}
              notifications={query.data.notifications}
            />
          )}
          {tab === "ai" && <AiTab ai={query.data.ai} />}
          {tab === "payments" && <PaymentsTab payments={query.data.payments} />}
          {tab === "integrations" && <IntegrationsTab infra={query.data.infrastructure} smtp={query.data.smtp} ai={query.data.ai} payments={query.data.payments} />}
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
          <TextInput
            label="Password"
            type="password"
            value={password}
            onChange={setPassword}
            maxLength={200}
            configured={smtp.password_configured}
            configuredMessage="Password saved"
            autoComplete="off"
          />
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
      <p className="mb-4 text-sm text-slate-600">
        In-app notifications are always on. Enable email per event when SMTP is configured and the user is verified.
        Edit subject and body copy on the Templates tab.
      </p>
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

const TEMPLATE_PLACEHOLDER_HINT =
  "Auth placeholders: {app_name}, {link}, {verification_hours}, {password_reset_minutes}, {institute_name}.";

const AUTH_TEMPLATE_LABELS: Record<string, string> = {
  verify_email: "Verify email",
  password_reset: "Password reset",
  account_exists: "Account already exists",
  institute_invite: "Institute invitation",
};

/** Per-event placeholders shown in the Templates editor (merged with global {app_name}, {link_url}). */
const EVENT_TEMPLATE_PLACEHOLDERS: Record<string, string> = {
  run_finished: "{title}, {message}",
  limit_reached: "{message}",
  plan_active: "{plan_name}, {message}",
  payment_failed: "{plan_name}, {message}",
  plan_ended: "{plan_name}, {message}",
  plan_cancelled: "{plan_name}, {message}",
  plan_granted: "{plan_name}, {message}",
  admin_broadcast: "{title}, {body}",
  institute_invite: "{institute_name}, {message}",
  institute_invite_accepted: "{candidate_email}, {message}",
  partner_commission: "{message}",
  job_applied: "{job_title}, {company}, {location}, {message}",
  daily_report: "{report_date}, {message}, {summary}, {applied_count}, {failed_count}, {skipped_count}, {external_count}",
};

function mergeEmailTemplatesFromServer(
  templates: EmailTemplates,
  notifications: AdminPlatformSettings["notifications"],
): EmailTemplates {
  const events = { ...templates.events };
  for (const key of Object.keys(notifications)) {
    if (!events[key]) {
      events[key] = {
        in_app_title: "",
        in_app_body: "",
        email_subject: "",
        email_body: "",
        email_html: "",
      };
    }
  }
  return { auth: { ...templates.auth }, events };
}

type TemplateModalMode = "view" | "edit" | "add";

function templatePreview(subject: string, max = 72) {
  const t = subject.trim();
  return t.length <= max ? t : `${t.slice(0, max)}…`;
}

function TemplateActionButtons({
  onView,
  onEdit,
  onDelete,
}: {
  onView: () => void;
  onEdit: () => void;
  onDelete: () => void;
}) {
  return (
    <div className="flex flex-wrap gap-1">
      <Button variant="secondary" className="!px-2 !py-1 text-xs" onClick={onView}>View</Button>
      <Button variant="secondary" className="!px-2 !py-1 text-xs" onClick={onEdit}>Edit</Button>
      <Button variant="danger" className="!px-2 !py-1 text-xs" onClick={onDelete}>Delete</Button>
    </div>
  );
}

function TemplatesTab({
  templates,
  notifications,
}: {
  templates: EmailTemplates;
  notifications: AdminPlatformSettings["notifications"];
}) {
  const qc = useQueryClient();
  const { data: session } = useSession();
  const [local, setLocal] = useState(templates);
  const [saved, setSaved] = useState(false);
  const serverDefaults = useRef(templates);
  useEffect(() => {
    const merged = mergeEmailTemplatesFromServer(templates, notifications);
    serverDefaults.current = merged;
    setLocal(merged);
  }, [templates, notifications]);

  const [authModal, setAuthModal] = useState<{ open: boolean; mode: TemplateModalMode; key: string; draft: AuthEmailTemplate }>({
    open: false, mode: "view", key: "", draft: { subject: "", body: "", html: "" },
  });
  const [eventModal, setEventModal] = useState<{
    open: boolean; mode: TemplateModalMode; key: string; draft: EventNotificationTemplate;
  }>({ open: false, mode: "view", key: "", draft: { in_app_title: "", in_app_body: "", email_subject: "", email_body: "", email_html: "" } });
  const [deleteTarget, setDeleteTarget] = useState<{ kind: "auth" | "event"; key: string } | null>(null);

  const save = useMutation({
    mutationFn: () => admin.updateEmailTemplates(local),
    onSuccess: () => { qc.invalidateQueries({ queryKey: SETTINGS_KEY }); setSaved(true); },
  });
  const testAuth = useMutation({
    mutationFn: (kind: string) => admin.testEmailTemplate({ kind, to: session?.email }),
  });

  const openAuth = (mode: TemplateModalMode, key: string) => {
    const draft = { ...local.auth[key] };
    setAuthModal({ open: true, mode, key, draft });
  };

  const openAuthAdd = () => {
    const firstKey = Object.keys(local.auth)[0] ?? "verify_email";
    setAuthModal({
      open: true,
      mode: "add",
      key: firstKey,
      draft: { subject: "", body: "", html: "" },
    });
  };

  const saveAuthModal = () => {
    const { key, draft } = authModal;
    setLocal((t) => ({ ...t, auth: { ...t.auth, [key]: { ...draft } } }));
    setAuthModal((m) => ({ ...m, open: false }));
  };

  const eventTemplateFor = (key: string): EventNotificationTemplate =>
    local.events[key] ?? serverDefaults.current.events[key] ?? {
      in_app_title: "", in_app_body: "", email_subject: "", email_body: "", email_html: "",
    };

  const openEvent = (mode: TemplateModalMode, key: string) => {
    setEventModal({ open: true, mode, key, draft: { ...eventTemplateFor(key) } });
  };

  const openEventAdd = () => {
    const firstKey = Object.keys(notifications)[0] ?? "";
    const src = local.events[firstKey] ?? {
      in_app_title: "", in_app_body: "", email_subject: "", email_body: "", email_html: "",
    };
    setEventModal({ open: true, mode: "add", key: firstKey, draft: { ...src, in_app_title: "", in_app_body: "", email_subject: "", email_body: "", email_html: "" } });
  };

  const saveEventModal = () => {
    const { key, draft } = eventModal;
    setLocal((t) => ({ ...t, events: { ...t.events, [key]: { ...draft } } }));
    setEventModal((m) => ({ ...m, open: false }));
  };

  const confirmDelete = () => {
    if (!deleteTarget) return;
    const defaults = serverDefaults.current;
    if (deleteTarget.kind === "auth") {
      const key = deleteTarget.key;
      setLocal((t) => ({
        ...t,
        auth: { ...t.auth, [key]: { ...(defaults.auth[key] ?? { subject: "", body: "", html: "" }) } },
      }));
    } else {
      const key = deleteTarget.key;
      setLocal((t) => ({
        ...t,
        events: { ...t.events, [key]: { ...(defaults.events[key] ?? t.events[key]) } },
      }));
    }
    setDeleteTarget(null);
  };

  const authReadOnly = authModal.mode === "view";

  return (
    <div className="space-y-6">
      <Card
        title="Auth email templates"
        actions={<Button onClick={openAuthAdd}>Add</Button>}
      >
        <p className="mb-4 text-sm text-slate-600">{TEMPLATE_PLACEHOLDER_HINT}</p>
        <Table head={["Template", "Subject", "Actions"]}>
          {Object.entries(local.auth).map(([key, row]) => (
            <tr key={key}>
              <Td>
                <p className="font-medium text-slate-900">{AUTH_TEMPLATE_LABELS[key] ?? key.replace(/_/g, " ")}</p>
                <p className="text-xs text-slate-500">{key}</p>
              </Td>
              <Td className="max-w-md text-slate-600">{templatePreview(row.subject) || "—"}</Td>
              <Td>
                <TemplateActionButtons
                  onView={() => openAuth("view", key)}
                  onEdit={() => openAuth("edit", key)}
                  onDelete={() => setDeleteTarget({ kind: "auth", key })}
                />
              </Td>
            </tr>
          ))}
        </Table>
        {testAuth.data && (
          <div className="mt-4">
            <Alert kind={testAuth.data.delivered ? "success" : "error"}>
              {testAuth.data.delivered ? "Test email sent." : testAuth.data.error || "Delivery failed."}
            </Alert>
          </div>
        )}
        {testAuth.error && <div className="mt-4"><Alert kind="error">{errorMessage(testAuth.error)}</Alert></div>}
      </Card>

      <Card
        title="Notification event copy"
        actions={<Button onClick={openEventAdd}>Add</Button>}
      >
        <p className="mb-4 text-sm text-slate-600">
          In-app and email text per event. Global: {"{app_name}"}, {"{link_url}"}. Each event has its own fields — open View/Edit to see placeholders for that row.
        </p>
        <Table head={["Event", "In-app title", "Actions"]}>
          {Object.entries(notifications).map(([key, meta]) => (
            <tr key={key}>
              <Td>
                <p className="font-medium text-slate-900">{meta.label}</p>
                <p className="text-xs text-slate-500">{key}</p>
              </Td>
              <Td className="max-w-md text-slate-600">{templatePreview(local.events[key]?.in_app_title ?? "") || "—"}</Td>
              <Td>
                <TemplateActionButtons
                  onView={() => openEvent("view", key)}
                  onEdit={() => openEvent("edit", key)}
                  onDelete={() => setDeleteTarget({ kind: "event", key })}
                />
              </Td>
            </tr>
          ))}
        </Table>
      </Card>

      <SaveBar saving={save.isPending} saved={saved} onSave={() => { setSaved(false); save.mutate(); }} />
      {save.error && <Alert kind="error">{errorMessage(save.error)}</Alert>}

      <Modal
        open={authModal.open}
        wide
        onClose={() => setAuthModal((m) => ({ ...m, open: false }))}
        title={
          authModal.mode === "view" ? "View auth template"
            : authModal.mode === "add" ? "Add auth template"
              : "Edit auth template"
        }
        footer={
          authReadOnly ? (
            <Button variant="secondary" onClick={() => setAuthModal((m) => ({ ...m, open: false }))}>Close</Button>
          ) : (
            <>
              <Button variant="secondary" onClick={() => setAuthModal((m) => ({ ...m, open: false }))}>Cancel</Button>
              <Button onClick={saveAuthModal}>{authModal.mode === "add" ? "Add" : "Save"}</Button>
            </>
          )
        }
      >
        {authModal.mode === "add" ? (
          <label className="mb-3 block text-sm">
            <span className="mb-1 block font-medium text-slate-700">Template</span>
            <select
              className="w-full rounded-lg border border-slate-300 px-3 py-2"
              value={authModal.key}
              onChange={(e) => {
                const key = e.target.value;
                setAuthModal((m) => ({ ...m, key, draft: { subject: "", body: "", html: "" } }));
              }}
            >
              {Object.keys(local.auth).map((k) => (
                <option key={k} value={k}>{AUTH_TEMPLATE_LABELS[k] ?? k}</option>
              ))}
            </select>
          </label>
        ) : (
          <p className="mb-3 text-sm text-slate-600">
            <span className="font-medium text-slate-800">{AUTH_TEMPLATE_LABELS[authModal.key] ?? authModal.key}</span>
            <span className="text-slate-400"> · {authModal.key}</span>
          </p>
        )}
        <div className="grid gap-3">
          <TextInput label="Subject" value={authModal.draft.subject} readOnly={authReadOnly}
                     onChange={(v) => setAuthModal((m) => ({ ...m, draft: { ...m.draft, subject: v } }))} maxLength={500} />
          <TextArea label="Plain body" value={authModal.draft.body} readOnly={authReadOnly} rows={8}
                    onChange={(v) => setAuthModal((m) => ({ ...m, draft: { ...m.draft, body: v } }))} />
          <TextArea label="HTML (optional)" value={authModal.draft.html} readOnly={authReadOnly} rows={4}
                    onChange={(v) => setAuthModal((m) => ({ ...m, draft: { ...m.draft, html: v } }))} />
          {!authReadOnly && (
            <Button variant="secondary" loading={testAuth.isPending} onClick={() => testAuth.mutate(authModal.key)}>
              Send test email
            </Button>
          )}
        </div>
      </Modal>

      <Modal
        open={eventModal.open}
        wide
        onClose={() => setEventModal((m) => ({ ...m, open: false }))}
        title={
          eventModal.mode === "view" ? "View event template"
            : eventModal.mode === "add" ? "Add event template"
              : "Edit event template"
        }
        footer={
          eventModal.mode === "view" ? (
            <Button variant="secondary" onClick={() => setEventModal((m) => ({ ...m, open: false }))}>Close</Button>
          ) : (
            <>
              <Button variant="secondary" onClick={() => setEventModal((m) => ({ ...m, open: false }))}>Cancel</Button>
              <Button onClick={saveEventModal}>{eventModal.mode === "add" ? "Add" : "Save"}</Button>
            </>
          )
        }
      >
        {eventModal.mode === "add" ? (
          <label className="mb-3 block text-sm">
            <span className="mb-1 block font-medium text-slate-700">Event</span>
            <select
              className="w-full rounded-lg border border-slate-300 px-3 py-2"
              value={eventModal.key}
              onChange={(e) => {
                const key = e.target.value;
                setEventModal((m) => ({ ...m, key, draft: { ...eventTemplateFor(key) } }));
              }}
            >
              {Object.entries(notifications).map(([k, meta]) => (
                <option key={k} value={k}>{meta.label}</option>
              ))}
            </select>
          </label>
        ) : (
          <p className="mb-3 text-sm text-slate-600">
            <span className="font-medium text-slate-800">{notifications[eventModal.key]?.label ?? eventModal.key}</span>
            {notifications[eventModal.key]?.description && (
              <span className="mt-1 block text-xs text-slate-500">{notifications[eventModal.key].description}</span>
            )}
            {EVENT_TEMPLATE_PLACEHOLDERS[eventModal.key] && (
              <span className="mt-2 block text-xs text-slate-500">
                Placeholders: {EVENT_TEMPLATE_PLACEHOLDERS[eventModal.key]}, {"{app_name}"}, {"{link_url}"}
              </span>
            )}
          </p>
        )}
        <div className="grid gap-3">
          <TextInput label="In-app title" value={eventModal.draft.in_app_title} readOnly={eventModal.mode === "view"}
                     onChange={(v) => setEventModal((m) => ({ ...m, draft: { ...m.draft, in_app_title: v } }))} maxLength={500} />
          <TextArea label="In-app body" value={eventModal.draft.in_app_body} readOnly={eventModal.mode === "view"} rows={3}
                    onChange={(v) => setEventModal((m) => ({ ...m, draft: { ...m.draft, in_app_body: v } }))} />
          <TextInput label="Email subject" value={eventModal.draft.email_subject} readOnly={eventModal.mode === "view"}
                     onChange={(v) => setEventModal((m) => ({ ...m, draft: { ...m.draft, email_subject: v } }))} maxLength={500} />
          <TextArea label="Email body" value={eventModal.draft.email_body} readOnly={eventModal.mode === "view"} rows={4}
                    onChange={(v) => setEventModal((m) => ({ ...m, draft: { ...m.draft, email_body: v } }))} />
          <TextArea label="Email HTML (optional)" value={eventModal.draft.email_html} readOnly={eventModal.mode === "view"} rows={3}
                    onChange={(v) => setEventModal((m) => ({ ...m, draft: { ...m.draft, email_html: v } }))} />
        </div>
      </Modal>

      <ConfirmDialog
        open={deleteTarget !== null}
        onClose={() => setDeleteTarget(null)}
        title="Reset template?"
        danger
        confirmLabel="Reset"
        onConfirm={confirmDelete}
        message="This restores the template text to what was last loaded from the server. Click Save changes on this page to persist."
      />
    </div>
  );
}

function BroadcastNotificationsCard() {
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [link, setLink] = useState("/app/notifications");
  const [userQuery, setUserQuery] = useState("");
  const [selected, setSelected] = useState<{ id: string; email: string }[]>([]);
  const [confirm, setConfirm] = useState(false);
  const search = useDebounced(userQuery.trim());
  const { data: usersPage } = useQuery({
    queryKey: ["admin", "users", "broadcast", search],
    queryFn: () => admin.users({ q: search || undefined, page: 1, page_size: 8 }),
    enabled: search.length >= 2,
  });
  const send = useMutation({
    mutationFn: () => admin.broadcastNotifications({
      title: title.trim(),
      body: body.trim(),
      link: link.trim(),
      user_ids: selected.map((u) => u.id),
    }),
    onSuccess: () => { setConfirm(false); setTitle(""); setBody(""); setSelected([]); },
  });

  const addUser = (u: { id: string; email: string }) => {
    if (selected.some((s) => s.id === u.id)) return;
    setSelected((s) => [...s, u]);
  };

  return (
    <Card title="Broadcast notification">
      <p className="mb-4 text-sm text-slate-600">Send an in-app announcement (and email if enabled) to selected users.</p>
      <div className="grid max-w-xl gap-3">
        <TextInput label="Title" value={title} onChange={setTitle} maxLength={255} />
        <TextArea label="Message" value={body} onChange={setBody} rows={4} maxLength={5000} />
        <TextInput label="In-app link" value={link} onChange={setLink} maxLength={512} hint="Must start with / e.g. /app/billing" />
        <TextInput label="Find users by email" value={userQuery} onChange={setUserQuery} maxLength={200} />
        {usersPage?.items.length ? (
          <ul className="rounded-lg border border-slate-200 text-sm">
            {usersPage.items.map((u) => (
              <li key={u.id}>
                <button type="button" className="block w-full px-3 py-2 text-left hover:bg-slate-50" onClick={() => addUser({ id: u.id, email: u.email })}>
                  {u.email}
                </button>
              </li>
            ))}
          </ul>
        ) : null}
        {selected.length > 0 && (
          <p className="text-sm text-slate-600">Recipients: {selected.map((u) => u.email).join(", ")}</p>
        )}
        <Button disabled={!title.trim() || selected.length === 0} onClick={() => setConfirm(true)}>Send broadcast</Button>
      </div>
      {send.data && <Alert kind="success">Sent to {send.data.sent} user(s).</Alert>}
      {send.error && <Alert kind="error">{errorMessage(send.error)}</Alert>}
      <ConfirmDialog open={confirm} onClose={() => setConfirm(false)} title="Send broadcast?"
                     confirmLabel="Send" loading={send.isPending}
                     onConfirm={() => send.mutate()}
                     message={`This will notify ${selected.length} user(s) in-app.`} />
    </Card>
  );
}

function AiTab({ ai }: { ai: AdminPlatformSettings["ai"] }) {
  const qc = useQueryClient();
  const [enabled, setEnabled] = useState(ai.enabled);
  const [provider, setProvider] = useState(ai.provider);
  const [baseUrl, setBaseUrl] = useState(ai.base_url);
  const [apiKey, setApiKey] = useState("");
  const [apiKeyConfigured, setApiKeyConfigured] = useState(ai.api_key_configured);
  const [fast, setFast] = useState(ai.models.fast);
  const [strong, setStrong] = useState(ai.models.strong);
  const [embedding, setEmbedding] = useState(ai.models.embedding);
  const [featApp, setFeatApp] = useState(ai.features.applications);
  const [featResume, setFeatResume] = useState(ai.features.resume);
  const [saved, setSaved] = useState(false);
  useEffect(() => {
    setEnabled(ai.enabled);
    setProvider(ai.provider);
    setBaseUrl(ai.base_url);
    setFast(ai.models.fast);
    setStrong(ai.models.strong);
    setEmbedding(ai.models.embedding);
    setFeatApp(ai.features.applications);
    setFeatResume(ai.features.resume);
    setApiKeyConfigured(ai.api_key_configured);
  }, [ai]);
  const save = useMutation({
    mutationFn: () => admin.updateAi({
      enabled, provider, base_url: baseUrl, api_key: apiKey,
      models: { fast, strong, embedding },
      features: { applications: featApp, resume: featResume },
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: SETTINGS_KEY });
      if (apiKey.trim()) setApiKeyConfigured(true);
      setApiKey("");
      setSaved(true);
    },
  });
  const test = useMutation({ mutationFn: () => admin.testAi() });

  return (
    <div className="space-y-6">
      <Card title="Platform AI" actions={<Badge tone={ai.ready ? "green" : "amber"}>{ai.ready ? "Ready" : "Not configured"}</Badge>}>
        <p className="mb-4 text-sm text-slate-600">API keys are encrypted and never shown to users or the desktop agent. Users opt in per feature in their preferences.</p>
        <Toggle label="Enable platform AI" checked={enabled} onChange={setEnabled} />
        <div className="mt-4 grid gap-4 sm:grid-cols-2">
          <label className="block text-sm">
            <span className="mb-1 block font-medium text-slate-700">Provider</span>
            <select className="w-full rounded-lg border border-slate-300 px-3 py-2" value={provider} onChange={(e) => setProvider(e.target.value)}>
              <option value="openai">OpenAI</option>
              <option value="openai_compatible">OpenAI-compatible</option>
              <option value="gemini">Google Gemini</option>
            </select>
          </label>
          <TextInput label="Base URL (OpenAI-compatible)" value={baseUrl} onChange={setBaseUrl} maxLength={512} />
          <TextInput
            label="API key"
            type="password"
            value={apiKey}
            onChange={setApiKey}
            maxLength={500}
            configured={apiKeyConfigured}
            configuredMessage="Key uploaded"
            autoComplete="off"
          />
          <TextInput label="Fast model (Q&A, scoring)" value={fast} onChange={setFast} maxLength={120} />
          <TextInput label="Strong model (resume tailor)" value={strong} onChange={setStrong} maxLength={120} />
          <TextInput label="Embedding model" value={embedding} onChange={setEmbedding} maxLength={120} />
        </div>
        <div className="mt-4 flex flex-wrap gap-4">
          <Toggle label="Application Q&A" checked={featApp} onChange={setFeatApp} />
          <Toggle label="Resume AI" checked={featResume} onChange={setFeatResume} />
        </div>
        <SaveBar saving={save.isPending} saved={saved} onSave={() => { setSaved(false); save.mutate(); }} />
        {save.error && <Alert kind="error">{errorMessage(save.error)}</Alert>}
      </Card>
      <Card title="Test AI connection">
        <Button variant="secondary" loading={test.isPending} disabled={!apiKeyConfigured && !apiKey} onClick={() => test.mutate()}>Run test</Button>
        {test.data && (
          test.data.ok ? <Alert kind="success">Provider replied: {test.data.reply}</Alert>
            : <Alert kind="error">Unexpected reply: {test.data.reply}</Alert>
        )}
        {test.error && <Alert kind="error">{errorMessage(test.error)}</Alert>}
      </Card>
    </div>
  );
}

function PaymentsTab({ payments }: { payments: AdminPlatformSettings["payments"] }) {
  const qc = useQueryClient();
  const webhookUrl = `${agentServerUrl()}/api/billing/webhook/razorpay`;
  const [provider, setProvider] = useState<"null" | "razorpay">(payments.provider);
  const [keyId, setKeyId] = useState(payments.key_id);
  const [keySecret, setKeySecret] = useState("");
  const [webhookSecret, setWebhookSecret] = useState("");
  const [saved, setSaved] = useState(false);
  useEffect(() => {
    setProvider(payments.provider);
    setKeyId(payments.key_id);
  }, [payments]);
  const save = useMutation({
    mutationFn: () => admin.updatePayments({
      provider,
      key_id: keyId,
      key_secret: keySecret || undefined,
      webhook_secret: webhookSecret || undefined,
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: SETTINGS_KEY });
      setKeySecret("");
      setWebhookSecret("");
      setSaved(true);
    },
  });
  const test = useMutation({ mutationFn: () => admin.testPayments() });
  const sync = useMutation({ mutationFn: () => admin.syncRazorpayPlans() });

  return (
    <div className="space-y-6">
      <Card
        title="Razorpay"
        actions={
          <Badge tone={payments.live_checkout ? "green" : payments.test_checkout ? "brand" : "amber"}>
            {payments.live_checkout ? "Live payments" : payments.test_checkout ? "Test checkout" : "Off / dev"}
          </Badge>
        }
      >
        <p className="mb-4 text-sm text-slate-600">
          Same Checkout flow for test and live: <code>rzp_test_…</code> opens Razorpay sandbox (no real charges);
          <code> rzp_live_…</code> charges real UPI/cards. Secrets are encrypted here or via <code>PAYMENT_*</code> in <code>.env</code>.
        </p>
        {payments.ready && payments.razorpay_mode === "test" && (
          <Alert kind="info">Test keys active — run <strong>Test API keys</strong>, then <strong>Sync plans</strong>, then upgrade on /app/billing with test card 4111 1111 1111 1111.</Alert>
        )}
        {payments.ready && payments.razorpay_mode === "live" && (
          <Alert kind="success">Live keys active — Checkout collects real payments. Ensure the webhook secret matches your Razorpay Dashboard.</Alert>
        )}
        <label className="block text-sm">
          <span className="mb-1 block font-medium text-slate-700">Mode</span>
          <select
            className="w-full max-w-md rounded-lg border border-slate-300 px-3 py-2"
            value={provider}
            onChange={(e) => setProvider(e.target.value as "null" | "razorpay")}
          >
            <option value="null">Development — activate plans without charging</option>
            <option value="razorpay">Razorpay — real checkout</option>
          </select>
        </label>
        {provider === "razorpay" && (
          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            <TextInput label="Key ID" value={keyId} onChange={setKeyId} maxLength={64} placeholder="rzp_test_…" />
            <TextInput
              label="Key secret"
              type="password"
              value={keySecret}
              onChange={setKeySecret}
              maxLength={200}
              configured={payments.key_secret_configured}
              configuredMessage="Key uploaded"
              autoComplete="off"
            />
            <TextInput
              label="Webhook secret"
              type="password"
              value={webhookSecret}
              onChange={setWebhookSecret}
              maxLength={200}
              configured={payments.webhook_secret_configured}
              configuredMessage="Key uploaded"
              autoComplete="off"
            />
          </div>
        )}
        <SaveBar saving={save.isPending} saved={saved} onSave={() => { setSaved(false); save.mutate(); }} />
        {save.error && <Alert kind="error">{errorMessage(save.error)}</Alert>}
      </Card>
      {provider === "razorpay" && (
        <>
          <Card title="Webhook URL">
            <p className="text-sm text-slate-600">In Razorpay Dashboard → Webhooks, subscribe to subscription events and point here:</p>
            <code className="mt-2 block break-all rounded-lg bg-slate-100 p-3 text-xs">{webhookUrl}</code>
          </Card>
          <Card title="Plans at Razorpay">
            <p className="mb-3 text-sm text-slate-600">After saving keys, sync paid plans once (or after price changes on new plan codes).</p>
            <div className="flex flex-wrap gap-2">
              <Button variant="secondary" loading={test.isPending} onClick={() => test.mutate()}>Test API keys</Button>
              <Button variant="secondary" loading={sync.isPending} onClick={() => sync.mutate()}>Sync plans to Razorpay</Button>
            </div>
            {test.data?.ok && (
              <Alert kind="success">
                {test.data.mode === "live"
                  ? (test.data.message ?? "Live API keys verified.")
                  : (test.data.test_checkout_hint ?? "Test API keys verified — use sandbox payment methods in Checkout.")}
              </Alert>
            )}
            {test.error && <Alert kind="error">{errorMessage(test.error)}</Alert>}
            {sync.data && (
              <Alert kind="success">
                {sync.data.created.length
                  ? `Created ${sync.data.created.length} plan(s) at Razorpay.`
                  : "Every paid plan already exists at Razorpay."}
              </Alert>
            )}
            {sync.error && <Alert kind="error">{errorMessage(sync.error)}</Alert>}
          </Card>
        </>
      )}
    </div>
  );
}

function IntegrationsTab({ infra, smtp, ai, payments }: {
  infra: AdminPlatformSettings["infrastructure"];
  smtp: AdminPlatformSettings["smtp"];
  ai: AdminPlatformSettings["ai"];
  payments: AdminPlatformSettings["payments"];
}) {
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
          <Row label="Razorpay ready">{payments.ready ? "Yes" : "No"}</Row>
          <Row label="Payment config source">{payments.source === "database" ? "Admin settings" : ".env"}</Row>
        </dl>
      </Card>
      <Card title="Email status">
        <dl className="divide-y divide-slate-100 text-sm">
          <Row label="Mode">{smtp.mode}</Row>
          <Row label="Host">{smtp.host || "—"}</Row>
          <Row label="From">{smtp.from_address}</Row>
        </dl>
      </Card>
      <Card title="AI status" className="lg:col-span-2">
        <dl className="divide-y divide-slate-100 text-sm sm:grid sm:grid-cols-2 sm:gap-x-6">
          <Row label="Enabled">{ai.enabled ? "Yes" : "No"}</Row>
          <Row label="Ready">{ai.ready ? "Yes" : "No"}</Row>
          <Row label="Provider">{ai.provider}</Row>
          <Row label="Fast model">{ai.models.fast}</Row>
        </dl>
      </Card>
    </div>
  );
}

function OperationsTab() {
  return (
    <div className="space-y-6">
      <BroadcastNotificationsCard />
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
  "settings.email_templates": "Updated email templates",
  "notifications.broadcast": "Broadcast notification",
  "email.test_template": "Sent template test email",
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
