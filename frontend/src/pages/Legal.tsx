import Markdown from "react-markdown";
import type { ReactNode } from "react";
import { Alert } from "../components/ui";
import { usePublicSite } from "../lib/usePublicSite";
import { APP_NAME, CONTACT_EMAIL } from "../lib/config";

function LegalPage({ title, markdown, fallback }: { title: string; markdown?: string; fallback: ReactNode }) {
  return (
    <article className="mx-auto max-w-3xl px-4 py-16">
      <h1 className="text-3xl font-bold tracking-tight">{title}</h1>
      <div className="mt-6">
        <Alert kind="info">Template text. Have it reviewed by a qualified lawyer for your jurisdiction before launch.</Alert>
      </div>
      <div className="mt-8 space-y-4 text-sm leading-6 text-slate-700 [&_h2]:mt-8 [&_h2]:text-lg [&_h2]:font-semibold [&_h2]:text-slate-900 [&_ul]:list-disc [&_ul]:pl-6">
        {markdown ? <Markdown>{markdown}</Markdown> : fallback}
      </div>
    </article>
  );
}

export function PrivacyPage() {
  const { data: site } = usePublicSite();
  const name = site?.branding.app_name ?? APP_NAME;
  const contact = site?.branding.contact_email ?? CONTACT_EMAIL;
  return (
    <LegalPage title="Privacy Policy" markdown={site?.legal.privacy_md} fallback={
      <>
        <p>This policy explains what {name} collects, why, and the choices you have.</p>
        <h2>Contact</h2>
        <p>Questions about privacy: <a className="text-brand-600 underline" href={`mailto:${contact}`}>{contact}</a>.</p>
      </>
    } />
  );
}

export function TermsPage() {
  const { data: site } = usePublicSite();
  const name = site?.branding.app_name ?? APP_NAME;
  return (
    <LegalPage title="Terms of Service" markdown={site?.legal.terms_md} fallback={
      <>
        <p>By using {name} you agree to these terms.</p>
        <h2>The service</h2>
        <p>{name} helps you manage and automate job applications. We don&apos;t guarantee interviews, offers, or any particular result.</p>
      </>
    } />
  );
}

export function RefundPage() {
  const { data: site } = usePublicSite();
  const contact = site?.branding.contact_email ?? CONTACT_EMAIL;
  return (
    <LegalPage title="Refund Policy" markdown={site?.legal.refund_md} fallback={
      <>
        <p>You can cancel a paid plan at any time. It stays active until the end of the current billing period.</p>
        <h2>How to ask</h2>
        <p>Email <a className="text-brand-600 underline" href={`mailto:${contact}`}>{contact}</a> with your account email and the payment date.</p>
      </>
    } />
  );
}
