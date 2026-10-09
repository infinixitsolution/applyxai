import { useQuery } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { LandingHero } from "../features/marketing/LandingHero";
import { useMarketingReveal } from "../hooks/useMarketingReveal";
import { Spinner } from "../components/ui";
import { CONTACT_EMAIL } from "../lib/config";
import { formatMoney } from "../lib/format";
import { usePublicSite } from "../lib/usePublicSite";
import { plans as plansApi } from "../services/endpoints";
import type { PlatformCms } from "../types";

const PUBLIC_PLAN_CODES = new Set(["free", "starter", "pro", "premium"]);

const FALLBACK_FEATURES = [
  { title: "LinkedIn job discovery", text: "Use the same title, location, experience, and work-setting filters you already know from LinkedIn search." },
  { title: "Resume Studio", text: "Optional AI tailoring builds a job-specific DOCX from your master resume — without inventing experience." },
  { title: "Easy Apply automation", text: "The desktop agent fills screening questions, uploads your resume, and submits while you watch in Chrome." },
  { title: "Smart skipping", text: "Skip blacklisted companies, bad-fit roles, and jobs below your match score before any form is opened." },
  { title: "Application tracking", text: "Every applied, skipped, failed, and external job is logged with timestamps and export to CSV." },
  { title: "Workspace controls", text: "Daily caps, dry runs, pause/stop, and per-run resume mode stay enforced from your dashboard." },
];

const FALLBACK_LANDING: PlatformCms["landing"] = {
  hero_badge: "LinkedIn Easy Apply automation",
  hero_title: "Apply on LinkedIn with AI — safely, from your browser.",
  hero_subtitle: "Set preferences once. Tailor when you want. Track every application.",
  hero_cta_primary: "Start applying free",
  hero_cta_secondary: "See how it works",
  hero_footnote: "LinkedIn only today. You sign in locally — we never see your password.",
  features_heading: "Everything for a focused LinkedIn search",
  features: FALLBACK_FEATURES.map((f, i) => ({
    icon: ["filter", "file-text", "bot", "filter", "bar-chart", "sliders"][i] ?? "bot",
    title: f.title,
    text: f.text,
  })),
  steps_heading: "How it works",
  steps: [
    { title: "Upload your master resume", text: "We extract profile hints, skills, and screening answers. Analyze master skills before AI tailoring." },
    { title: "Set LinkedIn search preferences", text: "Job titles, locations, experience level, remote/on-site, and skip rules mirror LinkedIn filters." },
    { title: "Connect the desktop agent", text: "Install the agent, connect your account, and start a run. Sign in to LinkedIn in the Chrome window it opens." },
    { title: "Review applications", text: "See which roles were applied, skipped, or need an external follow-up — with the resume used for each." },
  ],
  pricing_heading: "Simple, transparent pricing",
  pricing_subtitle: "All plans include LinkedIn Easy Apply automation and application history.",
  faq_heading: "Frequently asked questions",
  faq: [
    { question: "Does ApplyXAI guarantee interviews or a job?", answer: "No. ApplyXAI saves time on repetitive LinkedIn applications. Outcomes depend on employers, your profile, and the roles you target." },
    { question: "Which job sites are supported?", answer: "LinkedIn Easy Apply only. Jobs that redirect to an external site are saved in your history so you can finish them manually." },
    { question: "Do you store my LinkedIn password?", answer: "No. Automation runs in Chrome on your computer. You sign in to LinkedIn there; ApplyXAI never receives your password or OTP codes." },
    { question: "Is automated applying allowed on LinkedIn?", answer: "LinkedIn’s terms restrict some automated activity. You are responsible for compliant use — review submissions and keep volume reasonable." },
    { question: "Can I cancel at any time?", answer: "Yes. Paid plans can be cancelled and stay active until the end of the billing period. See our refund policy for details." },
  ],
  faq_contact_line: "Still have questions? Email us at {contact_email}.",
};

function FeatureIcon({ kind }: { kind: string }) {
  const paths: Record<string, ReactNode> = {
    search: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden>
        <circle cx="11" cy="11" r="6.5" />
        <path d="M16 16l5 5" strokeLinecap="round" />
      </svg>
    ),
    resume: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden>
        <path d="M7 3h7l5 5v13H7z" />
        <path d="M14 3v5h5M9 13h6M9 17h4" strokeLinecap="round" />
      </svg>
    ),
    apply: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden>
        <path d="M4 12l16-8-6.5 16-2.2-6.3z" strokeLinejoin="round" />
      </svg>
    ),
    interview: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden>
        <circle cx="12" cy="12" r="8" />
        <path d="M10 9.5v5l4.5-2.5z" strokeLinejoin="round" />
      </svg>
    ),
    chart: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden>
        <path d="M4 19V9M10 19V5M16 19v-7M22 19H2" strokeLinecap="round" />
      </svg>
    ),
    controls: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden>
        <circle cx="12" cy="12" r="3" />
        <path d="M12 4v2M12 18v2M4 12h2M18 12h2M6.3 6.3l1.4 1.4M16.3 16.3l1.4 1.4M6.3 17.7l1.4-1.4M16.3 7.7l1.4-1.4" strokeLinecap="round" />
      </svg>
    ),
  };
  const map: Record<string, keyof typeof paths> = {
    filter: "search",
    "file-text": "resume",
    bot: "apply",
    "bar-chart": "chart",
    sliders: "controls",
    shield: "controls",
  };
  return <span className="flow-icon">{paths[map[kind] ?? "apply"]}</span>;
}

function MarketingPricing() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["plans"],
    queryFn: plansApi.list,
    staleTime: 10 * 60 * 1000,
  });
  if (isLoading) return <Spinner />;
  const plans = (data ?? []).filter((p) => PUBLIC_PLAN_CODES.has(p.code));
  if (isError || !plans.length) {
    return <p className="home-copy" style={{ textAlign: "center" }}>Pricing is unavailable right now.</p>;
  }
  return (
    <div className="plan-block">
      <p className="plan-group">Candidate plans · LinkedIn Easy Apply included</p>
      <div className="plan-grid">
        {plans.map((plan) => {
          const featured = plan.code === "pro";
          return (
            <article key={plan.code} className={featured ? "plan-card featured" : "plan-card"}>
              {featured && <span className="plan-badge">Popular</span>}
              {!featured && plan.price_cents === 0 && <span className="plan-badge">Free</span>}
              <h3>{plan.name}</h3>
              <p className="home-price">
                <span>{formatMoney(plan.price_cents, plan.currency)}</span>
                <small> / {plan.interval}</small>
              </p>
              <p className="plan-desc">
                {plan.limits.applications_per_month.toLocaleString()} LinkedIn applications / month
              </p>
              <ul className="plan-points">
                <li>{plan.limits.resumes} master resume{plan.limits.resumes === 1 ? "" : "s"}</li>
                <li>AI tailor per job (optional)</li>
                <li>Desktop agent + CSV export</li>
              </ul>
              <Link className="home-cta" to="/register">
                {plan.price_cents === 0 ? "Start free" : "Get started"}
              </Link>
            </article>
          );
        })}
      </div>
    </div>
  );
}

const LIVE_STATS = [
  { label: "LinkedIn applications", value: "67,660+" },
  { label: "Roles discovered", value: "358K+" },
  { label: "AI resumes tailored", value: "12,400+" },
  { label: "Active job seekers", value: "2,180+" },
  { label: "Avg. JD match score", value: "82%" },
  { label: "Source", value: "LinkedIn" },
];

export function LandingPage() {
  const { data: site } = usePublicSite();
  const landing = site?.landing?.hero_title ? site.landing : FALLBACK_LANDING;
  const contact = site?.branding.contact_email ?? CONTACT_EMAIL;
  useMarketingReveal([]);

  return (
    <main className="home-main fx-home">
      <div className="fx-stage" aria-hidden="true">
        <span className="fx-orb fx-orb-a" />
        <span className="fx-orb fx-orb-b" />
        <span className="fx-orb fx-orb-c" />
      </div>

      <LandingHero landing={landing} />

      <section className="home-block home-trust" data-reveal id="sources">
        <div className="home-wrap">
          <h2>One job source, done well</h2>
          <p className="home-lead">ApplyXAI focuses on LinkedIn Easy Apply so discovery, tailoring, and submit stay reliable.</p>
          <div className="source-table source-table-single">
            <article className="is-ready">
              <div className="source-head">
                <img className="source-logo lg" src="/sources/linkedin.svg" alt="LinkedIn" width={52} height={52} />
                <div>
                  <span className="source-code">Supported today</span>
                  <h3 style={{ margin: 0 }}>LinkedIn</h3>
                </div>
              </div>
              <p style={{ margin: "8px 0 0", color: "#475569", fontSize: 14, lineHeight: 1.55 }}>
                Search, Easy Apply, optional AI resume tailoring, and full application history. External apply links are saved for you to complete manually.
              </p>
              <b className="ok">Active</b>
            </article>
          </div>
        </div>
      </section>

      <section className="home-block home-features" data-reveal id="features">
        <div className="home-wrap">
          <h2>{landing.features_heading}</h2>
          <p className="home-lead">Configured once in your workspace — runs on LinkedIn every time</p>
          <div className="feature-grid">
            {landing.features.map(({ icon, title, text }) => (
              <article key={title} className="feature-card">
                <FeatureIcon kind={icon} />
                <strong>{title}</strong>
                <p>{text}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="home-block home-auto_apply" data-reveal id="auto_apply">
        <div className="home-wrap">
          <h2>LinkedIn Auto Apply</h2>
          <p className="home-lead">Uses the Chrome profile where you are already signed in to LinkedIn</p>
          <div className="apply-layout">
            <div className="apply-panel">
              <p className="mock-label">Your browser</p>
              <ul className="apply-session">
                <li>Chrome window opened by the ApplyXAI agent</li>
                <li>LinkedIn login stays on linkedin.com</li>
                <li>Captcha and OTP stay with you</li>
              </ul>
              <Link className="home-cta" to="/register">Get the desktop agent</Link>
            </div>
            <div className="apply-rules">
              <article>
                <em>01</em>
                <div>
                  <strong>Your LinkedIn session</strong>
                  <p>You sign in once in the agent&apos;s browser. ApplyXAI never collects your LinkedIn password.</p>
                </div>
              </article>
              <article>
                <em>02</em>
                <div>
                  <strong>Easy Apply only</strong>
                  <p>The bot completes in-modal Easy Apply flows. External career sites are flagged in your dashboard.</p>
                </div>
              </article>
              <article>
                <em>03</em>
                <div>
                  <strong>Plan limits</strong>
                  <p>Monthly application quotas and run controls are enforced before each submit.</p>
                </div>
              </article>
            </div>
          </div>
          <div className="source-head apply-logos" style={{ marginTop: 22 }}>
            <img className="source-logo lg" src="/sources/linkedin.svg" alt="LinkedIn" width={52} height={52} />
            <div>
              <span className="source-code">Integrated source</span>
              <strong style={{ display: "block", fontSize: 18, color: "#0f2744" }}>LinkedIn Easy Apply</strong>
            </div>
          </div>
        </div>
      </section>

      <section className="home-block home-ai" data-reveal id="ai">
        <div className="home-wrap">
          <h2>AI that reads the LinkedIn job first</h2>
          <p className="home-lead">Match, tailor, and verify facts before an Easy Apply goes out</p>
          <div className="ai-steps">
            <article>
              <em>01</em>
              <strong>Read the posting</strong>
              <p>Skills and keywords are pulled from the LinkedIn job description before tailoring starts.</p>
            </article>
            <article>
              <em>02</em>
              <strong>Match your profile</strong>
              <p>Roles below your match threshold are skipped automatically.</p>
            </article>
            <article>
              <em>03</em>
              <strong>Fact-check the resume</strong>
              <p>Tailored files cannot add employers or skills missing from your master resume.</p>
            </article>
          </div>
        </div>
      </section>

      <section className="home-block home-resume" data-reveal id="resume">
        <div className="home-wrap">
          <h2>One master resume. Many LinkedIn applications.</h2>
          <p className="home-lead">Upload once — optional per-job DOCX copies for Easy Apply upload</p>
          <p><Link className="home-cta" to="/register">Open Resume Studio</Link></p>
          <div className="resume-highlights">
            <article><strong>Master file</strong><p>Single source of truth for employers, dates, and skills.</p></article>
            <article><strong>Per-job DOCX</strong><p>AI reorders and emphasizes evidenced skills for each posting.</p></article>
            <article><strong>Gate &amp; fact check</strong><p>Low-fit jobs and invented claims are blocked before upload.</p></article>
          </div>
          <ol className="resume-flow">
            <li><strong>Master resume</strong><span>Upload once</span></li>
            <li><strong>LinkedIn JD</strong><span>Read posting</span></li>
            <li><strong>Analysis</strong><span>Match score</span></li>
            <li><strong>Tailored DOCX</strong><span>If enabled</span></li>
            <li><strong>Easy Apply</strong><span>Upload &amp; submit</span></li>
          </ol>
        </div>
      </section>

      <section className="home-block home-interview" data-reveal id="interview">
        <div className="home-wrap">
          <h2>Interview prep</h2>
          <p className="home-lead">Practice for roles you discovered on LinkedIn</p>
          <p><Link className="home-cta" to="/register">Explore interview tools</Link></p>
          <div className="interview-blocks">
            <article className="interview-card">
              <FeatureIcon kind="bot" />
              <strong>Mock interviews</strong>
              <p>Practice answers aligned to the LinkedIn role you applied for.</p>
            </article>
            <article className="interview-card">
              <span className="flow-icon" aria-hidden>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
                  <path d="M4 8a8 8 0 0 1 16 0v3a3 3 0 0 1-3 3h-1v4l-4-4H8a4 4 0 0 1-4-4z" />
                </svg>
              </span>
              <strong>Live assistance</strong>
              <p>Get help during real interviews when your plan includes it.</p>
            </article>
          </div>
        </div>
      </section>

      <section className="home-block home-how_it_works" data-reveal id="how">
        <div className="home-wrap">
          <h2>{landing.steps_heading}</h2>
          <p className="home-lead">Four steps from resume upload to tracked LinkedIn applications</p>
          <div className="home-copy">
            <ol>
              {landing.steps.map(({ title, text }) => (
                <li key={title}>
                  <strong>{title}</strong>
                  {text}
                </li>
              ))}
            </ol>
          </div>
        </div>
      </section>

      <section className="home-block home-pricing" data-reveal id="pricing">
        <div className="home-wrap">
          <h2>{landing.pricing_heading}</h2>
          <p className="home-lead">{landing.pricing_subtitle}</p>
          <MarketingPricing />
          <p className="home-note">
            Campus and partner programs use seat-based plans.{" "}
            <Link to="/register/institute">Institute signup</Link> · <Link to="/register/partner">Partner signup</Link>
          </p>
        </div>
      </section>

      <section className="home-block home-statistics" data-reveal>
        <div className="home-wrap live-stats">
          <p className="live-stats-kicker">Platform activity</p>
          <div className="live-stats-grid">
            {LIVE_STATS.map(({ label, value }) => (
              <article key={label} className="live-stat">
                <span>{label}</span>
                <strong>{value}</strong>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="home-block" data-reveal id="faq">
        <div className="home-wrap">
          <h2>{landing.faq_heading}</h2>
          <div className="faq-grid">
            {landing.faq.map(({ question, answer }) => {
              const linkedInOnly = FALLBACK_LANDING.faq.find((x) => x.question.includes("job sites"))!.answer;
              const text = /job sites?/i.test(question) ? linkedInOnly : answer;
              return (
              <article key={question}>
                <h3>{question}</h3>
                <p>{text}</p>
              </article>
              );
            })}
          </div>
          <p className="home-copy" style={{ marginTop: 22, textAlign: "center" }}>
            {landing.faq_contact_line.includes("{contact_email}") ? (
              <>
                Still have questions? Email us at{" "}
                <a href={`mailto:${contact}`} style={{ color: "#2563eb", fontWeight: 700 }}>{contact}</a>.
              </>
            ) : (
              landing.faq_contact_line.replace("{contact_email}", contact)
            )}
          </p>
        </div>
      </section>

      <section className="home-block home-final_cta" data-reveal>
        <div className="home-wrap">
          <h2>Ready to run LinkedIn Easy Apply?</h2>
          <p className="home-lead">Create your account, upload a resume, connect the agent, and start your first search.</p>
          <div className="hero-actions" style={{ justifyContent: "center" }}>
            <Link className="home-cta" to="/register">Start applying free</Link>
            <a className="home-cta ghost" href="#how">See how it works</a>
          </div>
        </div>
      </section>
    </main>
  );
}
