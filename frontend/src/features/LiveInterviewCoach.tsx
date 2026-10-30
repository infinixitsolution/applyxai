import { Loader2, MessageSquare, Mic, Minus, Plus, X } from "lucide-react";
import {
  createContext,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
  type PointerEvent as ReactPointerEvent,
} from "react";
import { Badge, Button, cx } from "../components/ui";
import { useLiveInterviewCoach } from "../hooks/useLiveInterviewCoach";
import type { LiveInterviewCoachPhase } from "../lib/liveInterviewDesktop";
import { liveInterviewDesktop } from "../lib/liveInterviewDesktop";
import type { LiveInterviewTurn } from "../types";

const ROLE_LABEL: Record<string, string> = {
  interviewer: "Interviewer",
  candidate: "You",
  suggestion: "Suggested answer",
};

function phaseLabel(phase: LiveInterviewCoachPhase): string {
  if (phase === "waiting") return "Waiting for audio…";
  if (phase === "listening") return "Listening";
  if (phase === "answering") return "Drafting answer…";
  if (phase === "problem") return "Needs attention";
  return "Coach";
}

const DRAG_THRESHOLD_PX = 5;

/** Drag the detached Electron coach window by moving the overlay on screen. */
function useCoachWindowDrag(detached: boolean) {
  const api = detached ? liveInterviewDesktop() : null;
  const dragRef = useRef({ active: false, moved: false, lastScreenX: 0, lastScreenY: 0 });

  const onPointerDown = (event: ReactPointerEvent) => {
    if (!api?.moveCoachWindow) return;
    dragRef.current = {
      active: true,
      moved: false,
      lastScreenX: event.screenX,
      lastScreenY: event.screenY,
    };
    event.currentTarget.setPointerCapture(event.pointerId);
  };

  const onPointerMove = (event: ReactPointerEvent) => {
    if (!dragRef.current.active || !api?.moveCoachWindow) return;
    const dx = event.screenX - dragRef.current.lastScreenX;
    const dy = event.screenY - dragRef.current.lastScreenY;
    if (!dragRef.current.moved && Math.abs(dx) + Math.abs(dy) < DRAG_THRESHOLD_PX) return;
    dragRef.current.moved = true;
    dragRef.current.lastScreenX = event.screenX;
    dragRef.current.lastScreenY = event.screenY;
    void api.moveCoachWindow(dx, dy);
  };

  const endDrag = (event: ReactPointerEvent) => {
    if (!dragRef.current.active) return false;
    const wasClick = !dragRef.current.moved;
    dragRef.current.active = false;
    try {
      event.currentTarget.releasePointerCapture(event.pointerId);
    } catch {
      /* already released */
    }
    return wasClick;
  };

  return { onPointerDown, onPointerMove, endDrag, dragRef };
}

function ChatTurn({ turn }: { turn: LiveInterviewTurn }) {
  const role = turn.role;
  const isSuggestion = role === "suggestion";
  const isCandidate = role === "candidate";
  return (
    <div className={cx("flex w-full", isCandidate ? "justify-end" : "justify-start")}>
      <div
        className={cx(
          "max-w-[92%] rounded-lg px-3 py-2 text-sm shadow-sm backdrop-blur-sm",
          isSuggestion
            ? "border border-emerald-400/60 bg-emerald-50/90 text-emerald-950"
            : isCandidate
              ? "border border-sky-300/50 bg-sky-50/90 text-sky-950"
              : "border border-white/40 bg-white/90 text-slate-900",
        )}
      >
        <p className="text-[10px] font-bold uppercase tracking-wide opacity-80">{ROLE_LABEL[role] ?? role}</p>
        <p className="mt-0.5 whitespace-pre-wrap leading-snug">{turn.text}</p>
      </div>
    </div>
  );
}

function stopHeaderDrag(event: ReactPointerEvent) {
  event.stopPropagation();
}

function DetachedSupportAgent({
  phase,
  statusMessage,
  transcript,
  suggestion,
  answering,
  onEnd,
  onClose,
  ending,
  canEnd,
  windowDrag,
}: {
  phase: LiveInterviewCoachPhase;
  statusMessage: string;
  transcript: LiveInterviewTurn[];
  suggestion: string;
  answering: boolean;
  onEnd: () => void;
  onClose: () => void;
  ending: boolean;
  canEnd: boolean;
  windowDrag: ReturnType<typeof useCoachWindowDrag>;
}) {
  const desktop = liveInterviewDesktop();
  const transcriptWithoutLiveSuggestion = transcript.filter(
    (t, i) => !(t.role === "suggestion" && i === transcript.length - 1 && suggestion && t.text === suggestion),
  );
  const showLiveSuggestion = (answering || phase === "answering" || suggestion) && !transcript.some(
    (t) => t.role === "suggestion" && t.text === suggestion && suggestion,
  );

  return (
    <div className="flex h-screen min-h-0 w-screen flex-col border border-white/50 bg-transparent shadow-[0_0_0_1px_rgba(148,163,184,0.35)]">
      <header
        className="flex shrink-0 cursor-grab touch-none items-center gap-2 bg-[#e65100] px-2 py-2 text-white active:cursor-grabbing"
        onPointerDown={windowDrag.onPointerDown}
        onPointerMove={windowDrag.onPointerMove}
        onPointerUp={(event) => windowDrag.endDrag(event)}
        onPointerCancel={(event) => windowDrag.endDrag(event)}
        title="Drag to move"
      >
        <img src="/mascot.png" alt="" className="h-9 w-9 shrink-0 rounded bg-white/10 object-contain" />
        <p className="min-w-0 flex-1 text-center text-sm font-semibold leading-tight sm:text-base">
          Live interview support agent
        </p>
        <button
          type="button"
          onPointerDown={stopHeaderDrag}
          onClick={(event) => {
            event.stopPropagation();
            onEnd();
          }}
          disabled={!canEnd || ending}
          className="shrink-0 rounded bg-white px-2.5 py-1 text-xs font-semibold text-slate-900 hover:bg-slate-100 disabled:opacity-50"
        >
          {ending ? "Saving…" : "End interview"}
        </button>
        <button
          type="button"
          onPointerDown={stopHeaderDrag}
          onClick={(event) => {
            event.stopPropagation();
            onClose();
          }}
          className="flex h-8 w-8 shrink-0 items-center justify-center rounded bg-white text-lg font-bold leading-none text-slate-900 hover:bg-slate-100"
          aria-label="Hide coach"
        >
          <X className="h-5 w-5" aria-hidden />
        </button>
      </header>

      <main className="min-h-0 flex-1 space-y-2 overflow-y-auto bg-transparent px-2 py-2">
        {phase === "problem" && statusMessage && (
          <p className="rounded-lg border border-red-300/60 bg-red-50/90 px-3 py-2 text-xs text-red-900 backdrop-blur-sm">
            {statusMessage}
          </p>
        )}
        {phase === "waiting" && statusMessage && (
          <p className="rounded-lg border border-white/40 bg-white/75 px-3 py-2 text-xs text-slate-700 backdrop-blur-sm">
            {statusMessage}
          </p>
        )}
        {transcriptWithoutLiveSuggestion.length === 0 && !showLiveSuggestion && phase === "listening" && (
          <p className="rounded-lg border border-white/35 bg-white/70 px-3 py-2 text-center text-xs text-slate-600 backdrop-blur-sm">
            Transcription and suggested answers appear here when the interviewer speaks.
          </p>
        )}
        {transcriptWithoutLiveSuggestion.map((turn, index) => (
          <ChatTurn key={`${turn.role}-${index}-${turn.text.slice(0, 12)}`} turn={turn} />
        ))}
        {showLiveSuggestion && (
          <div className="flex justify-start">
            <div className="max-w-[92%] rounded-lg border border-emerald-400/60 bg-emerald-50/90 px-3 py-2 text-sm shadow-sm backdrop-blur-sm">
              <p className="text-[10px] font-bold uppercase tracking-wide text-emerald-800">
                Suggested answer{answering || phase === "answering" ? "…" : ""}
              </p>
              {suggestion ? (
                <p className="mt-0.5 whitespace-pre-wrap leading-snug text-emerald-950">{suggestion}</p>
              ) : (
                <p className="mt-1 flex items-center gap-2 text-emerald-900">
                  <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
                  Drafting…
                </p>
              )}
            </div>
          </div>
        )}
      </main>

      <footer className="flex shrink-0 items-center justify-between gap-2 bg-[#1a365d] px-2 py-2 text-xs font-medium text-white">
        <div className="flex items-center gap-1">
          <button
            type="button"
            title="Narrow panel"
            aria-label="Narrow panel"
            className="flex h-7 w-7 items-center justify-center rounded bg-white/15 hover:bg-white/25"
            onClick={() => void desktop?.resizeCoachWindow?.(-48)}
          >
            <Minus className="h-4 w-4" aria-hidden />
          </button>
          <button
            type="button"
            title="Widen panel"
            aria-label="Widen panel"
            className="flex h-7 w-7 items-center justify-center rounded bg-white/15 hover:bg-white/25"
            onClick={() => void desktop?.resizeCoachWindow?.(48)}
          >
            <Plus className="h-4 w-4" aria-hidden />
          </button>
        </div>
        <p className="min-w-0 flex-1 text-center leading-snug">
          Understand the question and answer carefully
          {phase === "listening" && (
            <span className="ml-1 inline-flex items-center gap-1 opacity-90">
              <span className="inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-emerald-400" aria-hidden />
              Listening
            </span>
          )}
        </p>
        <div className="w-[4.5rem]" aria-hidden />
      </footer>
    </div>
  );
}

export function LiveInterviewCoach({
  open,
  onToggle,
  phase,
  statusMessage,
  transcript,
  suggestion,
  answering,
  onEnd,
  ending,
  detached = false,
  canEnd = true,
}: {
  open: boolean;
  onToggle: () => void;
  phase: LiveInterviewCoachPhase;
  statusMessage: string;
  transcript: LiveInterviewTurn[];
  suggestion: string;
  answering: boolean;
  onEnd: () => void;
  ending: boolean;
  detached?: boolean;
  canEnd?: boolean;
}) {
  const windowDrag = useCoachWindowDrag(detached);

  if (detached) {
    if (!open) return null;
    return (
      <DetachedSupportAgent
        phase={phase}
        statusMessage={statusMessage}
        transcript={transcript}
        suggestion={suggestion}
        answering={answering}
        onEnd={onEnd}
        onClose={onToggle}
        ending={ending}
        canEnd={canEnd}
        windowDrag={windowDrag}
      />
    );
  }

  if (phase === "idle" && !open) return null;

  const anchor = "fixed";

  return (
    <>
      <button
        type="button"
        onClick={onToggle}
        className={cx(
          `${anchor} bottom-4 right-4 z-50 flex h-14 w-14 items-center justify-center rounded-full shadow-lg ring-2 ring-white transition-transform hover:scale-105`,
          phase === "listening"
            ? "bg-emerald-600 text-white"
            : phase === "answering"
              ? "bg-amber-500 text-white"
              : "bg-brand-600 text-white",
        )}
        aria-label={open ? "Hide live interview coach" : "Show live interview coach"}
      >
        {phase === "listening" ? (
          <Mic className="h-6 w-6" aria-hidden />
        ) : phase === "answering" ? (
          <Loader2 className="h-6 w-6 animate-spin" aria-hidden />
        ) : (
          <MessageSquare className="h-6 w-6" aria-hidden />
        )}
      </button>
      {open && (
        <div
          className={`${anchor} bottom-20 right-4 z-50 flex w-[min(24rem,calc(100vw-2rem))] flex-col overflow-hidden rounded-2xl bg-white shadow-2xl ring-1 ring-slate-200`}
        >
          <header className="flex items-center justify-between gap-2 border-b border-slate-100 px-4 py-3">
            <div>
              <p className="text-sm font-semibold text-slate-900">Live interview coach</p>
              <p className="text-xs text-slate-500">{phaseLabel(phase)}</p>
            </div>
            <Badge
              tone={
                phase === "listening" ? "green" : phase === "problem" ? "red" : phase === "answering" ? "amber" : "blue"
              }
            >
              {phaseLabel(phase)}
            </Badge>
          </header>
          {statusMessage && (
            <p
              className={cx(
                "px-4 py-2 text-xs",
                phase === "problem" ? "bg-red-50 text-red-800" : "bg-slate-50 text-slate-600",
              )}
            >
              {statusMessage}
            </p>
          )}
          <div className="max-h-64 flex-1 space-y-3 overflow-y-auto px-4 py-3 text-sm">
            {transcript.length === 0 && !suggestion && !answering && phase !== "answering" && (
              <p className="text-slate-500">Questions and suggested answers appear here during the call.</p>
            )}
            {transcript.map((turn, index) => (
              <div key={`${turn.role}-${index}`}>
                <p className="text-xs font-semibold uppercase tracking-wide text-brand-700">
                  {ROLE_LABEL[turn.role] ?? turn.role}
                </p>
                <p className="mt-0.5 whitespace-pre-wrap text-slate-800">{turn.text}</p>
              </div>
            ))}
            {(answering || phase === "answering" || suggestion) && (
              <div className="rounded-xl border border-emerald-200 bg-emerald-50/80 p-3">
                <p className="text-xs font-semibold uppercase tracking-wide text-emerald-800">
                  Say this{answering || phase === "answering" ? "…" : ""}
                </p>
                {suggestion ? (
                  <p className="mt-1 whitespace-pre-wrap text-emerald-950">{suggestion}</p>
                ) : (
                  <p className="mt-1 flex items-center gap-2 text-emerald-900">
                    <Loader2 className="h-4 w-4 shrink-0 animate-spin" aria-hidden />
                    Drafting your answer…
                  </p>
                )}
              </div>
            )}
          </div>
          <footer className="flex flex-wrap items-center justify-between gap-2 border-t border-slate-100 px-4 py-3">
            <Button variant="secondary" size="sm" onClick={onToggle}>
              <X className="h-4 w-4" aria-hidden /> Hide
            </Button>
            <Button variant="primary" size="sm" onClick={onEnd} loading={ending} disabled={phase === "idle"}>
              End interview
            </Button>
          </footer>
        </div>
      )}
    </>
  );
}

type CoachContextValue = ReturnType<typeof useLiveInterviewCoach> & { active: boolean };

const CoachContext = createContext<CoachContextValue | null>(null);

export function LiveInterviewCoachProvider({ children }: { children: ReactNode }) {
  const coach = useLiveInterviewCoach();
  const active = coach.phase !== "idle" || Boolean(coach.sessionId);
  return <CoachContext.Provider value={{ ...coach, active }}>{children}</CoachContext.Provider>;
}

export function useLiveInterviewCoachContext() {
  return useContext(CoachContext);
}

export function LiveInterviewCoachHost({ detached = false }: { detached?: boolean }) {
  const [panelOpen, setPanelOpen] = useState(true);
  const [ending, setEnding] = useState(false);
  const coach = useLiveInterviewCoachContext();
  const desktopCoach = detached ? liveInterviewDesktop() : null;

  useEffect(() => {
    if (!detached || !desktopCoach) return undefined;
    return desktopCoach.onEvent((event) => {
      if (event.type === "coachUi") setPanelOpen(event.panelOpen);
    });
  }, [detached, desktopCoach]);

  useEffect(() => {
    if (coach?.sessionId) setPanelOpen(true);
  }, [coach?.sessionId]);

  function togglePanel() {
    if (detached && desktopCoach) {
      if (panelOpen) void desktopCoach.concealCoach?.();
      else void desktopCoach.showCoach?.();
      return;
    }
    setPanelOpen((open) => !open);
  }

  const canEnd = Boolean(coach?.sessionId) || (coach?.phase ?? "idle") !== "idle";

  if (!coach?.active && !detached) return null;
  return (
    <LiveInterviewCoach
      detached={detached}
      open={panelOpen}
      onToggle={togglePanel}
      phase={coach?.phase ?? "idle"}
      statusMessage={coach?.statusMessage ?? ""}
      transcript={coach?.transcript ?? []}
      suggestion={coach?.suggestion ?? ""}
      answering={coach?.answering ?? false}
      ending={ending}
      canEnd={canEnd}
      onEnd={() => {
        if (!coach?.end) return;
        setEnding(true);
        void coach.end().finally(() => setEnding(false));
      }}
    />
  );
}
