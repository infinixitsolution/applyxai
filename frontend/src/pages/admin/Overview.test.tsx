import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { AdminAnalytics } from "../../types";
import { AdminOverviewPage } from "./Overview";

const ok = (data: unknown) => new Response(JSON.stringify({ success: true, data }), { status: 200 });

const analytics: AdminAnalytics = {
  users: { total: 12, active: 10, verified: 11, admins: 1, new_7d: 2, new_30d: 5, active_30d: 8 },
  subscriptions: { by_plan: [], mrr_cents: {}, past_due: 0 },
  revenue_30d_cents: {},
  applications: {
    this_month_by_status: {
      discovered: 0, queued: 0, running: 0, applied: 3, failed: 1, skipped: 0, external: 0, cancelled: 0,
    },
    daily: [{ date: "2026-10-01", applied: 1, failed: 0 }],
  },
  signups_daily: [{ date: "2026-10-01", applied: 1, failed: 0 }],
  revenue_daily: [{ date: "2026-10-01", applied: 0, failed: 0 }],
  automation: {
    active_runs: 0,
    last_24h_by_status: { queued: 0, running: 0, paused: 0, completed: 1, failed: 0, cancelled: 0 },
    devices: 2,
    devices_online: 1,
  },
  mock_interviews: {
    total_sessions: 9,
    this_month: 4,
    by_status: { active: 1, completed: 6, abandoned: 2 },
    failed_feedback_jobs_24h: 0,
    average_score: 71.5,
    scored_sessions: 6,
    daily: [{ date: "2026-10-01", applied: 2, failed: 0 }],
  },
  live_interviews: {
    total_sessions: 3,
    this_month: 1,
    by_status: { active: 0, completed: 3 },
  },
};

afterEach(() => vi.unstubAllGlobals());

describe("AdminOverviewPage", () => {
  it("shows mock interview totals, abandoned count, and live interview ops", async () => {
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo) => {
      const url = String(input);
      if (url.includes("/admin/analytics")) return ok(analytics);
      throw new Error(url);
    }));
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <MemoryRouter>
          <AdminOverviewPage />
        </MemoryRouter>
      </QueryClientProvider>,
    );
    expect(await screen.findByTestId("mi-ops-card")).toBeTruthy();
    expect(screen.getByText(/9 total · 6 completed · 2 abandoned/)).toBeTruthy();
    expect(screen.getByText(/avg 71.5/)).toBeTruthy();
    expect(screen.getByRole("img", { name: /Mock interview sessions/i })).toBeTruthy();
    expect(screen.getByTestId("live-interview-ops-card")).toBeTruthy();
    expect(screen.getByText(/3 total · 3 completed/)).toBeTruthy();
  });
});
