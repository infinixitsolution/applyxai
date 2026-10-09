import { useEffect, useRef, useState } from "react";
import { Link, Outlet, useLocation } from "react-router-dom";
import { homeFor, useSession } from "../auth/session";
import { cx } from "../components/ui";
import { APP_NAME, CONTACT_EMAIL } from "../lib/config";
import { usePublicSite } from "../lib/usePublicSite";

const BANNER_TONE = {
  info: "border-brand-200 bg-brand-50 text-brand-900",
  warning: "border-amber-200 bg-amber-50 text-amber-900",
  success: "border-emerald-200 bg-emerald-50 text-emerald-900",
};

function useClickOutside(ref: React.RefObject<HTMLElement | null>, onClose: () => void, active: boolean) {
  useEffect(() => {
    if (!active) return;
    const onDoc = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) onClose();
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [active, onClose, ref]);
}

export function PublicLayout() {
  const { data: user } = useSession();
  const { data: site } = usePublicSite();
  const location = useLocation();
  const appName = site?.branding.app_name ?? APP_NAME;
  const contact = site?.branding.contact_email ?? CONTACT_EMAIL;
  const rawFooter = (site?.branding.footer_line ?? "").trim();
  const footerLine = rawFooter === "Built on the open-source Auto Job Applier (MIT)." ? "" : rawFooter;
  const banner = site?.banner;

  const [navOpen, setNavOpen] = useState(false);
  const [moreOpen, setMoreOpen] = useState(false);
  const [startOpen, setStartOpen] = useState(false);
  const startRef = useRef<HTMLDivElement>(null);
  const moreRef = useRef<HTMLDivElement>(null);
  useClickOutside(startRef, () => setStartOpen(false), startOpen);
  useClickOutside(moreRef, () => setMoreOpen(false), moreOpen);

  useEffect(() => {
    setNavOpen(false);
    setMoreOpen(false);
    setStartOpen(false);
  }, [location.pathname, location.hash]);

  const dash = user ? homeFor(user) : null;

  return (
    <div className="marketing-surface flex min-h-screen flex-col">
      {banner?.enabled && banner.message && (
        <div className={cx("border-b px-4 py-2 text-center text-sm", BANNER_TONE[banner.tone] ?? BANNER_TONE.info)}>
          {banner.message}
        </div>
      )}

      <div className="home-chrome">
        <div className="home-topbar">
          <div className="home-topbar-inner">
            <p className="home-topbar-note">LinkedIn Easy Apply automation — sign in locally, apply with AI</p>
            <div className="home-topbar-links">
              <a href={`mailto:${contact}`}>Help</a>
              <a href="/#faq">FAQ</a>
              <a href="/#features">Features</a>
              <a href={`mailto:${contact}`}>Contact</a>
              {user ? (
                <Link className="home-topbar-strong" to={dash!}>Dashboard</Link>
              ) : (
                <Link className="home-topbar-strong" to="/login">Sign in</Link>
              )}
            </div>
          </div>
        </div>

        <header className="home-nav">
          <Link className="home-brand" to="/">
            <img src="/mascot.png" alt="" width={40} height={40} />
            <span>
              <strong>Apply X Ai</strong>
              <small>AI Job Application Assistant</small>
            </span>
          </Link>
          <button
            type="button"
            className="home-menu"
            aria-expanded={navOpen}
            aria-controls="home-links"
            onClick={() => setNavOpen((v) => !v)}
          >
            Menu
          </button>
          <nav id="home-links" className={navOpen ? "open" : undefined}>
            <div className="nav-links">
              <Link to="/">Home</Link>
              <a href="/#features">Features</a>
              <a href="/#pricing">Pricing</a>
              <div className={cx("nav-more", moreOpen && "open")} ref={moreRef}>
                <button
                  type="button"
                  className="nav-more-toggle"
                  aria-expanded={moreOpen}
                  aria-controls="nav-more-menu"
                  onClick={() => setMoreOpen((v) => !v)}
                >
                  More
                </button>
                <div id="nav-more-menu" className="nav-more-menu">
                  <a href="/#interview">Interview Assistant</a>
                  <a href="/#faq">FAQ</a>
                  <Link to="/privacy">Privacy</Link>
                  <Link to="/terms">Terms</Link>
                </div>
              </div>
            </div>
            <div className="nav-actions">
              {user ? (
                <Link className="home-cta" to={dash!}>Open dashboard</Link>
              ) : (
                <>
                  <Link to="/login">Sign in</Link>
                  <div className={cx("customer-type-selector", startOpen && "open")} ref={startRef}>
                    <button
                      type="button"
                      className="home-cta"
                      aria-expanded={startOpen}
                      aria-controls="customer-type-dropdown"
                      onClick={() => setStartOpen((v) => !v)}
                    >
                      Get Started
                    </button>
                    <div id="customer-type-dropdown" className="customer-type-dropdown">
                      <Link to="/register" onClick={() => setStartOpen(false)}>As Candidate</Link>
                      <Link to="/register/institute" onClick={() => setStartOpen(false)}>As Institute</Link>
                      <Link to="/register/partner" onClick={() => setStartOpen(false)}>As Partner</Link>
                    </div>
                  </div>
                </>
              )}
            </div>
          </nav>
        </header>
      </div>

      <div className="flex-1 min-w-0 w-full"><Outlet /></div>

      <footer className="home-foot">
        <div className="home-wrap">
          <div className="foot-grid">
            <div className="foot-brand">
              <Link className="home-brand" to="/">
                <img src="/mascot.png" alt="" width={40} height={40} />
                <span>
                  <strong>{appName}</strong>
                  <small style={{ color: "#94a3b8" }}>AI Job Application Assistant</small>
                </span>
              </Link>
              <p style={{ margin: "12px 0 0", color: "#94a3b8", fontSize: 14, lineHeight: 1.5, maxWidth: 280 }}>
                LinkedIn search, optional AI resume tailoring, and Easy Apply tracking from one workspace.
              </p>
            </div>
            <div>
              <h2>Product</h2>
              <a href="/#features">Features</a>
              <a href="/#pricing">Pricing</a>
              <a href="/#auto_apply">LinkedIn Auto Apply</a>
              <a href="/#sources">Job source</a>
            </div>
            <div>
              <h2>Accounts</h2>
              <Link to="/register">Candidates</Link>
              <Link to="/register/institute">Institutes</Link>
              <Link to="/register/partner">Partners</Link>
              <Link to="/login">Sign in</Link>
            </div>
            <div>
              <h2>Legal</h2>
              <Link to="/privacy">Privacy</Link>
              <Link to="/terms">Terms</Link>
              <Link to="/refund-policy">Refunds</Link>
            </div>
            <div>
              <h2>Support</h2>
              <a href="/#faq">FAQ</a>
              <a href={`mailto:${contact}`}>Contact</a>
            </div>
          </div>
          <p className="foot-copy">
            © {new Date().getFullYear()} {appName}{footerLine ? `. ${footerLine}` : "."}
          </p>
        </div>
      </footer>
    </div>
  );
}

export { AuthCard, AuthShell } from "../features/auth";
