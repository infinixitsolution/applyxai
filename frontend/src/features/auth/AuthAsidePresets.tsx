import type { ReactNode } from "react";

function AsideBlock({
  kicker,
  title,
  lead,
  bullets,
  footer,
}: {
  kicker: string;
  title: string;
  lead: string;
  bullets: ReactNode[];
  footer?: ReactNode;
}) {
  return (
    <>
      <p className="auth-aside-kicker">{kicker}</p>
      <h2 className="auth-aside-title">{title}</h2>
      <p className="auth-aside-lead">{lead}</p>
      <ul className="auth-aside-list">
        {bullets.map((item, i) => (
          <li key={i}>
            <span className="auth-aside-icon" aria-hidden>
              ✓
            </span>
            {item}
          </li>
        ))}
      </ul>
      {footer}
    </>
  );
}

export function DefaultAuthStory() {
  return (
    <AsideBlock
      kicker="LinkedIn Easy Apply"
      title="Apply smarter with AI — safely, from your browser."
      lead="Search LinkedIn, tailor resumes when you want, and track every submission from one workspace."
      bullets={[
        "Desktop agent runs on your PC — you sign in to LinkedIn locally",
        "Optional AI resume tailoring without inventing experience",
        "Full application history and screening-answer memory",
      ]}
      footer={
        <div className="auth-aside-source">
          <img src="/sources/linkedin.svg" alt="" width={28} height={28} className="source-logo" />
          <span>LinkedIn only</span>
        </div>
      }
    />
  );
}

export function LoginAside() {
  return (
    <AsideBlock
      kicker="Your workspace"
      title="Sign in and run LinkedIn Easy Apply from your PC."
      lead="Track every application, connect the desktop agent, and tune filters — we never see your LinkedIn password."
      bullets={[
        "Application history with AI-tailored vs master resume",
        "Saved screening answers plus optional AI for new questions",
        "Daily caps, dry runs, and pause/stop from one dashboard",
      ]}
      footer={
        <div className="auth-aside-source">
          <img src="/sources/linkedin.svg" alt="" width={28} height={28} className="source-logo" />
          <span>LinkedIn Easy Apply only</span>
        </div>
      }
    />
  );
}

export function RegisterCandidateAside() {
  return (
    <AsideBlock
      kicker="Free to start"
      title="Create a candidate account in under a minute."
      lead="Upload a master resume, set LinkedIn search preferences, and install the agent when you're ready to apply."
      bullets={[
        "Optional AI resume tailoring per job — no invented experience",
        "Skip blacklisted companies and low match scores automatically",
        "Export application history anytime",
      ]}
      footer={
        <div className="auth-aside-source">
          <img src="/sources/linkedin.svg" alt="" width={28} height={28} className="source-logo" />
          <span>Built for LinkedIn job search</span>
        </div>
      }
    />
  );
}

export function RegisterInstituteAside() {
  return (
    <AsideBlock
      kicker="Campus & training"
      title="Give students a guided path to LinkedIn applications."
      lead="Institute accounts manage seats, invite students, and see adoption — while each student runs automation on their own machine."
      bullets={[
        "Bulk invites and seat management from an institute dashboard",
        "Students keep their own ApplyXAI login and data",
        "Partner referral codes supported at signup",
      ]}
    />
  );
}

export function RegisterPartnerAside() {
  return (
    <AsideBlock
      kicker="Referral network"
      title="Partner with ApplyXAI and earn on referred institutes."
      lead="Submit your organisation details. Our team reviews partner applications and enables your referral tools after approval."
      bullets={[
        "Unique referral links for institute signups",
        "Commission tracking in the partner workspace",
        "Co-branded onboarding for referred campuses",
      ]}
    />
  );
}

export function PasswordAside() {
  return (
    <AsideBlock
      kicker="Account security"
      title="Reset access in a few clicks."
      lead="We email a single-use link. Choosing a new password signs you out everywhere for safety."
      bullets={[
        "Reset links expire after 60 minutes",
        "No password hints stored — only secure hashes",
        "Verify your email anytime from the login screen",
      ]}
    />
  );
}

export function CheckEmailAside() {
  return (
    <AsideBlock
      kicker="Almost there"
      title="Confirm your email to unlock your dashboard."
      lead="We sent a secure link to the address you used at signup. Click it once — links expire in 24 hours."
      bullets={[
        "Check spam or promotions if nothing arrives in a few minutes",
        "You can request a fresh link from this page",
        "After verifying, log in and complete onboarding",
      ]}
    />
  );
}

export function InviteAside({ instituteName }: { instituteName?: string }) {
  return (
    <AsideBlock
      kicker="Campus invitation"
      title={instituteName ? `Join ${instituteName}` : "Accept your campus seat"}
      lead="Your institute invited you to ApplyXAI. Create an account or log in with the invited email to activate your seat."
      bullets={[
        "Same LinkedIn automation as individual candidates",
        "Billing handled through your campus plan",
        "Your application data stays in your account",
      ]}
    />
  );
}
