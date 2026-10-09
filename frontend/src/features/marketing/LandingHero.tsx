import { Link } from "react-router-dom";
import type { PlatformCms } from "../../types";

type LandingCopy = PlatformCms["landing"];

const STEPS = ["Search", "Tailor", "Apply", "Track"] as const;

export function LandingHero({ landing }: { landing: LandingCopy }) {
  return (
    <section id="hero" className="ax-hero" aria-labelledby="ax-hero-title">
      <div className="ax-hero__glow" aria-hidden="true" />
      <div className="home-wrap ax-hero__inner">
        <div className="ax-hero__grid">
          <div className="ax-hero__copy">
            <p className="ax-hero__badge">
              <span className="ax-hero__badge-dot" aria-hidden />
              {landing.hero_badge}
            </p>
            <h1 id="ax-hero-title" className="ax-hero__title">
              {landing.hero_title}
            </h1>
            <p className="ax-hero__subtitle">{landing.hero_subtitle}</p>

            <ol className="ax-hero__flow" aria-label="How ApplyXAI works">
              {STEPS.map((label, i) => (
                <li key={label} className={i === 0 ? "is-current" : undefined}>
                  {label}
                </li>
              ))}
            </ol>

            <div className="ax-hero__actions">
              <Link className="home-cta ax-hero__cta" to="/register">
                {landing.hero_cta_primary}
              </Link>
              <a className="home-cta ghost ax-hero__cta" href="#how">
                {landing.hero_cta_secondary}
              </a>
            </div>

            <div className="ax-hero__meta">
              <p className="ax-hero__footnote">{landing.hero_footnote}</p>
              <nav className="ax-hero__links" aria-label="Create an account">
                <Link to="/register">Candidates</Link>
                <span aria-hidden>·</span>
                <Link to="/register/institute">Institutes</Link>
                <span aria-hidden>·</span>
                <Link to="/register/partner">Partners</Link>
              </nav>
            </div>
          </div>

          <aside className="ax-hero__panel" aria-label="LinkedIn Easy Apply preview">
            <div className="ax-hero__panel-chrome">
              <span aria-hidden />
              <span aria-hidden />
              <span aria-hidden />
              <span>LinkedIn · Easy Apply</span>
            </div>
            <div className="ax-hero__panel-job">
              <p className="ax-hero__panel-label">Now applying</p>
              <strong>Senior Product Designer</strong>
              <span>Remote · Easy Apply</span>
              <div className="ax-hero__panel-bar" aria-hidden>
                <i style={{ width: "68%" }} />
              </div>
            </div>
            <ul className="ax-hero__panel-steps">
              <li className="is-done">
                <em>1</em>
                <span>Resume uploaded</span>
              </li>
              <li className="is-active">
                <em>2</em>
                <span>Screening answers</span>
              </li>
              <li>
                <em>3</em>
                <span>Submit application</span>
              </li>
            </ul>
          </aside>
        </div>
      </div>
    </section>
  );
}
