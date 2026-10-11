import { Bell, Mail } from "lucide-react";
import { useState, type ReactNode } from "react";
import { cx } from "../../components/ui";

const PLACEHOLDER = /\{(\w+)\}/g;

/** Mirrors backend `template_service.render`: unknown placeholders become empty text. */
export function renderTemplate(template: string, vars: Record<string, string>): string {
  return (template || "").replace(PLACEHOLDER, (_, key: string) => vars[key] ?? "");
}

/** Same signature the server adds to every outgoing email (`email_service.with_footer`). */
const FOOTER_MARKER = "info@applyxai.com";
const FOOTER_TEXT = ["Regards,", "ApplyXAI", "www.applyxai.com", "Bangalore", "info@applyxai.com"].join("\n");
const FOOTER_HTML =
  '<div style="margin-top:24px;padding-top:16px;border-top:1px solid #e2e8f0;' +
  'font-family:Arial,Helvetica,sans-serif;font-size:14px;line-height:1.6;color:#334155">' +
  "Regards,<br><strong>ApplyXAI</strong><br>" +
  '<a href="https://www.applyxai.com" style="color:#2563eb">www.applyxai.com</a><br>' +
  "Bangalore<br>" +
  '<a href="mailto:info@applyxai.com" style="color:#2563eb">info@applyxai.com</a>' +
  "</div>";

export function withFooter(text: string, html: string): { text: string; html: string } {
  const outText = text.includes(FOOTER_MARKER) ? text : `${text.trimEnd()}\n\n${FOOTER_TEXT}`;
  let outHtml = html;
  if (html.trim() && !html.includes(FOOTER_MARKER)) {
    const cut = html.toLowerCase().lastIndexOf("</body>");
    outHtml = cut >= 0 ? `${html.slice(0, cut)}${FOOTER_HTML}${html.slice(cut)}` : `${html}${FOOTER_HTML}`;
  }
  return { text: outText, html: outHtml };
}

const URL_RE = /(https?:\/\/[^\s<>"']+|www\.[^\s<>"']+|[\w.+-]+@[\w-]+\.[\w.]+)/g;

function linkify(text: string): ReactNode[] {
  return text.split(URL_RE).map((part, i) =>
    i % 2 === 1 ? (
      <a
        key={i}
        href={part.includes("@") && !part.startsWith("http") ? `mailto:${part}` : part.startsWith("www.") ? `https://${part}` : part}
        target="_blank" rel="noreferrer" className="break-all text-brand-700 underline">
        {part}
      </a>
    ) : (
      part
    ),
  );
}

export function sampleTemplateVars(opts: {
  appName: string;
  frontendUrl: string;
  verificationHours: number;
  passwordResetMinutes: number;
}): Record<string, string> {
  const base = opts.frontendUrl.replace(/\/+$/, "");
  return {
    app_name: opts.appName,
    frontend_url: base,
    verification_hours: String(opts.verificationHours),
    password_reset_minutes: String(opts.passwordResetMinutes),
    institute_name: "Example Institute",
    link_url: `${base}/app/notifications`,
    title: "Automation run finished",
    message: "This is a sample message so you can see how the text reads.",
    body: "This is a sample announcement body.",
    plan_name: "Pro",
    candidate_email: "candidate@example.com",
    job_title: "Software Engineer",
    company: "Acme Corp",
    location: "Bengaluru, India",
    report_date: new Date().toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" }),
    summary: "12 applied · 2 failed · 5 skipped · 1 external",
    applied_count: "12",
    failed_count: "2",
    skipped_count: "5",
    external_count: "1",
  };
}

const AUTH_SAMPLE_PATHS: Record<string, string> = {
  verify_email: "/verify-email?token=sample-token",
  password_reset: "/reset-password?token=sample-token",
  account_exists: "/forgot-password",
  institute_invite: "/invite/sample-token?token=sample-token",
};

export function authSampleLink(frontendUrl: string, key: string): string {
  return `${frontendUrl.replace(/\/+$/, "")}${AUTH_SAMPLE_PATHS[key] ?? "/example"}`;
}

type View = "email" | "text" | "in_app";

export function EmailTemplatePreview({
  from,
  to = "candidate@example.com",
  subject,
  body,
  html,
  vars,
  appendLink,
  inApp,
}: {
  from: string;
  to?: string;
  subject: string;
  body: string;
  html: string;
  vars: Record<string, string>;
  /** Event emails without HTML get an "Open in …" link appended, as the server does. */
  appendLink?: string;
  inApp?: { title: string; body: string };
}) {
  const hasHtml = html.trim().length > 0;
  const [view, setView] = useState<View>("email");

  const renderedSubject = renderTemplate(subject, vars);
  let text = renderTemplate(body, vars).trim();
  if (appendLink && !text.includes("Open in")) {
    text += `\n\nOpen in ${vars.app_name}:\n${appendLink}`;
  }
  const signed = withFooter(text, renderTemplate(html, vars));
  const renderedText = signed.text;
  const renderedHtml = signed.html;

  const tabs: { id: View; label: string }[] = [
    { id: "email", label: hasHtml ? "Email (HTML)" : "Email" },
    ...(hasHtml ? [{ id: "text" as const, label: "Plain-text fallback" }] : []),
    ...(inApp ? [{ id: "in_app" as const, label: "In-app notification" }] : []),
  ];

  return (
    <div className="space-y-3">
      {tabs.length > 1 && (
        <div role="tablist" className="inline-flex rounded-lg bg-slate-100 p-1 text-sm">
          {tabs.map((t) => (
            <button
              key={t.id}
              type="button"
              role="tab"
              aria-selected={view === t.id}
              onClick={() => setView(t.id)}
              className={cx(
                "rounded-md px-3 py-1.5 font-medium transition-colors",
                view === t.id ? "bg-white text-slate-900 shadow-sm" : "text-slate-600 hover:text-slate-900",
              )}
            >
              {t.label}
            </button>
          ))}
        </div>
      )}

      {view === "in_app" && inApp ? (
        <div className="rounded-xl bg-slate-50 p-4 ring-1 ring-slate-200">
          <div className="mx-auto flex max-w-md items-start gap-3 rounded-lg bg-white p-4 shadow-sm ring-1 ring-slate-200">
            <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-brand-50 text-brand-700">
              <Bell className="h-4 w-4" aria-hidden />
            </span>
            <div className="min-w-0">
              <p className="font-medium text-slate-900">{renderTemplate(inApp.title, vars) || "(no title)"}</p>
              <p className="mt-1 whitespace-pre-wrap text-sm text-slate-600">{renderTemplate(inApp.body, vars) || "(no body)"}</p>
              <p className="mt-2 text-xs text-slate-400">just now</p>
            </div>
          </div>
        </div>
      ) : (
        <div className="overflow-hidden rounded-xl ring-1 ring-slate-200">
          <div className="space-y-1 border-b border-slate-200 bg-slate-50 px-4 py-3 text-sm">
            <div className="flex items-center gap-2">
              <Mail className="h-4 w-4 text-slate-400" aria-hidden />
              <p className="font-semibold text-slate-900">{renderedSubject || "(no subject)"}</p>
            </div>
            <p className="text-slate-600"><span className="text-slate-400">From:</span> {from}</p>
            <p className="text-slate-600"><span className="text-slate-400">To:</span> {to}</p>
          </div>
          {view === "email" && hasHtml ? (
            <iframe
              title="Email HTML preview"
              sandbox=""
              srcDoc={renderedHtml}
              className="block h-[420px] w-full bg-white"
            />
          ) : (
            <div className="max-h-[420px] overflow-auto bg-white px-5 py-4 font-sans text-sm leading-relaxed text-slate-800 whitespace-pre-wrap">
              {renderedText ? linkify(renderedText) : <span className="text-slate-400">(no body)</span>}
            </div>
          )}
        </div>
      )}
      <p className="text-xs text-slate-500">Placeholders are filled with sample values. Real emails use each recipient's data.</p>
    </div>
  );
}
