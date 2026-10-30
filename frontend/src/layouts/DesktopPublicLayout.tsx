import { Link, Navigate, Outlet } from "react-router-dom";
import { DesktopConnectionPanel } from "../components/DesktopConnectionPanel";
import { APP_NAME, publicWebsiteUrl } from "../lib/config";

/** Minimal shell for ApplyXAI Desktop — no marketing site, auth pages only. */
export function DesktopPublicLayout() {
  const website = publicWebsiteUrl();

  return (
    <div className="flex min-h-screen flex-col bg-slate-50">
      <header className="border-b border-slate-200 bg-white px-4 py-3 sm:px-6">
        <div className="mx-auto flex max-w-lg items-center justify-between gap-4">
          <Link to="/login" className="flex items-center gap-2 font-semibold text-slate-900">
            <img src="/mascot.png" alt="" className="h-9 w-9 rounded-lg ring-1 ring-slate-200" width={36} height={36} />
            {APP_NAME}
          </Link>
          <a
            href={website}
            target="_blank"
            rel="noopener noreferrer"
            className="text-sm font-medium text-brand-600 hover:underline"
          >
            Visit website
          </a>
        </div>
      </header>
      <main className="desktop-auth-shell mx-auto flex w-full max-w-[440px] flex-1 flex-col justify-center gap-4 px-4 py-6 sm:px-6">
        <DesktopConnectionPanel />
        <Outlet />
      </main>
      <footer className="border-t border-slate-200 px-4 py-4 text-center text-xs text-slate-500">
        <a href={website} target="_blank" rel="noopener noreferrer" className="font-medium text-brand-600 hover:underline">
          {website.replace(/^https?:\/\//, "")}
        </a>
        {" · "}
        Full marketing site, pricing, and legal pages open in your browser.
      </footer>
    </div>
  );
}

export function DesktopPublicIndex() {
  return <Navigate to="/login" replace />;
}
