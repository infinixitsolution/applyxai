import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowDownLeft, ArrowUpRight, MessageSquare, RefreshCw, Search } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { TextInput } from "../../../components/form";
import { useToast } from "../../../components/Toast";
import { Alert, Badge, Button, Card, EmptyState, PageHeader, Spinner, cx } from "../../../components/ui";
import { errorMessage } from "../../../services/api";
import { formatRelative } from "../../../lib/format";
import { admin } from "../../../services/endpoints";
import type { OutreachWhatsappChatThread } from "../../../types";
import { ChatThreadView } from "./ChatThreadView";
import { OutreachSetupAlert } from "./shared";

export function AdminOutreachWhatsappChatPage() {
  const { leadId: paramLeadId } = useParams();
  const navigate = useNavigate();
  const toast = useToast();
  const qc = useQueryClient();
  const [q, setQ] = useState("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const waStatus = useQuery({
    queryKey: ["admin-outreach-wa"],
    queryFn: () => admin.outreachWhatsappStatus(),
    refetchInterval: (query) => {
      const s = (query.state.data?.status || "").toLowerCase();
      return s === "connected" && query.state.data?.ready ? 12_000 : 3000;
    },
  });

  const waConnected = waStatus.data?.status === "connected" && waStatus.data?.ready;

  const inboundLive = Boolean(waConnected && waStatus.data?.inbound_enabled);

  const threads = useQuery({
    queryKey: ["admin-outreach-chat-threads", search, page],
    queryFn: () =>
      admin.outreachWhatsappChatThreads({ page, page_size: 100, q: search || undefined }),
    refetchInterval: inboundLive ? 3000 : 8000,
  });

  const syncFromWhatsapp = useMutation({
    mutationFn: () => admin.outreachWhatsappSyncChats({ limit: 200 }),
    onSuccess: (data) => {
      void qc.invalidateQueries({ queryKey: ["admin-outreach-chat-threads"] });
      void qc.invalidateQueries({ queryKey: ["admin-outreach-chat"] });
      if (data.synced) {
        toast.success(
          `Loaded ${data.chats} WhatsApp chat(s), imported ${data.messages_imported} message(s).`,
        );
      } else if (data.reason === "not_connected") {
        toast.error("WhatsApp is not connected. Open Outreach → WhatsApp to link or restart the bridge.");
      } else {
        toast.error(data.reason || "Could not sync from WhatsApp bridge.");
      }
    },
    onError: (err) => toast.error(errorMessage(err)),
  });

  useEffect(() => {
    setPage(1);
  }, [search]);

  const [mergedItems, setMergedItems] = useState<OutreachWhatsappChatThread[]>([]);

  useEffect(() => {
    const batch = threads.data?.items ?? [];
    if (page <= 1) {
      setMergedItems(batch);
      return;
    }
    setMergedItems((prev) => {
      const seen = new Set(prev.map((t) => t.lead_id));
      return [...prev, ...batch.filter((t) => !seen.has(t.lead_id))];
    });
  }, [threads.data?.items, page]);

  const items = mergedItems;
  const total = threads.data?.total ?? items.length;
  const hasMore = items.length < total;
  const selectedId = paramLeadId || items[0]?.lead_id || "";

  useEffect(() => {
    if (!paramLeadId && items[0]?.lead_id) {
      navigate(`/admin/outreach/chat/${items[0].lead_id}`, { replace: true });
    }
  }, [paramLeadId, items, navigate]);

  const selected = items.find((t) => t.lead_id === selectedId);

  return (
    <div className="space-y-4">
      <PageHeader
        title="WhatsApp chat"
        description="All institute threads — inbound replies and your outbound messages in one inbox."
        actions={
          <div className="flex flex-wrap items-center gap-3">
            <Button
              size="sm"
              variant="secondary"
              loading={syncFromWhatsapp.isPending}
              onClick={() => syncFromWhatsapp.mutate()}
            >
              <RefreshCw className="h-4 w-4 mr-1" aria-hidden />
              Load from WhatsApp
            </Button>
            <Link
              to="/admin/outreach/whatsapp"
              className="text-sm font-medium text-brand-700 hover:text-brand-800 underline"
            >
              Link WhatsApp session
            </Link>
          </div>
        }
      />

      <OutreachSetupAlert />

      {!waStatus.isLoading && !waConnected && (
        <Alert kind="error">
          <p className="font-medium">WhatsApp is not connected.</p>
          <p className="mt-1 text-sm">
            {waStatus.data?.error ||
              "Start the bridge with .\\scripts\\start_whatsapp_bridge.ps1, then link your phone under"}{" "}
            <Link className="font-medium text-brand-700 underline" to="/admin/outreach/whatsapp">
              Outreach → WhatsApp
            </Link>
            .
          </p>
        </Alert>
      )}

      {inboundLive && (
        <Alert kind="success">
          Live inbox is on. Incoming WhatsApp messages are forwarded to ApplyXAI and show up in this list within a few
          seconds.
        </Alert>
      )}

      {waConnected && waStatus.data?.inbound_enabled === false && (
        <Alert kind="error">
          <p className="font-medium">Inbound messages will not appear.</p>
          <p className="mt-1 text-sm">
            Add <code className="text-xs">WHATSAPP_BRIDGE_SECRET=dev-whatsapp-bridge-local</code> to{" "}
            <code className="text-xs">.env</code>, restart the API, then run{" "}
            <code className="text-xs">.\scripts\start_whatsapp_bridge.ps1</code> so the bridge uses the same secret.
          </p>
        </Alert>
      )}

      <div className="grid gap-4 lg:grid-cols-[minmax(260px,320px)_1fr] lg:h-[calc(100vh-12rem)] min-h-[480px]">
        <Card className="flex flex-col overflow-hidden !p-0 min-h-[320px] lg:min-h-0">
          <div className="border-b border-slate-100 px-3 py-3 space-y-2">
            <div className="flex items-center gap-2 text-sm font-semibold text-slate-900">
              <MessageSquare className="h-4 w-4" aria-hidden />
              Conversations
            </div>
            <form
              className="flex gap-2"
              onSubmit={(e) => {
                e.preventDefault();
                setSearch(q.trim());
              }}
            >
              <TextInput label="Search" value={q} onChange={setQ} placeholder="Institute or phone…" />
              <button
                type="submit"
                className="shrink-0 rounded-lg bg-slate-100 px-3 text-slate-600 hover:bg-slate-200"
                aria-label="Search"
              >
                <Search className="h-4 w-4" />
              </button>
            </form>
          </div>

          <div className="flex-1 overflow-y-auto">
            {threads.isLoading ? (
              <Spinner label="Loading conversations…" />
            ) : threads.isError ? (
              <div className="p-4">
                <Alert kind="error">{errorMessage(threads.error)}</Alert>
                <Button size="sm" variant="secondary" className="mt-2" onClick={() => void threads.refetch()}>
                  Retry
                </Button>
              </div>
            ) : items.length === 0 ? (
              <div className="p-4">
                <EmptyState title="No conversations yet">
                  Link WhatsApp, then click <strong>Load from WhatsApp</strong> to import your chats here.
                </EmptyState>
              </div>
            ) : (
              <ul className="divide-y divide-slate-100">
                {items.map((t: OutreachWhatsappChatThread) => {
                  const active = t.lead_id === selectedId;
                  const last = t.last_message;
                  const inbound = last?.direction === "inbound";
                  return (
                    <li key={t.lead_id}>
                      <button
                        type="button"
                        onClick={() => navigate(`/admin/outreach/chat/${t.lead_id}`)}
                        className={cx(
                          "w-full text-left px-3 py-3 hover:bg-slate-50 transition-colors",
                          active && "bg-brand-50/80 ring-1 ring-inset ring-brand-100",
                        )}
                      >
                        <div className="flex items-start justify-between gap-2">
                          <span className="font-medium text-slate-900 truncate">{t.display_name}</span>
                          {last?.created_at ? (
                            <span className="text-[10px] text-slate-400 shrink-0">{formatRelative(last.created_at)}</span>
                          ) : null}
                        </div>
                        <div className="mt-1 flex items-center gap-1.5 text-xs text-slate-500">
                          {inbound ? (
                            <ArrowDownLeft className="h-3 w-3 text-emerald-600 shrink-0" aria-hidden />
                          ) : (
                            <ArrowUpRight className="h-3 w-3 text-brand-600 shrink-0" aria-hidden />
                          )}
                          <span className="truncate">{last?.body || "—"}</span>
                        </div>
                        <div className="mt-1.5 flex flex-wrap gap-1">
                          <Badge tone="slate">{t.status}</Badge>
                          {t.whatsapp_phone ? (
                            <span className="text-[10px] text-slate-400">{t.whatsapp_phone}</span>
                          ) : null}
                        </div>
                      </button>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
          {items.length > 0 ? (
            <div className="border-t border-slate-100 px-3 py-2 flex items-center justify-between gap-2 text-xs text-slate-500">
              <span>
                Showing {items.length} of {total} conversation{total === 1 ? "" : "s"}
              </span>
              {hasMore ? (
                <button
                  type="button"
                  className="font-medium text-brand-700 hover:underline"
                  onClick={() => setPage((p) => p + 1)}
                  disabled={threads.isFetching}
                >
                  Load more
                </button>
              ) : null}
            </div>
          ) : null}
        </Card>

        <Card className="flex flex-col overflow-hidden !p-0 min-h-[360px] lg:min-h-0">
          {selectedId ? (
            <>
              <div className="border-b border-slate-100 px-4 py-3 flex flex-wrap items-center justify-between gap-2">
                <div>
                  <h2 className="text-base font-semibold text-slate-900">
                    {selected?.display_name || "Conversation"}
                  </h2>
                  {selected?.whatsapp_phone ? (
                    <p className="text-xs text-slate-500">{selected.whatsapp_phone}</p>
                  ) : null}
                </div>
                <Link
                  to={`/admin/outreach/leads/${selectedId}`}
                  className="text-xs font-medium text-brand-700 underline"
                >
                  Open lead
                </Link>
              </div>
              <div className="flex-1 min-h-0 p-4 flex flex-col">
                <ChatThreadView
                  leadId={selectedId}
                  compact
                  inboundLive={inboundLive}
                  autoSyncWhatsapp={waConnected}
                />
              </div>
            </>
          ) : (
            <div className="flex flex-1 items-center justify-center p-8">
              <Alert kind="info">Select a conversation or send outreach to start chatting.</Alert>
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}
