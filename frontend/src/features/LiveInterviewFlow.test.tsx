import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import type { ComponentProps } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { LiveInterviewFlow } from "./LiveInterviewFlow";

const startMock = vi.fn().mockResolvedValue("sess-1");
const probeAudioMock = vi.fn().mockResolvedValue({ ok: true, message: "Microphone and loopback look ready." });
const showCoachMock = vi.fn().mockResolvedValue(undefined);

vi.mock("./LiveInterviewCoach", () => ({
  useLiveInterviewCoachContext: () => ({
    available: true,
    sessionId: null,
    phase: "idle",
    start: startMock,
    probeAudio: probeAudioMock,
  }),
}));

vi.mock("../lib/desktop", () => ({
  isDesktopBridgeReady: () => true,
  isDesktopHost: true,
  hasLiveInterviewDesktop: () => true,
  hasDesktopAgent: () => true,
  liveInterviewUnavailableMessage: () => "",
  desktopAgent: () => ({
    status: vi.fn().mockResolvedValue({ connected: true, workerRunning: true }),
  }),
}));

vi.mock("../lib/desktopConnect", () => ({
  reconcileDesktopLink: vi.fn().mockResolvedValue(null),
}));

vi.mock("../lib/liveInterviewDesktop", () => ({
  liveInterviewDesktop: () => ({
    start: vi.fn(),
    probeAudio: probeAudioMock,
    showCoach: showCoachMock,
  }),
}));

const ok = (data: unknown, status = 200) => new Response(JSON.stringify({ success: true, data }), { status });

function mockFetch(routes: Record<string, unknown>) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      const path = url.split("?")[0];
      const key = `${init?.method ?? "GET"} ${path}`;
      if (!(key in routes)) throw new Error(`unexpected: ${key}`);
      return ok(routes[key]);
    }),
  );
}

const tokenMessage = {
  id: "m1",
  sender: "admin" as const,
  kind: "token" as const,
  body: "Your live interview token is ready.",
  created_at: "2026-10-18T00:00:00Z",
  meta: { token: "12345678", token_status: "unused" as const },
};

function renderFlow(props: Partial<ComponentProps<typeof LiveInterviewFlow>> = {}) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <LiveInterviewFlow messages={[tokenMessage]} {...props} />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  startMock.mockClear();
  probeAudioMock.mockClear();
  showCoachMock.mockClear();
  mockFetch({
    "GET /api/live-interviews/applications": { applications: [] },
    "GET /api/health": { status: "ok" },
  });
});

afterEach(() => vi.unstubAllGlobals());

describe("LiveInterviewFlow", () => {
  it("checks audio and starts interview when token is present", async () => {
    const user = userEvent.setup();
    renderFlow();
    const startBtn = await screen.findByRole("button", { name: "Start live interview" });
    await waitFor(() => expect(startBtn).not.toBeDisabled());
    await user.click(startBtn);
    await waitFor(() => {
      expect(probeAudioMock).toHaveBeenCalled();
      expect(startMock).toHaveBeenCalledWith("12345678", null);
      expect(showCoachMock).toHaveBeenCalled();
    });
  });

  it("resumes when resumeNonce increments with active session token", async () => {
    renderFlow({
      activeSession: {
        id: "s1",
        status: "active",
        token: "87654321",
        job_title: "Dev",
        company: "Acme",
        application_id: null,
        started_at: "2026-10-18T00:00:00Z",
        ended_at: null,
        transcript: [],
        feedback: null,
      },
      resumeNonce: 1,
    });
    await waitFor(() => {
      expect(startMock).toHaveBeenCalledWith("87654321", null, { resume: true });
    });
  });
});
