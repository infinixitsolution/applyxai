import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import {
  CheckCircle2,
  CircleAlert,
  Loader2,
  MessageCircle,
  QrCode,
  RefreshCw,
  Smartphone,
  Wifi,
  WifiOff,
} from "lucide-react";
import { Link } from "react-router-dom";
import { TextArea, TextInput } from "../../../components/form";
import { useToast } from "../../../components/Toast";
import { Alert, Badge, Button, ButtonLink, Card, EmptyState, PageHeader, Spinner, cx } from "../../../components/ui";
import { formatDateTime, formatRelative } from "../../../lib/format";
import { errorMessage } from "../../../services/api";
import { admin } from "../../../services/endpoints";
import type { OutreachWhatsappRecentSend } from "../../../types";
import { OutreachSetupAlert, useOutreachPlatform } from "./shared";

type WaState = "connected" | "qr" | "disconnected" | "unknown";

function normalizeState(status: string | undefined): WaState {
  const s = (status || "").toLowerCase();
  if (s === "connected") return "connected";
  if (s === "qr") return "qr";
  if (s === "disconnected") return "disconnected";
  return "unknown";
}

function statusTone(state: WaState): "green" | "amber" | "red" | "slate" {
  if (state === "connected") return "green";
  if (state === "qr") return "amber";
  if (state === "disconnected") return "red";
  return "slate";
}

function statusLabel(state: WaState): string {
  switch (state) {
    case "connected":
      return "Connected";
    case "qr":
      return "Scan QR code";
    case "disconnected":
      return "Disconnected";
    default:
      return "Unknown";
  }
}

const SETUP_STEPS = [
  "Install Node.js if needed, then from the repo root run the bridge (see command below).",
  "Keep the bridge terminal open on the same machine as the API.",
  "Open WhatsApp on your phone → Settings → Linked devices → Link a device.",
  "Scan the QR code shown here when status is “Scan QR code”.",
  "When status is Connected, automation and manual sends can deliver proposal text.",
];

const DEFAULT_TEST_TEXT =
  "ApplyXAI outreach test — if you received this, WhatsApp sending is working. (Admin test message.)";

export function AdminOutreachWhatsappPage() {
  const toast = useToast();
  const qc = useQueryClient();
  const [testPhone, setTestPhone] = useState("");
  const [testText, setTestText] = useState(DEFAULT_TEST_TEXT);

  const wa = useQuery({
    queryKey: ["admin-outreach-wa"],
    queryFn: () => admin.outreachWhatsappStatus(),
    refetchInterval: (query) => {
      const state = normalizeState(query.state.data?.status);
      return state === "connected" ? 12_000 : 2_500;
    },
  });

  const recentSends = useQuery({
    queryKey: ["admin-outreach-wa-recent"],
    queryFn: () => admin.outreachWhatsappRecentSends(15),
    refetchInterval: 30_000,
  });

  const state = normalizeState(wa.data?.status);
  const sentRows: OutreachWhatsappRecentSend[] = recentSends.data?.items ?? [];
  const bridgeUrl = wa.data?.bridge_url || "http://127.0.0.1:39219";
  const pollingFast = state !== "connected";

  const testSend = useMutation({
    mutationFn: () => admin.outreachWhatsappTestSend({ phone: testPhone, text: testText }),
    onSuccess: () => toast.success("Test message sent"),
    onError: (err) => toast.error(errorMessage(err)),
  });

  const resetSession = useMutation({
    mutationFn: () => admin.outreachWhatsappReset(),
    onSuccess: (data) => {
      void qc.invalidateQueries({ queryKey: ["admin-outreach-wa"] });
      if (data.reset?.ok === false) {
        toast.error(data.reset.error || "Could not reset bridge. Restart .\\scripts\\start_whatsapp_bridge.ps1");
        return;
      }
      toast.success("WhatsApp session restarting — wait for QR or Connected status.");
    },
    onError: (err) => toast.error(errorMessage(err)),
  });

  const canTestSend =
    state === "connected" &&
    wa.data?.ready &&
    testPhone.trim().length >= 8 &&
    testText.trim().length > 0 &&
    !testSend.isPending;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Outreach WhatsApp"
        description="Link WhatsApp Web for institute partnership messages. Sends run with email after profiles reach 100% and proposals are generated."
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <ButtonLink to="/admin/outreach/templates" variant="secondary" size="sm">
              Outreach templates
            </ButtonLink>
            <ButtonLink to="/admin/outreach/leads" variant="secondary" size="sm">
              View leads
            </ButtonLink>
          </div>
        }
      />

      <OutreachSetupAlert />

      <WhatsappProviderCard />

      {wa.data && wa.data.status === "connected" && wa.data.inbound_enabled === false && (
        <Alert kind="error">
          <p className="font-medium">Inbound WhatsApp chat is off.</p>
          <p className="mt-1 text-sm">
            Set the same <code className="text-xs">WHATSAPP_BRIDGE_SECRET</code> in project{" "}
            <code className="text-xs">.env</code> and restart the API and bridge (
            <code className="text-xs">.\scripts\start_whatsapp_bridge.ps1</code>
            ). Local dev default: <code className="text-xs">dev-whatsapp-bridge-local</code>.
            {!wa.data.api_inbound_configured && " API secret missing."}
            {!wa.data.bridge_inbound_configured && " Bridge secret missing — restart bridge after .env is set."}
          </p>
        </Alert>
      )}

      <Alert kind="info">
        Outreach automation sends <strong>email and WhatsApp together</strong>, with about <strong>1–2 minutes</strong>{" "}
        between each lead. Save your scrape campaign on{" "}
        <Link className="font-medium text-brand-700 underline" to="/admin/outreach/scrape">
          Outreach → Scrape
        </Link>{" "}
        and run Celery with beat for always-on delivery.
      </Alert>

      <div className="grid gap-6 lg:grid-cols-[1fr_minmax(280px,340px)]">
        <Card className="overflow-hidden !p-0">
          <div className="border-b border-slate-100 px-4 py-4 sm:px-6 flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <span
                className={cx(
                  "flex h-11 w-11 items-center justify-center rounded-xl ring-1 ring-inset",
                  state === "connected" && "bg-emerald-50 text-emerald-700 ring-emerald-200",
                  state === "qr" && "bg-amber-50 text-amber-700 ring-amber-200",
                  state === "disconnected" && "bg-red-50 text-red-700 ring-red-200",
                  state === "unknown" && "bg-slate-50 text-slate-600 ring-slate-200",
                )}
              >
                {state === "connected" ? (
                  <CheckCircle2 className="h-6 w-6" aria-hidden />
                ) : state === "qr" ? (
                  <QrCode className="h-6 w-6" aria-hidden />
                ) : state === "disconnected" ? (
                  <WifiOff className="h-6 w-6" aria-hidden />
                ) : (
                  <Smartphone className="h-6 w-6" aria-hidden />
                )}
              </span>
              <div>
                <h2 className="text-base font-semibold text-slate-900">Session status</h2>
                <p className="text-xs text-slate-500">
                  Bridge {bridgeUrl}
                  {pollingFast ? " · refreshing every 2s" : " · refreshing every 12s"}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              {wa.isFetching && !wa.isLoading ? (
                <Loader2 className="h-4 w-4 animate-spin text-slate-400" aria-hidden />
              ) : (
                <RefreshCw className="h-4 w-4 text-slate-400" aria-hidden />
              )}
              <Badge tone={statusTone(state)}>{statusLabel(state)}</Badge>
              {wa.data?.ready ? <Badge tone="green">Ready to send</Badge> : null}
            </div>
          </div>

          <div className="px-4 py-6 sm:px-6">
            {wa.isLoading ? (
              <Spinner label="Checking WhatsApp bridge…" />
            ) : wa.isError ? (
              <Alert kind="error">Could not reach the API. Ensure the backend is running.</Alert>
            ) : (
              <div className="space-y-6">
                {state === "connected" && (
                  <div className="rounded-xl bg-emerald-50/80 px-4 py-4 ring-1 ring-emerald-200/80">
                    <p className="flex items-center gap-2 text-sm font-medium text-emerald-900">
                      <Wifi className="h-4 w-4 shrink-0" aria-hidden />
                      WhatsApp Web is linked and ready for outreach sends.
                    </p>
                    {wa.data?.connected_at ? (
                      <p className="mt-2 text-sm text-emerald-800">
                        Connected {formatRelative(wa.data.connected_at)} ·{" "}
                        <span className="text-emerald-700/90">{formatDateTime(wa.data.connected_at)}</span>
                      </p>
                    ) : null}
                  </div>
                )}

                {state === "connected" && wa.data?.ready && (
                  <div className="rounded-xl border border-slate-200 bg-slate-50/50 p-4 space-y-4">
                    <div>
                      <h3 className="text-sm font-semibold text-slate-900">Test send</h3>
                      <p className="mt-1 text-xs text-slate-600">
                        Send to your own number first. Use a number you control (10-digit Indian mobile or +91…).
                      </p>
                    </div>
                    <TextInput
                      label="Phone"
                      value={testPhone}
                      onChange={setTestPhone}
                      placeholder="+919876543210"
                      autoComplete="tel"
                    />
                    <TextArea label="Message" rows={3} value={testText} onChange={setTestText} />
                    <div className="flex justify-end">
                      <Button size="sm" disabled={!canTestSend} loading={testSend.isPending} onClick={() => testSend.mutate()}>
                        Send test message
                      </Button>
                    </div>
                  </div>
                )}

                {state === "qr" && wa.data?.qr && (
                  <div className="flex flex-col items-center gap-4 text-center">
                    <p className="max-w-md text-sm text-slate-600">
                      Scan with your phone. The code refreshes automatically until linked.
                    </p>
                    <img
                      src={wa.data.qr}
                      alt="WhatsApp QR code to link this device"
                      className="h-72 w-72 rounded-xl border border-slate-200 bg-white p-3 shadow-sm"
                    />
                  </div>
                )}

                {state === "qr" && !wa.data?.qr && (
                  <Alert kind="info">Waiting for QR from the bridge… If this persists, restart the bridge process.</Alert>
                )}

                {state === "disconnected" && (
                  <div className="space-y-3">
                    <Alert kind="error">
                      {wa.data?.error || "Bridge is not connected. Start whatsapp-bridge on this machine, then reload."}
                    </Alert>
                    {(wa.data?.error || "").toLowerCase().includes("already running") && (
                      <Alert kind="info">
                        A leftover Chrome window from a previous bridge session is blocking WhatsApp. Close it in Task
                        Manager, or run <code className="rounded bg-slate-100 px-1 text-xs">.\scripts\start_whatsapp_bridge.ps1</code>{" "}
                        (it stops stale Chrome automatically), then use Restart session below.
                      </Alert>
                    )}
                    <div className="flex flex-wrap gap-2">
                      <Button
                        size="sm"
                        variant="secondary"
                        loading={resetSession.isPending}
                        onClick={() => resetSession.mutate()}
                      >
                        Restart session
                      </Button>
                      <Button size="sm" variant="ghost" onClick={() => void wa.refetch()}>
                        Refresh status
                      </Button>
                    </div>
                    <p className="text-sm text-slate-600">
                      The API calls <code className="rounded bg-slate-100 px-1 text-xs">{bridgeUrl}/status</code>. Use{" "}
                      <code className="rounded bg-slate-100 px-1 text-xs">WHATSAPP_BRIDGE_URL</code> in{" "}
                      <code className="rounded bg-slate-100 px-1 text-xs">.env</code> if the port differs.
                    </p>
                  </div>
                )}

                {state === "unknown" && (
                  <Alert kind="info">
                    Status &quot;{wa.data?.status}&quot; — check bridge logs. Expected: connected, qr, or disconnected.
                  </Alert>
                )}

                {wa.data?.error && state !== "disconnected" && (
                  <Alert kind="info">
                    <CircleAlert className="inline h-4 w-4 mr-1 align-text-bottom" aria-hidden />
                    {wa.data.error}
                  </Alert>
                )}
              </div>
            )}
          </div>
        </Card>

        <div className="space-y-6">
          <Card className="space-y-4 !p-4 sm:!p-5">
            <h2 className="text-base font-semibold text-slate-900">Setup</h2>
            <ol className="list-decimal space-y-2 pl-4 text-sm text-slate-600">
              {SETUP_STEPS.map((step) => (
                <li key={step}>{step}</li>
              ))}
            </ol>
            <div className="rounded-lg bg-slate-900 px-3 py-3 text-xs text-slate-100 font-mono leading-relaxed">
              .\scripts\start_whatsapp_bridge.ps1
              <br />
              <span className="text-slate-400"># or: cd whatsapp-bridge → npm install → npm start</span>
            </div>
            <p className="text-xs text-slate-500">
              After updating the repo, restart the bridge so <span className="font-mono">/chats</span> works. Check{" "}
              <a className="text-brand-700 underline" href="http://127.0.0.1:39219/" target="_blank" rel="noreferrer">
                http://127.0.0.1:39219/
              </a>{" "}
              — JSON should list <span className="font-mono">/chats</span> (version 1.1.0+). If you see{" "}
              <span className="font-mono">Cannot GET /chats</span>, an old bridge process is still running. If you see{" "}
              <span className="font-mono">detached Frame</span>, restart the bridge (
              <span className="font-mono">.\scripts\start_whatsapp_bridge.ps1</span>
              ), wait until status is Connected, then load chats again.
            </p>
            <p className="text-xs text-slate-500">
              Default listen address: <span className="font-mono">{bridgeUrl}</span>
            </p>
          </Card>

          <Card className="space-y-3 !p-4 sm:!p-5">
            <h2 className="text-base font-semibold text-slate-900 flex items-center gap-2">
              <MessageCircle className="h-4 w-4" aria-hidden />
              Compliance
            </h2>
            <ul className="list-disc space-y-1 pl-4 text-sm text-slate-600">
              <li>Only message numbers found on public institute listings.</li>
              <li>Proposal text is generated per lead; review on the lead detail page if needed.</li>
              <li>Unofficial WhatsApp Web automation — may break when WhatsApp updates.</li>
            </ul>
          </Card>
        </div>
      </div>

      <Card className="overflow-hidden !p-0 w-full">
        <div className="border-b border-slate-100 px-4 py-3 sm:px-5 flex items-center justify-between gap-2">
          <h2 className="text-base font-semibold text-slate-900">Recent WhatsApp sends</h2>
          <span className="text-xs text-slate-500">Stored proposal sends · last 15</span>
        </div>
        {recentSends.isLoading ? (
          <Spinner />
        ) : sentRows.length === 0 ? (
          <div className="px-4 py-10 sm:px-5">
            <EmptyState title="No WhatsApp messages sent yet">
              Proposal sends from a lead (manual or automation) are stored here. Test messages above are not logged in this
              list.
            </EmptyState>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[520px] text-sm">
              <thead className="bg-slate-50 text-left text-xs font-medium uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="px-4 py-2.5 sm:px-5">Institute</th>
                  <th className="px-4 py-2.5 sm:px-5">Sent</th>
                  <th className="px-4 py-2.5 sm:px-5">Preview</th>
                  <th className="px-4 py-2.5 sm:px-5 text-right"> </th>
                </tr>
              </thead>
              <tbody>
                {sentRows.map((row) => (
                  <tr key={`${row.lead_id}-${row.sent_at || ""}`} className="border-t border-slate-100 hover:bg-slate-50/80">
                    <td className="px-4 py-3 sm:px-5 font-medium text-slate-900">{row.name}</td>
                    <td className="px-4 py-3 sm:px-5 whitespace-nowrap text-slate-600" title={formatDateTime(row.sent_at)}>
                      {row.sent_at ? formatRelative(row.sent_at) : "—"}
                    </td>
                    <td className="px-4 py-3 sm:px-5 max-w-xs truncate text-slate-600">{row.preview || "—"}</td>
                    <td className="px-4 py-3 sm:px-5 text-right">
                      <ButtonLink to={`/admin/outreach/leads/${row.lead_id}`} variant="ghost" size="sm">
                        Open lead
                      </ButtonLink>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}

function WhatsappProviderCard() {
  const toast = useToast();
  const qc = useQueryClient();
  const { platform } = useOutreachPlatform();
  const current = platform.data?.outreach?.whatsapp_provider === "cloud" ? "cloud" : "bridge";
  const cloudOk = Boolean(platform.data?.outreach?.whatsapp_cloud_configured);
  const save = useMutation({
    mutationFn: (whatsapp_provider: "bridge" | "cloud") => admin.updateOutreach({ whatsapp_provider }),
    onSuccess: () => {
      toast.success("WhatsApp provider saved");
      void qc.invalidateQueries({ queryKey: ["admin", "settings"] });
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  return (
    <Card title="WhatsApp provider">
      <p className="mb-3 text-sm text-slate-600">
        Bridge is the unofficial WhatsApp Web client for local/dev. Cloud uses Meta WhatsApp Cloud API when WABA credentials are set in the server environment.
      </p>
      <div className="flex flex-wrap gap-2">
        <Button size="sm" variant={current === "bridge" ? "primary" : "secondary"} loading={save.isPending} onClick={() => save.mutate("bridge")}>
          Bridge
        </Button>
        <Button size="sm" variant={current === "cloud" ? "primary" : "secondary"} loading={save.isPending} onClick={() => save.mutate("cloud")}>
          Meta Cloud
        </Button>
      </div>
      <p className="mt-2 text-xs text-slate-500">
        Cloud credentials: {cloudOk ? "configured" : "not set (WHATSAPP_CLOUD_TOKEN + PHONE_NUMBER_ID)"}. Webhook: /api/internal/outreach/whatsapp-cloud
      </p>
    </Card>
  );
}
