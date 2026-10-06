import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { ChipSelect, TextInput } from "../../components/form";
import { Pagination } from "../../components/Pagination";
import { Alert, Badge, Card, PageHeader, Spinner } from "../../components/ui";
import { formatDateTime, formatRelative } from "../../lib/format";
import { useDebounced } from "../../lib/useDebounced";
import { errorMessage } from "../../services/api";
import { admin } from "../../services/endpoints";
import type { LogLevel } from "../../types";
import { FilterBar, PAGE_SIZE, Table, Td, UserLink } from "./shared";

export function AdminSystemPage() {
  return (
    <>
      <PageHeader title="System" description="Background workers, desktop agents, automation logs, and the admin audit log." />
      <div className="space-y-6">
        <Workers />
        <Logs />
        <AuditLog />
      </div>
    </>
  );
}

function Workers() {
  const { data, isLoading, error } = useQuery({ queryKey: ["admin", "workers"], queryFn: admin.workers, refetchInterval: 30_000 });
  if (isLoading) return <Card title="Workers"><Spinner /></Card>;
  if (error || !data) return <Alert kind="error">{errorMessage(error)}</Alert>;
  const { celery, devices } = data;
  return (
    <div className="grid gap-6 lg:grid-cols-3">
      <Card title="Background workers">
        <div className="flex items-center gap-2 text-sm">
          <span className="text-slate-600">Redis</span>
          <Badge tone={celery.broker === "ok" ? "green" : "red"}>{celery.broker === "ok" ? "Connected" : "Unreachable"}</Badge>
        </div>
        {celery.workers.length ? (
          <ul className="mt-3 space-y-1 text-sm text-slate-700">{celery.workers.map((w) => <li key={w}>{w}</li>)}</ul>
        ) : (
          <p className="mt-3 text-sm text-slate-500">
            No Celery worker answered. Scheduled cleanup (runs whose computer went silent, expired pairing codes) isn't running.
          </p>
        )}
      </Card>
      <Card title={`Desktop agents (${devices.filter((d) => d.online).length} online)`} className="lg:col-span-2">
        {devices.length === 0 ? <p className="text-sm text-slate-500">No computers are paired.</p> : (
          <Table head={["Computer", "User", "Version", "Last seen", ""]}>
            {devices.map((d) => (
              <tr key={d.id}>
                <Td><p className="font-medium text-slate-900">{d.name || "Unnamed"}</p><p className="text-xs text-slate-500">{d.platform}</p></Td>
                <Td><UserLink id={d.user_id} email={d.user_email} /></Td>
                <Td>{d.agent_version || "\u2014"}</Td>
                <Td className="whitespace-nowrap">{d.last_seen_at ? formatRelative(d.last_seen_at) : "Never"}</Td>
                <Td>
                  <div className="flex gap-1">
                    <Badge tone={d.online ? "green" : "slate"}>{d.online ? "Online" : "Offline"}</Badge>
                    {d.running && <Badge tone="blue">Running</Badge>}
                  </div>
                </Td>
              </tr>
            ))}
          </Table>
        )}
      </Card>
    </div>
  );
}

const LEVELS: LogLevel[] = ["error", "warning", "info"];
const LEVEL_TONES = { error: "red", warning: "amber", info: "slate" } as const;
const LEVEL_LABELS: Record<LogLevel, string> = { error: "Errors", warning: "Warnings", info: "Info" };

function Logs() {
  const [levels, setLevels] = useState<LogLevel[]>(["error", "warning"]);
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const search = useDebounced(q.trim());
  const query = { level: levels.length ? levels : LEVELS, q: search || undefined, page, page_size: PAGE_SIZE };
  const { data, isLoading, isFetching, error } = useQuery({
    queryKey: ["admin", "logs", query], queryFn: () => admin.logs(query), placeholderData: keepPreviousData,
  });
  const byLabel = Object.fromEntries(LEVELS.map((l) => [LEVEL_LABELS[l], l])) as Record<string, LogLevel>;

  return (
    <Card title="Automation logs">
      <FilterBar>
        <div className="sm:col-span-2">
          <ChipSelect label="Level" options={LEVELS.map((l) => LEVEL_LABELS[l])} value={levels.map((l) => LEVEL_LABELS[l])}
                      onChange={(v) => { setLevels(v.map((label) => byLabel[label])); setPage(1); }} />
        </div>
        <div className="sm:col-span-2">
          <TextInput label="Search messages" value={q} onChange={(v) => { setQ(v); setPage(1); }} maxLength={200} />
        </div>
      </FilterBar>
      {isLoading ? <Spinner /> : error || !data ? <Alert kind="error">{errorMessage(error)}</Alert> : data.total === 0 ? (
        <p className="text-sm text-slate-500">No log lines match.</p>
      ) : (
        <>
          <Table head={["Time", "Level", "User", "Message"]} dim={isFetching}>
            {data.items.map((l) => (
              <tr key={`${l.run_id}-${l.ts}-${l.event}`}>
                <Td className="whitespace-nowrap">{formatDateTime(l.ts)}</Td>
                <Td><Badge tone={LEVEL_TONES[l.level] ?? "slate"}>{l.level}</Badge></Td>
                <Td><UserLink id={l.user_id} email={l.user_email} /></Td>
                <Td className="max-w-xl break-words">{l.message}</Td>
              </tr>
            ))}
          </Table>
          <Pagination page={data.page} pageSize={data.page_size} total={data.total} onPage={setPage} />
        </>
      )}
    </Card>
  );
}

const ACTION_LABELS: Record<string, string> = {
  "user.update": "Changed account", "plan.grant": "Gave a plan", "plan.revoke": "Ended a complimentary plan",
  "plan.update": "Edited a plan", "run.stop": "Stopped a run",
};

function describe(details: Record<string, unknown>): string {
  return Object.entries(details)
    .filter(([, v]) => v !== "" && v !== null)
    .map(([k, v]) => Array.isArray(v) && v.length === 2 && k !== "plans"
      ? `${k}: ${JSON.stringify(v[0])} \u2192 ${JSON.stringify(v[1])}` : `${k}: ${typeof v === "string" ? v : JSON.stringify(v)}`)
    .join("; ");
}

function AuditLog() {
  const [page, setPage] = useState(1);
  const { data, isLoading, error } = useQuery({
    queryKey: ["admin", "audit", page], queryFn: () => admin.audit({ page, page_size: PAGE_SIZE }), placeholderData: keepPreviousData,
  });
  return (
    <Card title="Admin audit log">
      {isLoading ? <Spinner /> : error || !data ? <Alert kind="error">{errorMessage(error)}</Alert> : data.total === 0 ? (
        <p className="text-sm text-slate-500">No admin changes yet.</p>
      ) : (
        <>
          <Table head={["Time", "Admin", "Action", "Target", "Details"]}>
            {data.items.map((a) => (
              <tr key={a.id}>
                <Td className="whitespace-nowrap">{formatDateTime(a.created_at)}</Td>
                <Td>{a.admin_email}</Td>
                <Td>{ACTION_LABELS[a.action] ?? a.action}</Td>
                <Td>{a.target_user_id ? <UserLink id={a.target_user_id} email={a.target} /> : a.target}</Td>
                <Td className="max-w-md break-words text-xs text-slate-500">{describe(a.details)}</Td>
              </tr>
            ))}
          </Table>
          <Pagination page={data.page} pageSize={data.page_size} total={data.total} onPage={setPage} />
        </>
      )}
    </Card>
  );
}
