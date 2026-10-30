import { Bot, FileText, MessageSquare, Users } from "lucide-react";
import { Link, useLocation } from "react-router-dom";
import { cx } from "./ui";

/** Compact outreach helper pinned under the admin sidebar on outreach routes. */
export function AdminOutreachAssistant() {
  const { pathname } = useLocation();
  if (!pathname.startsWith("/admin/outreach")) return null;

  return (
    <div className="mx-3 mb-4 mt-auto rounded-xl border border-brand-100 bg-gradient-to-br from-brand-50/90 to-white p-3 shadow-sm">
      <div className="flex items-center gap-2 text-sm font-semibold text-slate-900">
        <Bot className="h-4 w-4 text-brand-600" aria-hidden />
        Outreach assistant
      </div>
      <p className="mt-1.5 text-xs leading-relaxed text-slate-600">
        After you send outreach, AI auto-reply is enabled for that institute&apos;s WhatsApp thread (inbound replies get a
        helpful follow-up).
      </p>
      <nav className="mt-3 flex flex-col gap-1 text-xs font-medium" aria-label="Outreach shortcuts">
        <Link
          to="/admin/outreach/chat"
          className={cx(
            "inline-flex items-center gap-1.5 rounded-lg px-2 py-1.5 text-brand-800 hover:bg-brand-100/60",
          )}
        >
          <MessageSquare className="h-3.5 w-3.5" aria-hidden />
          WhatsApp inbox
        </Link>
        <Link
          to="/admin/outreach/templates"
          className="inline-flex items-center gap-1.5 rounded-lg px-2 py-1.5 text-brand-800 hover:bg-brand-100/60"
        >
          <FileText className="h-3.5 w-3.5" aria-hidden />
          Edit templates
        </Link>
        <Link
          to="/admin/outreach/leads"
          className="inline-flex items-center gap-1.5 rounded-lg px-2 py-1.5 text-brand-800 hover:bg-brand-100/60"
        >
          <Users className="h-3.5 w-3.5" aria-hidden />
          Leads dashboard
        </Link>
      </nav>
    </div>
  );
}
