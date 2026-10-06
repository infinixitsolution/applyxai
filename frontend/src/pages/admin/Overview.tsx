import { useQuery } from "@tanstack/react-query";
import { Bot, CreditCard, IndianRupee, Users } from "lucide-react";
import { DailyChart } from "../../components/BarChart";
import { Alert, Badge, Card, PageHeader, Spinner } from "../../components/ui";
import { STATUS_LABELS, STATUS_TONES } from "../../lib/format";
import { errorMessage } from "../../services/api";
import { admin } from "../../services/endpoints";
import { APPLICATION_STATUSES, type RunStatus } from "../../types";
import { moneyByCurrency, RUN_TONES, Stat } from "./shared";

const RUN_STATUSES: RunStatus[] = ["queued", "running", "paused", "completed", "failed", "cancelled"];

export function AdminOverviewPage() {
  const { data, isLoading, error } = useQuery({ queryKey: ["admin", "analytics"], queryFn: admin.analytics, refetchInterval: 60_000 });
  if (isLoading) return <Spinner />;
  if (error || !data) return <Alert kind="error">{errorMessage(error)}</Alert>;
  const { users, subscriptions: subs, applications: apps, automation } = data;
  const paying = subs.by_plan.reduce((n, p) => n + p.count, 0);

  return (
    <>
      <PageHeader title="Overview" description="How ApplyXAI is doing across all users." />
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Stat icon={<Users className="h-4 w-4" aria-hidden />} label="Users" value={users.total.toLocaleString()}
              sub={`${users.new_7d} new this week \u00b7 ${users.active_30d} active in 30 days`} />
        <Stat icon={<CreditCard className="h-4 w-4" aria-hidden />} label="On a paid plan" value={paying.toLocaleString()}
              sub={subs.past_due ? `${subs.past_due} with a failed renewal` : "No failed renewals"} />
        <Stat icon={<IndianRupee className="h-4 w-4" aria-hidden />} label="Monthly recurring revenue"
              value={moneyByCurrency(subs.mrr_cents)} sub={`${moneyByCurrency(data.revenue_30d_cents)} collected in 30 days`} />
        <Stat icon={<Bot className="h-4 w-4" aria-hidden />} label="Runs in progress" value={automation.active_runs}
              sub={`${automation.devices_online} of ${automation.devices} computers online`} />
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-3">
        <Card title="Applications, last 30 days" className="lg:col-span-2"><DailyChart data={apps.daily} /></Card>
        <Card title="Plans">
          {subs.by_plan.length === 0 ? <p className="text-sm text-slate-500">Everyone is on the Free plan.</p> : (
            <ul className="space-y-2 text-sm">
              {subs.by_plan.map((p) => (
                <li key={p.code} className="flex justify-between"><span className="text-slate-700">{p.name}</span><span className="font-medium">{p.count}</span></li>
              ))}
            </ul>
          )}
          <p className="mt-4 text-xs text-slate-500">Includes complimentary and cancelled-but-not-yet-ended plans. Recurring revenue counts only paid plans that will renew.</p>
        </Card>
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <Card title="Applications this month">
          <div className="flex flex-wrap gap-2">
            {APPLICATION_STATUSES.filter((s) => apps.this_month_by_status[s] > 0).map((s) => (
              <Badge key={s} tone={STATUS_TONES[s]}>{STATUS_LABELS[s]}: {apps.this_month_by_status[s]}</Badge>
            ))}
            {APPLICATION_STATUSES.every((s) => !apps.this_month_by_status[s]) && <p className="text-sm text-slate-500">None yet.</p>}
          </div>
        </Card>
        <Card title="Runs in the last 24 hours">
          <div className="flex flex-wrap gap-2">
            {RUN_STATUSES.filter((s) => automation.last_24h_by_status[s] > 0).map((s) => (
              <Badge key={s} tone={RUN_TONES[s]}>{s}: {automation.last_24h_by_status[s]}</Badge>
            ))}
            {RUN_STATUSES.every((s) => !automation.last_24h_by_status[s]) && <p className="text-sm text-slate-500">No runs.</p>}
          </div>
        </Card>
      </div>
    </>
  );
}
