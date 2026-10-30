import { createRef } from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { MockInterviewSessionDetail } from "../types";
import { MockInterviewLiveStage } from "./MockInterviewLiveStage";

vi.mock("./InterviewerAgent", () => ({
  InterviewerAgent: () => <div data-testid="interviewer-agent" />,
}));

const session = {
  id: "sess-1",
  status: "active",
  application_id: "app-1",
  interview_types: ["behavioral"],
  turn_count: 1,
  context_snapshot: { job_title: "Engineer", company: "Acme" },
  messages: [{ id: "m1", role: "interviewer", content: "Tell me about a project.", created_at: "2026-01-01T00:00:00Z" }],
  feedback: {},
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:01:00Z",
  ends_at: "2026-01-01T01:00:00Z",
  max_duration_seconds: 1800,
  seconds_remaining: 900,
  max_questions: 20,
} as MockInterviewSessionDetail;

describe("MockInterviewLiveStage", () => {
  it("shows live chrome and toggles mute", async () => {
    const onToggleMic = vi.fn();
    const onEndReport = vi.fn();
    render(
      <MockInterviewLiveStage
        session={session}
        phase="listening"
        interim=""
        cameraVideoRef={createRef<HTMLVideoElement>()}
        cameraStatus="idle"
        videoOn={false}
        micMuted={false}
        onToggleVideo={() => {}}
        onToggleMic={onToggleMic}
        onEnd={() => {}}
        onEndReport={onEndReport}
        secondsLeft={600}
        statusLine="Listening for your answer"
      />,
    );
    expect(screen.getByText("ApplyXAI Mock Interview")).toBeTruthy();
    expect(screen.getByText(/Engineer · Acme/)).toBeTruthy();
    expect(screen.getByText("Listening for your answer")).toBeTruthy();
    await userEvent.click(screen.getByRole("button", { name: /mute/i }));
    expect(onToggleMic).toHaveBeenCalled();
    await userEvent.click(screen.getByRole("button", { name: /end & report/i }));
    expect(onEndReport).toHaveBeenCalled();
  });
});
