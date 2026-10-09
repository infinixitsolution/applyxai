import { useQuery } from "@tanstack/react-query";
import {
  Bot,
  CreditCard,
  IndianRupee,
  Laptop,
  ListChecks,
  Package,
  Receipt,
  ServerCog,
  Users,
} from "lucide-react";
import { Link } from "react-router-dom";
import { DailyChart } from "../../components/BarChart";
import { Alert, Badge, ButtonLink, Card, PageHeader, ProgressBar, Spinner, cx } from "../../components/ui";
import { formatRelative, STATUS_LABELS, STATUS_TONES } from "../../lib/format";
import { errorMessage } from "../../services/api";
import { admin } from "../../services/endpoints";
import { APPLICATION_STATUSES, type RunStatus } from "../../types";
import { moneyByCurrency, RUN_LABELS, RUN_TONES, Stat } from "./shared";

const RUN_STATUSES: RunStatus[] = ["queued", "running", "paused", "completed", "failed", "cancelled"];

const QUICK_LINKS = [
  { to: "/admin/users", label: "Users", icon: Users },
  { to: "/admin/institutes", label: "Institutes", icon: Users },
  { to: "/admin/partners", label: "Partners", icon: CreditCard },
  { to: "/admin/subscriptions", label: "Subscriptions", icon: Receipt },
  { to: "/admin/runs", label: "Automation runs", icon: Bot },
  { to: "/admin/applications", label: "Applications", icon: ListChecks },
  { to: "/admin/plans", label: "Plans", icon: Package },
  { to: "/admin/system", label: "Settings", icon: ServerCog },
] as const;

function CountRow({ label, count, tone }: { label: string; count: number; tone?: "blue" | "amber" | "green" | "red" | "slate" | "brand" }) {
  if (count <= 0) return null;
  return (
    <li className="flex items-center justify-between gap-3 py-2">
      <span className="text-slate-700">{label}</span>
      {tone ? <Badge tone={tone}>{count.toLocaleString()}</Badge> : <span className="font-medium tabular-nums text-slate-900">{count.toLocaleString()}</span>}
    </li>
  );
}

export function AdminOverviewPage() {
  const { data, isLoading, isFetching, error, dataUpdatedAt } = useQuery({
    queryKey: ["admin", "analytics"],
    queryFn: admin.analytics,
    refetchInterval: 60_000,
  });

  if (isLoading) return <Spinner />;
  if (error || !data) return <Alert kind="error">{errorMessage(error)}</Alert>;

  const { users, subscriptions: subs, applications: apps, automation } = data;
  const paying = subs.by_plan.reduce((n, p) => n + p.count, 0);
  const unverified = Math.max(0, users.total - users.verified);
  const appsThisMonth = APPLICATION_STATUSES.reduce((n, s) => n + apps.this_month_by_status[s], 0);
  const apps30d = apps.daily.reduce((n, d) => n + d.applied + d.failed, 0);
  const planMax = Math.max(users.total, paying, 1);

  return (
    <>
      <PageHeader
        title="Overview"
        description="Platform health across accounts, billing, automation, and applications."
        actions={
          <div className="flex flex-wrap items-center gap-3">
            {dataUpdatedAt > 0 && (
              <span className={cx("text-xs text-slate-500", isFetching && "opacity-60")}>
                Updated {formatRelative(new Date(dataUpdatedAt).toISOString())}
              </span>
            )}
            <ButtonLink to="/admin/system" variant="secondary" size="sm">
              <ServerCog className="h-4 w-4" aria-hidden /> Settings
            </ButtonLink>
          </div>
        }
      />

      {(subs.past_due > 0 || unverified > 0) && (
        <div className="mb-6 space-y-3">
          {subs.past_due > 0 && (
            <Alert kind="error">
              {subs.past_due} subscription{subs.past_due === 1 ? "" : "s"} {subs.past_due === 1 ? "has" : "have"} a failed renewal.{" "}
              <Link to="/admin/subscriptions?status=past_due" className="font-medium underline">Review past due</Link>
            </Alert>
          )}
          {unverified > 0 && (
            <Alert kind="info">
              {unverified} account{unverified === 1 ? "" : "s"} still need email verification.{" "}
              <Link to="/admin/users?status=unverified" className="font-medium underline">View unverified users</Link>
            </Alert>
          )}
        </div>
      )}

      <div className={cx("grid gap-4 sm:grid-cols-2 lg:grid-cols-4", isFetching && "opacity-80 transition-opacity")}>
        <Stat
          to="/admin/users"
          icon={<Users className="h-4 w-4" aria-hidden />}
          label="Users"
          value={users.total.toLocaleString()}
          sub={`${users.new_7d} new this week · ${users.active_30d} active in 30 days`}
        />
        <Stat
          to="/admin/subscriptions"
          icon={<CreditCard className="h-4 w-4" aria-hidden />}
          label="On a paid plan"
          value={paying.toLocaleString()}
          sub={subs.past_due ? `${subs.past_due} with a failed renewal` : "No failed renewals"}
        />
        <Stat
          to="/admin/subscriptions"
          icon={<IndianRupee className="h-4 w-4" aria-hidden />}
          label="Monthly recurring revenue"
          value={moneyByCurrency(subs.mrr_cents)}
          sub={`${moneyByCurrency(data.revenue_30d_cents)} collected in 30 days`}
        />
        <Stat
          to="/admin/runs"
          icon={<Bot className="h-4 w-4" aria-hidden />}
          label="Runs in progress"
          value={automation.active_runs.toLocaleString()}
          sub={`${automation.devices_online} of ${automation.devices} computers online`}
        />
      </div>

      <div className="mt-4 grid gap-4 sm:grid-cols-3">
        <Card className="!py-4">
          <p className="text-xs font-medium uppercase tracking-wide text-slate-500">Sign-ups</p>
          <p className="mt-1 text-lg font-semibold text-slate-900">{users.new_30d.toLocaleString()} <span className="text-sm font-normal text-slate-500">last 30 days</span></p>
        </Card>
        <Card className="!py-4">
          <p className="text-xs font-medium uppercase tracking-wide text-slate-500">Admins</p>
          <p className="mt-1 text-lg font-semibold text-slate-900">{users.admins.toLocaleString()}</p>
        </Card>
        <Card className="!py-4">
          <p className="text-xs font-medium uppercase tracking-wide text-slate-500">Agents online</p>
          <p className="mt-1 flex items-center gap-2 text-lg font-semibold text-slate-900">
            <Laptop className="h-4 w-4 text-slate-400" aria-hidden />
            {automation.devices_online} / {automation.devices}
          </p>
        </Card>
      </div>

      <Card className="mt-6" title="Quick links">
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
          {QUICK_LINKS.map(({ to, label, icon: Icon }) => (
            <Link
              key={to}
              to={to}
              className="flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium text-slate-700 ring-1 ring-slate-200 transition-colors hover:bg-slate-50 hover:text-brand-700 hover:ring-brand-200"
            >
              <Icon className="h-4 w-4 shrink-0 text-slate-400" aria-hidden />
              {label}
            </Link>
          ))}
        </div>
      </Card>

      <div className="mt-6 grid gap-6 lg:grid-cols-3">
        <Card
          className="lg:col-span-2"
          title="Applications, last 30 days"
          actions={
            <Link to="/admin/applications" className="text-sm font-medium text-brand-600 hover:underline">
              View all
            </Link>
          }
        >
          <p className="mb-4 text-sm text-slate-600">
            <span className="font-medium text-slate-900">{apps30d.toLocaleString()}</span> application events in the chart period
          </p>
          <DailyChart data={apps.daily} />
        </Card>
        <Card
          title="Plans"
          actions={
            <Link to="/admin/plans" className="text-sm font-medium text-brand-600 hover:underline">
              Edit plans
            </Link>
          }
        >
          {subs.by_plan.length === 0 ? (
            <p className="text-sm text-slate-500">Everyone is on the Free plan.</p>
          ) : (
            <div className="space-y-4">
              {subs.by_plan.map((p) => (
                <ProgressBar key={p.code} label={p.name} value={p.count} max={planMax} />
              ))}
            </div>
          )}
          <p className="mt-4 text-xs leading-relaxed text-slate-500">
            Includes complimentary and cancelled-but-not-yet-ended plans. MRR counts only paid plans set to renew.
          </p>
        </Card>
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <Card
          title="Applications this month"
          actions={
            <span className="text-sm tabular-nums text-slate-500">{appsThisMonth.toLocaleString()} total</span>
          }
        >
          {appsThisMonth === 0 ? (
            <p className="text-sm text-slate-500">None yet this month.</p>
          ) : (
            <ul className="divide-y divide-slate-100">
              {APPLICATION_STATUSES.map((s) => (
                <CountRow key={s} label={STATUS_LABELS[s]} count={apps.this_month_by_status[s]} tone={STATUS_TONES[s]} />
              ))}
            </ul>
          )}
        </Card>
        <Card
          title="Runs in the last 24 hours"
          actions={
            <Link to="/admin/runs" className="text-sm font-medium text-brand-600 hover:underline">
              View runs
            </Link>
          }
        >
          {RUN_STATUSES.every((s) => !automation.last_24h_by_status[s]) ? (
            <p className="text-sm text-slate-500">No runs in the last 24 hours.</p>
          ) : (
            <ul className="divide-y divide-slate-100">
              {RUN_STATUSES.map((s) => (
                <CountRow key={s} label={RUN_LABELS[s]} count={automation.last_24h_by_status[s]} tone={RUN_TONES[s]} />
              ))}
            </ul>
          )}
        </Card>
      </div>
    </>
  );
}
