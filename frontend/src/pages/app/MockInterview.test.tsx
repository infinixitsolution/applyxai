import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MockInterviewLivePage, MockInterviewReportPage } from "./MockInterview";

vi.mock("../../features/MockInterviewLiveStage", () => ({
  MockInterviewLiveStage: () => <div data-testid="live-stage">Live stage</div>,
}));
vi.mock("../../features/MockInterviewReportDashboard", () => ({
  MockInterviewReportDashboard: ({ onRegenerate }: { onRegenerate: () => void }) => (
    <div>
      <span>Report dashboard</span>
      <button type="button" onClick={onRegenerate}>Regenerate analysis</button>
    </div>
  ),
}));
vi.mock("../../features/useInterviewCamera", () => ({
  useInterviewCamera: () => ({
    videoRef: { current: null },
    status: "idle",
    issue: null,
    retry: vi.fn(),
  }),
}));
vi.mock("../../features/useMockInterviewVoice", () => ({
  useMockInterviewVoice: () => ({
    phase: "idle",
    interim: "",
    speechSupported: true,
    liveMode: false,
    ttsBuffering: false,
    awaitingSilence: false,
    setFetchTts: vi.fn(),
    startLiveMode: vi.fn(),
    stopLiveMode: vi.fn(),
    setMicMuted: vi.fn(),
    speak: vi.fn(),
    submitAnswer: vi.fn(),
    interruptSpeaking: vi.fn(),
    replayLine: vi.fn(),
  }),
}));

const ok = (data: unknown) =>
  new Response(JSON.stringify({ success: true, data }), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });

function wrapper(path: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return (
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/app/mock-interview/:sessionId" element={<MockInterviewLivePage />} />
          <Route path="/app/mock-interview/:sessionId/report" element={<MockInterviewReportPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

const activeSession = {
  id: "sess-1",
  status: "active",
  application_id: "app-1",
  interview_types: ["mixed"],
  turn_count: 0,
  context_snapshot: {},
  messages: [],
  feedback: null,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
  ends_at: "2026-01-01T01:00:00Z",
  max_duration_seconds: 1800,
  seconds_remaining: 900,
};

const completedSession = {
  ...activeSession,
  status: "completed",
  messages: [
    { id: "m1", role: "interviewer", content: "Intro?", created_at: "2026-01-01T00:00:00Z" },
  ],
  feedback: { overall_score: 50, dimensions: [] },
};

afterEach(() => vi.unstubAllGlobals());

describe("MockInterviewLivePage", () => {
  it("shows loading then live stage when session is active", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo) => {
        const url = String(input);
        if (url.includes("/mock-interviews/availability")) {
          return ok({ available: true, message: "", presenter: { mode: "digital_human_3d" } });
        }
        if (url.includes("/mock-interviews/sessions/sess-1") && !url.includes("opening")) {
          return ok(activeSession);
        }
        if (url.includes("/opening")) {
          return ok({
            interviewer_message: { id: "im1", role: "interviewer", content: "Hi", created_at: "2026-01-01T00:00:01Z" },
            should_end: false,
            audio_base64: null,
            audio_mime: null,
          });
        }
        return new Response(JSON.stringify({ success: false, error: { code: "X", message: "unexpected" } }), {
          status: 404,
        });
      }),
    );

    render(wrapper("/app/mock-interview/sess-1"));
    await waitFor(() => expect(screen.getByTestId("live-stage")).toBeTruthy());
  });
});

describe("MockInterviewReportPage", () => {
  it("renders report dashboard for completed session", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo) => {
        const url = String(input);
        if (url.includes("/mock-interviews/sessions/sess-1")) {
          return ok(completedSession);
        }
        return ok({ available: true, presenter: {} });
      }),
    );

    render(wrapper("/app/mock-interview/sess-1/report"));
    await waitFor(() => expect(screen.getByText("Report dashboard")).toBeTruthy());
  });
});
