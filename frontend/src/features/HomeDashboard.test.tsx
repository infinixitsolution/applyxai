import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { HomeDashboard } from "./HomeDashboard";

const ok = (data: unknown) => new Response(JSON.stringify({ success: true, data }), { status: 200 });

describe("HomeDashboard", () => {
  it("renders dashboard heading when stats load", async () => {
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo) => {
      const url = String(input);
      if (url.includes("/dashboard/stats")) {
        return ok({
          applications_by_status: { applied: 1, failed: 0, skipped: 0, queued: 0, running: 0, discovered: 0, external: 0, cancelled: 0 },
          total_applied: 1,
          applied_today: 0,
          success_rate: 1,
          daily: [],
          top_companies: [],
          recent_applications: [],
          automation: { active: null, last: null },
          usage: {
            plan: "free", plan_name: "Free", period: "2026-10", resets_at: "2026-11-01T00:00:00+00:00",
            applications: { used: 0, limit: 10, remaining: 10 },
            resumes: { used: 0, limit: 1, remaining: 1 },
            mock_interviews: { used: 0, limit: 2, remaining: 2, unlimited: false },
            jobs_discovered: 0, runtime_seconds: 0, limit_reached: false,
          },
          mock_interviews: {
            total: 0,
            by_status: { active: 0, completed: 0, abandoned: 0 },
            average_score: null,
            best_score: null,
            completed_with_score: 0,
            recent: [],
          },
        });
      }
      if (url.includes("/automation/overview")) return ok({ devices: [], runs: [] });
      throw new Error(`unexpected fetch ${url}`);
    }));
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <MemoryRouter>
          <HomeDashboard />
        </MemoryRouter>
      </QueryClientProvider>,
    );
    expect(await screen.findByText("Dashboard")).toBeTruthy();
    expect(screen.getByText("Mock interview practice")).toBeTruthy();
    expect(screen.getByText("No mock interviews yet")).toBeTruthy();
  });

  it("shows mock interview stats when sessions exist", async () => {
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo) => {
      const url = String(input);
      if (url.includes("/dashboard/stats")) {
        return ok({
          applications_by_status: { applied: 0, failed: 0, skipped: 0, queued: 0, running: 0, discovered: 0, external: 0, cancelled: 0 },
          total_applied: 0, applied_today: 0, success_rate: null, daily: [], top_companies: [], recent_applications: [],
          automation: { active: null, last: null },
          usage: {
            plan: "pro", plan_name: "Pro", period: "2026-10", resets_at: "2026-11-01T00:00:00+00:00",
            applications: { used: 1, limit: 100, remaining: 99 },
            resumes: { used: 1, limit: 5, remaining: 4 },
            mock_interviews: { used: 2, limit: 10, remaining: 8, unlimited: false },
            jobs_discovered: 0, runtime_seconds: 0, limit_reached: false,
          },
          mock_interviews: {
            total: 2,
            by_status: { active: 0, completed: 2, abandoned: 0 },
            average_score: 72,
            best_score: 80,
            completed_with_score: 2,
            recent: [{
              id: "11111111-1111-1111-1111-111111111111",
              status: "completed",
              job_title: "Engineer",
              company: "Acme",
              overall_score: 80,
              turn_count: 5,
              created_at: "2026-10-01T12:00:00Z",
            }],
          },
        });
      }
      if (url.includes("/automation/overview")) return ok({ devices: [], runs: [] });
      throw new Error(`unexpected fetch ${url}`);
    }));
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <MemoryRouter>
          <HomeDashboard />
        </MemoryRouter>
      </QueryClientProvider>,
    );
    expect(await screen.findByText("Total sessions")).toBeTruthy();
    expect(screen.getByText("Average score")).toBeTruthy();
    expect(screen.getByText("72")).toBeTruthy();
    expect(screen.getByText(/Engineer · Acme/)).toBeTruthy();
  });
});
