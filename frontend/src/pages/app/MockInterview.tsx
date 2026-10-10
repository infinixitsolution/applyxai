import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Component, useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { Navigate, useNavigate, useParams } from "react-router-dom";
import { Alert, Button, Spinner } from "../../components/ui";
import { MockInterviewAnalysisProgress } from "../../features/MockInterviewAnalysisProgress";
import { MockInterviewDashboard } from "../../features/MockInterviewDashboard";
import { captureVideoFrame, pushPresentationFrame } from "../../features/captureVideoFrame";
import { MockInterviewReportDashboard } from "../../features/MockInterviewReportDashboard";
import { MockInterviewLiveStage } from "../../features/MockInterviewLiveStage";
import { useInterviewCamera } from "../../features/useInterviewCamera";
import { useInterviewCountdown } from "../../features/useInterviewCountdown";
import { useMockInterviewVoice } from "../../features/useMockInterviewVoice";
import { ApiError, errorMessage } from "../../services/api";

function mockInterviewAiError(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.code === "AI_DISABLED") {
      return "Mock interview AI is not enabled. Ask an admin to turn on Platform AI and Mock interview under Admin → Settings → AI.";
    }
    if (error.code === "AI_AUTH_FAILED" || (error.code === "AI_ERROR" && error.message.includes("(401)"))) {
      return "The platform AI API key was rejected (401). An admin must save a valid OpenAI (or compatible) key under Admin → Settings → AI and run Test AI.";
    }
    if (error.code === "SESSION_EXPIRED") {
      return "The 30-minute session has ended. End the interview to generate your report.";
    }
    if (error.code === "AI_RATE_LIMIT") {
      return error.message;
    }
    if (error.code === "INTERNAL_ERROR") {
      return "The server hit an error (often a missing database migration). Restart the API, then run: python -m alembic -c backend/alembic.ini upgrade head";
    }
    if (error.code === "FEEDBACK_FAILED" || error.code === "TIMEOUT") {
      return error.message;
    }
    return error.message;
  }
  return errorMessage(error);
}

import { mergeMockInterviewPresenter } from "../../lib/mockInterviewPresenter";
import { mockInterviews } from "../../services/endpoints";
import type { MockInterviewFeedback, MockInterviewSessionDetail } from "../../types";

const SESSION_KEY = (id: string) => ["mock-interview", id] as const;

class MockInterviewLiveErrorBoundary extends Component<
  { children: ReactNode },
  { message: string | null }
> {
  state = { message: null };

  static getDerivedStateFromError(error: unknown) {
    const message = error instanceof Error ? error.message : "Unknown error";
    return { message };
  }

  render() {
    if (this.state.message) {
      return (
        <div className="mx-auto max-w-lg space-y-4 px-4 py-16">
          <Alert kind="error">
            The live interview page failed to render ({this.state.message}). Try a hard refresh (Ctrl+F5). If it
            persists, open DevTools → Console and share the error.
          </Alert>
          <div className="flex justify-center">
            <Button variant="secondary" onClick={() => window.location.reload()}>
              Reload page
            </Button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

export function MockInterviewSetupPage() {
  return <MockInterviewDashboard />;
}

export function MockInterviewLivePage() {
  const { sessionId = "" } = useParams();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [shouldEndHint, setShouldEndHint] = useState(false);
  const openingRequested = useRef(false);
  const spokenMessageIds = useRef(new Set<string>());
  const liveStarted = useRef(false);
  const [videoOn, setVideoOn] = useState(true);
  const [micMuted, setMicMuted] = useState(false);
  const [showCaptions, setShowCaptions] = useState(false);
  const autoEndingRef = useRef(false);
  const presentationFramesRef = useRef<string[]>([]);
  const finishInterviewRef = useRef<() => void>(() => {});

  const [loadSlow, setLoadSlow] = useState(false);
  const { data: session, isLoading, error, isError, refetch } = useQuery({
    queryKey: SESSION_KEY(sessionId),
    queryFn: () => mockInterviews.getSession(sessionId),
    enabled: Boolean(sessionId),
    staleTime: 5_000,
    retry: 1,
  });

  useEffect(() => {
    if (!isLoading) {
      setLoadSlow(false);
      return;
    }
    const id = window.setTimeout(() => setLoadSlow(true), 12_000);
    return () => window.clearTimeout(id);
  }, [isLoading]);

  const { data: aiStatus } = useQuery({
    queryKey: ["mock-interview", "availability"],
    queryFn: () => mockInterviews.availability(),
  });

  const sessionEnded = session?.status === "completed" || session?.status === "abandoned";
  const camera = useInterviewCamera(Boolean(sessionId && videoOn && !sessionEnded));

  const capturePresentationSnapshot = useCallback(() => {
    const el = camera.videoRef.current;
    if (!el) return;
    presentationFramesRef.current = pushPresentationFrame(
      presentationFramesRef.current,
      captureVideoFrame(el),
    );
  }, [camera.videoRef]);

  useEffect(() => {
    if (session?.status !== "active" || camera.status !== "active") return;
    capturePresentationSnapshot();
    const id = window.setInterval(capturePresentationSnapshot, 40_000);
    return () => window.clearInterval(id);
  }, [session?.status, camera.status, capturePresentationSnapshot]);

  const turnHandlerRef = useRef<(text: string) => Promise<void>>(async () => {});
  const turnInFlightRef = useRef(false);

  const presenter = mergeMockInterviewPresenter(aiStatus?.presenter);
  const supportsBargeIn = presenter.supports_barge_in !== false;
  const supportsReplay = presenter.supports_replay !== false;

  const voice = useMockInterviewVoice({
    onTranscript: (text) => turnHandlerRef.current(text),
    transcribe: (blob) => mockInterviews.transcribe(blob).then((r) => r.text),
    bargeInEnabled: supportsBargeIn,
    disabled: session?.status !== "active",
    continuous: true,
  });

  const voiceRef = useRef(voice);
  voiceRef.current = voice;

  useEffect(() => {
    voiceRef.current.setFetchTts(({ messageId }) => mockInterviews.messageTts(sessionId, messageId));
  }, [sessionId]);

  const opening = useMutation({
    mutationFn: () => mockInterviews.opening(sessionId),
    onSuccess: (data) => {
      qc.setQueryData<MockInterviewSessionDetail>(SESSION_KEY(sessionId), (prev) => {
        if (!prev) return prev;
        const has = prev.messages.some((m) => m.id === data.interviewer_message.id);
        if (has) return prev;
        return { ...prev, messages: [...prev.messages, data.interviewer_message] };
      });
      setShouldEndHint(data.should_end);
      if (!liveStarted.current) {
        liveStarted.current = true;
        voiceRef.current.startLiveMode();
      }
      const msgId = data.interviewer_message.id;
      if (!spokenMessageIds.current.has(msgId)) {
        spokenMessageIds.current.add(msgId);
        // Do not await: TanStack Query keeps isPending true until onSuccess settles, which
        // left the UI stuck on "Connecting…" for the whole TTS playback.
        void voiceRef.current.speak(
          data.interviewer_message.content,
          data.audio_base64,
          data.audio_mime,
          data.interviewer_message.id,
        );
      }
    },
    onError: (err) => {
      openingRequested.current = false;
      if (err instanceof ApiError && err.code === "SESSION_EXPIRED") {
        finishInterviewRef.current();
      }
    },
  });

  const openingMutateRef = useRef(opening.mutate);
  openingMutateRef.current = opening.mutate;

  const messageCount = session?.messages.length ?? 0;
  const hasInterviewerMsg = session?.messages.some((m) => m.role === "interviewer") ?? false;
  const lastInterviewerMessage = [...(session?.messages ?? [])].reverse().find((m) => m.role === "interviewer");

  useEffect(() => {
    if (session?.status === "completed") {
      navigate(`/app/mock-interview/${sessionId}/report`, { replace: true });
    }
  }, [session?.status, sessionId, navigate]);

  useEffect(() => {
    if (!session || session.status !== "active") return;
    const expired = session.ends_at && new Date(session.ends_at).getTime() <= Date.now();
    if (expired) return;
    if (session.messages.some((m) => m.role === "interviewer")) {
      if (!liveStarted.current) {
        liveStarted.current = true;
        voiceRef.current.startLiveMode();
      }
      return;
    }
    if (openingRequested.current || opening.isPending) return;
    openingRequested.current = true;
    openingMutateRef.current();
  }, [session?.id, session?.status, session?.ends_at, messageCount, hasInterviewerMsg, opening.isPending]);

  const complete = useMutation({
    mutationFn: (payload?: { presentation_frames?: string[] }) =>
      mockInterviews.complete(sessionId, {
        presentation_frames: payload?.presentation_frames ?? presentationFramesRef.current,
      }),
    onSuccess: (data) => {
      voiceRef.current.stopLiveMode();
      qc.setQueryData(SESSION_KEY(sessionId), data.session);
      navigate(`/app/mock-interview/${sessionId}/report`, { replace: true });
    },
  });

  const finishInterview = useCallback(() => {
    capturePresentationSnapshot();
    voiceRef.current.stopLiveMode();
    complete.mutate({ presentation_frames: presentationFramesRef.current });
  }, [capturePresentationSnapshot, complete]);

  const completeMutateRef = useRef(complete.mutate);
  completeMutateRef.current = complete.mutate;
  finishInterviewRef.current = finishInterview;

  turnHandlerRef.current = async (text: string) => {
    if (turnInFlightRef.current) return;
    turnInFlightRef.current = true;
    const optimisticId = `pending-${Date.now()}`;
    qc.setQueryData<MockInterviewSessionDetail>(SESSION_KEY(sessionId), (prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        messages: [
          ...prev.messages,
          {
            id: optimisticId,
            role: "candidate" as const,
            content: text,
            created_at: new Date().toISOString(),
          },
        ],
      };
    });
    try {
      let result;
      const clientTurnId = crypto.randomUUID();
      try {
        result = await mockInterviews.turn(sessionId, text, clientTurnId);
      } catch (err) {
        qc.setQueryData<MockInterviewSessionDetail>(SESSION_KEY(sessionId), (prev) => {
          if (!prev) return prev;
          return { ...prev, messages: prev.messages.filter((m) => m.id !== optimisticId) };
        });
        if (err instanceof ApiError && err.code === "SESSION_EXPIRED") {
          voiceRef.current.stopLiveMode();
          completeMutateRef.current();
          return;
        }
        throw err;
      }
      qc.setQueryData<MockInterviewSessionDetail>(SESSION_KEY(sessionId), (prev) => {
        if (!prev) return prev;
        const withoutOptimistic = prev.messages.filter((m) => m.id !== optimisticId);
        const ids = new Set(withoutOptimistic.map((m) => m.id));
        const msgs = [...withoutOptimistic];
        if (!ids.has(result.candidate_message.id)) msgs.push(result.candidate_message);
        if (!ids.has(result.interviewer_message.id)) msgs.push(result.interviewer_message);
        return { ...prev, messages: msgs, turn_count: result.turn_count };
      });
      setShouldEndHint(result.should_end);
      capturePresentationSnapshot();
      const msgId = result.interviewer_message.id;
      if (!spokenMessageIds.current.has(msgId)) {
        spokenMessageIds.current.add(msgId);
        await voiceRef.current.speak(
          result.interviewer_message.content,
          result.audio_base64,
          result.audio_mime,
          result.interviewer_message.id,
        );
      }
    } finally {
      turnInFlightRef.current = false;
    }
  };

  const handleTimeUp = useCallback(() => {
    if (autoEndingRef.current || complete.isPending) return;
    autoEndingRef.current = true;
    finishInterview();
  }, [complete.isPending, finishInterview]);

  const secondsLeft = useInterviewCountdown(
    session?.ends_at,
    Boolean(session && session.status === "active"),
    handleTimeUp,
  );

  const sessionExpiredOnLoad =
    session?.status === "active" &&
    session.ends_at &&
    new Date(session.ends_at).getTime() <= Date.now();

  useEffect(() => {
    if (!sessionExpiredOnLoad || autoEndingRef.current || complete.isPending) return;
    autoEndingRef.current = true;
    finishInterview();
  }, [sessionExpiredOnLoad, complete.isPending, finishInterview]);

  useEffect(() => {
    if (complete.isError && session?.status === "completed") {
      navigate(`/app/mock-interview/${sessionId}/report`, { replace: true });
    }
  }, [complete.isError, session?.status, sessionId, navigate]);

  if (isLoading || !session) {
    if (isLoading) {
      return (
        <div className="mx-auto max-w-lg space-y-4 px-4 py-16 text-center">
          <Spinner />
          <p className="text-sm text-slate-600">Loading interview session…</p>
          {loadSlow && (
            <Alert kind="info">
              This is taking longer than usual. Confirm the API is running on port 8000, then restart the frontend (
              <code className="rounded bg-slate-100 px-1">npm run dev</code>
              ). If the page still hangs, hard-refresh (Ctrl+F5).
            </Alert>
          )}
        </div>
      );
    }
    return (
      <div className="mx-auto max-w-lg space-y-4 px-4 py-16">
        <Alert kind="error">{errorMessage(error)}</Alert>
        {isError && (
          <div className="flex justify-center">
            <Button variant="secondary" onClick={() => void refetch()}>
              Retry
            </Button>
          </div>
        )}
      </div>
    );
  }
  if (complete.isPending) {
    return <MockInterviewAnalysisProgress title="Ending interview and building your report" />;
  }
  if (complete.isError && session.status !== "completed") {
    return (
      <div className="mx-auto max-w-lg space-y-4 px-4 py-16">
        <Alert kind="error">{mockInterviewAiError(complete.error)}</Alert>
        <div className="flex flex-wrap justify-center gap-2">
          <Button
            variant="primary"
            onClick={() => {
              complete.reset();
              finishInterview();
            }}
          >
            Try generating report again
          </Button>
          <Button variant="secondary" onClick={() => navigate("/app/mock-interview")}>
            Back to mock interviews
          </Button>
        </div>
      </div>
    );
  }
  if (session.status === "completed") {
    return <Navigate to={`/app/mock-interview/${sessionId}/report`} replace />;
  }

  const statusLine =
    voice.phase === "speaking"
      ? supportsBargeIn
        ? "Listen to the interviewer — speak to interrupt, or tap Interrupt"
        : "Listen to the interviewer — tap Replay or wait for your turn"
      : voice.ttsBuffering
        ? "Loading interviewer voice…"
        : hasInterviewerMsg && voice.phase === "idle" && !voice.liveMode
          ? "Starting microphone…"
          : voice.phase === "listening"
            ? voice.awaitingSilence
              ? "Still listening — finish your thought or tap Done speaking"
              : "Your turn — answer at your own pace (thinking pauses are fine)"
            : voice.phase === "processing"
              ? "Interviewer is preparing the next question…"
              : opening.isPending
                ? "Connecting to your interviewer…"
                : "Live interview in progress";

  return (
    <MockInterviewLiveErrorBoundary>
    <div className="mx-auto max-w-6xl space-y-4">
      {secondsLeft !== null && secondsLeft <= 300 && secondsLeft > 0 && (
        <div className="mb-4">
          <Alert kind="info">Less than 5 minutes left — finish your current answer, then end the interview for feedback.</Alert>
        </div>
      )}
      {secondsLeft === 0 && complete.isPending && (
        <div className="mb-4">
          <Alert kind="info">Time is up — generating your feedback report from your answers…</Alert>
        </div>
      )}
      {shouldEndHint && (
        <div className="mb-4">
          <Alert kind="info">
            The interviewer is ready to wrap up — click End &amp; get report to analyze your answers and generate feedback.
          </Alert>
        </div>
      )}
      {aiStatus && !aiStatus.available && (
        <div className="mb-4">
          <Alert kind="error">{aiStatus.message}</Alert>
        </div>
      )}
      {sessionExpiredOnLoad && !complete.isPending && (
        <div className="mb-4">
          <Alert kind="info">
            Your 30-minute window has ended. We are generating your report from answers already recorded.
          </Alert>
        </div>
      )}
      {session.context_snapshot?.resume_warning && (
        <div className="mb-4">
          <Alert kind="info">{String(session.context_snapshot.resume_warning)}</Alert>
        </div>
      )}
      {!voice.speechSupported && (
        <div className="mb-4">
          <Alert kind="info">
            This browser does not support live speech recognition. Allow microphone access, record your answer, then tap{" "}
            <strong>Done speaking</strong> to transcribe and send.
          </Alert>
        </div>
      )}
      <MockInterviewLiveStage
        session={session}
        presenter={presenter}
        supportsBargeIn={supportsBargeIn}
        supportsReplay={supportsReplay}
        phase={voice.phase}
        interim={voice.interim}
        cameraVideoRef={camera.videoRef}
        cameraStatus={camera.status}
        cameraIssue={camera.issue}
        videoOn={videoOn}
        micMuted={micMuted}
        onToggleVideo={() => setVideoOn((v) => !v)}
        onToggleMic={() => {
          const next = !micMuted;
          setMicMuted(next);
          voice.setMicMuted(next);
        }}
        onEnd={() => finishInterview()}
        onEndReport={() => finishInterview()}
        onRetryCamera={camera.retry}
        connecting={!hasInterviewerMsg && !complete.isPending && opening.isPending}
        awaitingSilence={voice.awaitingSilence}
        onDoneSpeaking={voice.submitAnswer}
        onInterruptInterviewer={voice.interruptSpeaking}
        onReplayQuestion={
          lastInterviewerMessage
            ? () => void voice.replayLine(lastInterviewerMessage.id, lastInterviewerMessage.content)
            : undefined
        }
        replayDisabled={voice.phase === "speaking" || voice.phase === "processing" || !lastInterviewerMessage}
        interviewerCaption={
          lastInterviewerMessage && (voice.phase === "speaking" || showCaptions)
            ? lastInterviewerMessage.content
            : showCaptions
              ? lastInterviewerMessage?.content
              : undefined
        }
        showCaptions={showCaptions}
        onToggleCaptions={() => setShowCaptions((v) => !v)}
        ttsBuffering={voice.ttsBuffering}
        endLoading={complete.isPending}
        secondsLeft={secondsLeft}
        statusLine={statusLine}
      />
      <p className="text-center text-xs text-slate-500">
        Camera stills (~every 40s and after answers, up to 12) feed on-camera behavior analysis. Images are not stored.
        Session limit: 30 minutes.
      </p>
      {(opening.error || complete.error) && (
        <div className="mt-4 space-y-2">
          <Alert kind="error">{mockInterviewAiError(opening.error ?? complete.error)}</Alert>
          {opening.error && (
            <Button
              variant="secondary"
              size="sm"
              loading={opening.isPending}
              onClick={() => {
                openingMutateRef.current();
              }}
            >
              Retry interviewer
            </Button>
          )}
        </div>
      )}
    </div>
    </MockInterviewLiveErrorBoundary>
  );
}

export function MockInterviewReportPage() {
  const { sessionId = "" } = useParams();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const { data: session, isLoading, error } = useQuery({
    queryKey: SESSION_KEY(sessionId),
    queryFn: () => mockInterviews.getSession(sessionId),
    enabled: Boolean(sessionId),
  });

  const regenerate = useMutation({
    mutationFn: () => mockInterviews.regenerateFeedback(sessionId),
    onSuccess: (data) => {
      qc.setQueryData(SESSION_KEY(sessionId), data.session);
    },
  });

  useEffect(() => {
    if (session?.status === "active") {
      navigate(`/app/mock-interview/${sessionId}`, { replace: true });
    }
  }, [session?.status, sessionId, navigate]);

  if (isLoading) return <Spinner />;
  if (error || !session) return <Alert kind="error">{errorMessage(error)}</Alert>;
  if (session.status === "active") return <Spinner />;
  if (regenerate.isPending) {
    return <MockInterviewAnalysisProgress title="Regenerating analysis from your saved transcript" />;
  }

  const fb = (session.feedback ?? {}) as MockInterviewFeedback;

  return (
    <MockInterviewReportDashboard
      session={session}
      feedback={fb}
      onRegenerate={() => regenerate.mutate()}
      regenerating={regenerate.isPending}
      regenerateError={regenerate.error ? errorMessage(regenerate.error) : null}
    />
  );
}

