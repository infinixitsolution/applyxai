import { Link } from "react-router-dom";
import { Card } from "../../../components/ui";
import { ChatThreadView } from "./ChatThreadView";

export function LeadChatPanel({ leadId, enabled }: { leadId: string; enabled: boolean }) {
  if (!enabled) return null;

  return (
    <Card className="p-4 sm:p-5 space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h2 className="text-base font-semibold text-slate-900">WhatsApp chat</h2>
          <p className="text-sm text-slate-600 mt-1">
            Institutes reply on WhatsApp after your proposal.
          </p>
        </div>
        <Link
          to={`/admin/outreach/chat/${leadId}`}
          className="text-sm font-medium text-brand-700 underline shrink-0"
        >
          Open in inbox
        </Link>
      </div>
      <ChatThreadView leadId={leadId} showBridgeHint />
    </Card>
  );
}
