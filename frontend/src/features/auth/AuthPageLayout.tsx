import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { cx } from "../../components/ui";

export type AuthHighlight = { title: string; description: string };

export type AuthPageTone = "default" | "institute" | "partner";

export type AuthRegisterTab = "candidate" | "institute" | "partner";

export function AuthRegisterTabs({ active }: { active: AuthRegisterTab }) {
  const tabs: { id: AuthRegisterTab; label: string; hint: string; to: string }[] = [
    { id: "candidate", label: "Job seeker", hint: "LinkedIn apply", to: "/register" },
    { id: "institute", label: "Institute", hint: "Campus seats", to: "/register/institute" },
    { id: "partner", label: "Partner", hint: "Referrals", to: "/register/partner" },
  ];
  return (
    <nav className="ax-login__tabs" aria-label="Account type">
      {tabs.map((tab) => (
        <Link
          key={tab.id}
          to={tab.to}
          className={cx("ax-login__tab", active === tab.id && "is-active")}
          aria-current={active === tab.id ? "page" : undefined}
        >
          <strong>{tab.label}</strong>
          <span>{tab.hint}</span>
        </Link>
      ))}
    </nav>
  );
}

export type AuthPageLayoutProps = {
  tone?: AuthPageTone;
  storyAriaLabel: string;
  kicker: ReactNode;
  storyTitle: string;
  storyLead: string;
  highlights: AuthHighlight[];
  showLinkedInTrust?: boolean;
  trustLabel?: string;
  trustSub?: string;
  cardHeadingId: string;
  cardTitle: string;
  cardSubtitle?: ReactNode;
  registerTabs?: AuthRegisterTab;
  wideCard?: boolean;
  children: ReactNode;
  footer?: ReactNode;
};

export function AuthPageLayout({
  tone = "default",
  storyAriaLabel,
  kicker,
  storyTitle,
  storyLead,
  highlights,
  showLinkedInTrust = true,
  trustLabel = "LinkedIn only",
  trustSub = "Easy Apply automation today",
  cardHeadingId,
  cardTitle,
  cardSubtitle,
  registerTabs,
  wideCard,
  children,
  footer,
}: AuthPageLayoutProps) {
  return (
    <div className={cx("ax-login", tone !== "default" && `ax-login--${tone}`)} data-tone={tone}>
      <div className="ax-login__backdrop" aria-hidden="true">
        <span className="ax-login__orb ax-login__orb-a" />
        <span className="ax-login__orb ax-login__orb-b" />
      </div>

      <div className="ax-login__main">
        <section className="ax-login__story" aria-label={storyAriaLabel}>
          <p className="ax-login__story-kicker">{kicker}</p>
          <h1 className="ax-login__story-title">{storyTitle}</h1>
          <p className="ax-login__story-lead">{storyLead}</p>
          <ul className="ax-login__highlights">
            {highlights.map((item) => (
              <li key={item.title}>
                <strong>{item.title}</strong>
                <span>{item.description}</span>
              </li>
            ))}
          </ul>
          {(showLinkedInTrust || trustLabel) && (
            <div className="ax-login__trust">
              {showLinkedInTrust ? (
                <img src="/sources/linkedin.svg" alt="" width={32} height={32} />
              ) : (
                <span className="ax-login__trust-mark" aria-hidden />
              )}
              <div>
                <strong>{trustLabel}</strong>
                <span>{trustSub}</span>
              </div>
            </div>
          )}
        </section>

        <section className="ax-login__panel" aria-labelledby={cardHeadingId}>
          <div className={cx("ax-login__card", wideCard && "ax-login__card--wide")}>
            {registerTabs && <AuthRegisterTabs active={registerTabs} />}
            <div className="ax-login__card-head">
              <h2 id={cardHeadingId}>{cardTitle}</h2>
              {cardSubtitle && <div className="ax-login__card-sub">{cardSubtitle}</div>}
            </div>
            {children}
            {footer}
          </div>
        </section>
      </div>
    </div>
  );
}

export function AuthLegalLinks() {
  return (
    <p className="ax-login__legal">
      By continuing you agree to our{" "}
      <Link to="/terms" className="ax-login__link">
        Terms
      </Link>{" "}
      and{" "}
      <Link to="/privacy" className="ax-login__link">
        Privacy Policy
      </Link>
      .
    </p>
  );
}
