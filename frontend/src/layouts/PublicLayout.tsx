import { Link, Outlet } from "react-router-dom";
import { Logo } from "../components/Logo";
import { ButtonLink, cx } from "../components/ui";
import { useSession } from "../auth/session";
import { usePublicSite } from "../lib/usePublicSite";
import { APP_NAME, CONTACT_EMAIL } from "../lib/config";

const BANNER_TONE = {
  info: "border-brand-200 bg-brand-50 text-brand-900",
  warning: "border-amber-200 bg-amber-50 text-amber-900",
  success: "border-emerald-200 bg-emerald-50 text-emerald-900",
};

export function PublicLayout() {
  const { data: user } = useSession();
  const { data: site } = usePublicSite();
  const appName = site?.branding.app_name ?? APP_NAME;
  const contact = site?.branding.contact_email ?? CONTACT_EMAIL;
  const footerLine = site?.branding.footer_line ?? "Built on the open-source Auto Job Applier (MIT).";
  const banner = site?.banner;

  return (
    <div className="flex min-h-screen flex-col bg-white">
      {banner?.enabled && banner.message && (
        <div className={cx("border-b px-4 py-2 text-center text-sm", BANNER_TONE[banner.tone] ?? BANNER_TONE.info)}>
          {banner.message}
        </div>
      )}
      <header className="sticky top-0 z-30 border-b border-slate-100 bg-white/90 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4">
          <Logo />
          <nav className="flex items-center gap-2 text-sm">
            <a href="/#features" className="hidden px-3 py-2 text-slate-600 hover:text-slate-900 sm:block">Features</a>
            <a href="/#pricing" className="hidden px-3 py-2 text-slate-600 hover:text-slate-900 sm:block">Pricing</a>
            <a href="/#faq" className="hidden px-3 py-2 text-slate-600 hover:text-slate-900 sm:block">FAQ</a>
            {user ? (
              <ButtonLink to="/app" size="sm">Open dashboard</ButtonLink>
            ) : (
              <>
                <Link to="/login" className="px-3 py-2 font-medium text-slate-700 hover:text-slate-900">Log in</Link>
                <ButtonLink to="/register" size="sm">Get started</ButtonLink>
              </>
            )}
          </nav>
        </div>
      </header>
      <main className="flex-1"><Outlet /></main>
      <footer className="border-t border-slate-100 bg-slate-50">
        <div className="mx-auto flex max-w-6xl flex-col gap-4 px-4 py-8 text-sm text-slate-500 sm:flex-row sm:justify-between">
          <p>© {new Date().getFullYear()} {appName}. {footerLine}</p>
          <nav className="flex flex-wrap gap-4">
            <Link to="/privacy" className="hover:text-slate-700">Privacy</Link>
            <Link to="/terms" className="hover:text-slate-700">Terms</Link>
            <Link to="/refund-policy" className="hover:text-slate-700">Refunds</Link>
            <a href={`mailto:${contact}`} className="hover:text-slate-700">Contact</a>
          </nav>
        </div>
      </footer>
    </div>
  );
}

export function AuthCard({ title, subtitle, children }: { title: string; subtitle?: React.ReactNode; children: React.ReactNode }) {
  return (
    <div className="mx-auto w-full max-w-md px-4 py-12">
      <h1 className="text-2xl font-bold tracking-tight text-slate-900">{title}</h1>
      {subtitle && <div className="mt-2 text-sm text-slate-600">{subtitle}</div>}
      <div className="mt-8 rounded-xl bg-white p-6 shadow-sm ring-1 ring-slate-200">{children}</div>
    </div>
  );
}
