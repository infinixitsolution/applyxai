import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { Alert, Badge, Button, Card, EmptyState, PageHeader, Spinner } from "../../components/ui";
import { formatDateTime } from "../../lib/format";
import { errorMessage } from "../../services/api";
import { support } from "../../services/endpoints";
import type { SupportMessage } from "../../types";

function Bubble({ message }: { message: SupportMessage }) {
  const mine = message.sender === "user";
  const system = message.sender === "system";
  const [copied, setCopied] = useState(false);
  const token = message.kind === "token" ? message.meta.token : undefined;
  const used = message.meta.token_status === "used";
  const reserved = message.meta.token_status === "reserved";

  async function copyToken() {
    if (!token) return;
    await navigator.clipboard.writeText(token);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1500);
  }

  return (
    <div className={mine ? "flex justify-end" : "flex justify-start"}>
      <div className={
        system
          ? "max-w-[36rem] rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-950"
          : mine
            ? "max-w-[36rem] rounded-2xl bg-brand-600 px-4 py-3 text-sm text-white"
            : "max-w-[36rem] rounded-2xl bg-slate-100 px-4 py-3 text-sm text-slate-800"
      }>
        <p className={`text-xs font-semibold uppercase tracking-wide ${mine && !system ? "text-brand-100" : "text-slate-500"}`}>
          {mine ? "You" : system ? "ApplyXAI" : "Support"}
        </p>
        <p className="mt-1 whitespace-pre-wrap">{message.body}</p>
        {message.kind === "payment_link" && message.meta.url && (
          <a className="mt-3 inline-flex rounded-lg bg-slate-900 px-3 py-1.5 text-sm font-medium text-white" href={message.meta.url} target="_blank" rel="noreferrer">
            Pay for this interview
          </a>
        )}
        {token && (
          <div className="mt-3 flex items-center gap-3 rounded-xl bg-white px-3 py-2 text-slate-900">
            <span className={`font-mono text-xl font-semibold tracking-[0.3em] ${used ? "text-slate-400 line-through" : ""}`}>{token}</span>
            {used ? (
              <Badge tone="slate">Used</Badge>
            ) : (
              <>
                {reserved && <Badge tone="amber">In progress</Badge>}
                <button type="button" onClick={() => void copyToken()} className="text-xs font-medium text-brand-700 underline">
                  {copied ? "Copied" : "Copy"}
                </button>
              </>
            )}
          </div>
        )}
        {message.created_at && (
          <p className={`mt-2 text-xs ${mine && !system ? "text-brand-100" : "text-slate-500"}`}>{formatDateTime(message.created_at)}</p>
        )}
      </div>
    </div>
  );
}

export function SupportPage() {
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState("");
  const scroller = useRef<HTMLDivElement>(null);
  const query = useQuery({
    queryKey: ["support", "thread"],
    queryFn: support.thread,
    refetchInterval: 4000,
  });
  const send = useMutation({
    mutationFn: () => support.send(draft.trim()),
    onSuccess: async () => {
      setDraft("");
      await queryClient.invalidateQueries({ queryKey: ["support", "thread"] });
    },
  });
  const requestToken = useMutation({
    mutationFn: support.requestLiveInterview,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["support", "thread"] });
    },
  });

  const messages = query.data?.messages ?? [];
  useEffect(() => {
    const node = scroller.current;
    if (node) node.scrollTop = node.scrollHeight;
  }, [messages.length]);

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (draft.trim()) send.mutate();
  }

  return (
    <>
      <PageHeader
        title="Support"
        description="Chat with ApplyXAI, or buy one live interview. The token is separate from your plan."
        actions={<Button onClick={() => requestToken.mutate()} loading={requestToken.isPending}>Request live interview</Button>}
      />
      {(send.error || requestToken.error) && <Alert kind="error">{errorMessage(send.error || requestToken.error)}</Alert>}
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_18rem]">
        <Card>
          {query.isPending ? <Spinner /> : query.error ? <Alert kind="error">{errorMessage(query.error)}</Alert> : (
            <div ref={scroller} className="flex max-h-[32rem] min-h-[16rem] flex-col gap-3 overflow-y-auto">
              {messages.length ? messages.map((m) => <Bubble key={m.id} message={m} />) : (
                <EmptyState title="No messages yet">
                  Ask a question, or request a live interview token. The reply shows up in this chat.
                </EmptyState>
              )}
            </div>
          )}
          <form onSubmit={onSubmit} className="mt-4 flex gap-2">
            <input
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              placeholder="Write a message"
              className="min-w-0 flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm"
            />
            <Button type="submit" loading={send.isPending} disabled={!draft.trim()}>Send</Button>
          </form>
        </Card>
        <Card title="Live interview">
          <ol className="space-y-3 text-sm text-slate-700">
            <li><Badge tone="brand">1</Badge> Request a token in this chat.</li>
            <li><Badge tone="brand">2</Badge> Pay the link we send. One payment is one interview.</li>
            <li><Badge tone="brand">3</Badge> Copy the 8-digit token from the chat.</li>
            <li><Badge tone="brand">4</Badge> In the desktop agent, open Live interview, paste the token, and start.</li>
          </ol>
          <p className="mt-4 text-sm text-slate-500">
            Answers in the popup are written as you, from your profile. The report lands under <Link className="font-medium text-brand-700 underline" to="/app/live-interviews">Live interviews</Link>.
          </p>
        </Card>
      </div>
    </>
  );
}
