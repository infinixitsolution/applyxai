import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Headphones, Laptop } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Select } from "../components/form";
import { Alert, Badge, Button, Card } from "../components/ui";
import { useLiveInterviewCoachContext } from "./LiveInterviewCoach";
import {
  desktopAgent,
  hasDesktopAgent,
  hasLiveInterviewDesktop,
  isDesktopBridgeReady,
  isDesktopHost,
  liveInterviewUnavailableMessage,
  waitForDesktopBridge,
} from "../lib/desktop";
import { reconcileDesktopLink } from "../lib/desktopConnect";
import { liveInterviewDesktop } from "../lib/liveInterviewDesktop";
import { latestPaymentLink, pickUsableToken } from "../lib/liveInterviewTokens";
import { errorMessage } from "../services/api";
import { liveInterviews, support } from "../services/endpoints";
import type { LiveInterviewSession, SupportMessage } from "../types";

type Props = {
  messages?: SupportMessage[];
  compact?: boolean;
  /** Pre-fill token (e.g. continue in-progress session). */
  initialToken?: string;
  activeSession?: LiveInterviewSession | null;
  onStarted?: () => void;
  /** When set, parent can trigger resume (Continue in coach). */
  resumeNonce?: number;
};

export function LiveInterviewFlow({
  messages: messagesProp,
  compact,
  initialToken,
  activeSession,
  onStarted,
  resumeNonce,
}: Props) {
  const queryClient = useQueryClient();
  const coach = useLiveInterviewCoachContext();
  const threadQuery = useQuery({
    queryKey: ["support", "thread"],
    queryFn: support.thread,
    enabled: messagesProp === undefined,
    refetchInterval: 4000,
  });
  const messages = messagesProp ?? threadQuery.data?.messages ?? [];
  const paymentUrl = latestPaymentLink(messages);
  const usable = pickUsableToken(messages);
  const [tokenOverride, setTokenOverride] = useState(initialToken ?? "");
  const [applicationId, setApplicationId] = useState("");
  const [localError, setLocalError] = useState("");
  const [statusLine, setStatusLine] = useState("");
  const [starting, setStarting] = useState(false);
  const [bridgeReady, setBridgeReady] = useState(() => isDesktopBridgeReady());
  const [bridgeWaiting, setBridgeWaiting] = useState(() => isDesktopHost && !isDesktopBridgeReady());

  useEffect(() => {
    if (!isDesktopHost || bridgeReady) return;
    let cancelled = false;
    void waitForDesktopBridge(5000).then((ok) => {
      if (cancelled) return;
      if (ok) setBridgeReady(true);
      setBridgeWaiting(false);
    });
    return () => {
      cancelled = true;
    };
  }, [bridgeReady]);

  const appsQuery = useQuery({
    queryKey: ["live-interview-applications"],
    queryFn: liveInterviews.applications,
  });

  const agentStatus = useQuery({
    queryKey: ["desktop-agent-local"],
    queryFn: () => desktopAgent()!.status(),
    enabled: hasDesktopAgent() && Boolean(desktopAgent()),
    refetchInterval: 15_000,
  });

  const requestToken = useMutation({
    mutationFn: support.requestLiveInterview,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["support", "thread"] });
    },
  });

  const tokenDigits = useMemo(() => {
    const raw = (tokenOverride || usable?.code || activeSession?.token || "").replace(/\D/g, "");
    return raw.length === 8 ? raw : "";
  }, [tokenOverride, usable, activeSession?.token]);

  useEffect(() => {
    if (initialToken) setTokenOverride(initialToken);
    else if (usable?.code && !tokenOverride) setTokenOverride(usable.code);
  }, [initialToken, usable?.code, tokenOverride]);

  useEffect(() => {
    if (activeSession?.application_id) setApplicationId(activeSession.application_id);
  }, [activeSession?.application_id]);

  useEffect(() => {
    if (!resumeNonce || !isDesktopHost || coach?.sessionId) return;
    const sessionToken = activeSession?.token?.replace(/\D/g, "").slice(0, 8) || "";
    const token = sessionToken || tokenDigits;
    if (token.length !== 8 || !coach?.start) return;
    void (async () => {
      setLocalError("");
      try {
        await coach.start(token, applicationId || activeSession?.application_id || null, { resume: true });
        await liveInterviewDesktop()?.showCoach?.();
        onStarted?.();
        await queryClient.invalidateQueries({ queryKey: ["live-interviews"] });
      } catch (e) {
        setLocalError(errorMessage(e));
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- resumeNonce is the intentional trigger
  }, [resumeNonce]);

  const appOptions = useMemo(
    () => [
      { value: "", label: "No application linked" },
      ...(appsQuery.data ?? []).map((a) => ({
        value: a.id,
        label: `${a.title} · ${a.company}`,
      })),
    ],
    [appsQuery.data],
  );

  const interviewRunning = Boolean(coach?.sessionId);

  async function ensureComputerLinked(): Promise<void> {
    if (agentStatus.data?.connected) return;
    if (!hasDesktopAgent()) {
      throw new Error("Automation on this PC is still starting. Wait a few seconds and try again.");
    }
    setStatusLine("Linking this computer to your account…");
    await reconcileDesktopLink(false);
    await queryClient.invalidateQueries({ queryKey: ["automation"] });
    await queryClient.invalidateQueries({ queryKey: ["desktop-agent-local"] });
    const fresh = await queryClient.fetchQuery({
      queryKey: ["desktop-agent-local"],
      queryFn: () => desktopAgent()!.status(),
    });
    if (!fresh.connected) {
      throw new Error("This computer is not linked yet. Open Automation and wait for pairing, then try again.");
    }
  }

  async function handleStartLiveInterview() {
    setLocalError("");
    setStatusLine("");
    if (!tokenDigits) {
      setLocalError("Enter or request an 8-digit token first.");
      return;
    }
    const bridgeOk = isDesktopBridgeReady() || (await waitForDesktopBridge(4000));
    if (bridgeOk) setBridgeReady(true);
    if (!bridgeOk || !hasLiveInterviewDesktop()) {
      setLocalError(liveInterviewUnavailableMessage());
      return;
    }
    if (!coach?.start) {
      setLocalError("Coach failed to load. Refresh the page and try again.");
      return;
    }
    const desktop = liveInterviewDesktop();

    setStarting(true);
    try {
      await ensureComputerLinked();

      setStatusLine("Checking microphone and call audio…");
      const probe = coach.probeAudio ? await coach.probeAudio() : await desktop!.probeAudio();
      if (!probe.ok) {
        throw new Error(probe.message || "Audio check failed. Allow microphone access and try again.");
      }

      setStatusLine("Connecting to interview coach (AI)…");
      const health = await fetch("/api/health", { credentials: "same-origin" });
      const body = (await health.json()) as { success?: boolean };
      if (!health.ok || !body.success) {
        throw new Error("Can't reach the ApplyXAI API. Check the server on the login screen, then try again.");
      }

      setStatusLine("Starting live interview…");
      await coach.start(tokenDigits, applicationId || null);
      await desktop?.showCoach?.();
      onStarted?.();
      await queryClient.invalidateQueries({ queryKey: ["live-interviews"] });
      await queryClient.invalidateQueries({ queryKey: ["support", "thread"] });
    } catch (e) {
      setLocalError(errorMessage(e));
    } finally {
      setStarting(false);
      setStatusLine("");
    }
  }

  const step = !usable && !paymentUrl && !requestToken.isSuccess ? 1 : paymentUrl && !usable ? 2 : tokenDigits ? 3 : 2;

  return (
    <div id="live-interview-flow">
      <Card title={compact ? undefined : "Live interview"} className={compact ? "!p-4" : undefined}>
        {!compact && (
          <p className="mb-4 text-sm text-slate-600">
            Request access, pay if prompted, pick the job you applied to, then start coaching in one step.
          </p>
        )}
        <ol className="mb-4 space-y-2 text-sm text-slate-700">
          <li className="flex flex-wrap items-center gap-2">
            <Badge tone={step >= 1 ? "brand" : "slate"}>1</Badge>
            <span>Request an interview token</span>
            <Button size="sm" variant="secondary" onClick={() => requestToken.mutate()} loading={requestToken.isPending}>
              Request
            </Button>
          </li>
          <li className="flex flex-wrap items-center gap-2">
            <Badge tone={step >= 2 ? "brand" : "slate"}>2</Badge>
            <span>Pay when a link appears in chat</span>
            {paymentUrl && (
              <a href={paymentUrl} target="_blank" rel="noreferrer" className="text-sm font-medium text-brand-700 underline">
                Open payment
              </a>
            )}
          </li>
          <li className="flex flex-wrap items-center gap-2">
            <Badge tone={step >= 3 ? "brand" : "slate"}>3</Badge>
            <span>Enter token and start — audio + AI are checked automatically</span>
          </li>
        </ol>

        {(requestToken.error || localError) && (
          <div className="mb-3">
            <Alert kind="error">{localError || errorMessage(requestToken.error)}</Alert>
          </div>
        )}

        <div className="grid gap-3 sm:grid-cols-2">
          <label className="block text-sm">
            <span className="mb-1 block font-medium text-slate-700">8-digit token</span>
            <input
              value={tokenOverride}
              onChange={(e) => setTokenOverride(e.target.value.replace(/\D/g, "").slice(0, 8))}
              placeholder="From Support chat"
              className="w-full rounded-lg border border-slate-300 px-3 py-2 font-mono tracking-widest"
              inputMode="numeric"
            />
            {usable?.status === "reserved" && (
              <p className="mt-1 text-xs text-amber-700">Token in progress — Start resumes the session.</p>
            )}
          </label>
          <Select label="Auto-applied job (optional)" value={applicationId} onChange={setApplicationId} options={appOptions} />
        </div>

        {statusLine && (
          <div className="mt-3">
            <Alert kind="info">{statusLine}</Alert>
          </div>
        )}

        {bridgeWaiting && (
          <div className="mt-3">
            <Alert kind="info">Connecting to ApplyXAI Desktop…</Alert>
          </div>
        )}
        {isDesktopHost && !bridgeReady && !bridgeWaiting && (
          <div className="mt-3">
            <Alert kind="info">{liveInterviewUnavailableMessage()}</Alert>
          </div>
        )}

        <div className="mt-4 flex flex-wrap items-center gap-2">
          {isDesktopHost ? (
            <>
              <Button
                type="button"
                variant="primary"
                onClick={() => void handleStartLiveInterview()}
                loading={starting}
                disabled={(!tokenDigits && !interviewRunning) || starting}
              >
                <Headphones className="h-4 w-4" aria-hidden />
                {interviewRunning ? "Interview running" : starting ? "Starting…" : "Start live interview"}
              </Button>
              {interviewRunning && (
                <>
                  <Button type="button" variant="secondary" size="sm" onClick={() => void liveInterviewDesktop()?.showCoach?.()}>
                    Show coach window
                  </Button>
                  <Button type="button" variant="secondary" size="sm" onClick={() => void liveInterviewDesktop()?.reconnectAudio?.()}>
                    Reconnect audio
                  </Button>
                </>
              )}
              {!tokenDigits && !interviewRunning && (
                <span className="text-xs text-slate-500">Enter an 8-digit token, then Start (audio + AI are checked automatically).</span>
              )}
            </>
          ) : (
            <p className="inline-flex items-center gap-2 text-sm text-slate-600">
              <Laptop className="h-4 w-4" aria-hidden />
              Open <strong>ApplyXAI Desktop</strong> to start the live coach after you have a token.
            </p>
          )}
        </div>

        <p className="mt-4 text-xs text-slate-500">
          Reports appear under{" "}
          <Link to="/app/live-interviews" className="font-medium text-brand-700 underline">
            Live interviews
          </Link>
          . The coach window opens when the interview starts{isDesktopHost ? "" : " (Desktop only)"}.
        </p>
      </Card>
    </div>
  );
}
