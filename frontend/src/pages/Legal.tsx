import type { ReactNode } from "react";
import { Alert } from "../components/ui";
import { APP_NAME, CONTACT_EMAIL } from "../lib/config";

function LegalPage({ title, children }: { title: string; children: ReactNode }) {
  return (
    <article className="mx-auto max-w-3xl px-4 py-16">
      <h1 className="text-3xl font-bold tracking-tight">{title}</h1>
      <div className="mt-6">
        <Alert kind="info">Template text. Have it reviewed by a qualified lawyer for your jurisdiction before launch.</Alert>
      </div>
      <div className="mt-8 space-y-4 text-sm leading-6 text-slate-700 [&_h2]:mt-8 [&_h2]:text-lg [&_h2]:font-semibold [&_h2]:text-slate-900 [&_ul]:list-disc [&_ul]:pl-6">
        {children}
      </div>
    </article>
  );
}

export function PrivacyPage() {
  return (
    <LegalPage title="Privacy Policy">
      <p>This policy explains what {APP_NAME} collects, why, and the choices you have.</p>
      <h2>What we collect</h2>
      <ul>
        <li>Account details: name, email address, and a hashed password (we never store your password itself).</li>
        <li>Profile and preferences you enter, such as job titles, locations, and answers to screening questions.</li>
        <li>Resumes you upload.</li>
        <li>Application records created by the automation: job titles, companies, links, and outcomes.</li>
        <li>Billing records from our payment provider. We don't store card numbers.</li>
      </ul>
      <h2>What we don't collect</h2>
      <p>We never receive your LinkedIn or other job-site passwords. The automation runs in a browser on your own computer, and you sign in there.</p>
      <h2>How we use it</h2>
      <p>We use your data to provide the service, run your automation with your settings, show your history, process payments, and send account emails. We don't sell personal data.</p>
      <h2>Retention and deletion</h2>
      <p>We keep your data while your account is active. You can export your applications at any time. To delete your account and data, contact us.</p>
      <h2>Contact</h2>
      <p>Questions about privacy: <a className="text-brand-600 underline" href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a>.</p>
    </LegalPage>
  );
}

export function TermsPage() {
  return (
    <LegalPage title="Terms of Service">
      <p>By using {APP_NAME} you agree to these terms.</p>
      <h2>The service</h2>
      <p>{APP_NAME} helps you manage and automate job applications. We don't guarantee interviews, offers, or any particular result.</p>
      <h2>Your responsibilities</h2>
      <ul>
        <li>Provide accurate information in your profile, answers, and resumes. Applications are sent in your name.</li>
        <li>Follow the terms of service of every job site you use with {APP_NAME}. Some sites restrict automated activity, and you're responsible for how you use the automation.</li>
        <li>Keep your account secure and don't share it.</li>
      </ul>
      <h2>Acceptable use</h2>
      <p>Don't use {APP_NAME} to send spam or misleading applications, to get around security measures on other sites, or to break any law.</p>
      <h2>Plans and limits</h2>
      <p>Each plan has monthly limits. Usage resets on the first day of each month (UTC).</p>
      <h2>Liability</h2>
      <p>The service is provided "as is". To the extent permitted by law, we aren't liable for indirect losses or for actions taken by third-party sites.</p>
    </LegalPage>
  );
}

export function RefundPage() {
  return (
    <LegalPage title="Refund Policy">
      <p>You can cancel a paid plan at any time. It stays active until the end of the current billing period, and you won't be charged again.</p>
      <h2>Refunds</h2>
      <p>If you were charged by mistake, or the service didn't work for you because of a fault on our side, contact us within 7 days of the charge and we'll review a refund.</p>
      <h2>How to ask</h2>
      <p>Email <a className="text-brand-600 underline" href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a> with your account email and the payment date.</p>
    </LegalPage>
  );
}
