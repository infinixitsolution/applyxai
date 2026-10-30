import { useCallback, useEffect, useState } from "react";
import type { LiveInterviewCoachPhase, LiveInterviewDesktopEvent } from "../lib/liveInterviewDesktop";
import { liveInterviewDesktop } from "../lib/liveInterviewDesktop";
import type { LiveInterviewTurn } from "../types";

export function useLiveInterviewCoach() {
  const api = liveInterviewDesktop();
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [phase, setPhase] = useState<LiveInterviewCoachPhase>("idle");
  const [statusMessage, setStatusMessage] = useState("");
  const [transcript, setTranscript] = useState<LiveInterviewTurn[]>([]);
  const [suggestion, setSuggestion] = useState("");
  const [answering, setAnswering] = useState(false);

  useEffect(() => {
    if (!api) return undefined;
    void (async () => {
      const status = await api.status();
      if (status.active && status.sessionId) {
        setSessionId(status.sessionId);
        await api.sync?.().catch(() => undefined);
      }
    })();
    return api.onEvent((event: LiveInterviewDesktopEvent) => {
      if (event.type === "phase") {
        setPhase(event.phase);
        if (event.message !== undefined) setStatusMessage(event.message);
      } else if (event.type === "session") {
        setSessionId(event.sessionId);
        if (event.transcript !== undefined) setTranscript(event.transcript);
      } else if (event.type === "transcript") {
        setTranscript(event.transcript ?? []);
      } else if (event.type === "answer") {
        if (!event.done) {
          setPhase("answering");
          setAnswering(true);
        } else {
          setAnswering(false);
        }
        setSuggestion(event.text);
      } else if (event.type === "ended") {
        setSessionId(null);
        setPhase(event.ok ? "idle" : "problem");
        setStatusMessage(event.message);
        setAnswering(false);
      }
    });
  }, [api]);

  const start = useCallback(
    async (token: string, applicationId?: string | null, options?: { resume?: boolean }) => {
      if (!api) throw new Error("Live interview start is only available in ApplyXAI Desktop.");
      if (!options?.resume) {
        setPhase("waiting");
        setStatusMessage("Starting session…");
        setTranscript([]);
        setSuggestion("");
      }
      const result = await api.start({
        token,
        applicationId: applicationId ?? null,
        resume: options?.resume,
      });
      setSessionId(result.sessionId);
      return result.sessionId;
    },
    [api],
  );

  const end = useCallback(async () => {
    if (!api) return;
    let id = sessionId;
    if (!id) {
      const status = await api.status();
      id = status.sessionId;
      if (id) setSessionId(id);
    }
    if (!id) {
      setStatusMessage("No active interview session found.");
      setPhase("problem");
      return;
    }
    setStatusMessage("Saving report…");
    if (api.endActive) {
      await api.endActive();
      return;
    }
    await api.end(id);
  }, [api, sessionId]);

  const probeAudio = useCallback(async () => {
    if (!api) return { ok: false, message: "Desktop only." };
    return api.probeAudio();
  }, [api]);

  return {
    available: Boolean(api),
    sessionId,
    phase,
    statusMessage,
    transcript,
    suggestion,
    answering,
    start,
    end,
    probeAudio,
  };
}
