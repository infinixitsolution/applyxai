import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bot, ExternalLink, Laptop, ListChecks, Receipt, Search } from "lucide-react";
import { useState } from "react";
import { Select, TextInput } from "../../components/form";
import { ConfirmDialog, Modal } from "../../components/Modal";
import { Pagination } from "../../components/Pagination";
import { useToast } from "../../components/Toast";
import { Alert, Badge, Button, Card, EmptyState, PageHeader, Spinner, cx } from "../../components/ui";
import { formatDate, formatDateTime, formatMoney, safeExternalUrl, STATUS_LABELS, STATUS_TONES } from "../../lib/format";
import { useDebounced } from "../../lib/useDebounced";
import { errorMessage } from "../../services/api";
import { admin, plans as plansApi } from "../../services/endpoints";
import { APPLICATION_STATUSES, type AdminRun, type ApplicationStatus, type SubscriptionStatus } from "../../types";
import { PAGE_SIZE, providerLabel, RUN_LABELS, RUN_TONES, SUB_LABELS, SubBadge, Table, Td, UserLink } from "./shared";

// ------------------------------------------------------------------------------------------ subscriptions
const SUB_STATUSES: SubscriptionStatus[] = ["active", "pending", "past_due", "trialing", "cancelled", "expired"];

function AdminSubscriptionFilters({ status, plan, onStatus, onPlan }: {
  status: SubscriptionStatus | "";
  plan: string;
  onStatus: (v: SubscriptionStatus | "") => void;
  onPlan: (v: string) => void;
}) {
  const { data: plans } = useQuery({ queryKey: ["plans"], queryFn: plansApi.list, staleTime: 5 * 60 * 1000 });
  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_minmax(0,14rem)] lg:items-end">
      <div>
        <span className="mb-2 block text-sm font-medium text-slate-700">Status</span>
        <div className="flex flex-wrap gap-2">
          <button type="button" aria-pressed={status === ""} onClick={() => onStatus("")}
                  className={cx("rounded-full px-3 py-1 text-sm ring-1 ring-inset transition-colors",
                    status === "" ? "bg-slate-900 text-white ring-slate-900" : "bg-white text-slate-700 ring-slate-300 hover:bg-slate-50")}>
            All
          </button>
          {SUB_STATUSES.map((s) => (
            <button key={s} type="button" aria-pressed={status === s} onClick={() => onStatus(status === s ? "" : s)}
                    className={cx("rounded-full px-3 py-1 text-sm ring-1 ring-inset transition-colors",
                      status === s ? "bg-brand-600 text-white ring-brand-600" : "bg-white text-slate-700 ring-slate-300 hover:bg-slate-50")}>
              {SUB_LABELS[s]}
            </button>
          ))}
        </div>
      </div>
      <Select label="Plan" value={plan} onChange={onPlan}
              options={[{ value: "", label: "All plans" }, ...(plans ?? []).map((p) => ({ value: p.code, label: p.name }))]} />
    </div>
  );
}

function ProviderBadge({ provider }: { provider: string }) {
  const tone = provider === "admin" ? "blue" : provider === "null" ? "amber" : "slate";
  return <Badge tone={tone}>{providerLabel(provider)}</Badge>;
}

export function AdminSubscriptionsPage() {
  const [status, setStatus] = useState<SubscriptionStatus | "">("");
  const [plan, setPlan] = useState("");
  const [page, setPage] = useState(1);
  const query = { status, plan: plan || undefined, page, page_size: PAGE_SIZE };
  const { data, isLoading, isFetching, error } = useQuery({
    queryKey: ["admin", "subscriptions", query], queryFn: () => admin.subscriptions(query), placeholderData: keepPreviousData,
  });
  const hasFilters = Boolean(status || plan);
  const resetPage = () => setPage(1);

  return (
    <>
      <PageHeader title="Subscriptions" description="Paid, trial, and complimentary plans across all accounts." />
      <Card>
        <AdminSubscriptionFilters
          status={status}
          plan={plan}
          onStatus={(v) => { setStatus(v); resetPage(); }}
          onPlan={(v) => { setPlan(v); resetPage(); }}
        />
        {hasFilters && (
          <p className="mt-3 text-xs text-slate-500">
            Filtering{status ? ` · ${SUB_LABELS[status]}` : ""}{plan ? ` · ${plan}` : ""}.{" "}
            <button type="button" className="font-medium text-brand-700 hover:underline"
                    onClick={() => { setStatus(""); setPlan(""); resetPage(); }}>Clear filters</button>
          </p>
        )}
      </Card>

      <div className="mt-6">
        {isLoading ? <Spinner /> : error || !data ? <Alert kind="error">{errorMessage(error)}</Alert> : data.total === 0 ? (
          <Card>
            <EmptyState icon={<Receipt className="h-10 w-10" />} title="No subscriptions found">
              {hasFilters ? "Try different filters." : "Subscriptions appear when users upgrade or receive a complimentary plan."}
            </EmptyState>
          </Card>
        ) : (
          <Card className={cx(isFetching && "opacity-70 transition-opacity")}>
            <p className="mb-4 text-sm text-slate-600">
              Showing <span className="font-medium text-slate-900">{data.items.length}</span> of{" "}
              <span className="font-medium text-slate-900">{data.total.toLocaleString()}</span> subscriptions
            </p>
            <Table head={["User", "Plan", "Status", "Source", "Current period"]} dim={isFetching}>
              {data.items.map((s) => (
                <tr key={s.id} className="hover:bg-slate-50/80">
                  <Td className="whitespace-nowrap"><UserLink id={s.user_id} email={s.user_email} /></Td>
                  <Td>
                    <p className="font-medium text-slate-900">{s.plan.name}</p>
                    <p className="text-xs text-slate-500">
                      {formatMoney(s.plan.price_cents, s.plan.currency)} / {s.plan.interval}
                    </p>
                  </Td>
                  <Td>
                    <div className="flex flex-wrap gap-1">
                      <SubBadge sub={s} />
                      {s.cancel_at_period_end && s.provider !== "admin" && s.status === "active" && (
                        <Badge tone="amber">Won&apos;t renew</Badge>
                      )}
                    </div>
                  </Td>
                  <Td><ProviderBadge provider={s.provider} /></Td>
                  <Td className="whitespace-nowrap text-slate-600">
                    <p>{formatDate(s.current_period_start ?? s.created_at)}</p>
                    <p className="text-xs text-slate-500">through {formatDate(s.current_period_end) || "—"}</p>
                  </Td>
                </tr>
              ))}
            </Table>
            <Pagination page={data.page} pageSize={data.page_size} total={data.total} onPage={setPage} />
          </Card>
        )}
      </div>
    </>
  );
}

// ------------------------------------------------------------------------------------------ runs
const RUN_FILTERS = [
  { value: "", label: "All runs" },
  { value: "active", label: "In progress" },
  { value: "completed", label: "Completed" },
  { value: "failed", label: "Failed" },
  { value: "cancelled", label: "Stopped" },
] as const;

const STOP_REASONS: Record<AdminRun["stop_reason"], string> = {
  "": "", user: "Stopped by the user", plan_limit: "Stopped at the monthly limit", admin: "Stopped by ApplyXAI support",
};

function AdminRunFilters({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  return (
    <div>
      <span className="mb-2 block text-sm font-medium text-slate-700">Status</span>
      <div className="flex flex-wrap gap-2">
        {RUN_FILTERS.map((f) => (
          <button key={f.value || "all"} type="button" aria-pressed={value === f.value}
                  onClick={() => onChange(f.value === "" ? "" : value === f.value ? "" : f.value)}
                  className={cx("rounded-full px-3 py-1 text-sm ring-1 ring-inset transition-colors",
                    value === f.value
                      ? f.value === "" ? "bg-slate-900 text-white ring-slate-900" : "bg-brand-600 text-white ring-brand-600"
                      : "bg-white text-slate-700 ring-slate-300 hover:bg-slate-50")}>
            {f.label}
          </button>
        ))}
      </div>
    </div>
  );
}

function RunResults({ applied, failed, skipped }: { applied: number; failed: number; skipped: number }) {
  return (
    <div className="flex flex-wrap gap-x-3 gap-y-1 text-xs">
      <span className="font-medium text-emerald-700">{applied} applied</span>
      <span className="text-red-700">{failed} failed</span>
      <span className="text-slate-600">{skipped} skipped</span>
    </div>
  );
}

function runErrorTitle(message: string): string {
  const line = message.trim().split(/\n/)[0] ?? "";
  const named = line.match(/\b([A-Z][A-Za-z0-9_]*(?:Error|Exception))\b/);
  if (named) return named[1];
  const colon = line.indexOf(":");
  if (colon > 0 && colon < 72) return line.slice(0, colon).trim();
  return line.length > 64 ? `${line.slice(0, 64)}…` : line || "Error";
}

function RunErrorBlock({ message }: { message: string }) {
  const toast = useToast();
  const [open, setOpen] = useState(false);
  const title = runErrorTitle(message);
  const long = message.length > 96 || message.includes("\n");

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(message);
      toast.success("Copied to clipboard.");
    } catch {
      toast.error("Could not copy.");
    }
  };

  return (
    <>
      <div className="mt-2 max-w-xs rounded-md bg-red-50 px-2 py-1.5 ring-1 ring-red-100">
        <p className="text-xs font-medium text-red-900">{title}</p>
        <p className="mt-0.5 line-clamp-2 break-all text-xs leading-snug text-red-800">{message}</p>
        {long && (
          <button type="button" className="mt-1 text-xs font-medium text-red-900 underline decoration-red-300 hover:decoration-red-900"
                  onClick={() => setOpen(true)}>
            View full error
          </button>
        )}
      </div>
      {open && (
        <Modal open title="Run error" wide onClose={() => setOpen(false)} footer={
          <>
            <Button variant="secondary" onClick={() => void copy()}>Copy</Button>
            <Button onClick={() => setOpen(false)}>Close</Button>
          </>
        }>
          <pre className="max-h-[min(24rem,60vh)] overflow-auto whitespace-pre-wrap break-all rounded-lg bg-slate-900 p-4 text-xs leading-relaxed text-slate-100">
            {message}
          </pre>
        </Modal>
      )}
    </>
  );
}

function runIsActive(r: AdminRun) {
  return r.status === "queued" || r.status === "running" || r.status === "paused";
}

function runStatusLabel(r: AdminRun): string {
  if (r.control === "stop" && runIsActive(r)) return "Stopping";
  if (r.status === "paused") return RUN_LABELS.paused;
  return RUN_LABELS[r.status];
}

export function AdminRunsPage() {
  const client = useQueryClient();
  const toast = useToast();
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);
  const [stopping, setStopping] = useState<AdminRun | null>(null);
  const query = { status: status || undefined, page, page_size: PAGE_SIZE };
  const { data, isLoading, isFetching, error, dataUpdatedAt } = useQuery({
    queryKey: ["admin", "runs", query], queryFn: () => admin.runs(query), placeholderData: keepPreviousData,
    refetchInterval: 15_000,
  });
  const stop = useMutation({
    mutationFn: (id: string) => admin.stopRun(id),
    onSuccess: () => {
      setStopping(null);
      toast.success("The run stops after its current job.");
      void client.invalidateQueries({ queryKey: ["admin", "runs"] });
    },
    onError: (e) => { setStopping(null); toast.error(errorMessage(e)); },
  });

  return (
    <>
      <PageHeader title="Automation runs" description="Runs on users' computers. The list refreshes every 15 seconds while this page is open." />
      <Card>
        <AdminRunFilters value={status} onChange={(v) => { setStatus(v); setPage(1); }} />
        {status && (
          <p className="mt-3 text-xs text-slate-500">
            Showing {RUN_FILTERS.find((f) => f.value === status)?.label ?? status} runs.{" "}
            <button type="button" className="font-medium text-brand-700 hover:underline" onClick={() => { setStatus(""); setPage(1); }}>
              Show all
            </button>
          </p>
        )}
      </Card>

      <div className="mt-6">
        {isLoading ? <Spinner /> : error || !data ? <Alert kind="error">{errorMessage(error)}</Alert> : data.total === 0 ? (
          <Card>
            <EmptyState icon={<Bot className="h-10 w-10" />} title="No runs yet">
              {status ? "Try another status filter." : "Runs appear here when users start automation."}
            </EmptyState>
          </Card>
        ) : (
          <Card className={cx(isFetching && "opacity-70 transition-opacity")}>
            <div className="mb-4 flex flex-wrap items-center justify-between gap-2 text-sm text-slate-600">
              <p>
                Showing <span className="font-medium text-slate-900">{data.items.length}</span> of{" "}
                <span className="font-medium text-slate-900">{data.total.toLocaleString()}</span> runs
              </p>
              <p className="text-xs text-slate-500">Last updated {formatDateTime(new Date(dataUpdatedAt).toISOString())}</p>
            </div>
            <Table head={["User", "Started", "Status", "Results", "Computer", ""]} dim={isFetching}>
              {data.items.map((r) => {
                const active = runIsActive(r);
                const tone = r.control === "stop" && active ? "amber" : RUN_TONES[r.status];
                return (
                  <tr key={r.id} className="align-top hover:bg-slate-50/80">
                    <Td className="whitespace-nowrap">
                      <UserLink id={r.user_id} email={r.user_email} />
                      <div className="mt-1 flex flex-wrap gap-1">
                        {r.dry_run && <Badge tone="amber">Practice</Badge>}
                        {!r.claimed && r.status === "queued" && <Badge tone="slate">Unclaimed</Badge>}
                      </div>
                    </Td>
                    <Td className="whitespace-nowrap text-slate-600">
                      <p>{formatDateTime(r.started_at ?? r.created_at)}</p>
                      {r.finished_at && <p className="mt-0.5 text-xs text-slate-500">Ended {formatDateTime(r.finished_at)}</p>}
                    </Td>
                    <Td className="min-w-[9rem] max-w-xs">
                      <Badge tone={tone}>{runStatusLabel(r)}</Badge>
                      {r.current_job && active && (
                        <p className="mt-1 line-clamp-2 text-xs text-slate-600" title={r.current_job}>Now: {r.current_job}</p>
                      )}
                      {STOP_REASONS[r.stop_reason] && (
                        <p className="mt-1 text-xs text-amber-800">{STOP_REASONS[r.stop_reason]}</p>
                      )}
                      {r.error_message && <RunErrorBlock message={r.error_message} />}
                    </Td>
                    <Td><RunResults applied={r.successful_count} failed={r.failed_count} skipped={r.skipped_count} /></Td>
                    <Td className="max-w-[8rem]">
                      {r.device ? (
                        <span className="inline-flex items-start gap-1.5 text-slate-700">
                          <Laptop className="mt-0.5 h-4 w-4 shrink-0 text-slate-400" aria-hidden />
                          <span className="line-clamp-2 text-xs" title={r.device}>{r.device}</span>
                        </span>
                      ) : (
                        <span className="text-slate-400">—</span>
                      )}
                    </Td>
                    <Td className="whitespace-nowrap">
                      {active && r.control !== "stop" && (
                        <Button size="sm" variant="secondary" onClick={() => setStopping(r)}>Stop</Button>
                      )}
                    </Td>
                  </tr>
                );
              })}
            </Table>
            <Pagination page={data.page} pageSize={data.page_size} total={data.total} onPage={setPage} />
          </Card>
        )}
      </div>
      {stopping && (
        <ConfirmDialog open title="Stop this run?" danger confirmLabel="Stop run" loading={stop.isPending}
                       message={`${stopping.user_email}'s run finishes the job it's on, then stops. They'll see that ApplyXAI support stopped it.`}
                       onConfirm={() => stop.mutate(stopping.id)} onClose={() => setStopping(null)} />
      )}
    </>
  );
}

// ------------------------------------------------------------------------------------------ applications
function AdminStatusFilters({ value, onChange }: { value: ApplicationStatus | ""; onChange: (v: ApplicationStatus | "") => void }) {
  return (
    <div>
      <span className="mb-2 block text-sm font-medium text-slate-700">Status</span>
      <div className="flex flex-wrap gap-2">
        <button type="button" aria-pressed={value === ""} onClick={() => onChange("")}
                className={cx("rounded-full px-3 py-1 text-sm ring-1 ring-inset transition-colors",
                  value === "" ? "bg-slate-900 text-white ring-slate-900" : "bg-white text-slate-700 ring-slate-300 hover:bg-slate-50")}>
          All
        </button>
        {APPLICATION_STATUSES.map((s) => (
          <button key={s} type="button" aria-pressed={value === s} onClick={() => onChange(value === s ? "" : s)}
                  className={cx("rounded-full px-3 py-1 text-sm ring-1 ring-inset transition-colors",
                    value === s ? "bg-brand-600 text-white ring-brand-600" : "bg-white text-slate-700 ring-slate-300 hover:bg-slate-50")}>
            {STATUS_LABELS[s]}
          </button>
        ))}
      </div>
    </div>
  );
}

export function AdminApplicationsPage() {
  const [q, setQ] = useState("");
  const [status, setStatus] = useState<ApplicationStatus | "">("");
  const [page, setPage] = useState(1);
  const search = useDebounced(q.trim());
  const query = { q: search || undefined, status, page, page_size: PAGE_SIZE };
  const { data, isLoading, isFetching, error } = useQuery({
    queryKey: ["admin", "applications", query], queryFn: () => admin.applications(query), placeholderData: keepPreviousData,
  });
  const resetPage = () => setPage(1);
  const hasFilters = Boolean(search || status);

  return (
    <>
      <PageHeader title="Applications" description="Every application across all accounts, newest updates first." />
      <Card>
        <div className="grid gap-4 lg:grid-cols-[1fr_minmax(0,2fr)] lg:items-end">
          <div className="relative">
            <TextInput label="Search" value={q} onChange={(v) => { setQ(v); resetPage(); }}
                       placeholder="Job title, company, or user email" maxLength={200} className="pl-9" />
            <Search className="pointer-events-none absolute bottom-2.5 left-3 h-4 w-4 text-slate-400" aria-hidden />
          </div>
          <AdminStatusFilters value={status} onChange={(v) => { setStatus(v); resetPage(); }} />
        </div>
        {hasFilters && (
          <p className="mt-3 text-xs text-slate-500">
            Filtering{search ? ` for “${search}”` : ""}{status ? ` · ${STATUS_LABELS[status]}` : ""}.
            <button type="button" className="ml-2 font-medium text-brand-700 hover:underline"
                    onClick={() => { setQ(""); setStatus(""); resetPage(); }}>Clear filters</button>
          </p>
        )}
      </Card>

      <div className="mt-6">
        {isLoading ? <Spinner /> : error || !data ? <Alert kind="error">{errorMessage(error)}</Alert> : data.total === 0 ? (
          <Card>
            <EmptyState icon={<ListChecks className="h-10 w-10" />} title="No applications found">
              {hasFilters ? "Try different search terms or clear filters." : "Applications appear here once users run automation."}
            </EmptyState>
          </Card>
        ) : (
          <Card className={cx(isFetching && "opacity-70 transition-opacity")}>
            <p className="mb-4 text-sm text-slate-600">
              Showing <span className="font-medium text-slate-900">{data.items.length}</span> of{" "}
              <span className="font-medium text-slate-900">{data.total.toLocaleString()}</span> applications
            </p>
            <Table head={["Job", "Location", "User", "Status", "Applied", "Updated"]} dim={isFetching}>
              {data.items.map((a) => {
                const url = safeExternalUrl(a.job.job_url);
                return (
                  <tr key={a.id} className="hover:bg-slate-50/80">
                    <Td className="max-w-[14rem] sm:max-w-xs">
                      <div className="flex items-start gap-1.5">
                        <div className="min-w-0 flex-1">
                          {url ? (
                            <a href={url} target="_blank" rel="noopener noreferrer"
                               className="group inline-flex max-w-full items-center gap-1 font-medium text-slate-900 hover:text-brand-700">
                              <span className="truncate">{a.job.title}</span>
                              <ExternalLink className="h-3.5 w-3.5 shrink-0 opacity-0 transition-opacity group-hover:opacity-100" aria-hidden />
                            </a>
                          ) : (
                            <span className="block truncate font-medium text-slate-900">{a.job.title}</span>
                          )}
                          <span className="block truncate text-slate-500">{a.job.company}</span>
                        </div>
                      </div>
                    </Td>
                    <Td className="max-w-[10rem] text-slate-600">
                      <span className="line-clamp-2" title={a.job.location}>{a.job.location || "—"}</span>
                    </Td>
                    <Td className="whitespace-nowrap"><UserLink id={a.user_id} email={a.user_email} /></Td>
                    <Td>
                      <Badge tone={STATUS_TONES[a.status]}>{STATUS_LABELS[a.status]}</Badge>
                      {a.failure_reason && (a.status === "failed" || a.status === "skipped") && (
                        <p className="mt-1 max-w-[12rem] truncate text-xs text-slate-500" title={a.failure_reason}>{a.failure_reason}</p>
                      )}
                    </Td>
                    <Td className="whitespace-nowrap text-slate-600">{a.applied_at ? formatDate(a.applied_at) : "—"}</Td>
                    <Td className="whitespace-nowrap text-slate-600">{formatDateTime(a.updated_at)}</Td>
                  </tr>
                );
              })}
            </Table>
            <Pagination page={data.page} pageSize={data.page_size} total={data.total} onPage={setPage} />
          </Card>
        )}
      </div>
    </>
  );
}
