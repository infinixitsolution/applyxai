import type { BrowserWindow } from "electron";
import {
  liveInterviewAnswerStream,
  liveInterviewClip,
  liveInterviewEnd,
  liveInterviewStart,
} from "./liveInterviewAgent";
import {
  isLiveCaptureRunning,
  liveCaptureMode,
  probeLiveCapture,
  startLiveCapture,
  stopLiveCapture,
} from "./liveInterviewCapture";
import {
  concealLiveInterviewCoachWindow,
  ensureLiveInterviewCoachWindow,
  getLiveInterviewCoachWindow,
  hideLiveInterviewCoachWindow,
  revealLiveInterviewCoachWindow,
} from "./liveInterviewCoachWindow";
import type { LiveInterviewCoachPhase, LiveInterviewDesktopEvent } from "./liveInterviewTypes";

let activeSessionId: string | null = null;
let mainWindowRef: (() => BrowserWindow | null) | null = null;
let interviewerClipQueue: Promise<void> = Promise.resolve();
let lastTranscript: { role: string; text: string; at?: string }[] = [];
let lastPhase: LiveInterviewCoachPhase = "idle";
let lastPhaseMessage = "";
let lastSuggestion = "";
let lastAnswering = false;

export function setLiveInterviewMainWindow(getter: () => BrowserWindow | null): void {
  mainWindowRef = getter;
}

function trackUiEvent(event: LiveInterviewDesktopEvent): void {
  if (event.type === "phase") {
    lastPhase = event.phase;
    if (event.message !== undefined) lastPhaseMessage = event.message;
  } else if (event.type === "answer") {
    lastSuggestion = event.text;
    lastAnswering = !event.done;
  } else if (event.type === "ended") {
    lastPhase = event.ok ? "idle" : "problem";
    lastPhaseMessage = event.message;
    lastSuggestion = "";
    lastAnswering = false;
  }
}

function emit(event: LiveInterviewDesktopEvent): void {
  trackUiEvent(event);
  const wins: BrowserWindow[] = [];
  const main = mainWindowRef?.();
  if (main && !main.isDestroyed()) wins.push(main);
  const coach = getLiveInterviewCoachWindow();
  if (coach && !coach.isDestroyed() && coach !== main) wins.push(coach);
  for (const win of wins) {
    win.webContents.send("live-interview:event", event);
  }
}

/** Push current session UI state to the coach window (after load or navigation). */
export function replayLiveInterviewUiState(): void {
  if (!activeSessionId) return;
  emit({
    type: "session",
    sessionId: activeSessionId,
    transcript: lastTranscript,
  });
  emit({
    type: "phase",
    phase: lastPhase,
    message: lastPhaseMessage || undefined,
  });
  if (lastSuggestion || lastAnswering) {
    emit({ type: "answer", text: lastSuggestion, done: !lastAnswering });
  }
}

function emitSession(session: {
  id: string;
  transcript?: { role: string; text: string; at?: string }[];
  started_at?: string | null;
}): string {
  const sessionId = String(session.id);
  lastTranscript = session.transcript ?? [];
  emit({
    type: "session",
    sessionId,
    transcript: lastTranscript,
    startedAt: session.started_at ?? null,
  });
  return sessionId;
}

async function attachLiveCapture(sessionId: string): Promise<void> {
  const attachAudio = async () => {
    try {
      await startLiveCapture((speaker, wav) => {
        if (activeSessionId !== sessionId) return;
        if (speaker === "interviewer") {
          interviewerClipQueue = interviewerClipQueue
            .then(() => handleClip(sessionId, speaker, wav))
            .catch((err: unknown) => {
              const message = err instanceof Error ? err.message : String(err);
              emit({ type: "phase", phase: "problem", message });
            });
          return;
        }
        void handleClip(sessionId, speaker, wav).catch((err: unknown) => {
          const message = err instanceof Error ? err.message : String(err);
          emit({ type: "phase", phase: "problem", message });
        });
      });
      const mode = liveCaptureMode();
      emit({
        type: "phase",
        phase: "listening",
        message:
          mode === "native"
            ? "Listening to your speakers and microphone. Suggested answers appear after the interviewer speaks."
            : "Listening via screen share audio. Suggested answers appear after the interviewer speaks.",
      });
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      emit({ type: "phase", phase: "problem", message });
      setTimeout(() => {
        if (activeSessionId === sessionId) void attachAudio();
      }, 2000);
    }
  };
  void attachAudio();
}

async function handleClip(sessionId: string, speaker: string, wav: Buffer): Promise<void> {
  try {
    if (speaker === "interviewer") {
      emit({ type: "phase", phase: "listening", message: "Transcribing question…" });
    }
    const data = await liveInterviewClip(sessionId, speaker, wav);
    if (data.transcript) {
      lastTranscript = data.transcript;
      emit({ type: "transcript", transcript: data.transcript });
    }
    if (data.answer_pending) {
      emit({ type: "phase", phase: "answering", message: "Drafting your answer…" });
      emit({ type: "answer", text: "", done: false });
      let text = "";
      for await (const piece of liveInterviewAnswerStream(sessionId)) {
        text += piece;
        emit({ type: "answer", text, done: false });
      }
      emit({ type: "answer", text, done: true });
      if (text.trim()) {
        lastTranscript = [
          ...lastTranscript,
          { role: "suggestion", text: text.trim(), at: new Date().toISOString() },
        ];
        emit({ type: "transcript", transcript: lastTranscript });
      }
      emit({ type: "phase", phase: "listening", message: "Listening for the next question…" });
    }
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    emit({ type: "phase", phase: "problem", message });
    emit({ type: "answer", text: "", done: true });
  }
}

async function reconnectDesktopInterview(
  token: string,
  applicationId: string | null,
): Promise<{ sessionId: string }> {
  await ensureLiveInterviewCoachWindow();
  emit({ type: "phase", phase: "waiting", message: "Reconnecting to your interview…" });
  const session = await liveInterviewStart(token, applicationId);
  const sessionId = emitSession(session);
  activeSessionId = sessionId;
  if (!isLiveCaptureRunning()) {
    emit({ type: "phase", phase: "waiting", message: "Reconnecting microphone and call audio…" });
    void attachLiveCapture(sessionId);
  } else {
    emit({
      type: "phase",
      phase: "listening",
      message: "Interview in progress. Use End interview when the call is over.",
    });
  }
  return { sessionId };
}

async function stopLocalInterviewSession(): Promise<void> {
  if (!activeSessionId) return;
  await stopLiveCapture();
  activeSessionId = null;
  lastTranscript = [];
  interviewerClipQueue = Promise.resolve();
  hideLiveInterviewCoachWindow();
  emit({
    type: "ended",
    ok: true,
    message: "Previous interview closed. Starting a new session…",
  });
}

export async function startLiveInterviewSession(
  token: string,
  applicationId: string | null,
  options: { resume?: boolean } = {},
): Promise<{ sessionId: string }> {
  const resume = options.resume === true;

  if (resume) {
    return reconnectDesktopInterview(token, applicationId);
  }

  if (activeSessionId) {
    await stopLocalInterviewSession();
  }

  try {
    await ensureLiveInterviewCoachWindow();
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    throw new Error(`Could not open interview coach window: ${message}`);
  }
  emit({ type: "phase", phase: "waiting", message: "Starting session…" });
  let session;
  try {
    session = await liveInterviewStart(token, applicationId);
  } catch (err) {
    hideLiveInterviewCoachWindow();
    throw err;
  }
  const sessionId = emitSession(session);
  activeSessionId = sessionId;
  void attachLiveCapture(sessionId);
  return { sessionId };
}

/** Re-sync renderer state after navigation without starting a new backend session. */
export async function syncLiveInterviewSession(): Promise<{ active: boolean; sessionId: string | null }> {
  if (!activeSessionId) return { active: false, sessionId: null };
  await ensureLiveInterviewCoachWindow();
  const sessionId = activeSessionId;
  if (!isLiveCaptureRunning()) {
    emit({ type: "phase", phase: "waiting", message: "Starting microphone and call audio capture…" });
    void attachLiveCapture(sessionId);
  } else {
    emit({
      type: "phase",
      phase: "listening",
      message: "Interview in progress. Use End interview when the call is over.",
    });
  }
  emit({
    type: "session",
    sessionId,
    transcript: lastTranscript.length ? lastTranscript : undefined,
    startedAt: null,
  });
  return { active: true, sessionId };
}

export async function endLiveInterviewSession(sessionId: string): Promise<{ ok: boolean; message: string }> {
  if (!activeSessionId || activeSessionId !== sessionId) {
    return { ok: false, message: "No matching interview is running." };
  }
  await stopLiveCapture();
  activeSessionId = null;
  lastTranscript = [];
  interviewerClipQueue = Promise.resolve();
  try {
    await liveInterviewEnd(sessionId);
    const message = "Interview saved. Open Live interviews for your report.";
    emit({ type: "ended", ok: true, message });
    hideLiveInterviewCoachWindow();
    return { ok: true, message };
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    emit({ type: "ended", ok: false, message });
    hideLiveInterviewCoachWindow();
    return { ok: false, message };
  }
}

export function liveInterviewStatus(): { active: boolean; sessionId: string | null } {
  return { active: Boolean(activeSessionId), sessionId: activeSessionId };
}

export async function showLiveInterviewCoachOverlay(): Promise<void> {
  await revealLiveInterviewCoachWindow();
  emit({ type: "coachUi", panelOpen: true });
}

export async function concealLiveInterviewCoachOverlay(): Promise<void> {
  concealLiveInterviewCoachWindow();
  emit({ type: "coachUi", panelOpen: false });
}

export async function probeLiveInterviewAudio(): Promise<{ ok: boolean; message: string }> {
  if (activeSessionId) {
    return { ok: true, message: "Interview already running." };
  }
  return probeLiveCapture();
}

/** End whichever interview is active in the main process (coach window safe). */
export async function endActiveLiveInterviewSession(): Promise<{ ok: boolean; message: string }> {
  const sessionId = activeSessionId;
  if (!sessionId) {
    return { ok: false, message: "No active interview session found." };
  }
  return endLiveInterviewSession(sessionId);
}
