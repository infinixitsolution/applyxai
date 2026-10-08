import { useQuery } from "@tanstack/react-query";
import { BarChart3, Bot, FileText, Filter, ShieldCheck, SlidersHorizontal, type LucideIcon } from "lucide-react";
import { ButtonLink, Spinner } from "../components/ui";
import { usePublicSite } from "../lib/usePublicSite";
import { CONTACT_EMAIL } from "../lib/config";
import { formatMoney } from "../lib/format";
import { plans as plansApi } from "../services/endpoints";
import type { PlatformCms } from "../types";

const ICONS: Record<string, LucideIcon> = {
  sliders: SlidersHorizontal,
  bot: Bot,
  filter: Filter,
  "file-text": FileText,
  "bar-chart": BarChart3,
  shield: ShieldCheck,
};

const FALLBACK_FEATURES = [
  { icon: "sliders", title: "Precise job preferences", text: "Pick titles, locations, experience levels, job types, and work settings with the same filters LinkedIn uses." },
  { icon: "bot", title: "Automated Easy Apply", text: "The automation fills in application forms with your saved answers and your chosen resume, and records every outcome." },
  { icon: "filter", title: "Smart skipping", text: "Skip roles with words you don't want, companies you'd rather avoid, or jobs that won't sponsor a visa." },
  { icon: "file-text", title: "Resume management", text: "Keep several resumes for different roles and choose a default for each run." },
  { icon: "bar-chart", title: "Application tracking", text: "See every application, its status, and why anything failed. Export the full history to CSV whenever you like." },
  { icon: "shield", title: "Your data, protected", text: "Encrypted sessions, strict per-account data isolation, and your job-site password never leaves your computer." },
];

const FALLBACK_LANDING: PlatformCms["landing"] = {
  hero_badge: "Job search automation, under your control",
  hero_title: "AI-Powered Job Search & Application Management",
  hero_subtitle: "Set your preferences once. ApplyXAI finds matching roles, fills in Easy Apply forms with your answers, and keeps a clear record of every application.",
  hero_cta_primary: "Get started free",
  hero_cta_secondary: "See how it works",
  hero_footnote: "No credit card needed for the free plan.",
  features_heading: "Everything you need for a focused search",
  features: FALLBACK_FEATURES,
  steps_heading: "How it works",
  steps: [
    { title: "Create your profile", text: "Add your details, upload a resume, and answer the common screening questions once." },
    { title: "Set your preferences", text: "Choose the roles, locations, and filters that fit what you're looking for." },
    { title: "Run the automation", text: "It searches and applies in your browser while you watch, and you can pause or stop it at any time." },
    { title: "Track the results", text: "Review applications, failures, and monthly usage on your dashboard." },
  ],
  pricing_heading: "Simple, transparent pricing",
  pricing_subtitle: "Start free. Upgrade when you need more applications.",
  faq_heading: "Frequently asked questions",
  faq: [
    { question: "Does ApplyXAI guarantee interviews or a job?", answer: "No. ApplyXAI saves you time on repetitive applications. Whether you hear back depends on employers, your profile, and the roles you choose." },
    { question: "Which job sites are supported?", answer: "LinkedIn Easy Apply today. Jobs that use an external application site are recorded so you can finish them yourself." },
    { question: "Do you store my LinkedIn password?", answer: "No. The automation runs in a browser on your own computer, and you sign in there. ApplyXAI never receives your job-site password." },
    { question: "Is automated applying allowed?", answer: "Job sites set their own rules, and some limit automation. You're responsible for using ApplyXAI in line with the terms of the sites you use. Review applications and keep the volume reasonable." },
    { question: "Can I cancel at any time?", answer: "Yes. Paid plans can be cancelled at any time and stay active until the end of the billing period. See our refund policy for details." },
  ],
  faq_contact_line: "Still have questions? Email us at {contact_email}.",
};

function Pricing() {
  const { data, isLoading, isError } = useQuery({ queryKey: ["plans"], queryFn: plansApi.list, staleTime: 10 * 60 * 1000 });
  if (isLoading) return <Spinner />;
  if (isError || !data) return <p className="text-center text-sm text-slate-500">Pricing is unavailable right now.</p>;
  return (
    <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
      {data.map((plan) => (
        <div key={plan.code} className={`flex flex-col rounded-2xl p-6 ring-1 ${plan.code === "pro" ? "bg-brand-600 text-white ring-brand-600" : "bg-white ring-slate-200"}`}>
          <h3 className="text-lg font-semibold">{plan.name}</h3>
          <p className="mt-4">
            <span className="text-3xl font-bold tracking-tight">{formatMoney(plan.price_cents, plan.currency)}</span>
            <span className={plan.code === "pro" ? "text-brand-100" : "text-slate-500"}> / {plan.interval}</span>
          </p>
          <ul className={`mt-6 flex-1 space-y-2 text-sm ${plan.code === "pro" ? "text-brand-50" : "text-slate-600"}`}>
            <li>{plan.limits.applications_per_month.toLocaleString()} applications / month</li>
            <li>{plan.limits.resumes} resume{plan.limits.resumes === 1 ? "" : "s"}</li>
            <li>Application tracking and CSV export</li>
          </ul>
          <ButtonLink to="/register" variant={plan.code === "pro" ? "secondary" : "primary"} className="mt-6 w-full">
            {plan.price_cents === 0 ? "Start free" : "Get started"}
          </ButtonLink>
        </div>
      ))}
    </div>
  );
}

export function LandingPage() {
  const { data: site } = usePublicSite();
  const landing = site?.landing ?? FALLBACK_LANDING;
  const contact = site?.branding.contact_email ?? CONTACT_EMAIL;

  return (
    <>
      <section className="relative overflow-hidden bg-gradient-to-b from-brand-50 to-white">
        <div className="mx-auto max-w-6xl px-4 py-20 text-center sm:py-28">
          <p className="mx-auto mb-4 inline-block rounded-full bg-white px-3 py-1 text-xs font-medium text-brand-700 ring-1 ring-brand-100">
            {landing.hero_badge}
          </p>
          <h1 className="mx-auto max-w-3xl text-4xl font-bold tracking-tight text-slate-900 sm:text-5xl">
            {landing.hero_title}
          </h1>
          <p className="mx-auto mt-6 max-w-2xl text-lg text-slate-600">{landing.hero_subtitle}</p>
          <div className="mt-10 flex flex-col justify-center gap-3 sm:flex-row">
            <ButtonLink to="/register" className="px-6 py-3 text-base">{landing.hero_cta_primary}</ButtonLink>
            <a href="#how-it-works" className="inline-flex items-center justify-center rounded-lg px-6 py-3 text-base font-medium text-slate-700 hover:bg-white">
              {landing.hero_cta_secondary}
            </a>
          </div>
          <p className="mt-4 text-xs text-slate-500">{landing.hero_footnote}</p>
        </div>
      </section>

      <section id="features" className="mx-auto max-w-6xl scroll-mt-20 px-4 py-20">
        <h2 className="text-center text-3xl font-bold tracking-tight">{landing.features_heading}</h2>
        <div className="mt-12 grid gap-8 sm:grid-cols-2 lg:grid-cols-3">
          {landing.features.map(({ icon, title, text }) => {
            const Icon = ICONS[icon] ?? Bot;
            return (
              <div key={title} className="rounded-xl p-6 ring-1 ring-slate-200">
                <Icon className="h-8 w-8 text-brand-600" aria-hidden />
                <h3 className="mt-4 font-semibold">{title}</h3>
                <p className="mt-2 text-sm text-slate-600">{text}</p>
              </div>
            );
          })}
        </div>
      </section>

      <section id="how-it-works" className="scroll-mt-20 bg-slate-50 py-20">
        <div className="mx-auto max-w-6xl px-4">
          <h2 className="text-center text-3xl font-bold tracking-tight">{landing.steps_heading}</h2>
          <ol className="mt-12 grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
            {landing.steps.map(({ title, text }, i) => (
              <li key={title} className="rounded-xl bg-white p-6 ring-1 ring-slate-200">
                <span className="flex h-8 w-8 items-center justify-center rounded-full bg-brand-600 text-sm font-semibold text-white">{i + 1}</span>
                <h3 className="mt-4 font-semibold">{title}</h3>
                <p className="mt-2 text-sm text-slate-600">{text}</p>
              </li>
            ))}
          </ol>
        </div>
      </section>

      <section id="pricing" className="mx-auto max-w-6xl scroll-mt-20 px-4 py-20">
        <h2 className="text-center text-3xl font-bold tracking-tight">{landing.pricing_heading}</h2>
        <p className="mt-3 text-center text-slate-600">{landing.pricing_subtitle}</p>
        <div className="mt-12"><Pricing /></div>
      </section>

      <section id="faq" className="scroll-mt-20 bg-slate-50 py-20">
        <div className="mx-auto max-w-3xl px-4">
          <h2 className="text-center text-3xl font-bold tracking-tight">{landing.faq_heading}</h2>
          <div className="mt-10 divide-y divide-slate-200 rounded-xl bg-white ring-1 ring-slate-200">
            {landing.faq.map(({ question, answer }) => (
              <details key={question} className="group px-6 py-4">
                <summary className="cursor-pointer list-none font-medium text-slate-900 marker:hidden">{question}</summary>
                <p className="mt-2 text-sm text-slate-600">{answer}</p>
              </details>
            ))}
          </div>
          <p className="mt-10 text-center text-sm text-slate-600">
            {landing.faq_contact_line.replace("{contact_email}", contact).includes("@") ? (
              <>Still have questions? Email us at <a href={`mailto:${contact}`} className="font-medium text-brand-600 hover:underline">{contact}</a>.</>
            ) : landing.faq_contact_line.replace("{contact_email}", contact)}
          </p>
        </div>
      </section>
    </>
  );
}
