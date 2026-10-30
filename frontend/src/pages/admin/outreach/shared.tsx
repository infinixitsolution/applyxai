import { useQuery } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { Link } from "react-router-dom";
import { Alert } from "../../../components/ui";
import { admin } from "../../../services/endpoints";
import type { OutreachLead } from "../../../types";

export const OUTREACH_SOURCES = [
  { id: "google", label: "Google / web" },
  { id: "facebook", label: "Facebook (public URLs)" },
  { id: "instagram", label: "Instagram (public URLs)" },
  { id: "linkedin", label: "LinkedIn (public URLs)" },
];

export type LeadEditDraft = {
  name: string;
  institute_type: string;
  contact_name: string;
  emails: string;
  phones: string;
  website: string;
  description: string;
  address_line: string;
  city: string;
  state: string;
  pin: string;
  programs: string;
};

export function str(v: unknown): string {
  return typeof v === "string" ? v : v != null ? String(v) : "";
}

export function isLeadProfileCompleting(lead: OutreachLead): boolean {
  return lead.profile_completing === true || lead.status === "completing_profile";
}

export function LeadCompletenessScore({ lead }: { lead: OutreachLead }) {
  const completing = isLeadProfileCompleting(lead);
  return (
    <div className="min-w-[5.5rem]">
      <div className="font-medium tabular-nums">{lead.completeness_score}%</div>
      {completing ? (
        <div className="mt-0.5 inline-flex items-center gap-1 text-xs text-brand-700" role="status">
          <Loader2 className="h-3 w-3 shrink-0 animate-spin" aria-hidden />
          Completing profile…
        </div>
      ) : null}
    </div>
  );
}

export function outreachLeadStatusTone(status: string): "green" | "amber" | "slate" {
  if (status === "sent" || status === "replied") return "green";
  if (status === "skipped_incomplete" || status === "completing_profile") return "amber";
  return "slate";
}

export function outreachLeadStatusLabel(status: string): string {
  if (status === "completing_profile") return "Completing profile";
  return status.replace(/_/g, " ");
}

export function listStr(v: unknown): string {
  return Array.isArray(v) ? v.map((x) => str(x)).filter(Boolean).join(", ") : str(v);
}

export function draftFromLead(lead: OutreachLead): LeadEditDraft {
  const p = lead.profile || {};
  const addr = (p.address && typeof p.address === "object" ? p.address : {}) as Record<string, unknown>;
  return {
    name: str(p.name) || lead.display_name,
    institute_type: str(p.institute_type) || "OTHER",
    contact_name: str(p.contact_name),
    emails: listStr(p.emails),
    phones: listStr(p.phones),
    website: str(p.website) || lead.source_url,
    description: str(p.description),
    address_line: str(addr.line),
    city: str(addr.city),
    state: str(addr.state),
    pin: str(addr.pin),
    programs: listStr(p.programs),
  };
}

export function payloadFromDraft(draft: LeadEditDraft, base: Record<string, unknown>): Record<string, unknown> {
  const addr = (base.address && typeof base.address === "object" ? base.address : {}) as Record<string, unknown>;
  const social = (base.social && typeof base.social === "object" ? base.social : {}) as Record<string, unknown>;
  return {
    ...base,
    name: draft.name.trim(),
    institute_type: draft.institute_type.trim() || "OTHER",
    contact_name: draft.contact_name.trim(),
    emails: draft.emails.split(/[,;\n]+/).map((e) => e.trim().toLowerCase()).filter(Boolean).slice(0, 5),
    phones: draft.phones.split(/[,;\n]+/).map((p) => p.trim()).filter(Boolean).slice(0, 5),
    website: draft.website.trim(),
    description: draft.description.trim(),
    address: {
      ...addr,
      line: draft.address_line.trim(),
      city: draft.city.trim(),
      state: draft.state.trim(),
      pin: draft.pin.trim(),
      country: str(addr.country) || "India",
    },
    social,
    programs: draft.programs.split(/[,;\n]+/).map((p) => p.trim()).filter(Boolean).slice(0, 20),
  };
}

export function ProfileView({ lead }: { lead: OutreachLead }) {
  const p = lead.profile || {};
  const addr = (p.address && typeof p.address === "object" ? p.address : {}) as Record<string, unknown>;
  const rows: [string, string][] = [
    ["Name", str(p.name) || lead.display_name],
    ["Type", str(p.institute_type)],
    ["Contact", str(p.contact_name)],
    ["Emails", listStr(p.emails)],
    ["Phones", listStr(p.phones)],
    ["Website", str(p.website)],
    ["Programs", listStr(p.programs)],
    ["Address", [addr.line, addr.city, addr.state, addr.pin].map(str).filter(Boolean).join(", ")],
    ["Description", str(p.description)],
    ["Source", `${lead.source_platform} · ${lead.source_url}`],
    ["Completeness", `${lead.completeness_score}%`],
    ["AI confidence", `${Math.round(lead.confidence * 100)}%`],
  ];
  return (
    <dl className="divide-y divide-slate-100">
      {rows.map(([label, value]) => (
        <div key={label} className="grid gap-1 py-2 sm:grid-cols-[8rem_1fr]">
          <dt className="font-medium text-slate-500">{label}</dt>
          <dd className="whitespace-pre-wrap break-words text-slate-800">{value || "—"}</dd>
        </div>
      ))}
    </dl>
  );
}

export function useOutreachPlatform() {
  const platform = useQuery({
    queryKey: ["admin", "settings"],
    queryFn: () => admin.settings(),
  });
  const firecrawlOk = platform.data?.outreach?.firecrawl_api_key_configured ?? false;
  const aiOutreachOk = platform.data?.ai?.outreach_ready ?? false;
  return { platform, firecrawlOk, aiOutreachOk };
}

export function OutreachSetupAlert() {
  const { platform, firecrawlOk, aiOutreachOk } = useOutreachPlatform();
  if (!platform.data || (firecrawlOk && aiOutreachOk)) return null;
  return (
    <Alert kind="info">
      {!firecrawlOk && (
        <p>
          Firecrawl is not configured. Add and test your API key under{" "}
          <Link className="font-medium text-brand-700 underline" to="/admin/system">
            Admin → Settings → Integrations
          </Link>
          .
        </p>
      )}
      {!aiOutreachOk && (
        <p className={!firecrawlOk ? "mt-2" : undefined}>
          Platform AI is off for outreach. Under{" "}
          <Link className="font-medium text-brand-700 underline" to="/admin/system">
            Admin → Settings → AI
          </Link>
          , enable Platform AI, save an API key, turn on <strong>Institute outreach (enrichment)</strong>, and run{" "}
          <strong>Test AI connection</strong>.
        </p>
      )}
    </Alert>
  );
}
