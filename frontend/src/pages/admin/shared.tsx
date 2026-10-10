import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { ChevronRight, type LucideIcon } from "lucide-react";
import { Badge, cx, surfaceCardClass } from "../../components/ui";
import { formatMoney } from "../../lib/format";
import type { RunStatus, Subscription, SubscriptionStatus } from "../../types";

export const PAGE_SIZE = 25;

export function Stat({ icon, label, value, sub, to }: { icon?: ReactNode; label: string; value: ReactNode; sub?: ReactNode; to?: string }) {
  const body = (
    <>
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2 text-sm font-medium text-slate-500">{icon}{label}</div>
        {to && <ChevronRight className="h-4 w-4 shrink-0 text-slate-300 transition-transform group-hover:translate-x-0.5 group-hover:text-brand-500" aria-hidden />}
      </div>
      <p className="mt-2 text-3xl font-bold tracking-tight text-slate-900">{value}</p>
      {sub && <p className="mt-1 text-xs leading-relaxed text-slate-500">{sub}</p>}
    </>
  );
  const className = cx(
    surfaceCardClass,
    "group p-4 transition-[box-shadow,ring-color] hover:shadow-md sm:p-5",
    to && "block hover:ring-brand-200",
  );
  if (to) {
    return <Link to={to} className={className}>{body}</Link>;
  }
  return <div className={className}>{body}</div>;
}

export function AdminMiniStat({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className={cx(surfaceCardClass, "px-4 py-3.5")}>
      <p className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</p>
      <div className="mt-1 text-lg font-semibold text-slate-900">{children}</div>
    </div>
  );
}

export function AdminQuickLink({ to, label, icon: Icon }: { to: string; label: string; icon: LucideIcon }) {
  return (
    <Link
      to={to}
      className={cx(
        surfaceCardClass,
        "flex items-center gap-3 px-3 py-2.5 text-sm font-medium text-slate-700 transition-colors",
        "hover:bg-brand-50/50 hover:text-brand-800 hover:ring-brand-200",
      )}
    >
      <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-slate-100 text-slate-600">
        <Icon className="h-4 w-4" aria-hidden />
      </span>
      {label}
    </Link>
  );
}

/** A table that scrolls sideways on small screens instead of squashing columns. */
export function Table({ head, children, dim }: { head: string[]; children: ReactNode; dim?: boolean }) {
  return (
    <div className={cx("table-scroll -mx-4 sm:-mx-5", dim && "opacity-70 transition-opacity")}>
      <table className="min-w-full text-sm">
        <thead>
          <tr className="border-b border-slate-200 bg-slate-50/80 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
            {head.map((h) => <th key={h} className="whitespace-nowrap px-5 py-3 first:rounded-tl-lg last:rounded-tr-lg">{h}</th>)}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">{children}</tbody>
      </table>
    </div>
  );
}

export function Td({ children, className }: { children: ReactNode; className?: string }) {
  return <td className={cx("px-5 py-3.5 align-top text-slate-700", className)}>{children}</td>;
}

export function UserLink({ id, email }: { id: string; email: string }) {
  return <Link to={`/admin/users/${id}`} className="font-medium text-brand-700 hover:underline">{email}</Link>;
}

export const RUN_TONES: Record<RunStatus, "blue" | "amber" | "green" | "red" | "slate"> = {
  queued: "blue", running: "blue", paused: "amber", completed: "green", failed: "red", cancelled: "slate",
};

export const RUN_LABELS: Record<RunStatus, string> = {
  queued: "Waiting", running: "Running", paused: "Paused", completed: "Finished", failed: "Failed", cancelled: "Stopped",
};

export const SUB_TONES: Record<SubscriptionStatus, "blue" | "amber" | "green" | "red" | "slate"> = {
  pending: "blue", trialing: "blue", active: "green", past_due: "amber", cancelled: "slate", expired: "slate",
};

export const SUB_LABELS: Record<SubscriptionStatus, string> = {
  pending: "Pending", trialing: "Trial", active: "Active", past_due: "Past due", cancelled: "Cancelled", expired: "Expired",
};

export function SubBadge({ sub }: { sub: Subscription }) {
  return <Badge tone={SUB_TONES[sub.status]}>{SUB_LABELS[sub.status]}</Badge>;
}

export function providerLabel(provider: string): string {
  if (provider === "admin") return "Complimentary";
  if (provider === "null") return "Dev (no payment)";
  return provider.charAt(0).toUpperCase() + provider.slice(1);
}

/** {"INR": 49900, "USD": 1200} rendered as "Rs 499 + $12"; "0" when empty. */
export function moneyByCurrency(amounts: Record<string, number>): string {
  const parts = Object.entries(amounts).filter(([, v]) => v > 0).map(([c, v]) => formatMoney(v, c));
  return parts.length ? parts.join(" + ") : formatMoney(0, "INR");
}

export function FilterBar({ children }: { children: ReactNode }) {
  return <div className="mb-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">{children}</div>;
}

export function FilterChip({ active, onClick, children }: { active: boolean; onClick: () => void; children: ReactNode }) {
  return (
    <button
      type="button"
      aria-pressed={active}
      onClick={onClick}
      className={cx(
        "rounded-full px-3 py-1 text-sm font-medium ring-1 ring-inset transition-colors",
        active ? "bg-slate-900 text-white ring-slate-900" : "bg-white text-slate-700 ring-slate-300 hover:bg-slate-50",
      )}
    >
      {children}
    </button>
  );
}

export function FilterChipBrand({ active, onClick, children }: { active: boolean; onClick: () => void; children: ReactNode }) {
  return (
    <button
      type="button"
      aria-pressed={active}
      onClick={onClick}
      className={cx(
        "rounded-full px-3 py-1 text-sm font-medium ring-1 ring-inset transition-colors",
        active ? "bg-brand-600 text-white ring-brand-600" : "bg-white text-slate-700 ring-slate-300 hover:bg-slate-50",
      )}
    >
      {children}
    </button>
  );
}
