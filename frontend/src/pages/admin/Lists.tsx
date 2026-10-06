import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bot, ListChecks, Receipt, Search } from "lucide-react";
import { useState } from "react";
import { Select, TextInput } from "../../components/form";
import { ConfirmDialog } from "../../components/Modal";
import { Pagination } from "../../components/Pagination";
import { useToast } from "../../components/Toast";
import { Alert, Badge, Button, Card, EmptyState, PageHeader, Spinner } from "../../components/ui";
import { formatDate, formatDateTime, safeExternalUrl, STATUS_LABELS, STATUS_TONES } from "../../lib/format";
import { useDebounced } from "../../lib/useDebounced";
import { errorMessage } from "../../services/api";
import { admin } from "../../services/endpoints";
import { APPLICATION_STATUSES, type AdminRun, type ApplicationStatus, type SubscriptionStatus } from "../../types";
import { FilterBar, PAGE_SIZE, providerLabel, RUN_TONES, SUB_LABELS, SubBadge, Table, Td, UserLink } from "./shared";

// ------------------------------------------------------------------------------------------ subscriptions
const SUB_STATUSES: SubscriptionStatus[] = ["active", "pending", "past_due", "cancelled", "expired", "trialing"];

export function AdminSubscriptionsPage() {
  const [status, setStatus] = useState<SubscriptionStatus | "">("");
  const [page, setPage] = useState(1);
  const query = { status, page, page_size: PAGE_SIZE };
  const { data, isLoading, isFetching, error } = useQuery({
    queryKey: ["admin", "subscriptions", query], queryFn: () => admin.subscriptions(query), placeholderData: keepPreviousData,
  });

  return (
    <>
      <PageHeader title="Subscriptions" description="Paid and complimentary plans, newest first." />
      <Card>
        <FilterBar>
          <Select label="Status" value={status} onChange={(v) => { setStatus(v as SubscriptionStatus | ""); setPage(1); }}
                  options={[{ value: "", label: "Any status" }, ...SUB_STATUSES.map((s) => ({ value: s, label: SUB_LABELS[s] }))]} />
        </FilterBar>
        {isLoading ? <Spinner /> : error || !data ? <Alert kind="error">{errorMessage(error)}</Alert> : data.total === 0 ? (
          <EmptyState icon={<Receipt className="h-10 w-10" />} title="No subscriptions" />
        ) : (
          <>
            <Table head={["User", "Plan", "Status", "Source", "Started", "Ends"]} dim={isFetching}>
              {data.items.map((s) => (
                <tr key={s.id}>
                  <Td><UserLink id={s.user_id} email={s.user_email} /></Td>
                  <Td>{s.plan.name}</Td>
                  <Td>
                    <div className="flex flex-wrap gap-1">
                      <SubBadge sub={s} />
                      {s.cancel_at_period_end && s.provider !== "admin" && s.status === "active" && <Badge tone="amber">Won't renew</Badge>}
                    </div>
                  </Td>
                  <Td>{providerLabel(s.provider)}</Td>
                  <Td className="whitespace-nowrap">{formatDate(s.current_period_start ?? s.created_at)}</Td>
                  <Td className="whitespace-nowrap">{formatDate(s.current_period_end)}</Td>
                </tr>
              ))}
            </Table>
            <Pagination page={data.page} pageSize={data.page_size} total={data.total} onPage={setPage} />
          </>
        )}
      </Card>
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
];

const STOP_REASONS: Record<AdminRun["stop_reason"], string> = {
  "": "", user: "Stopped by the user", plan_limit: "Stopped at the monthly limit", admin: "Stopped by an admin",
};

export function AdminRunsPage() {
  const client = useQueryClient();
  const toast = useToast();
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);
  const [stopping, setStopping] = useState<AdminRun | null>(null);
  const query = { status: status || undefined, page, page_size: PAGE_SIZE };
  const { data, isLoading, isFetching, error } = useQuery({
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
  const active = (r: AdminRun) => ["queued", "running", "paused"].includes(r.status);

  return (
    <>
      <PageHeader title="Automation runs" description="Runs on every user's computer. In-progress runs refresh every 15 seconds." />
      <Card>
        <FilterBar>
          <Select label="Status" value={status} onChange={(v) => { setStatus(v); setPage(1); }} options={RUN_FILTERS} />
        </FilterBar>
        {isLoading ? <Spinner /> : error || !data ? <Alert kind="error">{errorMessage(error)}</Alert> : data.total === 0 ? (
          <EmptyState icon={<Bot className="h-10 w-10" />} title="No runs" />
        ) : (
          <>
            <Table head={["User", "Started", "Status", "Results", "Computer", ""]} dim={isFetching}>
              {data.items.map((r) => (
                <tr key={r.id}>
                  <Td><UserLink id={r.user_id} email={r.user_email} />{r.dry_run && <p className="text-xs text-slate-500">Dry run</p>}</Td>
                  <Td className="whitespace-nowrap">{formatDateTime(r.started_at ?? r.created_at)}</Td>
                  <Td>
                    <Badge tone={RUN_TONES[r.status]}>{r.control === "stop" && active(r) ? "stopping" : r.status}</Badge>
                    {STOP_REASONS[r.stop_reason] && <p className="mt-1 text-xs text-slate-500">{STOP_REASONS[r.stop_reason]}</p>}
                    {r.error_message && <p className="mt-1 max-w-xs truncate text-xs text-red-600" title={r.error_message}>{r.error_message}</p>}
                  </Td>
                  <Td className="whitespace-nowrap">{r.successful_count} applied &middot; {r.failed_count} failed &middot; {r.skipped_count} skipped</Td>
                  <Td>{r.device || "\u2014"}</Td>
                  <Td>
                    {active(r) && r.control !== "stop" && (
                      <Button size="sm" variant="secondary" onClick={() => setStopping(r)}>Stop</Button>
                    )}
                  </Td>
                </tr>
              ))}
            </Table>
            <Pagination page={data.page} pageSize={data.page_size} total={data.total} onPage={setPage} />
          </>
        )}
      </Card>
      {stopping && (
        <ConfirmDialog open title="Stop this run?" danger confirmLabel="Stop run" loading={stop.isPending}
                       message={`${stopping.user_email}'s run finishes the job it's on, then stops. They'll see that ApplyXAI support stopped it.`}
                       onConfirm={() => stop.mutate(stopping.id)} onClose={() => setStopping(null)} />
      )}
    </>
  );
}

// ------------------------------------------------------------------------------------------ applications
export function AdminApplicationsPage() {
  const [q, setQ] = useState("");
  const [status, setStatus] = useState<ApplicationStatus | "">("");
  const [page, setPage] = useState(1);
  const search = useDebounced(q.trim());
  const query = { q: search || undefined, status, page, page_size: PAGE_SIZE };
  const { data, isLoading, isFetching, error } = useQuery({
    queryKey: ["admin", "applications", query], queryFn: () => admin.applications(query), placeholderData: keepPreviousData,
  });

  return (
    <>
      <PageHeader title="Applications" description="Applications across all users, most recently updated first." />
      <Card>
        <FilterBar>
          <div className="relative sm:col-span-2">
            <TextInput label="Search" value={q} onChange={(v) => { setQ(v); setPage(1); }} placeholder="Job title, company, or user email"
                       maxLength={200} className="pl-9" />
            <Search className="pointer-events-none absolute bottom-2.5 left-3 h-4 w-4 text-slate-400" aria-hidden />
          </div>
          <Select label="Status" value={status} onChange={(v) => { setStatus(v as ApplicationStatus | ""); setPage(1); }}
                  options={[{ value: "", label: "Any status" }, ...APPLICATION_STATUSES.map((s) => ({ value: s, label: STATUS_LABELS[s] }))]} />
        </FilterBar>
        {isLoading ? <Spinner /> : error || !data ? <Alert kind="error">{errorMessage(error)}</Alert> : data.total === 0 ? (
          <EmptyState icon={<ListChecks className="h-10 w-10" />} title="No applications found" />
        ) : (
          <>
            <Table head={["Job", "User", "Status", "Updated"]} dim={isFetching}>
              {data.items.map((a) => {
                const url = safeExternalUrl(a.job.job_url);
                return (
                  <tr key={a.id}>
                    <Td className="max-w-xs">
                      {url ? <a href={url} target="_blank" rel="noopener noreferrer" className="block truncate font-medium text-slate-900 hover:underline">{a.job.title}</a>
                        : <span className="block truncate font-medium text-slate-900">{a.job.title}</span>}
                      <span className="block truncate text-slate-500">{a.job.company}{a.job.location && ` \u00b7 ${a.job.location}`}</span>
                    </Td>
                    <Td><UserLink id={a.user_id} email={a.user_email} /></Td>
                    <Td>
                      <Badge tone={STATUS_TONES[a.status]}>{STATUS_LABELS[a.status]}</Badge>
                      {a.failure_reason && <p className="mt-1 max-w-xs truncate text-xs text-slate-500" title={a.failure_reason}>{a.failure_reason}</p>}
                    </Td>
                    <Td className="whitespace-nowrap">{formatDateTime(a.updated_at)}</Td>
                  </tr>
                );
              })}
            </Table>
            <Pagination page={data.page} pageSize={data.page_size} total={data.total} onPage={setPage} />
          </>
        )}
      </Card>
    </>
  );
}
