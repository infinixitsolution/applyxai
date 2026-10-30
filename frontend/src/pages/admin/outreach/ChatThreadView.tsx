import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Paperclip, RefreshCw, Send, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { TextArea } from "../../../components/form";
import { useToast } from "../../../components/Toast";
import { Link } from "react-router-dom";
import { Alert, Button, Spinner } from "../../../components/ui";
import { formatDateTime } from "../../../lib/format";
import { errorMessage } from "../../../services/api";
import { admin } from "../../../services/endpoints";
import type { OutreachLeadChatMessage } from "../../../types";

function ChatBubble({ m }: { m: OutreachLeadChatMessage }) {
  const outbound = m.direction === "outbound";
  return (
    <div className={`flex ${outbound ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[85%] rounded-2xl px-3 py-2 text-sm shadow-sm ${
          outbound
            ? "bg-brand-600 text-white rounded-br-md"
            : "bg-white text-slate-800 ring-1 ring-slate-200 rounded-bl-md"
        }`}
      >
        <p className="whitespace-pre-wrap break-words">{m.body}</p>
        <p className={`mt-1 text-[10px] ${outbound ? "text-brand-100" : "text-slate-400"}`}>
          {outbound ? "You · outbound" : "Institute · inbound"} ·{" "}
          {m.created_at ? formatDateTime(m.created_at) : ""}
        </p>
      </div>
    </div>
  );
}

export function ChatThreadView({
  leadId,
  compact,
  inboundLive,
  autoSyncWhatsapp,
  showBridgeHint,
}: {
  leadId: string;
  compact?: boolean;
  /** @deprecated use inboundLive */
  showBridgeHint?: boolean;
  inboundLive?: boolean;
  /** Pull WhatsApp Web history automatically while this thread is open. */
  autoSyncWhatsapp?: boolean;
}) {
  const toast = useToast();
  const qc = useQueryClient();
  const [text, setText] = useState("");
  const [attachment, setAttachment] = useState<File | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const syncSilent = useRef(true);

  const waStatus = useQuery({
    queryKey: ["admin-outreach-wa"],
    queryFn: () => admin.outreachWhatsappStatus(),
    enabled: autoSyncWhatsapp === undefined || inboundLive === undefined || Boolean(showBridgeHint),
    refetchInterval: 8000,
  });

  const waConnected = Boolean(waStatus.data?.status === "connected" && waStatus.data?.ready);
  const autoSync = autoSyncWhatsapp ?? waConnected;

  const liveInbound =
    inboundLive ??
    Boolean(waConnected && waStatus.data?.inbound_enabled);

  const chat = useQuery({
    queryKey: ["admin-outreach-chat", leadId],
    queryFn: () => admin.outreachLeadChat(leadId),
    enabled: Boolean(leadId),
    refetchInterval: autoSync ? 4000 : liveInbound ? 6000 : 12_000,
  });

  const syncThread = useMutation({
    mutationFn: () => admin.outreachLeadChatSync(leadId),
    onSuccess: (data) => {
      qc.setQueryData(["admin-outreach-chat", leadId], {
        items: data.items,
        whatsapp_phone: data.whatsapp_phone,
      });
      void qc.invalidateQueries({ queryKey: ["admin-outreach-chat-threads"] });
      if (!syncSilent.current) {
        toast.success(
          data.imported > 0 ? `Synced ${data.imported} message(s) from WhatsApp` : "Thread is up to date with WhatsApp",
        );
      }
      syncSilent.current = true;
    },
    onError: (err) => {
      const silent = syncSilent.current;
      syncSilent.current = true;
      if (!silent) toast.error(errorMessage(err));
    },
  });

  useEffect(() => {
    if (!leadId || !autoSync) return;
    let cancelled = false;
    const runSync = () => {
      if (cancelled || syncThread.isPending) return;
      syncSilent.current = true;
      syncThread.mutate();
    };
    runSync();
    const timer = window.setInterval(runSync, 12_000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [leadId, autoSync, syncThread]);

  const canSend = Boolean(text.trim() || attachment);

  const send = useMutation({
    mutationFn: async () => {
      if (attachment) {
        const form = new FormData();
        form.append("file", attachment);
        if (text.trim()) form.append("text", text.trim());
        return admin.outreachLeadChatSendAttachment(leadId, form);
      }
      return admin.outreachLeadChatSend(leadId, { channel: "whatsapp", text: text.trim() });
    },
    onSuccess: () => {
      setText("");
      setAttachment(null);
      if (fileInputRef.current) fileInputRef.current.value = "";
      toast.success("Sent on WhatsApp");
      void qc.invalidateQueries({ queryKey: ["admin-outreach-chat", leadId] });
      void qc.invalidateQueries({ queryKey: ["admin-outreach-chat-threads"] });
      void qc.invalidateQueries({ queryKey: ["admin-outreach-wa"] });
      void qc.invalidateQueries({ queryKey: ["admin-outreach-lead", leadId] });
      void qc.invalidateQueries({ queryKey: ["admin-outreach-leads"] });
    },
    onError: (err) => toast.error(errorMessage(err)),
  });

  const items = chat.data?.items ?? [];

  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [items.length, leadId]);

  if (chat.isLoading) {
    return <Spinner label="Loading messages…" />;
  }

  if (chat.isError) {
    return (
      <Alert kind="error">
        {errorMessage(chat.error)}
        <div className="mt-2">
          <Button size="sm" variant="secondary" onClick={() => void chat.refetch()}>
            Retry
          </Button>
        </div>
      </Alert>
    );
  }

  return (
    <div className={`flex flex-col ${compact ? "h-full min-h-0" : "space-y-4"}`}>
      {!compact && chat.data?.whatsapp_phone ? (
        <p className="text-xs text-slate-500">Thread: {chat.data.whatsapp_phone}</p>
      ) : null}

      <div
        ref={scrollRef}
        className={
          compact
            ? "flex-1 min-h-0 overflow-y-auto rounded-lg border border-slate-200 bg-slate-50/50 p-3 space-y-3"
            : "max-h-80 overflow-y-auto rounded-lg border border-slate-200 bg-slate-50/50 p-3 space-y-3"
        }
      >
        {items.length === 0 ? (
          <p className="text-sm text-slate-500 text-center py-6">
            No messages yet. Send a proposal first, or wait for an institute reply on WhatsApp.
          </p>
        ) : (
          items.map((m) => <ChatBubble key={m.id} m={m} />)
        )}
      </div>

      <div className="flex flex-wrap items-center justify-between gap-2 shrink-0">
        {autoSync ? (
          <p className="text-xs text-emerald-700">
            Auto-syncing with WhatsApp — new messages appear here every few seconds.
            {liveInbound ? " Live inbound forwarding is on." : ""}
          </p>
        ) : liveInbound ? (
          <p className="text-xs text-emerald-700">Live inbox — new WhatsApp replies appear here automatically.</p>
        ) : showBridgeHint ? (
          <p className="text-xs text-slate-500">Connect WhatsApp to receive replies in this thread.</p>
        ) : (
          <span />
        )}
        {!autoSync ? (
          <Button
            size="sm"
            variant="secondary"
            loading={syncThread.isPending}
            onClick={() => {
              syncSilent.current = false;
              syncThread.mutate();
            }}
          >
            <RefreshCw className="h-3.5 w-3.5 mr-1" aria-hidden />
            Sync from WhatsApp
          </Button>
        ) : (
          <Button
            size="sm"
            variant="secondary"
            loading={syncThread.isPending || chat.isFetching}
            onClick={() => {
              syncSilent.current = false;
              syncThread.mutate();
            }}
            title="Force refresh from WhatsApp now"
          >
            <RefreshCw className="h-3.5 w-3.5 mr-1" aria-hidden />
            Refresh
          </Button>
        )}
      </div>

      {!liveInbound && showBridgeHint ? (
        <Alert kind="info">
          To receive replies in this inbox, keep the bridge running and set matching{" "}
          <code className="text-xs">WHATSAPP_BRIDGE_SECRET</code> in <code className="text-xs">.env</code>, then{" "}
          <Link className="font-medium text-brand-700 underline" to="/admin/outreach/whatsapp">
            link WhatsApp
          </Link>
          .
        </Alert>
      ) : null}

      <div className="space-y-2 shrink-0">
        <input
          ref={fileInputRef}
          type="file"
          className="sr-only"
          accept=".jpg,.jpeg,.png,.webp,.gif,.pdf,.doc,.docx,.ppt,.pptx,.xls,.xlsx,.mp4,.apk,image/*,application/pdf"
          onChange={(e) => setAttachment(e.target.files?.[0] ?? null)}
        />
        {attachment ? (
          <div className="flex items-center gap-2 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700">
            <Paperclip className="h-4 w-4 shrink-0 text-slate-500" aria-hidden />
            <span className="truncate flex-1">{attachment.name}</span>
            <button
              type="button"
              className="rounded p-1 text-slate-500 hover:bg-slate-200 hover:text-slate-800"
              aria-label="Remove attachment"
              onClick={() => {
                setAttachment(null);
                if (fileInputRef.current) fileInputRef.current.value = "";
              }}
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        ) : null}
        <div className="flex gap-2 items-end">
          <button
            type="button"
            className="shrink-0 rounded-lg border border-slate-300 bg-white p-2.5 text-slate-600 hover:bg-slate-50"
            aria-label="Attach file"
            title="Attach image, PDF, or document (max 16 MB)"
            onClick={() => fileInputRef.current?.click()}
          >
            <Paperclip className="h-4 w-4" aria-hidden />
          </button>
          <div className="flex-1 min-w-0">
            <TextArea
              label="Reply"
              rows={compact ? 2 : 3}
              value={text}
              onChange={setText}
              placeholder="Type your reply… (optional caption when sending a file)"
            />
          </div>
        </div>
      </div>
      <div className="flex justify-end shrink-0">
        <Button
          size="sm"
          disabled={!canSend || send.isPending}
          loading={send.isPending}
          onClick={() => send.mutate()}
        >
          <Send className="h-4 w-4 mr-1" aria-hidden />
          Send on WhatsApp
        </Button>
      </div>
    </div>
  );
}
