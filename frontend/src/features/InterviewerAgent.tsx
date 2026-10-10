import { Component, useEffect, useState, type ReactNode } from "react";
import InterviewerAvatar3D, { type InterviewerAvatarExpression } from "./mock-interview/InterviewerAvatar3D";
import { isPortrait3DModelUrl } from "./mock-interview/InterviewerPortrait3D";
import { subscribeInterviewerPose, type InterviewerPose } from "./interviewerMotion";

export type InterviewerPresenterConfig = {
  mode?: "digital_human_3d" | "static_photo" | "live_stream";
  image_url?: string;
  glb_url?: string;
  live_stream_url?: string;
  supports_barge_in?: boolean;
  supports_replay?: boolean;
};

type Props = {
  presenter?: InterviewerPresenterConfig;
  caption?: string;
  showCaptions?: boolean;
  ttsBuffering?: boolean;
};

const REST: InterviewerPose = {
  speaking: false,
  jaw: 0.04,
  width: 0.22,
  round: 0.08,
  blink: 0,
  nod: 0,
  tilt: 0,
  expression: 0.35,
};

function expressionFromPose(pose: InterviewerPose, ttsBuffering?: boolean): InterviewerAvatarExpression {
  if (ttsBuffering) return "thinking";
  if (pose.speaking) return "friendly";
  return "neutral";
}

/** Interviewer visual: 3D digital human (default), live stream POC, or static photo fallback. */
export function InterviewerAgent({ presenter, caption, showCaptions, ttsBuffering }: Props) {
  const mode = presenter?.mode ?? "digital_human_3d";
  const imageUrl = presenter?.image_url?.trim() || "/interviewer-portrait.png";
  const liveUrl = presenter?.live_stream_url?.trim() || "";

  if (mode === "live_stream" && liveUrl) {
    const isVideo = /\.(mp4|webm|m3u8)(\?|$)/i.test(liveUrl);
    return (
      <div className="absolute inset-0 overflow-hidden bg-slate-950">
        {isVideo ? (
          <video src={liveUrl} className="h-full w-full object-cover" playsInline autoPlay muted loop />
        ) : (
          <iframe
            title="Interviewer stream"
            src={liveUrl}
            className="h-full w-full border-0"
            allow="autoplay; microphone; camera"
          />
        )}
        <div
          className="pointer-events-none absolute inset-0 bg-gradient-to-t from-black/55 via-transparent to-black/25"
          aria-hidden
        />
        {showCaptions && caption?.trim() && (
          <div className="absolute inset-x-0 bottom-0 z-10 bg-gradient-to-t from-black/90 to-transparent px-3 pb-3 pt-8">
            <p className="text-center text-sm leading-snug text-white/95">{caption}</p>
          </div>
        )}
      </div>
    );
  }

  if (mode === "static_photo") {
    return (
      <StaticPhotoAgent
        imageUrl={imageUrl}
        caption={caption}
        showCaptions={showCaptions}
        ttsBuffering={ttsBuffering}
      />
    );
  }

  return (
    <DigitalHumanAgent
      caption={caption}
      showCaptions={showCaptions}
      ttsBuffering={ttsBuffering}
      glbUrl={presenter?.glb_url}
      portraitUrl={imageUrl}
    />
  );
}

class InterviewerVisualErrorBoundary extends Component<
  { children: ReactNode; fallback: ReactNode },
  { failed: boolean }
> {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  render() {
    if (this.state.failed) return this.props.fallback;
    return this.props.children;
  }
}

function DigitalHumanAgent({
  caption,
  showCaptions,
  ttsBuffering,
  glbUrl,
  portraitUrl,
}: {
  caption?: string;
  showCaptions?: boolean;
  ttsBuffering?: boolean;
  glbUrl?: string;
  portraitUrl?: string;
}) {
  const [pose, setPose] = useState<InterviewerPose>(REST);
  useEffect(() => subscribeInterviewerPose(setPose), []);
  const portraitMode = isPortrait3DModelUrl(glbUrl?.trim() || "/portrait");
  const imageUrl = portraitUrl?.trim() || "/interviewer-portrait.png";

  return (
    <div className={portraitMode ? "absolute inset-0 overflow-hidden bg-white" : "absolute inset-0 overflow-hidden bg-slate-950"}>
      <InterviewerVisualErrorBoundary
        key={`${glbUrl ?? ""}|${imageUrl}`}
        fallback={
          <StaticPhotoAgent
            imageUrl={imageUrl}
            caption={caption}
            showCaptions={showCaptions}
            ttsBuffering={ttsBuffering}
          />
        }
      >
        <InterviewerAvatar3D
          speaking={pose.speaking}
          expression={expressionFromPose(pose, ttsBuffering)}
          modelUrl={glbUrl}
          portraitUrl={portraitUrl}
        />
      </InterviewerVisualErrorBoundary>
      <div
        className={
          portraitMode
            ? "pointer-events-none absolute inset-0 z-[2] bg-gradient-to-t from-black/8 via-transparent to-transparent"
            : "pointer-events-none absolute inset-0 z-[2] bg-gradient-to-t from-black/55 via-transparent to-black/25"
        }
        aria-hidden
      />
      {ttsBuffering && (
        <div className="absolute bottom-14 left-3 z-10 rounded-full bg-black/60 px-2 py-1 text-[10px] text-white/90">
          Buffering voice…
        </div>
      )}
      {showCaptions && caption?.trim() && (
        <div
          className={
            portraitMode
              ? "absolute inset-x-0 bottom-0 z-10 bg-gradient-to-t from-black/75 via-black/40 to-transparent px-3 pb-3 pt-10"
              : "absolute inset-x-0 bottom-0 z-10 bg-gradient-to-t from-black/90 to-transparent px-3 pb-3 pt-8"
          }
        >
          <p className="text-center text-sm leading-snug text-white/95" aria-live="polite">
            {caption}
          </p>
        </div>
      )}
    </div>
  );
}

function StaticPhotoAgent({
  imageUrl,
  caption,
  showCaptions,
  ttsBuffering,
}: {
  imageUrl: string;
  caption?: string;
  showCaptions?: boolean;
  ttsBuffering?: boolean;
}) {
  const [pose, setPose] = useState<InterviewerPose>(REST);
  useEffect(() => subscribeInterviewerPose(setPose), []);
  const energy = pose.speaking ? 0.55 + pose.jaw * 0.45 : 0;
  return (
    <div className="absolute inset-0 overflow-hidden bg-slate-950">
      <img
        src={imageUrl}
        alt=""
        className="h-full w-full object-cover object-[center_18%] transition-[transform,filter] duration-150 ease-out"
        style={{
          transform: `scale(${1 + pose.jaw * 0.012}) translateY(${pose.nod * -2}px)`,
          filter: pose.speaking ? `brightness(${1 + energy * 0.06})` : undefined,
        }}
      />
      <div className="pointer-events-none absolute inset-0 bg-gradient-to-t from-black/55 via-transparent to-black/25" aria-hidden />
      {ttsBuffering && (
        <div className="absolute left-3 bottom-14 z-10 rounded-full bg-black/60 px-2 py-1 text-[10px] text-white/90">
          Buffering voice…
        </div>
      )}
      {showCaptions && caption?.trim() && (
        <div className="absolute inset-x-0 bottom-0 z-10 bg-gradient-to-t from-black/90 to-transparent px-3 pb-3 pt-8">
          <p className="text-center text-sm leading-snug text-white/95">{caption}</p>
        </div>
      )}
    </div>
  );
}
