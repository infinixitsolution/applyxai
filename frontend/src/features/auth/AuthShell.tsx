import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { cx } from "../../components/ui";
import { DefaultAuthStory } from "./AuthAsidePresets";

export type AuthShellProps = {
  kicker?: string;
  title: string;
  subtitle?: ReactNode;
  /** Left panel content (defaults to generic product story). */
  aside?: ReactNode;
  asideTone?: "default" | "institute" | "partner";
  /** @deprecated Equal two-column layout; form panel scrolls when needed. */
  wide?: boolean;
  top?: ReactNode;
  /** Shown under the form panel tag (legacy prop name). */
  brandTagline?: string;
  children: ReactNode;
};

export function AuthShell({
  kicker,
  title,
  subtitle,
  aside,
  asideTone = "default",
  top,
  brandTagline = "Your account",
  children,
}: AuthShellProps) {
  const story = aside ?? <DefaultAuthStory />;

  return (
    <main className="home-main auth-page">
      <div className="auth-dual-wrap">
        <article className="auth-dual">
          <section
            className={cx(
              "auth-dual-section auth-dual-story",
              asideTone !== "default" && `auth-dual-story-${asideTone}`,
            )}
            aria-label="Product overview"
          >
            <div className="auth-dual-story-inner">
              <p className="auth-panel-tag auth-panel-tag-light">Overview</p>
              <Link to="/" className="auth-dual-brand">
                <img src="/mascot.png" alt="" width={48} height={48} />
                <span>
                  <strong>Apply X Ai</strong>
                  <small>AI Job Application Assistant</small>
                </span>
              </Link>
              <div className="auth-dual-story-content">{story}</div>
            </div>
            <div className="auth-dual-story-glow" aria-hidden />
          </section>

          <section className="auth-dual-section auth-dual-form" aria-label="Account">
            <div className="auth-dual-form-inner">
              <p className="auth-panel-tag">{brandTagline}</p>
              {top}
              {kicker && <p className="auth-kicker">{kicker}</p>}
              <h1 className="auth-title">{title}</h1>
              {subtitle && <div className="auth-subtitle">{subtitle}</div>}
              <div className="auth-form-body">{children}</div>
            </div>
          </section>
        </article>
      </div>
    </main>
  );
}

export function AuthCard(props: Omit<AuthShellProps, "aside" | "wide" | "top">) {
  return <AuthShell {...props} />;
}

export function AuthAccountTabs({ active }: { active: "candidate" | "institute" | "partner" }) {
  const tabs = [
    { id: "candidate" as const, label: "Job seeker", hint: "LinkedIn apply", to: "/register" },
    { id: "institute" as const, label: "Institute", hint: "Campus seats", to: "/register/institute" },
    { id: "partner" as const, label: "Partner", hint: "Referrals", to: "/register/partner" },
  ];
  return (
    <nav className="auth-account-tabs" aria-label="Account type">
      {tabs.map((tab) => (
        <Link
          key={tab.id}
          to={tab.to}
          className={cx("auth-account-tab", active === tab.id && "active")}
          aria-current={active === tab.id ? "page" : undefined}
        >
          <strong>{tab.label}</strong>
          <span>{tab.hint}</span>
        </Link>
      ))}
    </nav>
  );
}

export function AuthFormSection({ title, children }: { title: string; children: ReactNode }) {
  return (
    <fieldset className="auth-form-section">
      <legend>{title}</legend>
      <div className="auth-form-section-fields">{children}</div>
    </fieldset>
  );
}

export function AuthLegalFoot() {
  return (
    <p className="auth-form-foot">
      By continuing you agree to our{" "}
      <Link to="/terms" className="auth-text-link">
        Terms
      </Link>{" "}
      and{" "}
      <Link to="/privacy" className="auth-text-link">
        Privacy Policy
      </Link>
      .
    </p>
  );
}
