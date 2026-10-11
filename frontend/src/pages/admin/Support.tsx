import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Alert, Badge, Button, Card, EmptyState, PageHeader, Spinner, cx } from "../../components/ui";
import { formatDateTime } from "../../lib/format";
import { errorMessage } from "../../services/api";
import { admin } from "../../services/endpoints";
import type { SupportMessage } from "../../types";

function Message({ message }: { message: SupportMessage }) {
  return (
    <div className={cx(
      "rounded-xl px-3 py-2 text-sm",
      message.sender === "user" && "bg-slate-100",
      message.sender === "admin" && "bg-brand-50",
      message.sender === "system" && "border border-amber-200 bg-amber-50",
    )}>
      <p className="flex flex-wrap items-center gap-2 text-xs font-semibold uppercase text-slate-500">
        {message.sender}
        {message.kind === "token" && (
          <Badge tone={message.meta.token_status === "used" ? "slate" : message.meta.token_status === "reserved" ? "amber" : "green"}>
            {message.meta.token_status === "used" ? "Used" : message.meta.token_status === "reserved" ? "In progress" : "Token"}
          </Badge>
        )}
        {message.kind === "payment_link" && <Badge tone="amber">Payment</Badge>}
        {message.created_at ? <span className="font-normal normal-case">{formatDateTime(message.created_at)}</span> : null}
      </p>
      <p className="mt-1 whitespace-pre-wrap text-slate-800">{message.body}</p>
      {message.kind === "token" && message.meta.token && (
        <p className={`mt-2 font-mono text-lg font-semibold tracking-[0.25em] ${message.meta.token_status === "used" ? "text-slate-400 line-through" : ""}`}>{message.meta.token}</p>
      )}
      {message.kind === "payment_link" && message.meta.url && (
        <a className="mt-2 inline-block text-sm font-medium text-brand-700 underline" href={message.meta.url} target="_blank" rel="noreferrer">Open payment link</a>
      )}
    </div>
  );
}

export function AdminSupportPage() {
  const queryClient = useQueryClient();
  const [selected, setSelected] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const threads = useQuery({ queryKey: ["admin", "support"], queryFn: admin.supportThreads, refetchInterval: 5000 });
  const thread = useQuery({
    queryKey: ["admin", "support", selected],
    queryFn: () => admin.supportThread(selected as string),
    enabled: Boolean(selected),
    refetchInterval: 4000,
  });
  const reply = useMutation({
    mutationFn: () => admin.supportReply(selected as string, draft.trim()),
    onSuccess: async () => {
      setDraft("");
      await queryClient.invalidateQueries({ queryKey: ["admin", "support", selected] });
      await queryClient.invalidateQueries({ queryKey: ["admin", "support"] });
    },
  });

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (selected && draft.trim()) reply.mutate();
  }

  return (
    <>
      <PageHeader title="Support" description="Private chats with candidates. Live interview payment links and 8-digit tokens appear here after a request." />
      <div className="grid gap-4 lg:grid-cols-[18rem_minmax(0,1fr)]">
        <Card title="Inbox">
          {threads.isPending ? <Spinner /> : threads.error ? <Alert kind="error">{errorMessage(threads.error)}</Alert> : (
            threads.data?.length ? (
              <ul className="divide-y divide-slate-100">
                {threads.data.map((t) => (
                  <li key={t.id}>
                    <button
                      type="button"
                      onClick={() => setSelected(t.id)}
                      className={cx("w-full rounded-lg px-2 py-2 text-left", selected === t.id ? "bg-slate-100" : "hover:bg-slate-50")}
                    >
                      <p className="text-sm font-medium text-slate-900">{t.name || t.email}</p>
                      <p className="truncate text-xs text-slate-500">{t.email}</p>
                      {t.last_message_at && <p className="text-xs text-slate-400">{formatDateTime(t.last_message_at)}</p>}
                    </button>
                  </li>
                ))}
              </ul>
            ) : <EmptyState title="No conversations yet" />
          )}
        </Card>
        <Card title={thread.data ? (thread.data.thread.name || thread.data.thread.email) : "Conversation"}>
          {!selected ? <p className="text-sm text-slate-500">Choose a conversation.</p> : thread.isPending ? <Spinner /> : thread.error ? <Alert kind="error">{errorMessage(thread.error)}</Alert> : (
            <>
              <p className="mb-3 text-xs text-slate-500">{thread.data?.thread.email}</p>
              <div className="flex max-h-[28rem] flex-col gap-3 overflow-y-auto">
                {thread.data?.messages.map((m) => <Message key={m.id} message={m} />)}
              </div>
              {reply.error && <div className="mt-3"><Alert kind="error">{errorMessage(reply.error)}</Alert></div>}
              <form onSubmit={onSubmit} className="mt-4 flex gap-2">
                <input value={draft} onChange={(e) => setDraft(e.target.value)} placeholder="Reply" className="min-w-0 flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm" />
                <Button type="submit" loading={reply.isPending} disabled={!draft.trim()}>Send</Button>
              </form>
            </>
          )}
        </Card>
      </div>
    </>
  );
}
