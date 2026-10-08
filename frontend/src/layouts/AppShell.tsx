import { useMutation } from "@tanstack/react-query";
import {
  ArrowLeft, Bot, Briefcase, CreditCard, FileText, LayoutDashboard, ListChecks, LogOut, Menu, Package, Receipt,
  ServerCog, Settings, Shield, SlidersHorizontal, UserRound, Users, X,
} from "lucide-react";
import { useEffect, useState } from "react";
import { Link, NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { useSession, useSetSession } from "../auth/session";
import { Logo } from "../components/Logo";
import { NotificationBell } from "../components/NotificationBell";
import { cx } from "../components/ui";
import { auth } from "../services/endpoints";

const APP_NAV = [
  { to: "/app", label: "Dashboard", icon: LayoutDashboard, end: true },
  { to: "/app/jobs", label: "Jobs", icon: Briefcase },
  { to: "/app/applications", label: "Applications", icon: ListChecks },
  { to: "/app/automation", label: "Automation", icon: Bot },
  { to: "/app/resumes", label: "Resumes", icon: FileText },
  { to: "/app/preferences", label: "Preferences", icon: SlidersHorizontal },
  { to: "/app/profile", label: "Profile", icon: UserRound },
  { to: "/app/billing", label: "Billing", icon: CreditCard },
  { to: "/app/settings", label: "Settings", icon: Settings },
];

const ADMIN_NAV = [
  { to: "/admin", label: "Overview", icon: LayoutDashboard, end: true },
  { to: "/admin/users", label: "Users", icon: Users },
  { to: "/admin/subscriptions", label: "Subscriptions", icon: Receipt },
  { to: "/admin/runs", label: "Automation runs", icon: Bot },
  { to: "/admin/applications", label: "Applications", icon: ListChecks },
  { to: "/admin/plans", label: "Plans", icon: Package },
  { to: "/admin/system", label: "Settings", icon: ServerCog },
];

type Variant = "app" | "admin";

function SidebarNav({ variant, onNavigate }: { variant: Variant; onNavigate?: () => void }) {
  return (
    <nav className="flex flex-1 flex-col gap-1 px-3 py-4" aria-label="Main">
      {(variant === "admin" ? ADMIN_NAV : APP_NAV).map(({ to, label, icon: Icon, end }) => (
        <NavLink key={to} to={to} end={end} onClick={onNavigate}
                 className={({ isActive }) => cx(
                   "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                   isActive ? "bg-brand-50 text-brand-700" : "text-slate-600 hover:bg-slate-100 hover:text-slate-900",
                 )}>
          <Icon className="h-5 w-5 shrink-0" aria-hidden />
          {label}
        </NavLink>
      ))}
    </nav>
  );
}

function Brand({ variant }: { variant: Variant }) {
  return (
    <div className="flex items-center gap-2">
      <Logo to={variant === "admin" ? "/admin" : "/app"} />
      {variant === "admin" && (
        <span className="rounded bg-slate-900 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-white">Admin</span>
      )}
    </div>
  );
}

export function AppShell({ variant = "app" }: { variant?: Variant }) {
  const [drawer, setDrawer] = useState(false);
  const { data: user } = useSession();
  const setSession = useSetSession();
  const navigate = useNavigate();
  const location = useLocation();
  const logout = useMutation({
    mutationFn: auth.logout,
    onSettled: () => { setSession(null); navigate("/login", { replace: true }); },
  });

  useEffect(() => setDrawer(false), [location.pathname]);

  const name = user ? [user.first_name, user.last_name].filter(Boolean).join(" ") || user.email : "";
  const switchLink = "hidden items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-medium text-slate-600 ring-1 ring-slate-200 hover:bg-slate-50 sm:inline-flex";

  return (
    <div className="min-h-screen bg-slate-50">
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-64 flex-col border-r border-slate-200 bg-white md:flex">
        <div className="flex h-16 items-center px-6"><Brand variant={variant} /></div>
        <SidebarNav variant={variant} />
      </aside>

      {drawer && (
        <div className="fixed inset-0 z-40 md:hidden" role="dialog" aria-modal="true" aria-label="Menu">
          <div className="absolute inset-0 bg-slate-900/40" onClick={() => setDrawer(false)} />
          <aside className="absolute inset-y-0 left-0 flex w-72 flex-col bg-white shadow-xl">
            <div className="flex h-16 items-center justify-between px-6">
              <Brand variant={variant} />
              <button type="button" aria-label="Close menu" onClick={() => setDrawer(false)} className="text-slate-500">
                <X className="h-5 w-5" />
              </button>
            </div>
            <SidebarNav variant={variant} onNavigate={() => setDrawer(false)} />
          </aside>
        </div>
      )}

      <div className="md:pl-64">
        <header className="sticky top-0 z-20 flex h-16 items-center gap-3 border-b border-slate-200 bg-white/90 px-4 backdrop-blur sm:px-6">
          <button type="button" aria-label="Open menu" onClick={() => setDrawer(true)}
                  className="rounded-lg p-2 text-slate-500 hover:bg-slate-100 md:hidden">
            <Menu className="h-5 w-5" />
          </button>
          <div className="flex-1" />
          {variant === "admin" ? (
            <Link to="/app" className={switchLink}><ArrowLeft className="h-4 w-4" aria-hidden /> Back to app</Link>
          ) : user?.is_admin ? (
            <Link to="/admin" className={switchLink}><Shield className="h-4 w-4" aria-hidden /> Admin</Link>
          ) : null}
          {variant === "app" && <NotificationBell />}
          <div className="hidden text-right text-sm sm:block">
            <p className="font-medium text-slate-900">{name}</p>
            {name !== user?.email && <p className="text-xs text-slate-500">{user?.email}</p>}
          </div>
          <button type="button" onClick={() => logout.mutate()} aria-label="Log out" title="Log out"
                  className="rounded-lg p-2 text-slate-500 hover:bg-slate-100 hover:text-slate-700">
            <LogOut className="h-5 w-5" />
          </button>
        </header>
        <main className={cx("mx-auto px-4 py-8 sm:px-6", variant === "admin" ? "max-w-7xl" : "max-w-6xl")}><Outlet /></main>
      </div>
    </div>
  );
}
