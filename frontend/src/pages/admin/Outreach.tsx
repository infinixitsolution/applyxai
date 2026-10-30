import { Navigate } from "react-router-dom";

/** @deprecated Use /admin/outreach/scrape, /leads, /whatsapp */
export function AdminOutreachPage() {
  return <Navigate to="/admin/outreach/scrape" replace />;
}

export { AdminOutreachScrapePage } from "./outreach/ScrapePage";
export { AdminOutreachLeadsPage } from "./outreach/LeadsPage";
export { AdminOutreachLeadDetailPage } from "./outreach/LeadDetailPage";
export { AdminOutreachWhatsappPage } from "./outreach/WhatsappPage";
export { AdminOutreachWhatsappChatPage } from "./outreach/WhatsappChatPage";
export { AdminOutreachTemplatesPage } from "./outreach/OutreachTemplatesPage";
