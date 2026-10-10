import { AlertCircle, CheckCircle2, Info, Loader2 } from "lucide-react";
import type { ButtonHTMLAttributes, ReactNode } from "react";
import { Link } from "react-router-dom";
import {
  formatUsageCap,
  isUnlimitedUsageCap,
  usageMeterPercent,
  type UsageMeterKind,
} from "../lib/format";

export function cx(...classes: (string | false | null | undefined)[]): string {
  return classes.filter(Boolean).join(" ");
}

/** Shared surface for tiles (jobs, stats, plan cards). */
export const surfaceCardClass =
  "rounded-xl bg-white shadow-sm ring-1 ring-slate-200/80";

type Variant = "primary" | "secondary" | "ghost" | "danger";

const VARIANTS: Record<Variant, string> = {
  primary: "bg-brand-600 text-white hover:bg-brand-700 shadow-sm",
  secondary: "bg-white text-slate-700 ring-1 ring-slate-300 hover:bg-slate-50 shadow-sm",
  ghost: "text-slate-600 hover:bg-slate-100",
  danger: "bg-red-600 text-white hover:bg-red-700 shadow-sm",
};

export function buttonClass(variant: Variant = "primary", size: "sm" | "md" = "md"): string {
  return cx(
    "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-lg font-medium transition-colors",
    "disabled:cursor-not-allowed disabled:opacity-60",
    size === "sm" ? "px-3 py-1.5 text-sm" : "px-4 py-2 text-sm",
    VARIANTS[variant],
  );
}

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: "sm" | "md";
  loading?: boolean;
}

export function Button({ variant = "primary", size = "md", loading, disabled, className, children, ...rest }: ButtonProps) {
  return (
    <button type="button" {...rest} disabled={disabled || loading}
            className={cx(buttonClass(variant, size), className)}>
      {loading && <Loader2 className="h-4 w-4 animate-spin" aria-hidden />}
      {children}
    </button>
  );
}

export function ButtonLink({ to, variant = "primary", size = "md", className, children }:
  { to: string; variant?: Variant; size?: "sm" | "md"; className?: string; children: ReactNode }) {
  return <Link to={to} className={cx(buttonClass(variant, size), className)}>{children}</Link>;
}

export function Card({ title, actions, children, className }:
  { title?: ReactNode; actions?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={cx(surfaceCardClass, "p-4 sm:p-5", className)}>
      {(title || actions) && (
        <header className="mb-4 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between sm:gap-3">
          {title && <h2 className="text-base font-semibold text-slate-900">{title}</h2>}
          {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
        </header>
      )}
      {children}
    </section>
  );
}

const TONES = {
  green: "bg-emerald-50 text-emerald-700 ring-emerald-600/20",
  red: "bg-red-50 text-red-700 ring-red-600/20",
  amber: "bg-amber-50 text-amber-800 ring-amber-600/20",
  blue: "bg-blue-50 text-blue-700 ring-blue-600/20",
  slate: "bg-slate-100 text-slate-700 ring-slate-500/20",
  brand: "bg-brand-50 text-brand-700 ring-brand-600/20",
};

export function Badge({ tone = "slate", children }: { tone?: keyof typeof TONES; children: ReactNode }) {
  return (
    <span className={cx("inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset", TONES[tone])}>
      {children}
    </span>
  );
}

export function Spinner({ label = "Loading…" }: { label?: string }) {
  return (
    <div role="status" className="flex items-center justify-center gap-2 py-10 text-sm text-slate-500">
      <Loader2 className="h-5 w-5 animate-spin" aria-hidden /> {label}
    </div>
  );
}

const ALERTS = {
  error: { cls: "bg-red-50 text-red-800 ring-red-200", Icon: AlertCircle },
  success: { cls: "bg-emerald-50 text-emerald-800 ring-emerald-200", Icon: CheckCircle2 },
  info: { cls: "bg-blue-50 text-blue-800 ring-blue-200", Icon: Info },
};

export function Alert({ kind = "info", children }: { kind?: keyof typeof ALERTS; children: ReactNode }) {
  const { cls, Icon } = ALERTS[kind];
  return (
    <div role={kind === "error" ? "alert" : "status"} className={cx("flex gap-2 rounded-lg p-3 text-sm ring-1", cls)}>
      <Icon className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
      <div>{children}</div>
    </div>
  );
}

export function EmptyState({ icon, title, children }: { icon?: ReactNode; title: string; children?: ReactNode }) {
  return (
    <div className="flex flex-col items-center gap-2 py-12 text-center">
      {icon && <div className="text-slate-400">{icon}</div>}
      <p className="font-medium text-slate-900">{title}</p>
      {children && <div className="max-w-md text-sm text-slate-500">{children}</div>}
    </div>
  );
}

export function PageHeader({ title, description, actions }: { title: string; description?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="mb-8 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-slate-900 sm:text-[1.65rem]">{title}</h1>
        {description && <p className="mt-1.5 max-w-2xl text-sm leading-relaxed text-slate-600">{description}</p>}
      </div>
      {actions && <div className="flex shrink-0 flex-wrap gap-2">{actions}</div>}
    </div>
  );
}

export function StatCard({ icon, label, value, sub, className }: {
  icon: ReactNode; label: string; value: ReactNode; sub?: ReactNode; className?: string;
}) {
  return (
    <div className={cx(surfaceCardClass, "p-5", className)}>
      <div className="flex items-center gap-2 text-sm font-medium text-slate-500">{icon}{label}</div>
      <p className="mt-2 text-3xl font-bold tracking-tight text-slate-900">{value}</p>
      {sub && <p className="mt-1 text-xs text-slate-500">{sub}</p>}
    </div>
  );
}

export function Tabs<T extends string>({ tabs, value, onChange, className }: {
  tabs: { id: T; label: string }[]; value: T; onChange: (id: T) => void; className?: string;
}) {
  return (
    <div role="tablist" className={cx("mb-6 flex gap-1 rounded-xl bg-slate-100/90 p-1 ring-1 ring-slate-200/70 sm:inline-flex", className)}>
      {tabs.map((t) => (
        <button
          key={t.id}
          role="tab"
          type="button"
          aria-selected={value === t.id}
          onClick={() => onChange(t.id)}
          className={cx(
            "flex-1 rounded-lg px-4 py-2 text-sm font-medium transition-colors sm:flex-none",
            value === t.id ? "bg-white text-slate-900 shadow-sm ring-1 ring-slate-200/80" : "text-slate-600 hover:text-slate-900",
          )}
        >
          {t.label}
        </button>
      ))}
    </div>
  );
}

/** Horizontal tabs for admin settings and long tab lists (scrolls on small screens). */
export function AdminTabNav<T extends string>({ tabs, value, onChange, ariaLabel = "Sections" }: {
  tabs: { id: T; label: string }[]; value: T; onChange: (id: T) => void; ariaLabel?: string;
}) {
  return (
    <nav className="mb-8 flex gap-0.5 overflow-x-auto border-b border-slate-200/80 pb-px" aria-label={ariaLabel}>
      {tabs.map((t) => (
        <button
          key={t.id}
          type="button"
          onClick={() => onChange(t.id)}
          className={cx(
            "shrink-0 border-b-2 px-3 py-2.5 text-sm font-medium whitespace-nowrap transition-colors",
            value === t.id
              ? "border-brand-600 text-brand-700"
              : "border-transparent text-slate-600 hover:border-slate-300 hover:text-slate-900",
          )}
        >
          {t.label}
        </button>
      ))}
    </nav>
  );
}

/** Vertical section menu for admin settings (left panel + content on lg+). */
export function AdminSettingsSideNav<T extends string>({ tabs, value, onChange, ariaLabel = "Settings sections" }: {
  tabs: { id: T; label: string }[]; value: T; onChange: (id: T) => void; ariaLabel?: string;
}) {
  return (
    <aside className="lg:sticky lg:top-24 lg:self-start">
      <nav className={cx(surfaceCardClass, "flex flex-col gap-0.5 p-2")} aria-label={ariaLabel}>
        {tabs.map((t) => {
          const active = value === t.id;
          return (
            <button
              key={t.id}
              type="button"
              onClick={() => onChange(t.id)}
              aria-current={active ? "page" : undefined}
              className={cx(
                "relative rounded-lg py-2 pr-3 text-left text-sm font-medium transition-colors",
                active ? "bg-slate-100 pl-4 text-slate-900" : "pl-3 text-slate-600 hover:bg-slate-50 hover:text-slate-900",
              )}
            >
              {active && (
                <span className="absolute inset-y-1.5 left-0 w-1 rounded-full bg-slate-900" aria-hidden />
              )}
              {t.label}
            </button>
          );
        })}
      </nav>
    </aside>
  );
}

export function UserAvatar({ name, email }: { name: string; email?: string }) {
  const source = name.trim() || email || "?";
  const parts = source.replace(/@.*/, "").split(/\s+/).filter(Boolean);
  const initials = parts.length >= 2
    ? `${parts[0][0]}${parts[1][0]}`.toUpperCase()
    : source.slice(0, 2).toUpperCase();
  return (
    <span
      className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-brand-600 text-xs font-bold text-white ring-2 ring-white"
      title={email ? `${name} (${email})` : name}
      aria-hidden
    >
      {initials}
    </span>
  );
}

export function ProgressBar({ value, max, label, usageKind }: {
  value: number; max: number; label: string; usageKind?: UsageMeterKind;
}) {
  const kind = usageKind ?? (label.toLowerCase().includes("resume") ? "resumes" : "applications");
  const unlimited = isUnlimitedUsageCap(max, kind);
  const pct = usageMeterPercent(value, max, kind);
  const atCap = !unlimited && max > 0 && value >= max;
  return (
    <div>
      <div className="mb-1.5 flex justify-between gap-2 text-sm">
        <span className="text-slate-600">{label}</span>
        <span className="shrink-0 font-medium tabular-nums text-slate-900">
          {value.toLocaleString()} / {formatUsageCap(max, kind)}
        </span>
      </div>
      <div
        className="h-2.5 overflow-hidden rounded-full bg-slate-100 ring-1 ring-slate-200/60"
        role="progressbar"
        aria-label={label}
        aria-valuenow={value}
        aria-valuemin={0}
        aria-valuemax={unlimited ? undefined : max}
        aria-valuetext={unlimited ? `${value} used, unlimited plan` : `${pct}% of plan limit`}
      >
        <div
          className={cx(
            "h-full min-w-[6px] rounded-full transition-[width] duration-300",
            atCap ? "bg-red-500" : pct >= 80 && !unlimited ? "bg-amber-500" : "bg-brand-600",
          )}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}
