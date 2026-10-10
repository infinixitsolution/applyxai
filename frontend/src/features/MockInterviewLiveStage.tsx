import {
  Brain,
  CheckCircle2,
  Loader2,
  MessageCircle,
  Mic,
  MicOff,
  PhoneOff,
  Smile,
  Sparkles,
  Square,
  Subtitles,
  User,
  Video,
  VideoOff,
  Volume2,
} from "lucide-react";
import type { ReactNode, RefObject } from "react";
import { Button, cx } from "../components/ui";
import { cameraStatusMessage, type CameraIssue, type CameraStatus } from "./useInterviewCamera";
import { formatInterviewCountdown } from "./useInterviewCountdown";
import type { MockInterviewSessionDetail } from "../types";
import { isPortrait3DModelUrl } from "./mock-interview/InterviewerPortrait3D";
import { InterviewerAgent, type InterviewerPresenterConfig } from "./InterviewerAgent";

const TRACKED_PARAMS = [
  { icon: MessageCircle, label: "Communication" },
  { icon: User, label: "Confidence" },
  { icon: Brain, label: "Technical knowledge" },
  { icon: Sparkles, label: "Problem solving" },
  { icon: Smile, label: "Behavior & attitude" },
] as const;

const MAX_QUESTIONS = 12;

function PanelBadge({ children, tone }: { children: ReactNode; tone?: "brand" | "green" | "neutral" }) {
  const cls =
    tone === "green"
      ? "bg-emerald-600/90 text-white"
      : tone === "brand"
        ? "bg-brand-600/90 text-white"
        : "bg-black/50 text-white backdrop-blur";
  return (
    <div className={cx("absolute right-3 top-3 z-10 flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium", cls)}>
      {children}
    </div>
  );
}

function VideoPanel({
  label,
  activeRing,
  activeRingClass = "ring-brand-400",
  badge,
  footer,
  children,
}: {
  label: string;
  activeRing?: boolean;
  activeRingClass?: string;
  badge?: ReactNode;
  footer?: ReactNode;
  children: ReactNode;
}) {
  return (
    <div
      className={cx(
        "relative flex min-h-[220px] flex-col overflow-hidden rounded-xl bg-slate-950 shadow-md ring-1 ring-slate-800 sm:min-h-0 sm:aspect-video",
        activeRing && `ring-2 ring-offset-2 ring-offset-white ${activeRingClass}`,
      )}
    >
      <div className="absolute left-3 top-3 z-10 rounded-full bg-black/50 px-2.5 py-1 text-xs font-medium text-white backdrop-blur">
        {label}
      </div>
      {badge}
      <div className="relative min-h-[200px] flex-1 sm:min-h-0">{children}</div>
      {footer}
    </div>
  );
}

export function MockInterviewLiveStage({
  session,
  phase,
  interim,
  cameraVideoRef,
  cameraStatus,
  cameraIssue = null,
  videoOn,
  micMuted,
  onToggleVideo,
  onToggleMic,
  onEnd,
  onEndReport,
  onRetryCamera,
  connecting,
  awaitingSilence,
  onDoneSpeaking,
  onReplayQuestion,
  replayDisabled,
  onInterruptInterviewer,
  endLoading,
  secondsLeft,
  statusLine,
  presenter,
  supportsBargeIn = true,
  supportsReplay = true,
  interviewerCaption,
  showCaptions = false,
  onToggleCaptions,
  ttsBuffering,
}: {
  session: MockInterviewSessionDetail;
  presenter?: InterviewerPresenterConfig;
  supportsBargeIn?: boolean;
  supportsReplay?: boolean;
  interviewerCaption?: string;
  showCaptions?: boolean;
  onToggleCaptions?: () => void;
  ttsBuffering?: boolean;
  phase: string;
  interim: string;
  cameraVideoRef: RefObject<HTMLVideoElement | null>;
  cameraStatus: CameraStatus | string;
  cameraIssue?: CameraIssue | null;
  videoOn: boolean;
  micMuted: boolean;
  onToggleVideo: () => void;
  onToggleMic: () => void;
  onEnd: () => void;
  onEndReport: () => void;
  onRetryCamera?: () => void;
  connecting?: boolean;
  awaitingSilence?: boolean;
  onDoneSpeaking?: () => void;
  onReplayQuestion?: () => void;
  replayDisabled?: boolean;
  onInterruptInterviewer?: () => void;
  endLoading?: boolean;
  secondsLeft: number | null;
  statusLine: string;
}) {
  const interviewerSpeaking = phase === "speaking";
  const candidateListening = phase === "listening" && !micMuted;
  const questionIndex = session.messages.filter((m) => m.role === "interviewer").length;
  const snap = session.context_snapshot ?? {};
  const qDisplay = Math.max(questionIndex, connecting ? 0 : questionIndex || 1);
  const portraitInterviewer = isPortrait3DModelUrl(presenter?.glb_url ?? "/portrait");

  return (
    <div className="overflow-hidden rounded-2xl bg-white shadow-sm ring-1 ring-slate-200/80">
      {/* Toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 bg-gradient-to-r from-brand-600 to-violet-600 px-4 py-3 text-white">
        <div className="flex items-center gap-3">
          <img src="/mascot.png" alt="" className="h-9 w-9 rounded-lg bg-white object-contain p-0.5" />
          <div>
            <p className="text-sm font-semibold leading-tight">ApplyXAI Mock Interview</p>
            <p className="text-xs text-white/80 line-clamp-1">
              {snap.job_title ? `${snap.job_title} · ${snap.company}` : "Live practice session"}
            </p>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <span className="inline-flex items-center gap-1.5 rounded-full bg-black/20 px-2.5 py-1 text-xs font-medium">
            <span className="h-2 w-2 animate-pulse rounded-full bg-emerald-300" aria-hidden />
            Live
          </span>
          <span className="rounded-full bg-black/20 px-2.5 py-1 text-xs font-medium">
            Q {qDisplay}/{MAX_QUESTIONS}
          </span>
          {secondsLeft !== null && (
            <span
              className={cx(
                "rounded-full px-2.5 py-1 font-mono text-xs font-semibold tabular-nums",
                secondsLeft <= 300 ? "bg-amber-400 text-amber-950" : "bg-black/20",
              )}
            >
              {formatInterviewCountdown(secondsLeft)}
            </span>
          )}
          <Button
            size="sm"
            variant="secondary"
            className="border-white/30 bg-white/15 text-white hover:bg-white/25"
            loading={endLoading}
            onClick={onEndReport}
          >
            <Square className="h-3.5 w-3.5" aria-hidden /> End &amp; report
          </Button>
        </div>
      </div>

      <p className="border-b border-slate-100 bg-slate-50 px-4 py-2 text-sm font-medium text-slate-700" aria-live="polite">
        {statusLine}
      </p>

      {/* Two panels */}
      <div className="grid gap-3 p-3 lg:grid-cols-2 lg:gap-4 lg:p-4">
        <VideoPanel
          label="AI interviewer"
          activeRing={interviewerSpeaking}
          badge={
            connecting ? (
              <PanelBadge>
                <Loader2 className="h-3 w-3 animate-spin" aria-hidden />
                Connecting…
              </PanelBadge>
            ) : interviewerSpeaking ? (
              <PanelBadge tone="brand">
                <span className="h-2 w-2 animate-pulse rounded-full bg-white" aria-hidden />
                Speaking
              </PanelBadge>
            ) : null
          }
          footer={
            portraitInterviewer ? null : (
              <div className="pointer-events-none absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/70 to-transparent px-4 pb-3 pt-8">
                <p className="text-sm font-medium text-white">Hiring manager</p>
                <p className="text-xs text-white/75">
                  {showCaptions ? "Listen and read captions if needed" : "Audio first — use CC for captions"}
                </p>
              </div>
            )
          }
        >
          <InterviewerAgent
            presenter={presenter}
            caption={interviewerCaption}
            showCaptions={showCaptions}
            ttsBuffering={ttsBuffering}
          />
        </VideoPanel>

        <VideoPanel
          label="You"
          activeRing={candidateListening}
          activeRingClass="ring-emerald-500"
          badge={
            candidateListening ? (
              <PanelBadge tone="green">
                <span className="h-2 w-2 animate-pulse rounded-full bg-white" aria-hidden />
                {awaitingSilence ? "Listening…" : "Your turn"}
              </PanelBadge>
            ) : phase === "processing" ? (
              <PanelBadge>Sending answer…</PanelBadge>
            ) : micMuted ? (
              <PanelBadge>Muted</PanelBadge>
            ) : null
          }
          footer={
            <div className="absolute inset-x-0 bottom-0 z-10 bg-gradient-to-t from-black/85 to-transparent px-4 pb-3 pt-10">
              {interim ? (
                <p className="text-sm italic text-white/95">{interim}</p>
              ) : (
                <p className="text-xs text-white/70">
                  Speak in full sentences. Pauses are OK — we wait a few seconds of silence, or tap Done speaking.
                </p>
              )}
              {candidateListening && onDoneSpeaking && (interim || awaitingSilence) && (
                <Button
                  variant="secondary"
                  size="sm"
                  className="mt-2 border-white/30 bg-white/15 text-white hover:bg-white/25"
                  onClick={onDoneSpeaking}
                >
                  <CheckCircle2 className="h-4 w-4" aria-hidden /> Done speaking
                </Button>
              )}
            </div>
          }
        >
          {phase === "processing" && (
            <div className="absolute inset-0 z-20 flex items-center justify-center bg-black/45 text-sm font-medium text-white">
              Processing…
            </div>
          )}
          {videoOn && cameraStatus === "active" ? (
            <video
              ref={cameraVideoRef}
              className="absolute inset-0 h-full w-full object-cover [transform:scaleX(-1)]"
              playsInline
              muted
              autoPlay
            />
          ) : (
            <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 bg-slate-800 px-4 text-center text-sm text-slate-300">
              <VideoOff className="h-10 w-10 opacity-60" aria-hidden />
              {videoOn
                ? cameraStatusMessage(cameraStatus as CameraStatus, cameraIssue ?? null)
                : "Camera turned off"}
              {videoOn && cameraStatus !== "active" && cameraStatus !== "pending" && onRetryCamera && (
                <Button variant="secondary" size="sm" className="mt-2" onClick={onRetryCamera}>
                  Try again
                </Button>
              )}
            </div>
          )}
        </VideoPanel>
      </div>

      {/* Controls */}
      <div className="flex justify-center border-t border-slate-100 bg-slate-50 px-4 py-3">
        <div className="flex items-center gap-2 rounded-full bg-slate-900 px-2 py-2 shadow-lg ring-1 ring-slate-700">
          {supportsBargeIn && interviewerSpeaking && onInterruptInterviewer && (
            <button
              type="button"
              className="flex min-w-[4.25rem] flex-col items-center gap-0.5 rounded-full bg-amber-500/90 px-3 py-1.5 text-[10px] font-medium text-white hover:bg-amber-400"
              onClick={onInterruptInterviewer}
            >
              <Mic className="h-5 w-5" aria-hidden />
              Interrupt
            </button>
          )}
          <button
            type="button"
            className={cx(
              "flex min-w-[4.25rem] flex-col items-center gap-0.5 rounded-full px-3 py-1.5 text-[10px] font-medium text-white transition",
              micMuted ? "bg-red-500/30" : "hover:bg-white/10",
            )}
            onClick={onToggleMic}
            aria-pressed={micMuted}
          >
            {micMuted ? <MicOff className="h-5 w-5" /> : <Mic className="h-5 w-5" />}
            {micMuted ? "Unmute" : "Mute"}
          </button>
          {supportsReplay && onReplayQuestion && (
            <button
              type="button"
              className="flex min-w-[4.25rem] flex-col items-center gap-0.5 rounded-full px-3 py-1.5 text-[10px] font-medium text-white transition hover:bg-white/10 disabled:opacity-40"
              onClick={onReplayQuestion}
              disabled={replayDisabled}
              title="Replay the last question"
            >
              <Volume2 className="h-5 w-5" aria-hidden />
              Replay
            </button>
          )}
          {onToggleCaptions && (
            <button
              type="button"
              className={cx(
                "flex min-w-[4.25rem] flex-col items-center gap-0.5 rounded-full px-3 py-1.5 text-[10px] font-medium text-white transition",
                showCaptions ? "bg-white/20" : "hover:bg-white/10",
              )}
              onClick={onToggleCaptions}
              aria-pressed={showCaptions}
              title="Toggle captions"
            >
              <Subtitles className="h-5 w-5" aria-hidden />
              CC
            </button>
          )}
          <button
            type="button"
            className="flex min-w-[4.25rem] flex-col items-center gap-0.5 rounded-full bg-red-600 px-4 py-1.5 text-[10px] font-medium text-white hover:bg-red-500 disabled:opacity-60"
            onClick={onEnd}
            disabled={endLoading}
          >
            <PhoneOff className="h-5 w-5" />
            End call
          </button>
          <button
            type="button"
            className={cx(
              "flex min-w-[4.25rem] flex-col items-center gap-0.5 rounded-full px-3 py-1.5 text-[10px] font-medium text-white transition",
              !videoOn ? "bg-white/15" : "hover:bg-white/10",
            )}
            onClick={onToggleVideo}
            aria-pressed={!videoOn}
          >
            {videoOn ? <Video className="h-5 w-5" /> : <VideoOff className="h-5 w-5" />}
            Video
          </button>
        </div>
      </div>

      {/* Parameters */}
      <div className="border-t border-slate-100 px-4 py-3 lg:px-4">
        <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Tracked in your report</p>
        <ul className="mt-2 flex flex-wrap gap-2">
          {TRACKED_PARAMS.map(({ icon: Icon, label }) => (
            <li
              key={label}
              className="inline-flex items-center gap-1.5 rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-700"
            >
              <Icon className="h-3.5 w-3.5 text-brand-600" aria-hidden />
              {label}
            </li>
          ))}
          <li className="inline-flex items-center rounded-full bg-brand-50 px-2.5 py-1 text-xs font-medium text-brand-800">
            + 50 more parameters
          </li>
        </ul>
      </div>
    </div>
  );
}
