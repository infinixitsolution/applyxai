import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Pencil, Search, Send } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useToast } from "../../../components/Toast";
import { Alert, Badge, Button, Card, PageHeader, Spinner, cx } from "../../../components/ui";
import { errorMessage } from "../../../services/api";
import { admin } from "../../../services/endpoints";
import type { OutreachLead } from "../../../types";
import type { OutreachProfileCompletion } from "../../../types";
import { LeadChatPanel } from "./LeadChatPanel";
import { isLeadProfileCompleting, LeadCompletenessScore, ProfileView } from "./shared";

function hasDraftProposal(lead: OutreachLead): boolean {
  return lead.messages.some((m) => m.channel === "email" && m.status === "draft");
}

function canSendOutreach(lead: OutreachLead): boolean {
  if (lead.completeness_score < 100) return false;
  const email = lead.messages.some((m) => m.channel === "email" && m.status === "draft");
  const wa = lead.messages.some((m) => m.channel === "whatsapp" && m.status === "draft");
  const profile = lead.profile || {};
  const emails = profile.emails as string[] | undefined;
  const phones = profile.phones as string[] | undefined;
  return Boolean(email && wa && emails?.length && phones?.length);
}

function PipelineStepper({ lead }: { lead: OutreachLead }) {
  const profileDone = lead.completeness_score >= 100;
  const proposalDone = hasDraftProposal(lead) || lead.status === "sent";
  const sentDone = lead.status === "sent" || lead.status === "replied";
  const chatDone = lead.status === "replied";

  const steps = [
    { id: "profile", label: "Profile 100%", done: profileDone },
    { id: "proposal", label: "Proposal", done: proposalDone },
    { id: "sent", label: "Sent", done: sentDone },
    { id: "chat", label: "Chat", done: chatDone },
  ];

  return (
    <ol className="flex flex-wrap gap-2 text-sm">
      {steps.map((step, i) => (
        <li
          key={step.id}
          className={cx(
            "inline-flex items-center gap-2 rounded-full px-3 py-1 ring-1 ring-inset",
            step.done ? "bg-emerald-50 text-emerald-800 ring-emerald-200" : "bg-slate-50 text-slate-600 ring-slate-200",
          )}
        >
          <span className="font-medium">{i + 1}.</span>
          {step.label}
          {step.done ? " ✓" : ""}
        </li>
      ))}
    </ol>
  );
}

export function AdminOutreachLeadDetailPage() {
  const { id = "" } = useParams();
  const navigate = useNavigate();
  const toast = useToast();
  const qc = useQueryClient();
  const key = ["admin-outreach-lead", id];
  const [completionNote, setCompletionNote] = useState<OutreachProfileCompletion | null>(null);

  const { data: lead, isLoading, error } = useQuery({
    queryKey: key,
    queryFn: () => admin.outreachLead(id),
    enabled: Boolean(id),
    refetchInterval: (query) => {
      const data = query.state.data;
      return data && isLeadProfileCompleting(data) ? 3000 : false;
    },
  });

  const completeProfile = useMutation({
    mutationFn: () => admin.outreachCompleteProfile(id),
    onSuccess: ({ lead: updated, completion }) => {
      qc.setQueryData(key, updated);
      setCompletionNote(completion);
      const delta = completion.score_after - completion.score_before;
      toast.success(
        delta > 0
          ? `Profile ${completion.score_after}% complete (+${delta}%). Scraped ${completion.urls_scraped} page(s).`
          : `Profile ${completion.score_after}% complete. Scraped ${completion.urls_scraped} page(s).`,
      );
      void qc.invalidateQueries({ queryKey: ["admin-outreach-leads"] });
    },
    onError: (err) => toast.error(errorMessage(err)),
  });

  const generate = useMutation({
    mutationFn: () => admin.outreachGenerateProposal(id),
    onSuccess: (updated) => {
      qc.setQueryData(key, updated);
      toast.success("Proposal drafts generated");
      void qc.invalidateQueries({ queryKey: ["admin-outreach-leads"] });
    },
    onError: (err) => toast.error(errorMessage(err)),
  });

  const send = useMutation({
    mutationFn: () => admin.outreachSend(id, { channels: ["email", "whatsapp"], approve: true }),
    onSuccess: (res) => {
      qc.setQueryData(key, res.lead);
      toast.success("Outreach sent");
      void qc.invalidateQueries({ queryKey: ["admin-outreach-leads"] });
    },
    onError: (err) => toast.error(errorMessage(err)),
  });

  const convert = useMutation({
    mutationFn: () => admin.outreachConvert(id),
    onSuccess: () => {
      toast.success("Institute created — password reset email sent");
      void qc.invalidateQueries({ queryKey: ["admin-outreach-leads"] });
      void qc.invalidateQueries({ queryKey: key });
    },
    onError: (err) => toast.error(errorMessage(err)),
  });

  if (isLoading) return <Spinner />;
  if (error || !lead) return <Alert kind="error">{errorMessage(error)}</Alert>;

  const profileComplete = lead.completeness_score >= 100;
  const proposalReady = hasDraftProposal(lead);
  const sendReady = canSendOutreach(lead);

  return (
    <div className="space-y-6">
      <Link
        to="/admin/outreach/leads"
        className="inline-flex items-center gap-1 text-sm font-medium text-slate-600 hover:text-slate-900"
      >
        <ArrowLeft className="h-4 w-4" aria-hidden />
        Back to leads
      </Link>

      <PageHeader
        title={lead.display_name || "Lead profile"}
        description={
          <span className="inline-flex flex-wrap items-center gap-x-2 gap-y-1">
            <span>{lead.status.replace(/_/g, " ")}</span>
            <span aria-hidden>·</span>
            <LeadCompletenessScore lead={lead} />
            <span aria-hidden>·</span>
            <span className="capitalize">{lead.source_platform}</span>
          </span>
        }
      />

      {isLeadProfileCompleting(lead) && (
        <Alert kind="info">Complete profile is running in the background. This page refreshes automatically.</Alert>
      )}

      <PipelineStepper lead={lead} />

      {lead.status === "skipped_incomplete" && (
        <Alert kind="info">
          Automation skipped this lead because the profile could not reach 100% from public sources. Edit missing fields,
          then run Complete profile again.
        </Alert>
      )}

      {completionNote && (
        <Alert kind={completionNote.score_after > completionNote.score_before ? "success" : "info"}>
          <p>
            Searches: {completionNote.searches_run}, hits: {completionNote.search_hits}, pages scraped:{" "}
            {completionNote.urls_scraped}
            {completionNote.urls_skipped > 0 && ` (${completionNote.urls_skipped} social URLs skipped)`}.
            Score {completionNote.score_before}% → {completionNote.score_after}%.
          </p>
          {completionNote.hints.map((hint) => (
            <p key={hint} className="mt-1">
              {hint}
            </p>
          ))}
          <p className="mt-2 text-xs text-slate-600">
            100% needs name, email, phone, website, address, and description from public sources — add missing fields
            manually if the web does not expose them.
          </p>
        </Alert>
      )}

      <div className="flex flex-wrap gap-2">
        <Button loading={completeProfile.isPending} onClick={() => completeProfile.mutate()}>
          <Search className="h-4 w-4 mr-1" aria-hidden />
          Complete profile
        </Button>
        <Button
          variant="secondary"
          onClick={() => navigate("/admin/outreach/leads", { state: { editLeadId: lead.id } })}
        >
          <Pencil className="h-4 w-4 mr-1" aria-hidden />
          Edit profile
        </Button>
        <Button
          variant="secondary"
          loading={generate.isPending}
          disabled={!profileComplete || proposalReady}
          onClick={() => generate.mutate()}
          title={!profileComplete ? "Reach 100% profile completeness first" : undefined}
        >
          Generate proposal
        </Button>
        <Button
          loading={send.isPending}
          disabled={!sendReady || lead.status === "sent" || lead.status === "replied"}
          onClick={() => send.mutate()}
          title={!sendReady ? "Generate proposal and ensure email + phone are present" : undefined}
        >
          <Send className="h-4 w-4 mr-1" aria-hidden />
          Send email + WhatsApp
        </Button>
        <Button variant="secondary" loading={convert.isPending} onClick={() => convert.mutate()}>
          Convert to institute
        </Button>
      </div>

      <Card className="p-6">
        <ProfileView lead={lead} />
      </Card>

      <LeadChatPanel
        leadId={lead.id}
        enabled={lead.status === "sent" || lead.status === "replied" || Boolean(lead.whatsapp_phone)}
      />

      {lead.messages.length > 0 && (
        <Card className="p-6">
          <h2 className="mb-4 text-lg font-semibold text-slate-900">Outreach messages</h2>
          <ul className="space-y-3 text-sm">
            {lead.messages.map((m) => (
              <li key={m.id} className="rounded-lg border border-slate-200 p-3">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge tone="slate">{m.channel}</Badge>
                  <span className="text-slate-600">{m.status}</span>
                  {m.subject && <span className="font-medium text-slate-800">{m.subject}</span>}
                </div>
                {m.body && (
                  <pre className="mt-2 max-h-48 overflow-auto whitespace-pre-wrap text-xs text-slate-600">{m.body}</pre>
                )}
              </li>
            ))}
          </ul>
        </Card>
      )}

      {lead.institute_id && (
        <p className="text-sm text-slate-600">
          Linked institute:{" "}
          <button
            type="button"
            className="font-medium text-brand-700 underline"
            onClick={() => navigate(`/admin/institutes/${lead.institute_id}`)}
          >
            Open institute
          </button>
        </p>
      )}
    </div>
  );
}
