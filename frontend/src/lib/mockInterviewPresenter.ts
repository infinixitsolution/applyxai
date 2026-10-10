import type { MockInterviewPresenterSettings } from "../types";
import type { InterviewerPresenterConfig } from "../features/InterviewerAgent";

export const MOCK_INTERVIEW_PRESENTER_DEFAULTS: Required<
  Pick<
    MockInterviewPresenterSettings,
    "mode" | "image_url" | "glb_url" | "supports_barge_in" | "supports_replay"
  >
> & { live_stream_url: string } = {
  mode: "digital_human_3d",
  image_url: "/interviewer-portrait.png",
  glb_url: "/portrait",
  live_stream_url: "",
  supports_barge_in: true,
  supports_replay: true,
};

/** Merge API/admin presenter JSON with product defaults (legacy rows may omit glb_url). */
export function mergeMockInterviewPresenter(
  raw?: MockInterviewPresenterSettings | null,
): InterviewerPresenterConfig {
  const d = MOCK_INTERVIEW_PRESENTER_DEFAULTS;
  return {
    mode: raw?.mode ?? d.mode,
    image_url: raw?.image_url?.trim() || d.image_url,
    glb_url: raw?.glb_url?.trim() || d.glb_url,
    live_stream_url: raw?.live_stream_url?.trim() || d.live_stream_url,
    supports_barge_in: raw?.supports_barge_in !== false,
    supports_replay: raw?.supports_replay !== false,
  };
}
