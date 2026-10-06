import { Link, Outlet } from "react-router-dom";
import { Logo } from "../components/Logo";
import { ButtonLink } from "../components/ui";
import { useSession } from "../auth/session";
import { APP_NAME, CONTACT_EMAIL } from "../lib/config";

export function PublicLayout() {
  const { data: user } = useSession();
  return (
    <div className="flex min-h-screen flex-col bg-white">
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
          <p>© {new Date().getFullYear()} {APP_NAME}. Built on the open-source Auto Job Applier (MIT).</p>
          <nav className="flex flex-wrap gap-4">
            <Link to="/privacy" className="hover:text-slate-700">Privacy</Link>
            <Link to="/terms" className="hover:text-slate-700">Terms</Link>
            <Link to="/refund-policy" className="hover:text-slate-700">Refunds</Link>
            <a href={`mailto:${CONTACT_EMAIL}`} className="hover:text-slate-700">Contact</a>
          </nav>
        </div>
      </footer>
    </div>
  );
}

export function AuthCard({ title, subtitle, children }: { title: string; subtitle?: React.ReactNode; children: React.ReactNode }) {
  return (
    <div className="flex min-h-[calc(100vh-10rem)] items-center justify-center px-4 py-12">
      <div className="w-full max-w-md">
        <h1 className="text-center text-2xl font-semibold tracking-tight text-slate-900">{title}</h1>
        {subtitle && <p className="mt-2 text-center text-sm text-slate-500">{subtitle}</p>}
        <div className="mt-8 rounded-xl bg-white p-6 shadow-sm ring-1 ring-slate-200">{children}</div>
      </div>
    </div>
  );
}
